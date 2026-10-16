"""新增形态 / 回测 / 账本导出，并锁住原接口的返回形状。"""
from __future__ import annotations

import csv
import io
import json

from app.models import Draw
from app.services.ledger import month_key
from app.services.shape import summarize


def _draw(db, lottery_type, issue, main, special=None, draw_date=""):
    row = Draw(
        lottery_type=lottery_type,
        issue=issue,
        numbers=json.dumps({"main": main, "special": special or []}, ensure_ascii=False),
        draw_date=draw_date,
        source="seed",
    )
    db.add(row)
    db.commit()
    return row


def test_month_key_formats():
    assert month_key("2026-10-15") == "2026-10"
    assert month_key("2026/09/02") == "2026-09"
    assert month_key("20261001") == "2026-10"
    assert month_key("2026-13-01") == "未填日期"
    assert month_key("") == "未填日期"
    assert month_key(None) == "未填日期"


def test_summarize_ssq_shape():
    draws = [
        [1, 2, 3, 10, 20, 30],
        [5, 7, 9, 11, 13, 15],
    ]
    body = summarize(draws, "ssq")
    assert body["sample_size"] == 2
    assert body["mode"] == "set"
    assert body["number_scope"] == "主号"
    assert body["sum"]["min"] == 60
    assert body["sum"]["max"] == 66
    assert body["sum"]["avg"] == 63
    assert sum(item["count"] for item in body["sum"]["buckets"]) == 2
    assert body["odd_even"][0]["label"] in {"2奇4偶", "6奇0偶"}
    labels = {item["label"]: item["count"] for item in body["odd_even"]}
    assert labels["2奇4偶"] == 1
    assert labels["6奇0偶"] == 1
    sizes = {item["label"]: item["count"] for item in body["big_small"]}
    assert sizes["2大4小"] == 1
    assert sizes["0大6小"] == 1
    assert body["consecutive"]["draws_with"] == 1
    assert body["consecutive"]["draws_without"] == 1
    assert body["consecutive"]["avg_pairs"] == 1
    zones = {item["label"]: item["avg"] for item in body["zones"]}
    assert zones["一区 01–11"] == 4
    assert zones["二区 12–22"] == 1.5
    assert zones["三区 23–33"] == 0.5
    assert body["patterns"] == []


def test_summarize_fc3d_patterns():
    body = summarize([[8, 8, 8], [1, 2, 3], [1, 1, 2]], "fc3d")
    assert body["mode"] == "digit3"
    patterns = {item["label"]: item["count"] for item in body["patterns"]}
    assert patterns == {"豹子": 1, "组三": 1, "组六": 1}
    assert body["sum"]["avg"] == 11.33
    assert body["span"]["avg"] == 1
    assert body["consecutive"]["draws_with"] == 2
    assert {item["label"]: item["count"] for item in body["big_small"]}["0大3小"] == 2


def test_summarize_empty_and_unknown():
    empty = summarize([], "ssq")
    assert empty["sample_size"] == 0
    assert empty["sum"]["avg"] is None
    assert empty["zones"][0]["avg"] == 0
    try:
        summarize([[1]], "nope")
    except ValueError as exc:
        assert "未知彩种" in str(exc)
    else:
        raise AssertionError("unknown type should fail")


