"""购买记录按本地开奖批量核对奖金。"""
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


def _record(client, **overrides):
    body = {
        "lottery_type": "ssq",
        "issue": "2026001",
        "numbers": {
            "play": "single",
            "main": ["01", "02", "03", "04", "05", "06"],
            "special": ["16"],
            "multiple": 1,
        },
        "cost": 2,
        "prize": 0,
        "note": "keep-me",
        "purchased_at": "2026-10-02",
    }
    body.update(overrides)
    res = client.post("/api/records", json=body)
    assert res.status_code == 200, res.text
    return res.json()


def _by_id(payload):
    return {item["id"]: item for item in payload["items"]}


def test_verify_empty_ledger(client):
    res = client.post("/api/records/verify", json={})
    assert res.status_code == 200
    body = res.json()
    assert body["apply"] is False
    assert body["items"] == []
    assert body["summary"] == {
        "total": 0,
        "updated": 0,
        "preview": 0,
        "unchanged": 0,
        "no_issue": 0,
        "no_draw": 0,
        "error": 0,
    }
    assert "官方" in body["disclaimer"]


def test_preview_does_not_write_and_apply_updates_only_prize(client, db):
    _draw(db, "ssq", "2026001", ["11", "12", "13", "14", "15", "16"], ["16"])
    _draw(db, "fc3d", "2026280", ["1", "2", "3"])
    ssq = _record(client, prize=0, note="ssq-note")
    digit = _record(
        client,
        lottery_type="fc3d",
        issue="2026280",
        numbers={"play": "direct", "main": ["1", "2", "3"], "multiple": 2},
        cost=4,
        prize=1,
        note="digit-note",
    )

    preview = client.post("/api/records/verify", json={}).json()
    assert preview["apply"] is False
    found = _by_id(preview)
    assert found[ssq["id"]]["status"] == "preview"
    assert found[ssq["id"]]["old_prize"] == 0
    assert found[ssq["id"]]["new_prize"] == 5
    assert found[ssq["id"]]["level"] == "六等奖"
    assert found[ssq["id"]]["main_hit"] == 0
    assert found[ssq["id"]]["special_hit"] == 1
    assert found[digit["id"]]["status"] == "preview"
    assert found[digit["id"]]["new_prize"] == 2080
    assert found[digit["id"]]["level"] == "直选"
    assert found[digit["id"]]["main_hit"] == 3
    assert client.get("/api/records").json()["summary"]["total_prize"] == 1

    applied = client.post("/api/records/verify", json={"apply": True}).json()
    assert applied["apply"] is True
    assert applied["summary"]["updated"] == 2
    assert applied["summary"]["preview"] == 0
    written = _by_id(applied)
    assert written[ssq["id"]]["status"] == "updated"
    assert written[digit["id"]]["status"] == "updated"

    listed = {row["id"]: row for row in client.get("/api/records").json()["items"]}
    assert listed[ssq["id"]]["prize"] == 5
    assert listed[ssq["id"]]["cost"] == 2
    assert listed[ssq["id"]]["issue"] == "2026001"
    assert listed[ssq["id"]]["note"] == "ssq-note"
    assert listed[ssq["id"]]["numbers"]["main"] == ["01", "02", "03", "04", "05", "06"]
    assert listed[digit["id"]]["prize"] == 2080
    assert listed[digit["id"]]["cost"] == 4
    assert listed[digit["id"]]["note"] == "digit-note"
    assert listed[digit["id"]]["numbers"]["main"] == ["1", "2", "3"]


