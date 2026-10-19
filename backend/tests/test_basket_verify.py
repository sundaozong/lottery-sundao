"""选号篮对照本地开奖：只读预览，不写购彩记录。"""
from __future__ import annotations

import json

from app.models import Draw, PurchaseRecord


def _draw(db, lottery_type, issue, main, special=None):
    row = Draw(
        lottery_type=lottery_type,
        issue=issue,
        numbers=json.dumps({"main": main, "special": special or []}, ensure_ascii=False),
        draw_date="2026-10-01",
        source="seed",
    )
    db.add(row)
    db.commit()
    return row


def _ssq(main, special, **extra):
    ticket = {
        "id": extra.pop("id", "t1"),
        "numbers": {"main": main, "special": special},
        "play": extra.pop("play", "single"),
    }
    if "pick" in extra:
        ticket["pick"] = extra.pop("pick")
    ticket.update(extra)
    return ticket


def test_empty_tickets_uses_latest_issue_and_writes_nothing(client, db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["07"])
    _draw(db, "ssq", "2026008", ["11", "12", "13", "14", "15", "16"], ["08"])
    before = db.query(PurchaseRecord).count()

    res = client.post("/api/basket/verify", json={"lottery_type": "ssq", "tickets": []})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["issue"] == "2026008"
    assert body["draw_numbers"]["main"] == ["11", "12", "13", "14", "15", "16"]
    assert body["draw_numbers"]["special"] == ["08"]
    assert body["items"] == []
    assert body["summary"] == {
        "total": 0,
        "win_count": 0,
        "illustrative_amount": 0,
        "cost": 0,
        "net": 0,
    }
    assert "空" in body["message"]
    assert "官方" in body["disclaimer"]
    assert "投注建议" in body["disclaimer"]
    assert "apply" not in body
    assert db.query(PurchaseRecord).count() == before