def test_shape_api_ignores_special_and_keeps_analysis_contract(client, db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "10", "20", "30"], ["16"])
    _draw(db, "ssq", "2026002", ["05", "07", "09", "11", "13", "15"], ["02"])
    _draw(db, "qxc", "2026001", ["1", "2", "3", "4", "5", "6"], ["14"])

    analysis = client.get("/api/analysis/ssq")
    assert analysis.status_code == 200
    assert set(analysis.json()) == {
        "lottery_type",
        "sample_size",
        "main_freq",
        "special_freq",
        "main_omit",
        "special_omit",
        "hot_main",
        "cold_main",
        "heatmap",
        "history",
        "data_status",
        "disclaimer",
    }

    shape = client.get("/api/analysis/ssq/shape")
    assert shape.status_code == 200
    body = shape.json()
    assert body["sum"]["avg"] == 63
    assert body["sample_size"] == 2

    qxc = client.get("/api/analysis/qxc/shape")
    assert qxc.status_code == 200
    assert qxc.json()["sum"]["min"] == 21
    assert qxc.json()["sum"]["max"] == 21

    unknown = client.get("/api/analysis/nope/shape")
    assert unknown.status_code == 400
    assert client.get("/api/analysis/ssq/shape?limit=1").status_code == 422


def test_backtest_scans_newest_first_and_calc_stays(client, db):
    _draw(db, "ssq", "2026001", ["11", "12", "13", "14", "15", "16"], ["16"], "2026-10-01")
    _draw(db, "ssq", "2026002", ["01", "02", "03", "04", "05", "06"], ["16"], "2026-10-03")
    _draw(db, "ssq", "2026003", ["07", "08", "09", "10", "11", "12"], ["01"], "2026-10-05")
    ticket = {
        "lottery_type": "ssq",
        "play": "single",
        "bet_numbers": {"main": ["01", "02", "03", "04", "05", "06"], "special": ["16"]},
        "multiple": 1,
    }
    calc = client.post(
        "/api/prize/calc",
        json={**ticket, "draw_numbers": {"main": ["11", "12", "13", "14", "15", "16"], "special": ["16"]}},
    )
    assert calc.status_code == 200
    calc_body = calc.json()
    assert calc_body["ok"] is True
    assert calc_body["level"] == "六等奖"
    assert calc_body["amount"] == 5
    assert calc_body["cost"] == 2
    assert calc_body["opened"] is True

    report = client.post("/api/prize/backtest", json={**ticket, "limit": 30})
    assert report.status_code == 200
    body = report.json()
    assert body["sample_size"] == 3
    assert body["win_count"] == 2
    assert body["cost_each"] == 2
    assert body["illustrative_spent"] == 6
    assert body["illustrative_amount"] == 5000005
    assert body["illustrative_net"] == 4999999
    assert [hit["issue"] for hit in body["hits"]] == ["2026002", "2026001"]
    assert body["hits"][0]["level"] == "一等奖"
    assert body["hits"][0]["floating"] is True
    assert body["hits"][0]["main_hit"] == 6
    assert body["hits"][1]["amount"] == 5
    assert body["hits"][1]["main_hit"] == 0
    assert body["hits"][1]["special_hit"] == 1

    latest_only = client.post("/api/prize/backtest", json={**ticket, "limit": 1})
    assert latest_only.json()["sample_size"] == 1
    assert latest_only.json()["win_count"] == 0
    assert latest_only.json()["illustrative_net"] == -2

    invalid = client.post(
        "/api/prize/backtest",
        json={"lottery_type": "ssq", "bet_numbers": {"main": ["99"], "special": ["1"]}},
    )
    assert invalid.status_code == 400
    assert client.post("/api/prize/backtest", json={"lottery_type": "nope", "bet_numbers": {}}).status_code == 400
    rules = client.get("/api/prize/rules")
    assert rules.status_code == 200
    rules_body = rules.json()
    assert set(rules_body) == {"stake", "lotteries"}
    assert rules_body["stake"] == 2
    assert "ssq" in rules_body["lotteries"] and "dlt" in rules_body["lotteries"]