def test_verify_skips_blank_issue_missing_draw_and_unchanged(client, db):
    _draw(db, "ssq", "2026001", ["11", "12", "13", "14", "15", "16"], ["16"])
    _draw(db, "dlt", "2026001", ["01", "02", "03", "04", "05"], ["01", "02"])
    blank = _record(client, issue="  ", prize=9)
    missing = _record(client, issue="2099001", prize=3)
    same = _record(client, prize=5)
    other_type = _record(
        client,
        lottery_type="pl3",
        issue="2026001",
        numbers={"play": "direct", "main": ["1", "2", "3"]},
        prize=0,
    )

    body = client.post("/api/records/verify", json={"apply": True}).json()
    found = _by_id(body)
    assert found[blank["id"]]["status"] == "no_issue"
    assert found[blank["id"]]["new_prize"] is None
    assert found[missing["id"]]["status"] == "no_draw"
    assert found[missing["id"]]["new_prize"] is None
    assert found[same["id"]]["status"] == "unchanged"
    assert found[same["id"]]["old_prize"] == 5
    assert found[same["id"]]["new_prize"] == 5
    assert found[other_type["id"]]["status"] == "no_draw"
    assert body["summary"]["no_issue"] == 1
    assert body["summary"]["no_draw"] == 2
    assert body["summary"]["unchanged"] == 1
    assert body["summary"]["updated"] == 0

    listed = {row["id"]: row for row in client.get("/api/records").json()["items"]}
    assert listed[blank["id"]]["prize"] == 9
    assert listed[missing["id"]]["prize"] == 3
    assert listed[same["id"]]["prize"] == 5
    assert listed[other_type["id"]]["prize"] == 0


def test_verify_invalid_bet_is_item_error_and_does_not_abort(client, db):
    _draw(db, "ssq", "2026001", ["11", "12", "13", "14", "15", "16"], ["16"])
    good = _record(client, prize=0)
    bad = PurchaseRecord(
        lottery_type="ssq",
        issue="2026001",
        numbers=json.dumps({"play": "single", "main": ["99"], "special": ["01"]}, ensure_ascii=False),
        cost=2,
        prize=7,
        note="bad",
        purchased_at="2026-10-02",
    )
    db.add(bad)
    db.commit()
    db.refresh(bad)

    res = client.post("/api/records/verify", json={"apply": True, "record_ids": [good["id"], bad.id, 999999]})
    assert res.status_code == 200
    body = res.json()
    found = _by_id(body)
    assert found[good["id"]]["status"] == "updated"
    assert found[good["id"]]["new_prize"] == 5
    assert found[bad.id]["status"] == "error"
    assert found[bad.id]["new_prize"] is None
    assert found[bad.id]["message"]
    assert body["summary"]["updated"] == 1
    assert body["summary"]["error"] == 1
    assert body["summary"]["total"] == 2

    listed = {row["id"]: row for row in client.get("/api/records").json()["items"]}
    assert listed[good["id"]]["prize"] == 5
    assert listed[bad.id]["prize"] == 7
    assert listed[bad.id]["cost"] == 2


def test_verify_record_ids_limit_and_empty_selection(client, db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["16"])
    first = _record(client, prize=0)
    second = _record(client, issue="2026002", prize=8)

    skipped = client.post("/api/records/verify", json={"apply": True, "record_ids": []}).json()
    assert skipped["items"] == []
    assert skipped["summary"]["total"] == 0

    only = client.post("/api/records/verify", json={"apply": True, "record_ids": [first["id"]]}).json()
    assert [item["id"] for item in only["items"]] == [first["id"]]
    assert only["items"][0]["status"] == "updated"
    assert only["items"][0]["level"] == "一等奖"
    listed = {row["id"]: row for row in client.get("/api/records").json()["items"]}
    assert listed[first["id"]]["prize"] == 5_000_000
    assert listed[second["id"]]["prize"] == 8
    assert listed[second["id"]]["issue"] == "2026002"


def test_verify_strips_issue_when_matching_draw(client, db):
    _draw(db, "ssq", "2026001", ["11", "12", "13", "14", "15", "16"], ["16"])
    row = _record(client, issue=" 2026001 ", prize=0)
    body = client.post("/api/records/verify", json={"apply": True, "record_ids": [row["id"]]}).json()
    assert body["items"][0]["status"] == "updated"
    assert body["items"][0]["new_prize"] == 5
    assert body["items"][0]["issue"] == " 2026001 "
    stored = client.get("/api/records").json()["items"][0]
    assert stored["issue"] == " 2026001 "
    assert stored["prize"] == 5
