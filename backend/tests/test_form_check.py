"""一注体检：对照历史形态区间，不走短长窗脉动。

主号指标用已有静态算法。特别号单独列出，不并进主号。
常见带是历史 p25–p75，标签只有偏低、居中、偏高；没有样本时标样本不足。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models import Draw
from app.services.pulse_ensemble import PULSE_MODULES

GET_KEYS = {
    "lottery_type",
    "mode",
    "sample_size",
    "limit",
    "band",
    "query",
    "metrics",
    "special_metrics",
    "summary",
    "glance",
    "data_status",
    "disclaimer",
    "number_scope",
}

METRIC_KEYS = {
    "key",
    "label",
    "value",
    "display",
    "compared",
    "percentile",
    "band_low",
    "band_high",
    "band_label",
    "history_min",
    "history_max",
    "stance",
    "stance_label",
    "sample_size",
    "note",
}

MAIN_KEYS = ["sum", "span", "odd", "zone", "ac", "tail", "hewei", "road"]


def _draw(db, lottery_type, issue, main, special=None, source="seed", draw_date=""):
    row = Draw(
        lottery_type=lottery_type,
        issue=issue,
        numbers=json.dumps({"main": main, "special": special or []}, ensure_ascii=False),
        draw_date=draw_date,
        source=source,
    )
    db.add(row)
    db.commit()
    return row


def _by_key(rows):
    return {item["key"]: item for item in rows}


def test_module_is_not_a_pulse():
    source = (Path(__file__).resolve().parents[1] / "app" / "services" / "form_check.py").read_text(encoding="utf-8")
    assert "pulse_ensemble" not in source
    assert "def _pulse" not in source
    assert "short_avg" not in source
    assert "long_avg" not in source
    assert all(module.key != "form_check" for module in PULSE_MODULES)
    assert all("form_check" not in module.key for module in PULSE_MODULES)


def test_band_marks_low_center_and_high():
    from app.services.form_check import place_value

    low = place_value(10, [10, 20, 30, 40])
    assert low["band_low"] == 17.5
    assert low["band_high"] == 32.5
    assert low["band_label"] == "17.5–32.5"
    assert low["percentile"] == 0.25
    assert low["stance"] == "low"
    assert low["stance_label"] == "偏低"
    assert low["history_min"] == 10
    assert low["history_max"] == 40
    assert low["sample_size"] == 4

    center = place_value(20, [10, 20, 30, 40])
    assert center["stance"] == "center"
    assert center["stance_label"] == "居中"
    assert center["percentile"] == 0.5

    high = place_value(40, [10, 20, 30, 40])
    assert high["stance"] == "high"
    assert high["stance_label"] == "偏高"
    assert high["percentile"] == 1.0


def test_band_edges_are_inclusive_and_single_sample_centers():
    from app.services.form_check import place_value

    on_low = place_value(17.5, [10, 20, 30, 40])
    on_high = place_value(32.5, [10, 20, 30, 40])
    assert on_low["stance"] == "center"
    assert on_high["stance"] == "center"

    same = place_value(15, [15])
    assert same["stance"] == "center"
    assert same["band_low"] == 15
    assert same["band_high"] == 15
    assert same["band_label"] == "15"
    assert same["percentile"] == 1.0
    assert place_value(14, [15])["stance"] == "low"
    assert place_value(16, [15])["stance"] == "high"


def test_empty_history_has_no_band():
    from app.services.form_check import place_value

    placed = place_value(8, [])
    assert placed["percentile"] is None
    assert placed["band_low"] is None
    assert placed["band_high"] is None
    assert placed["band_label"] == ""
    assert placed["history_min"] is None
    assert placed["history_max"] is None
    assert placed["stance"] == "unavailable"
    assert placed["stance_label"] == "样本不足"
    assert placed["sample_size"] == 0


def test_ssq_metrics_ignore_special_and_use_static_formulas(db):
    from app.services.form_check import DISCLAIMER, check_form

    _draw(db, "ssq", "2026004", ["01", "02", "03", "04", "05", "06"], ["01"])
    _draw(db, "ssq", "2026003", ["02", "03", "04", "05", "06", "07"], ["02"])
    _draw(db, "ssq", "2026002", ["03", "04", "05", "06", "07", "08"], ["03"])
    _draw(db, "ssq", "2026001", ["04", "05", "06", "07", "08", "09"], ["04"])

    body = check_form(db, "ssq", ["1", "2", "3", "4", "5", "33"], "16", limit=80)
    assert set(body) == GET_KEYS
    assert body["lottery_type"] == "ssq"
    assert body["mode"] == "set"
    assert body["sample_size"] == 4
    assert body["limit"] == 80
    assert body["band"] == "p25-p75"
    assert body["number_scope"] == "主号"
    assert body["data_status"] == "seed"
    assert body["disclaimer"] == DISCLAIMER
    assert "仅供娱乐" in body["disclaimer"]
    assert "不构成投注建议" in body["disclaimer"]
    assert "pulse" not in body
    assert "drift" not in body
    assert "short" not in body
    assert "long" not in body
    assert body["query"] == {"main": ["01", "02", "03", "04", "05", "33"], "special": ["16"]}

    metrics = _by_key(body["metrics"])
    assert list(metrics) == MAIN_KEYS
    for item in body["metrics"]:
        assert set(item) == METRIC_KEYS
        assert "pulse" not in item
        assert "drift" not in item

    assert metrics["sum"]["value"] == 48
    assert metrics["sum"]["display"] == "48"
    assert metrics["sum"]["band_low"] == 25.5
    assert metrics["sum"]["band_high"] == 34.5
    assert metrics["sum"]["stance"] == "high"
    assert metrics["sum"]["percentile"] == 1.0
    assert metrics["sum"]["history_min"] == 21
    assert metrics["sum"]["history_max"] == 39

    assert metrics["span"]["value"] == 32
    assert metrics["odd"]["value"] == 4
    assert metrics["odd"]["display"] == "4奇2偶"
    assert metrics["odd"]["compared"] == "奇数个数"
    assert metrics["zone"]["value"] == 5
    assert metrics["zone"]["display"] == "5:0:1"
    assert metrics["zone"]["compared"] == "偏度"
    assert metrics["ac"]["value"] == 4
    assert metrics["tail"]["value"] == 5
    assert metrics["tail"]["display"] == "5种"
    assert metrics["hewei"]["value"] == 8
    assert metrics["road"]["value"] == 0
    assert metrics["road"]["display"] == "2:2:2"
    assert metrics["road"]["compared"] == "路偏"

    special = _by_key(body["special_metrics"])
    assert special["sum"]["value"] == 16
    assert "span" not in special
    assert "ac" not in special
    assert special["sum"]["value"] != metrics["sum"]["value"]
    assert "偏高" in body["glance"] or "居中" in body["glance"]
    assert body["summary"]["high"] >= 1
    assert body["summary"]["centered"] + body["summary"]["low"] + body["summary"]["high"] + body["summary"]["unavailable"] == 8


def test_matching_history_is_centered_and_special_stays_separate(db):
    from app.services.form_check import check_form

    main = ["01", "02", "03", "04", "05", "06"]
    for index in range(4):
        _draw(db, "ssq", f"202600{index}", main, ["16"])

    body = check_form(db, "ssq", main, ["16"])
    assert body["glance"] == "形态居中"
    assert body["summary"] == {"centered": 8, "low": 0, "high": 0, "unavailable": 0}
    assert all(item["stance"] == "center" for item in body["metrics"])
    assert _by_key(body["metrics"])["sum"]["value"] == 21
    assert _by_key(body["special_metrics"])["sum"]["value"] == 16
    assert _by_key(body["special_metrics"])["hewei"]["value"] == 6


def test_empty_history_still_returns_ticket_values(db):
    from app.services.form_check import check_form

    body = check_form(db, "ssq", "01 02 03 04 05 06", "07")
    assert body["sample_size"] == 0
    assert body["glance"] == "还没有历史可对照"
    assert body["summary"]["unavailable"] == 8
    metrics = _by_key(body["metrics"])
    assert metrics["sum"]["value"] == 21
    assert metrics["sum"]["stance"] == "unavailable"
    assert metrics["sum"]["stance_label"] == "样本不足"
    assert metrics["span"]["value"] == 5
    assert body["special_metrics"]
    assert all(item["stance"] == "unavailable" for item in body["special_metrics"])


def test_blank_rows_do_not_count_and_limit_cuts_oldest(db):
    from app.services.form_check import check_form

    _draw(db, "ssq", "2026001", ["10", "11", "12", "13", "14", "15"], ["01"])
    _draw(db, "ssq", "2026002", ["01", "02", "03", "04", "05", "06"], ["02"])
    _draw(db, "ssq", "2026003", [], ["03"])
    _draw(db, "ssq", "2026004", ["02", "03", "04", "05", "06", "07"], ["04"], source="crawl")

    body = check_form(db, "ssq", ["01", "02", "03", "04", "05", "06"], ["09"], limit=2)
    assert body["limit"] == 2
    assert body["sample_size"] == 1
    assert body["data_status"] == "mixed"
    assert _by_key(body["metrics"])["sum"]["history_min"] == 27
    assert _by_key(body["metrics"])["sum"]["sample_size"] == 1


def test_digit_keeps_repeats_and_rejects_special(db):
    from app.services.form_check import check_form

    _draw(db, "fc3d", "2026002", ["1", "2", "3"], [])
    _draw(db, "fc3d", "2026001", ["0", "0", "0"], [])
    body = check_form(db, "3d", ["1", "1", "1"], None)
    assert body["lottery_type"] == "fc3d"
    assert body["mode"] == "digit"
    metrics = _by_key(body["metrics"])
    assert metrics["sum"]["value"] == 3
    assert metrics["span"]["value"] == 0
    assert metrics["odd"]["display"] == "3奇0偶"
    assert metrics["zone"]["display"] == "3:0:0"
    assert metrics["zone"]["value"] == 3
    assert metrics["ac"]["value"] == -1
    assert metrics["tail"]["value"] == 1
    assert metrics["hewei"]["value"] == 3
    assert metrics["road"]["display"] == "0:3:0"
    assert metrics["road"]["value"] == 3
    assert body["special_metrics"] == []
    assert metrics["sum"]["sample_size"] == 2

    with pytest.raises(ValueError, match="没有特别号"):
        check_form(db, "fc3d", ["1", "2", "3"], ["1"])


def test_each_lottery_accepts_a_legal_ticket(db):
    from app.services.form_check import check_form

    tickets = {
        "ssq": (["01", "08", "09", "16", "22", "33"], ["07"]),
        "dlt": (["01", "02", "03", "04", "35"], ["01", "12"]),
        "qlc": (["01", "02", "03", "04", "05", "06", "30"], ["09"]),
        "kl8": (["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"], None),
        "pl3": (["0", "5", "9"], None),
        "pl5": (["0", "1", "2", "3", "4"], None),
        "qxc": (["0", "1", "2", "3", "4", "9"], ["14"]),
    }
    for lottery, (main, special) in tickets.items():
        body = check_form(db, lottery, main, special)
        assert body["lottery_type"] == lottery
        assert [item["key"] for item in body["metrics"]] == MAIN_KEYS
        assert all("pulse" not in item for item in body["metrics"])

    dlt = check_form(db, "dlt", ["01", "02", "03", "04", "35"], ["01", "12"])
    assert _by_key(dlt["metrics"])["sum"]["value"] == 45
    special = _by_key(dlt["special_metrics"])
    assert special["sum"]["value"] == 13
    assert special["span"]["value"] == 11
    assert special["ac"]["value"] == 0

    qxc = check_form(db, "qxc", ["0", "1", "2", "3", "4", "5"], ["14"])
    assert _by_key(qxc["metrics"])["sum"]["value"] == 15
    assert _by_key(qxc["special_metrics"])["sum"]["value"] == 14
    assert _by_key(qxc["special_metrics"])["zone"]["display"] == "0:0:1"

    one = check_form(db, "kl8", ["08"], None)
    kl8_metrics = _by_key(one["metrics"])
    assert kl8_metrics["sum"]["value"] == 8
    assert kl8_metrics["span"]["value"] == 0
    assert kl8_metrics["ac"]["value"] is None
    assert kl8_metrics["ac"]["stance"] == "unavailable"
    assert kl8_metrics["ac"]["stance_label"] == "不适用"
    assert kl8_metrics["odd"]["display"] == "0奇1偶"
    assert kl8_metrics["zone"]["display"] == "1:0:0"


def test_invalid_numbers_raise():
    from app.services.form_check import check_form

    class Empty:
        def query(self, *_args, **_kwargs):
            raise AssertionError("非法号码不应查库")

    with pytest.raises(ValueError, match="未知彩种"):
        check_form(Empty(), "nope", ["01"], None)
    with pytest.raises(ValueError, match="超出"):
        check_form(Empty(), "ssq", ["01", "02", "03", "04", "05", "99"], ["01"])
    with pytest.raises(ValueError, match="需要"):
        check_form(Empty(), "pl5", ["0", "1"], None)
    with pytest.raises(ValueError, match="重复"):
        check_form(Empty(), "ssq", ["01", "01", "03", "04", "05", "06"], ["01"])


def test_api_get_post_and_leaves_span_pulse_alone(client, db):
    _draw(db, "ssq", "2026002", ["01", "02", "03", "04", "05", "06"], ["08"], source="crawl")
    _draw(db, "ssq", "2026001", ["02", "03", "04", "05", "06", "16"], ["09"])

    before = client.get("/api/analysis/ssq/span")
    assert before.status_code == 200
    assert "pulse" in before.json()
    assert "drift" in before.json()

    posted = client.post(
        "/api/analysis/form-check",
        json={
            "lottery_type": "ssq",
            "main": ["01", "02", "03", "04", "05", "06"],
            "special": ["07"],
            "limit": 80,
        },
    )
    assert posted.status_code == 200
    body = posted.json()
    assert body["query"]["main"] == ["01", "02", "03", "04", "05", "06"]
    assert "pulse" not in body
    assert "仅供娱乐" in body["disclaimer"]
    assert _by_key(body["metrics"])["sum"]["value"] == 21

    got = client.get(
        "/api/analysis/form-check",
        params={"type": "ssq", "numbers": "01，02,03 04 05 06", "special": "07"},
    )
    assert got.status_code == 200
    assert got.json()["metrics"] == body["metrics"]
    assert "hot_main" not in got.json()

    numbered = client.post(
        "/api/analysis/form-check",
        json={"type": "ssq", "numbers": {"main": ["01", "02", "03", "04", "05", "06"], "special": ["07"]}},
    )
    assert numbered.status_code == 200
    assert numbered.json()["query"]["special"] == ["07"]

    analysis = client.get("/api/analysis/ssq")
    assert analysis.status_code == 200
    assert "hot_main" in analysis.json()

    after = client.get("/api/analysis/ssq/span")
    assert after.json()["pulse"] == before.json()["pulse"]
    assert after.json()["drift"] == before.json()["drift"]
    assert "ticket" not in after.json()


def test_api_rejects_bad_input(client):
    missing = client.post("/api/analysis/form-check", json={"lottery_type": "ssq", "main": []})
    assert missing.status_code == 400
    too_many = [f"{index:02d}" for index in range(1, 22)]
    assert client.post("/api/analysis/form-check", json={"lottery_type": "ssq", "main": too_many}).status_code == 400

    unknown = client.get("/api/analysis/form-check", params={"type": "nope", "numbers": "1"})
    assert unknown.status_code == 400

    low = client.get("/api/analysis/form-check", params={"type": "ssq", "numbers": "1 2 3 4 5 6", "limit": 4})
    high = client.post("/api/analysis/form-check", json={"lottery_type": "ssq", "main": ["01", "02", "03", "04", "05", "06"], "limit": 201})
    assert low.status_code == 422
    assert high.status_code == 422

    empty = client.get("/api/analysis/form-check", params={"type": "ssq", "numbers": "01 02 03 04 05 06", "special": "01"})
    assert empty.status_code == 200
    assert empty.json()["sample_size"] == 0
    assert empty.json()["glance"] == "还没有历史可对照"


def test_batch_matches_single_and_isolates_bad_tickets(db):
    from app.services.form_check import check_form, check_form_batch

    _draw(db, "ssq", "2026002", ["01", "02", "03", "04", "05", "06"], ["08"])
    _draw(db, "ssq", "2026001", ["02", "03", "04", "05", "06", "16"], ["09"])
    good_main = ["01", "02", "03", "04", "05", "33"]
    other_main = ["02", "03", "04", "05", "06", "16"]
    batch = check_form_batch(
        db,
        "ssq",
        [
            {"id": "good", "main": good_main, "special": ["16"]},
            {"id": "bad", "main": ["01", "01", "03", "04", "05", "06"], "special": ["16"]},
            {"id": "other", "numbers": {"main": other_main, "special": ["07"]}},
        ],
        limit=40,
    )
    assert batch["lottery_type"] == "ssq"
    assert batch["limit"] == 40
    assert batch["sample_size"] == 2
    assert "pulse" not in batch
    assert "short" not in batch
    assert "long" not in batch
    assert [item["id"] for item in batch["items"]] == ["good", "bad", "other"]
    good = check_form(db, "ssq", good_main, ["16"], limit=40)
    other = check_form(db, "ssq", other_main, ["07"], limit=40)
    assert batch["items"][0]["ok"] is True
    assert batch["items"][0]["report"] == good
    assert batch["items"][1]["ok"] is False
    assert batch["items"][1]["report"] is None
    assert "重复" in batch["items"][1]["error"]
    assert batch["items"][2]["ok"] is True
    assert batch["items"][2]["report"] == other
    assert good["summary"] != other["summary"] or good["query"] != other["query"]
    assert good["glance"] == batch["items"][0]["report"]["glance"]
    assert "特别" not in str(good["summary"])


def test_batch_unknown_lottery_does_not_query():
    from app.services.form_check import check_form_batch

    class Empty:
        def query(self, *_args, **_kwargs):
            raise AssertionError("未知彩种不应查库")

    with pytest.raises(ValueError, match="未知彩种"):
        check_form_batch(Empty(), "nope", [{"id": "a", "main": ["01", "02", "03", "04", "05", "06"], "special": ["01"]}])


def test_api_batch_matches_single_and_keeps_span_pulse(client, db):
    _draw(db, "ssq", "2026002", ["01", "02", "03", "04", "05", "06"], ["08"], source="crawl")
    _draw(db, "ssq", "2026001", ["02", "03", "04", "05", "06", "16"], ["09"])
    before = client.get("/api/analysis/ssq/span")
    assert before.status_code == 200

    single = client.post(
        "/api/analysis/form-check",
        json={"lottery_type": "ssq", "main": ["01", "02", "03", "04", "05", "06"], "special": ["07"], "limit": 80},
    )
    assert single.status_code == 200
    batched = client.post(
        "/api/analysis/form-check/batch",
        json={
            "lottery_type": "ssq",
            "limit": 80,
            "tickets": [
                {"id": "a", "main": ["01", "02", "03", "04", "05", "06"], "special": ["07"]},
                {"id": "b", "main": ["01", "01", "03", "04", "05", "06"]},
            ],
        },
    )
    assert batched.status_code == 200
    body = batched.json()
    assert body["items"][0]["ok"] is True
    assert body["items"][0]["report"]["metrics"] == single.json()["metrics"]
    assert body["items"][0]["report"]["summary"] == single.json()["summary"]
    assert body["items"][0]["report"]["glance"] == single.json()["glance"]
    assert body["items"][0]["report"]["special_metrics"] == single.json()["special_metrics"]
    assert body["items"][1]["ok"] is False
    assert body["items"][1]["report"] is None
    assert "pulse" not in body
    assert "short" not in body
    assert "long" not in body

    after = client.get("/api/analysis/ssq/span")
    assert after.json()["pulse"] == before.json()["pulse"]
    assert after.json()["drift"] == before.json()["drift"]

    unknown = client.post("/api/analysis/form-check/batch", json={"lottery_type": "nope", "tickets": []})
    assert unknown.status_code == 400