def test_records_monthly_export_and_crud_contract(client):
    created = client.post(
        "/api/records",
        json={
            "lottery_type": "ssq",
            "issue": "2026001",
            "numbers": {"play": "single", "main": ["01", "02", "03", "04", "05", "06"], "special": ["07"]},
            "cost": 2,
            "prize": 0,
            "note": "=不要当公式",
            "purchased_at": "2026-10-15",
        },
    )
    assert created.status_code == 200
    assert set(created.json()) == {
        "id",
        "lottery_type",
        "name",
        "issue",
        "numbers",
        "play_name",
        "cost",
        "prize",
        "note",
        "purchased_at",
        "profit",
    }
    assert created.json()["profit"] == -2
    rid = created.json()["id"]

    client.post(
        "/api/records",
        json={
            "lottery_type": "fc3d",
            "issue": "2026002",
            "numbers": {"play": "group6", "main": ["1", "2", "3"]},
            "cost": 2,
            "prize": 10,
            "note": "",
            "purchased_at": "2026/09/02",
        },
    )
    client.post(
        "/api/records",
        json={
            "lottery_type": "dlt",
            "issue": "2026003",
            "numbers": {"main": ["01", "02", "03", "04", "05"], "special": ["06", "07"]},
            "cost": 2,
            "prize": 0,
            "purchased_at": "20261001",
        },
    )
    client.post(
        "/api/records",
        json={
            "lottery_type": "pl3",
            "issue": "2026004",
            "numbers": {"play": "group6", "main": ["1", "2", "3"]},
            "cost": 2,
            "prize": 0,
            "purchased_at": "bad-date",
        },
    )

    listed = client.get("/api/records")
    assert listed.status_code == 200
    body = listed.json()
    assert set(body) == {"items", "summary"}
    assert set(body["summary"]) == {"count", "total_cost", "total_prize", "net"}
    assert body["summary"]["count"] == 4
    assert body["summary"]["total_cost"] == 8
    assert body["summary"]["total_prize"] == 10
    assert body["summary"]["net"] == 2

    monthly = client.get("/api/records/monthly").json()
    assert [item["month"] for item in monthly["months"]] == ["2026-10", "2026-09", "未填日期"]
    october = monthly["months"][0]
    assert october["count"] == 2
    assert october["total_cost"] == 4
    assert october["net"] == -4

    exported = client.get("/api/records/export")
    assert exported.status_code == 200
    assert "text/csv" in exported.headers["content-type"]
    assert exported.content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert rows[0] == ["彩种", "期号", "玩法", "号码", "投入", "奖金", "盈亏", "购买日期", "备注"]
    notes = [row[8] for row in rows[1:]]
    assert "'=不要当公式" in notes
    assert any(row[0] == "双色球" and "01 02 03 04 05 06 + 07" in row[3] for row in rows[1:])

    updated = client.put(f"/api/records/{rid}", json={"prize": 5})
    assert updated.status_code == 200
    assert updated.json()["prize"] == 5
    assert updated.json()["profit"] == 3
    assert client.get("/api/records").json()["summary"]["net"] == 7

    missing = client.delete("/api/records/999999")
    assert missing.status_code == 404
    assert client.delete(f"/api/records/{rid}").json() == {"ok": True}
    assert client.get("/api/records").json()["summary"]["count"] == 3


def _slip(client, **overrides):
    body = {
        "lottery_type": "ssq",
        "issue": "2026001",
        "numbers": {"play": "single", "main": ["06", "05", "04", "03", "02", "01"], "special": ["01"]},
        "cost": 2,
        "prize": 0,
        "note": "",
        "purchased_at": "2026-10-02",
    }
    body.update(overrides)
    res = client.post("/api/records", json=body)
    assert res.status_code == 200, res.text
    return res.json()


