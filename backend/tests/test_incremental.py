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


def test_echo_ssq_ranks_shared_sets_and_exact_match(client, db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "10", "20", "30"], ["16"], "2026-10-01")
    _draw(db, "ssq", "2026002", ["01", "02", "03", "04", "05", "07"], ["08"], "2026-10-03")
    exact = _draw(db, "ssq", "2026003", ["01", "02", "03", "04", "05", "06"], ["16"], "2026-10-05")
    exact.source = "crawl"
    db.commit()
    _draw(db, "ssq", "2026004", ["21", "22", "23", "24", "25", "26"], ["02"], "2026-10-07")
    _draw(db, "ssq", "2026005", ["01", "02", "03", "21", "22", "23"], ["09"], "2026-10-02")
    _draw(db, "ssq", "2026006", ["04", "05", "06", "21", "22", "23"], ["09"], "2026-10-04")
    _draw(db, "ssq", "2026007", ["01", "02", "03", "24", "25", "26"], ["09"], "2026-10-04")

    res = client.post(
        "/api/analysis/ssq/echo",
        json={"main": [6, 5, 4, "03", "02", 1], "special": ["16"]},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == {
        "lottery_type",
        "query",
        "sample_size",
        "top",
        "mode",
        "echoes",
        "disclaimer",
        "data_status",
    }
    assert body["lottery_type"] == "ssq"
    assert body["mode"] == "set"
    assert body["sample_size"] == 7
    assert body["top"] == 8
    assert body["data_status"] == "mixed"
    assert body["query"] == {"main": ["06", "05", "04", "03", "02", "01"], "special": ["16"]}
    assert body["disclaimer"] == "回声对照仅供娱乐，不代表下期结果；请理性购彩。"
    assert [row["issue"] for row in body["echoes"]] == [
        "2026003",
        "2026002",
        "2026001",
        "2026007",
        "2026006",
        "2026005",
    ]
    best = body["echoes"][0]
    assert set(best) == {
        "issue",
        "draw_date",
        "main",
        "special",
        "main_shared",
        "special_shared",
        "score",
        "shared_main",
        "shared_special",
        "exact_match",
    }
    assert best["exact_match"] is True
    assert best["main_shared"] == 6
    assert best["special_shared"] == 1
    assert best["score"] == 61
    assert best["shared_main"] == ["01", "02", "03", "04", "05", "06"]
    assert best["shared_special"] == ["16"]
    assert best["draw_date"] == "2026-10-05"
    assert body["echoes"][1]["main_shared"] == 5
    assert body["echoes"][1]["special_shared"] == 0
    assert body["echoes"][1]["score"] == 50
    assert body["echoes"][1]["exact_match"] is False
    assert body["echoes"][2]["score"] == 31
    assert body["echoes"][2]["shared_main"] == ["01", "02", "03"]
    assert all(row["score"] > 0 for row in body["echoes"])

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

    newest = client.post(
        "/api/analysis/ssq/echo",
        json={"main": "01 02 03 04 05 06", "special": "16", "limit": 2, "top": 1},
    )
    assert newest.status_code == 200
    window = newest.json()
    assert window["sample_size"] == 2
    assert window["top"] == 1
    assert [row["issue"] for row in window["echoes"]] == ["2026007"]
    assert window["echoes"][0]["exact_match"] is False


def test_echo_fc3d_matches_positions_not_sets(client, db):
    _draw(db, "fc3d", "2026101", ["1", "2", "9"], [], "2026-01-01")
    _draw(db, "fc3d", "2026102", ["1", "9", "3"], [], "2026-01-02")
    _draw(db, "fc3d", "2026103", ["1", "2", "3"], [], "2026-01-03")
    _draw(db, "fc3d", "2026104", ["3", "2", "1"], [], "2026-01-04")
    _draw(db, "fc3d", "2026105", ["9", "8", "7"], [], "2026-01-05")

    res = client.post("/api/analysis/fc3d/echo", json={"main": ["01", "02", "03"]})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["mode"] == "digit"
    assert body["query"] == {"main": ["1", "2", "3"], "special": []}
    assert body["sample_size"] == 5
    assert body["data_status"] == "seed"
    assert [row["issue"] for row in body["echoes"]] == ["2026103", "2026102", "2026101", "2026104"]
    assert body["echoes"][0]["exact_match"] is True
    assert body["echoes"][0]["main_shared"] == 3
    assert body["echoes"][0]["score"] == 30
    assert body["echoes"][0]["shared_main"] == ["1", "2", "3"]
    swapped = body["echoes"][3]
    assert swapped["issue"] == "2026104"
    assert swapped["main_shared"] == 1
    assert swapped["shared_main"] == ["2"]
    assert swapped["score"] == 10
    assert swapped["exact_match"] is False
    assert body["echoes"][1]["shared_main"] == ["1", "3"]
    assert body["echoes"][2]["shared_main"] == ["1", "2"]


def test_echo_empty_history_and_bad_numbers(client):
    empty = client.post(
        "/api/analysis/ssq/echo",
        json={"main": ["01", "02", "03", "04", "05", "06"], "special": ["07"]},
    )
    assert empty.status_code == 200
    body = empty.json()
    assert body["sample_size"] == 0
    assert body["echoes"] == []
    assert body["mode"] == "set"
    assert body["data_status"] == "seed"

    bad = client.post("/api/analysis/ssq/echo", json={"main": ["99"], "special": ["01"]})
    assert bad.status_code == 400
    duplicate = client.post(
        "/api/analysis/ssq/echo",
        json={"main": ["01", "01", "03", "04", "05", "06"], "special": ["01"]},
    )
    assert duplicate.status_code == 400
    short = client.post("/api/analysis/fc3d/echo", json={"main": ["1", "2"]})
    assert short.status_code == 400
    extra = client.post("/api/analysis/fc3d/echo", json={"main": ["1", "2", "3"], "special": ["4"]})
    assert extra.status_code == 400
    unknown = client.post("/api/analysis/nope/echo", json={"main": ["01"]})
    assert unknown.status_code == 400

    calc = client.post(
        "/api/prize/calc",
        json={
            "lottery_type": "ssq",
            "bet_numbers": {"main": ["01", "02", "03", "04", "05", "06"], "special": ["07"]},
            "draw_numbers": {"main": ["01", "02", "03", "04", "05", "06"], "special": ["07"]},
        },
    )
    assert calc.status_code == 200
    assert calc.json()["level"] == "一等奖"
    settings = client.get("/api/settings")
    assert set(settings.json()) == {
        "crawl_interval_minutes",
        "subscribed_types",
        "mail_enabled",
        "mail_to",
        "smtp_configured",
        "lotteries",
    }


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