def test_specified_issue_hit_miss_multiple_and_does_not_touch_records(client, db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["16"])
    _draw(db, "ssq", "2026008", ["21", "22", "23", "24", "25", "26"], ["01"])
    kept = PurchaseRecord(
        lottery_type="ssq",
        issue="2026001",
        numbers=json.dumps({"play": "single", "main": ["01"], "special": ["01"]}, ensure_ascii=False),
        cost=2,
        prize=7,
        note="leave-me",
        purchased_at="2026-10-02",
    )
    db.add(kept)
    db.commit()

    res = client.post(
        "/api/basket/verify",
        json={
            "lottery_type": "ssq",
            "issue": " 2026001 ",
            "multiple": 3,
            "tickets": [
                _ssq(["01", "02", "03", "04", "05", "06"], ["16"], id="hit"),
                _ssq(["11", "12", "13", "14", "15", "16"], ["01"], id="miss"),
            ],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["issue"] == "2026001"
    assert body["draw_numbers"]["special"] == ["16"]
    assert [item["id"] for item in body["items"]] == ["hit", "miss"]
    hit, miss = body["items"]
    assert hit["status"] == "ok"
    assert hit["level"] == "一等奖"
    assert hit["main_hit"] == 6
    assert hit["special_hit"] == 1
    assert hit["amount"] == 15_000_000
    assert hit["cost"] == 6
    assert miss["status"] == "ok"
    assert miss["level"] == "未中奖"
    assert miss["main_hit"] == 0
    assert miss["special_hit"] == 0
    assert miss["amount"] == 0
    assert miss["cost"] == 6
    assert body["summary"] == {
        "total": 2,
        "win_count": 1,
        "illustrative_amount": 15_000_000,
        "cost": 12,
        "net": 14_999_988,
    }
    assert body["message"] == ""
    db.refresh(kept)
    assert kept.prize == 7
    assert kept.note == "leave-me"
    assert db.query(PurchaseRecord).count() == 1


def test_blank_issue_picks_latest_not_older_draw(client, db):
    _draw(db, "fc3d", "2026270", ["9", "8", "7"])
    _draw(db, "fc3d", "2026280", ["1", "2", "3"])
    _draw(db, "ssq", "2026999", ["01", "02", "03", "04", "05", "06"], ["01"])

    res = client.post(
        "/api/basket/verify",
        json={
            "lottery_type": "fc3d",
            "issue": "   ",
            "tickets": [
                {
                    "id": "d1",
                    "numbers": {"play": "direct", "main": ["1", "2", "3"]},
                }
            ],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["issue"] == "2026280"
    item = body["items"][0]
    assert item["status"] == "ok"
    assert item["level"] == "直选"
    assert item["main_hit"] == 3
    assert item["amount"] == 1040
    assert item["cost"] == 2
    assert body["summary"]["win_count"] == 1
    assert body["summary"]["net"] == 1038


def test_missing_draw_keeps_cost_and_marks_no_draw(client, db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["16"])
    res = client.post(
        "/api/basket/verify",
        json={
            "lottery_type": "ssq",
            "issue": "1999001",
            "multiple": 2,
            "tickets": [_ssq(["01", "02", "03", "04", "05", "06"], ["16"], id="gone")],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["issue"] == "1999001"
    assert body["draw_numbers"] is None
    assert "开奖" in body["message"]
    item = body["items"][0]
    assert item["status"] == "no_draw"
    assert item["amount"] == 0
    assert item["cost"] == 4
    assert item["level"] == "未开奖"
    assert body["summary"]["win_count"] == 0
    assert body["summary"]["illustrative_amount"] == 0
    assert body["summary"]["cost"] == 4
    assert body["summary"]["net"] == -4


def test_compound_ticket_uses_prize_rules(client, db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["16"])
    res = client.post(
        "/api/basket/verify",
        json={
            "lottery_type": "ssq",
            "issue": "2026001",
            "multiple": 2,
            "tickets": [
                _ssq(
                    ["01", "02", "03", "04", "05", "06", "07"],
                    ["16"],
                    id="compound",
                    play="compound",
                )
            ],
        },
    )
    assert res.status_code == 200, res.text
    item = res.json()["items"][0]
    assert item["status"] == "ok"
    assert item["play"] == "compound"
    assert item["bets"] == 7
    assert item["main_hit"] == 6
    assert item["special_hit"] == 1
    assert item["level"] == "一等奖等"
    assert item["amount"] == 10_036_000
    assert item["cost"] == 28
    assert res.json()["summary"]["win_count"] == 1
    assert res.json()["summary"]["cost"] == 28


def test_illegal_numbers_are_400_and_do_not_write(client, db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["16"])
    before = db.query(PurchaseRecord).count()
    res = client.post(
        "/api/basket/verify",
        json={
            "lottery_type": "ssq",
            "issue": "2026001",
            "tickets": [_ssq(["99", "02", "03", "04", "05", "06"], ["16"])],
        },
    )
    assert res.status_code == 400
    assert "红球" in res.json()["detail"]
    assert db.query(PurchaseRecord).count() == before


def test_unknown_lottery_is_400(client):
    res = client.post("/api/basket/verify", json={"lottery_type": "nope", "tickets": []})
    assert res.status_code == 400
    assert "彩种" in res.json()["detail"]


def test_incomplete_draw_is_item_error_not_a_client_400(client, db):
    _draw(db, "ssq", "2026001", ["01", "02"], ["16"])
    res = client.post(
        "/api/basket/verify",
        json={
            "lottery_type": "ssq",
            "issue": "2026001",
            "tickets": [
                _ssq(["01", "02", "03", "04", "05", "06"], ["16"], id="bad-draw"),
                _ssq(["11", "12", "13", "14", "15", "16"], ["01"], id="also"),
            ],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert [item["status"] for item in body["items"]] == ["error", "error"]
    assert "开奖" in body["items"][0]["message"]
    assert body["items"][0]["amount"] == 0
    assert body["summary"]["win_count"] == 0
    assert body["summary"]["illustrative_amount"] == 0


def test_default_multiple_is_one(client, db):
    _draw(db, "ssq", "2026001", ["11", "12", "13", "14", "15", "16"], ["16"])
    res = client.post(
        "/api/basket/verify",
        json={
            "lottery_type": "ssq",
            "issue": "2026001",
            "tickets": [_ssq(["01", "02", "03", "04", "05", "06"], ["16"])],
        },
    )
    assert res.status_code == 200, res.text
    item = res.json()["items"][0]
    assert item["status"] == "ok"
    assert item["level"] == "六等奖"
    assert item["main_hit"] == 0
    assert item["special_hit"] == 1
    assert item["amount"] == 5
    assert item["cost"] == 2
    assert item["multiple"] == 1