def test_rhythm_repeats_pace_and_old_list_shape(client):
    _slip(client, issue="2026106", prize=0, purchased_at="2026-10-02")
    _slip(
        client,
        issue="2026101",
        numbers={"play": "single", "main": ["01", "02", "03", "04", "05", "06"], "special": ["01"], "multiple": 3},
        prize=5,
        purchased_at="2026-09-02",
    )
    _slip(
        client,
        lottery_type="ssq",
        issue="2026102",
        numbers={"play": "single", "main": ["01", "02", "03", "04", "05", "06"], "special": ["02"]},
        purchased_at="2026-09-09",
    )
    _slip(
        client,
        lottery_type="fc3d",
        issue="2026252",
        numbers={"play": "direct", "positions": [["1"], ["2"], ["3"]]},
        purchased_at="2025-12-20",
    )
    _slip(
        client,
        lottery_type="fc3d",
        issue="2026253",
        numbers={"play": "direct", "positions": [["3"], ["2"], ["1"]]},
        purchased_at="2026-01-02",
    )
    _slip(
        client,
        lottery_type="fc3d",
        issue="2026254",
        numbers={"play": "group6", "main": ["3", "2", "1"]},
        purchased_at="2026-01-02",
    )
    _slip(
        client,
        lottery_type="fc3d",
        issue="2026255",
        numbers={"play": "group6", "main": ["1", "2", "3"]},
        purchased_at="bad",
    )

    listed = client.get("/api/records")
    assert set(listed.json()) == {"items", "summary"}
    assert "repeat_groups" not in listed.json()

    rhythm = client.get("/api/records/rhythm?on=2026-10-16")
    assert rhythm.status_code == 200
    body = rhythm.json()
    assert body["current_month"] == "2026-10"
    assert body["previous_month"] == "2026-09"
    assert body["current"]["total_cost"] == 2
    assert body["previous"]["total_cost"] == 4
    assert body["cost_delta"] == -2
    assert body["slip_count"] == 7
    assert body["distinct_days"] == 5
    assert body["longest_gap_days"] == 243
    assert body["avg_cost"] == 2
    groups = {(item["lottery_type"], item["numbers_text"]): item for item in body["repeat_groups"]}
    assert len(groups) == 2
    ssq = groups[("ssq", "01 02 03 04 05 06 + 01")]
    assert ssq["count"] == 2
    assert ssq["issues"] == ["2026101", "2026106"]
    assert ssq["total_prize"] == 5
    assert groups[("fc3d", "1 2 3")]["count"] == 2
    assert ("fc3d", "1 | 2 | 3") not in groups
    assert ("fc3d", "3 | 2 | 1") not in groups

    january = client.get("/api/records/rhythm?on=2026-01-15").json()
    assert january["current_month"] == "2026-01"
    assert january["previous_month"] == "2025-12"
    assert january["current"]["count"] == 2
    assert january["previous"]["count"] == 1
    assert january["longest_gap_days"] == 243

    assert client.get("/api/records/rhythm?on=2026-13-01").status_code == 400
    empty = client.get("/api/records/rhythm?on=2024-01-01").json()
    assert empty["current"]["count"] == 0
    assert empty["cost_delta"] == 0


def test_empty_backtest_and_export(client):
    report = client.post(
        "/api/prize/backtest",
        json={
            "lottery_type": "dlt",
            "bet_numbers": {"main": ["01", "02", "03", "04", "05"], "special": ["06", "07"]},
        },
    )
    assert report.status_code == 200
    body = report.json()
    assert body["sample_size"] == 0
    assert body["win_count"] == 0
    assert body["illustrative_amount"] == 0
    assert body["illustrative_net"] == 0

    exported = client.get("/api/records/export")
    rows = list(csv.reader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert rows == [["彩种", "期号", "玩法", "号码", "投入", "奖金", "盈亏", "购买日期", "备注"]]

    shape = client.get("/api/analysis/kl8/shape")
    assert shape.status_code == 200
    assert shape.json()["sample_size"] == 0
    assert shape.json()["mode"] == "set"


def test_health_and_settings_contract(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True
    assert "disclaimer" in health.json()

    settings = client.get("/api/settings")
    assert settings.status_code == 200
    assert set(settings.json()) == {
        "crawl_interval_minutes",
        "subscribed_types",
        "mail_enabled",
        "mail_to",
        "smtp_configured",
        "lotteries",
    }
