"""升平降脉动：相邻两期同位比较后，用升的个数看短窗相对长窗的升降。

乐透主号去重升序，按该彩种标准个数对齐；任一侧不足则跳过该期。
数字彩按位比较，保留重复和位置，不排序。
特别号不并进主号。乐透特别号升序对齐；没有特别号的数字彩不做 special。
空白主号跳过，不占窗口名额。最早一期没有上期，不能计算。
这不是邻号±1，也不是重号个数，也不是大小个数或区位。
只读本地开奖，不改其他分析接口的返回形状。
"""
from __future__ import annotations

import json

import pytest

from app.models import Draw
from app.services.daxiao import daxiao_summary
from app.services.neighbor import neighbor_summary
from app.services.pulse_ensemble import PULSE_MODULES, _MEMO_TARGETS, score_ticket
from app.services.repeat import repeat_pulse
from app.services.shengping import (
    COMMON_LIMIT,
    DIGIT_NOTE,
    DISCLAIMER,
    THRESHOLD,
    score_shengping,
    shengping_summary,
)
from app.services.zone import zone_summary

GET_KEYS = {
    "lottery_type",
    "mode",
    "basis",
    "sample_size",
    "short",
    "long",
    "threshold",
    "distribution",
    "common",
    "mean",
    "median",
    "short_avg",
    "long_avg",
    "pulse",
    "drift",
    "note",
    "latest_draw",
    "special",
    "data_status",
    "disclaimer",
}

POST_KEYS = GET_KEYS | {"query", "ticket", "special_ticket"}

BUCKET_KEYS = {"rise_count", "count", "rate"}
COMMON_KEYS = {"rise_count", "flat_count", "fall_count", "pattern", "count", "rate"}
TICKET_KEYS = {
    "rise_count",
    "flat_count",
    "fall_count",
    "pattern",
    "percentile",
    "typicality",
    "rarity",
    "alignment",
    "note",
}
LATEST_KEYS = {
    "issue",
    "draw_date",
    "main",
    "special",
    "rise_count",
    "flat_count",
    "fall_count",
    "pattern",
    "special_rise_count",
    "special_flat_count",
    "special_fall_count",
    "special_pattern",
}
SPECIAL_KEYS = {
    "label",
    "sample_size",
    "distribution",
    "common",
    "mean",
    "median",
    "short_avg",
    "long_avg",
    "pulse",
    "drift",
}


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


def _bucket(rows, rise_count):
    found = [item for item in rows if item["rise_count"] == rise_count]
    assert len(found) == 1
    return found[0]


def _empty_ticket():
    return {
        "rise_count": None,
        "flat_count": None,
        "fall_count": None,
        "pattern": None,
        "percentile": None,
        "typicality": None,
        "rarity": None,
        "alignment": None,
        "note": "",
    }


def test_shengping_constants_and_equal_weight_registry():
    assert THRESHOLD == 0.5
    assert COMMON_LIMIT == 8
    assert "仅供娱乐" in DISCLAIMER
    assert "不构成投注建议" in DISCLAIMER
    assert "升" in DISCLAIMER
    assert "按位" in DIGIT_NOTE and "不排序" in DIGIT_NOTE
    keys = [item.key for item in PULSE_MODULES]
    assert keys[-1] == "shengping"
    assert keys[-2] == "daxiao"
    assert [item.label for item in PULSE_MODULES if item.key == "shengping"] == ["升平降"]
    assert ("app.services.shengping", "shengping_summary") in _MEMO_TARGETS
    assert len(keys) == len(set(keys))


def test_set_sorts_before_compare_and_digit_keeps_position(db):
    _draw(db, "ssq", "2026001", ["06", "05", "04", "03", "02", "01"], ["01"])
    _draw(db, "ssq", "2026002", ["01", "02", "03", "04", "05", "07"], ["02"])
    body = shengping_summary(db, "ssq", limit=5)
    assert body["mode"] == "set"
    assert body["basis"] == "main"
    assert body["sample_size"] == 1
    assert body["latest_draw"]["main"] == ["01", "02", "03", "04", "05", "07"]
    assert body["latest_draw"]["rise_count"] == 1
    assert body["latest_draw"]["flat_count"] == 5
    assert body["latest_draw"]["fall_count"] == 0
    assert body["latest_draw"]["pattern"] == "1升5平0降"
    assert body["latest_draw"]["special_rise_count"] == 1
    assert body["latest_draw"]["special_pattern"] == "1升0平0降"
    assert "邻号" in body["note"] and "重号" in body["note"]
    assert body["special"]["label"] == "蓝球"
    assert body["special"]["sample_size"] == 1

    _draw(db, "fc3d", "2026201", ["1", "3", "2"])
    _draw(db, "fc3d", "2026202", ["3", "1", "2"])
    digit = shengping_summary(db, "fc3d", limit=5)
    assert digit["mode"] == "digit"
    assert digit["basis"] == "digits"
    assert digit["note"] == DIGIT_NOTE
    assert digit["latest_draw"]["main"] == ["3", "1", "2"]
    assert digit["latest_draw"]["pattern"] == "1升1平1降"
    assert digit["latest_draw"]["rise_count"] == 1
    assert digit["special"] is None
    assert digit["latest_draw"]["special_rise_count"] is None


def test_set_dedupes_ignores_extra_and_keeps_special_apart(db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["08"], draw_date="2026-01-01")
    _draw(
        db,
        "ssq",
        "2026002",
        ["01", "01", "02", "03", "04", "05", "06", "33"],
        ["16"],
        source="crawl",
        draw_date="2026-01-03",
    )

    body = shengping_summary(db, "ssq", limit=80, short=10, long=50)
    assert set(body) == GET_KEYS
    assert body["lottery_type"] == "ssq"
    assert body["sample_size"] == 1
    assert body["short"] == 10
    assert body["long"] == 50
    assert body["threshold"] == 0.5
    assert body["data_status"] == "mixed"
    assert body["disclaimer"] == DISCLAIMER
    assert body["mean"] == 0
    assert body["median"] == 0
    assert body["short_avg"] == 0
    assert body["long_avg"] == 0
    assert body["pulse"] == 0.0
    assert body["drift"] == "flat"
    assert set(body["latest_draw"]) == LATEST_KEYS
    assert body["latest_draw"]["issue"] == "2026002"
    assert body["latest_draw"]["pattern"] == "0升6平0降"
    assert body["latest_draw"]["special"] == ["16"]
    assert body["latest_draw"]["special_pattern"] == "1升0平0降"
    assert [item["rise_count"] for item in body["distribution"]] == list(range(7))
    assert all(set(item) == BUCKET_KEYS for item in body["distribution"])
    assert _bucket(body["distribution"], 0) == {"rise_count": 0, "count": 1, "rate": 1.0}
    assert _bucket(body["distribution"], 1)["count"] == 0
    assert body["common"] == [
        {
            "rise_count": 0,
            "flat_count": 6,
            "fall_count": 0,
            "pattern": "0升6平0降",
            "count": 1,
            "rate": 1.0,
        }
    ]
    assert all(set(item) == COMMON_KEYS for item in body["common"])

    special = body["special"]
    assert set(special) == SPECIAL_KEYS
    assert special["label"] == "蓝球"
    assert special["sample_size"] == 1
    assert [item["rise_count"] for item in special["distribution"]] == [0, 1]
    assert _bucket(special["distribution"], 1)["count"] == 1
    assert special["common"][0]["pattern"] == "1升0平0降"
    assert 16 not in [int(item) for item in body["latest_draw"]["main"]]


def test_short_row_is_skipped_and_first_period_has_no_previous(db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["08"])
    alone = shengping_summary(db, "ssq")
    assert alone["sample_size"] == 0
    assert alone["distribution"] == []
    assert alone["common"] == []
    assert alone["mean"] is None
    assert alone["pulse"] is None
    assert alone["drift"] is None
    assert alone["latest_draw"]["issue"] == "2026001"
    assert alone["latest_draw"]["rise_count"] is None
    assert alone["latest_draw"]["pattern"] is None
    assert alone["latest_draw"]["special_rise_count"] is None
    assert alone["special"] is None

    _draw(db, "ssq", "2026002", ["11", "12", "13", "14", "15"], ["09"])
    _draw(db, "ssq", "2026003", ["21", "22", "23", "24", "25", "26"], ["10"])
    skipped = shengping_summary(db, "ssq")
    assert skipped["sample_size"] == 0
    assert skipped["latest_draw"]["issue"] == "2026003"
    assert skipped["latest_draw"]["rise_count"] is None
    assert skipped["latest_draw"]["pattern"] is None
    assert skipped["special"]["sample_size"] == 2
    assert skipped["latest_draw"]["special_pattern"] == "1升0平0降"
    assert skipped["special"]["mean"] == 1.0


def test_shengping_is_not_neighbor_repeat_daxiao_or_zone(db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["08"])
    _draw(db, "ssq", "2026002", ["02", "03", "04", "05", "06", "07"], ["09"])
    body = shengping_summary(db, "ssq")
    assert body["latest_draw"]["pattern"] == "6升0平0降"
    assert "big_count" not in body
    assert "pulled_count" not in body
    assert "overlap" not in body
    assert "zone_counts" not in body
    assert "imbalance" not in body
    neighbor = neighbor_summary(db, "ssq")
    repeat = repeat_pulse(db, "ssq")
    daxiao = daxiao_summary(db, "ssq")
    zone = zone_summary(db, "ssq")
    assert "rise_count" not in neighbor
    assert "rise_count" not in repeat
    assert "rise_count" not in daxiao
    assert "pattern" not in daxiao
    assert "rise_count" not in zone


def test_pulse_rises_when_recent_rise_counts_are_higher(db):
    series = [
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["07", "08", "09", "10", "11", "12"],
        ["13", "14", "15", "16", "17", "18"],
        ["19", "20", "21", "22", "23", "24"],
        ["25", "26", "27", "28", "29", "30"],
        ["27", "28", "29", "30", "31", "32"],
    ]
    for index, balls in enumerate(series, start=1):
        _draw(db, "ssq", f"2026{index:03d}", balls, ["08"])

    body = shengping_summary(db, "ssq", short=5, long=10)
    assert body["sample_size"] == 10
    assert body["short_avg"] == 6.0
    assert body["long_avg"] == 3.0
    assert body["pulse"] == 3.0
    assert body["drift"] == "rising"
    assert body["mean"] == 3.0
    assert body["median"] == 3.0
    assert [item["rise_count"] for item in body["distribution"]] == list(range(7))
    assert _bucket(body["distribution"], 0)["count"] == 5
    assert _bucket(body["distribution"], 6)["count"] == 5
    assert body["common"][0]["pattern"] == "0升6平0降"
    assert body["common"][1]["pattern"] == "6升0平0降"
    assert body["latest_draw"]["pattern"] == "6升0平0降"
    assert body["special"]["drift"] == "flat"
    assert body["special"]["pulse"] == 0.0
    assert body["special"]["common"][0]["pattern"] == "0升1平0降"


def test_pulse_threshold_edges(db):
    flat_series = [
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "07", "08"],
        ["01", "02", "03", "04", "09", "10"],
        ["01", "02", "03", "04", "11", "12"],
        ["01", "02", "03", "04", "13", "14"],
        ["01", "02", "03", "04", "15", "16"],
    ]
    for index, balls in enumerate(flat_series, start=1):
        _draw(db, "ssq", f"2026{index:03d}", balls, ["08"])
    flat = shengping_summary(db, "ssq", short=5, long=20)
    assert flat["sample_size"] == 6
    assert flat["short_avg"] == 2.0
    assert flat["long_avg"] == pytest.approx(1.6667)
    assert flat["pulse"] == pytest.approx(0.3333)
    assert flat["drift"] == "flat"

    rising_series = [
        ["01", "02", "03", "04", "05"],
        ["01", "02", "03", "04", "05"],
        ["01", "02", "06", "07", "08"],
        ["01", "02", "09", "10", "11"],
        ["01", "02", "12", "13", "14"],
        ["01", "02", "15", "16", "17"],
        ["01", "02", "18", "19", "20"],
    ]
    for index, balls in enumerate(rising_series, start=1):
        _draw(db, "dlt", f"2026{index:03d}", balls, ["01", "02"])
    rising = shengping_summary(db, "dlt", short=5, long=20)
    assert rising["basis"] == "main"
    assert rising["short_avg"] == 3.0
    assert rising["long_avg"] == 2.5
    assert rising["pulse"] == 0.5
    assert rising["drift"] == "rising"
    assert rising["special"]["drift"] == "flat"

    falling_series = [
        ["1", "1", "1"],
        ["4", "4", "4"],
        ["4", "4", "4"],
        ["4", "4", "4"],
        ["4", "4", "4"],
        ["4", "4", "4"],
        ["4", "4", "4"],
    ]
    for index, balls in enumerate(falling_series, start=1):
        _draw(db, "fc3d", f"2026{index:03d}", balls)
    falling = shengping_summary(db, "fc3d", short=5, long=20)
    assert falling["basis"] == "digits"
    assert falling["short_avg"] == 0.0
    assert falling["long_avg"] == 0.5
    assert falling["pulse"] == -0.5
    assert falling["drift"] == "falling"
    assert falling["special"] is None


def test_dlt_special_sorted_and_qlc_single_ball(db):
    _draw(db, "dlt", "2026001", ["01", "02", "03", "04", "05"], ["07", "01"])
    _draw(db, "dlt", "2026002", ["01", "02", "03", "04", "05"], ["08", "02"], draw_date="2026-02-02")
    body = shengping_summary(db, "dlt", short=5, long=20)
    assert body["latest_draw"]["pattern"] == "0升5平0降"
    assert body["latest_draw"]["special"] == ["08", "02"]
    assert body["latest_draw"]["special_pattern"] == "2升0平0降"
    assert body["latest_draw"]["special_rise_count"] == 2
    assert 8 not in [int(item) for item in body["latest_draw"]["main"]]
    assert body["special"]["label"] == "后区"
    assert [item["rise_count"] for item in body["special"]["distribution"]] == [0, 1, 2]
    assert body["special"]["common"][0]["pattern"] == "2升0平0降"

    _draw(db, "qlc", "2026001", ["01", "02", "03", "04", "05", "06", "07"], ["09"])
    _draw(db, "qlc", "2026002", ["02", "03", "04", "05", "06", "07", "08"], ["04"])
    single = shengping_summary(db, "qlc")
    assert single["latest_draw"]["rise_count"] == 7
    assert single["latest_draw"]["flat_count"] == 0
    assert single["latest_draw"]["fall_count"] == 0
    assert single["latest_draw"]["pattern"] == "7升0平0降"
    assert single["special"]["label"] == "特别号"
    assert single["latest_draw"]["special_pattern"] == "0升0平1降"
    assert single["special"]["sample_size"] == 1


def test_digit_keeps_repeats_and_qxc_special_is_positional(db):
    _draw(db, "fc3d", "2026001", ["5", "5", "5"])
    _draw(db, "fc3d", "2026002", ["5", "4", "6"], draw_date="2026-03-02")
    body = shengping_summary(db, "fc3d")
    assert body["sample_size"] == 1
    assert body["latest_draw"]["main"] == ["5", "4", "6"]
    assert body["latest_draw"]["pattern"] == "1升1平1降"
    assert body["special"] is None
    assert [item["rise_count"] for item in body["distribution"]] == [0, 1, 2, 3]

    _draw(db, "qxc", "2026001", ["1", "2", "3", "4", "9", "5"], ["3"])
    _draw(db, "qxc", "2026002", ["1", "2", "3", "4", "5", "9"], ["5"])
    qxc = shengping_summary(db, "qxc")
    assert qxc["basis"] == "digits"
    assert qxc["latest_draw"]["pattern"] == "1升4平1降"
    assert qxc["latest_draw"]["rise_count"] == 1
    assert qxc["latest_draw"]["special"] == ["5"]
    assert qxc["latest_draw"]["special_pattern"] == "1升0平0降"
    assert qxc["special"]["sample_size"] == 1
    assert qxc["special"]["mean"] == 1.0

    _draw(db, "pl5", "2026001", ["1", "2", "3", "4", "5"])
    _draw(db, "pl5", "2026002", ["1", "2", "3", "4", "4"])
    pl5 = shengping_summary(db, "pl5")
    assert pl5["special"] is None
    assert pl5["latest_draw"]["pattern"] == "0升4平1降"
    assert pl5["latest_draw"]["special_rise_count"] is None


def test_blank_main_does_not_consume_the_analysis_window(db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"])
    _draw(db, "ssq", "2026002", ["02", "03", "04", "05", "06", "07"])
    _draw(db, "ssq", "2026003", ["03", "04", "05", "06", "07", "08"])
    _draw(db, "ssq", "2026004", ["04", "05", "06", "07", "08", "09"])
    _draw(db, "ssq", "2026005", [])
    _draw(db, "ssq", "2026006", ["06", "07", "08", "09", "10", "11"])

    body = shengping_summary(db, "ssq", limit=5, short=5, long=20)
    assert body["sample_size"] == 3
    assert body["latest_draw"]["issue"] == "2026006"
    assert body["latest_draw"]["pattern"] == "6升0平0降"
    assert body["latest_draw"]["issue"] != "2026001"


def test_score_aligns_with_pulse_and_marks_rarity(db):
    series = [
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["07", "08", "09", "10", "11", "12"],
        ["13", "14", "15", "16", "17", "18"],
        ["19", "20", "21", "22", "23", "24"],
        ["25", "26", "27", "28", "29", "30"],
        ["27", "28", "29", "30", "31", "32"],
    ]
    for index, balls in enumerate(series, start=1):
        _draw(db, "ssq", f"2026{index:03d}", balls, ["08"])

    wide = score_shengping(
        db,
        "ssq",
        ["28", "29", "30", "31", "32", "33"],
        ["09"],
        short=5,
        long=10,
    )
    assert set(wide) == POST_KEYS
    assert wide["query"] == {
        "main": ["28", "29", "30", "31", "32", "33"],
        "special": ["09"],
    }
    assert set(wide["ticket"]) == TICKET_KEYS
    assert wide["ticket"]["rise_count"] == 6
    assert wide["ticket"]["flat_count"] == 0
    assert wide["ticket"]["fall_count"] == 0
    assert wide["ticket"]["pattern"] == "6升0平0降"
    assert wide["ticket"]["percentile"] == 1.0
    assert wide["ticket"]["typicality"] == 0.5
    assert wide["ticket"]["rarity"] == "common"
    assert wide["ticket"]["alignment"] == "aligned"
    assert wide["ticket"]["note"] == (
        "升的个数 6（6升0平0降），历史分位 100%，出现率 50%，常见，"
        "短窗 6 比长窗 3 走高，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert wide["special_ticket"]["rise_count"] == 1
    assert wide["special_ticket"]["pattern"] == "1升0平0降"
    assert wide["special_ticket"]["percentile"] == 1.0
    assert wide["special_ticket"]["typicality"] == 0.0
    assert wide["special_ticket"]["rarity"] == "rare"
    assert wide["special_ticket"]["alignment"] == "neutral"
    assert wide["special_ticket"]["note"] == (
        "升的个数 1（1升0平0降），历史分位 100%，出现率 0%，少见，"
        "短窗 0 和长窗 0 差不多，没有明显顺逆。仅供娱乐，不构成投注建议。"
    )
    assert wide["drift"] == "rising"

    narrow = score_shengping(db, "ssq", "01 02 03 04 05 06", special="16", short=5, long=10)
    assert narrow["ticket"]["rise_count"] == 0
    assert narrow["ticket"]["pattern"] == "0升0平6降"
    assert narrow["ticket"]["percentile"] == 0.5
    assert narrow["ticket"]["typicality"] == 0.5
    assert narrow["ticket"]["rarity"] == "common"
    assert narrow["ticket"]["alignment"] == "against"
    assert narrow["ticket"]["note"] == (
        "升的个数 0（0升0平6降），历史分位 50%，出现率 50%，常见，"
        "短窗 6 比长窗 3 走高，和短窗脉动反向。仅供娱乐，不构成投注建议。"
    )

    rare = score_shengping(
        db,
        "ssq",
        ["20", "21", "22", "30", "31", "33"],
        ["08"],
        short=5,
        long=10,
    )
    assert rare["ticket"]["pattern"] == "1升2平3降"
    assert rare["ticket"]["rise_count"] == 1
    assert rare["ticket"]["percentile"] == 0.5
    assert rare["ticket"]["typicality"] == 0.0
    assert rare["ticket"]["rarity"] == "rare"
    assert rare["ticket"]["alignment"] == "against"
    assert "少见" in rare["ticket"]["note"]
    assert rare["special_ticket"]["pattern"] == "0升1平0降"
    assert rare["special_ticket"]["rarity"] == "common"
    assert rare["special_ticket"]["alignment"] == "neutral"

    dlt_series = [
        (["01", "02", "03", "04", "05"], ["01", "02"]),
        (["06", "07", "08", "09", "10"], ["03", "04"]),
        (["11", "12", "13", "14", "15"], ["05", "06"]),
        (["16", "17", "18", "19", "20"], ["07", "08"]),
        (["21", "22", "23", "24", "25"], ["09", "10"]),
        (["26", "27", "28", "29", "30"], ["11", "12"]),
        (["26", "27", "28", "29", "30"], ["11", "12"]),
        (["26", "27", "28", "29", "30"], ["11", "12"]),
        (["26", "27", "28", "29", "30"], ["11", "12"]),
        (["26", "27", "28", "29", "30"], ["11", "12"]),
        (["26", "27", "28", "29", "30"], ["11", "12"]),
    ]
    for index, (main, special) in enumerate(dlt_series, start=1):
        _draw(db, "dlt", f"2027{index:03d}", main, special)

    tight = score_shengping(db, "dlt", ["01", "02", "03", "04", "05"], ["01", "02"], short=5, long=10)
    assert tight["drift"] == "falling"
    assert tight["short_avg"] == 0.0
    assert tight["long_avg"] == 2.5
    assert tight["ticket"]["rise_count"] == 0
    assert tight["ticket"]["pattern"] == "0升0平5降"
    assert tight["ticket"]["alignment"] == "aligned"
    assert tight["ticket"]["note"] == (
        "升的个数 0（0升0平5降），历史分位 50%，出现率 50%，常见，"
        "短窗 0 比长窗 2.5 走低，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert tight["special"]["drift"] == "falling"
    assert tight["special_ticket"]["rise_count"] == 0
    assert tight["special_ticket"]["pattern"] == "0升0平2降"
    assert tight["special_ticket"]["alignment"] == "aligned"
    assert "不构成投注建议" in tight["special_ticket"]["note"]
    assert tight["query"]["main"] == ["01", "02", "03", "04", "05"]
    assert 11 not in [int(item) for item in tight["query"]["main"]]


def test_digit_score_keeps_position_and_empty_history(db):
    _draw(db, "fc3d", "2026001", ["1", "3", "2"])
    _draw(db, "fc3d", "2026002", ["3", "1", "2"])
    body = score_shengping(db, "fc3d", ["3", "1", "2"])
    assert body["basis"] == "digits"
    assert body["ticket"]["pattern"] == "0升3平0降"
    assert body["ticket"]["rise_count"] == 0
    assert body["ticket"]["percentile"] == 0.0
    assert body["ticket"]["typicality"] == 0.0
    assert body["ticket"]["rarity"] == "rare"
    assert body["ticket"]["alignment"] == "neutral"
    assert body["ticket"]["note"] == (
        "升的个数 0（0升3平0降），历史分位 0%，出现率 0%，少见，"
        "短窗 1 和长窗 1 差不多，没有明显顺逆。仅供娱乐，不构成投注建议。"
    )
    assert body["special_ticket"] == _empty_ticket()

    repeated = score_shengping(db, "fc3d", ["9", "0", "2"])
    assert repeated["ticket"]["pattern"] == "1升1平1降"
    assert repeated["ticket"]["rise_count"] == 1
    assert repeated["ticket"]["rarity"] == "common"

    _draw(db, "pl3", "2026101", ["1", "1", "1"])
    low = score_shengping(db, "pl3", [2, 2, 2])
    assert low["sample_size"] == 0
    assert low["ticket"]["rise_count"] == 3
    assert low["ticket"]["pattern"] == "3升0平0降"
    assert low["ticket"]["percentile"] is None
    assert low["ticket"]["rarity"] is None
    assert low["ticket"]["alignment"] is None
    assert low["ticket"]["note"] == "升的个数 3（3升0平0降），还没有历史可对照。仅供娱乐，不构成投注建议。"

    _draw(db, "qxc", "2026101", ["1", "2", "3", "4", "5", "6"], ["4"])
    high = score_shengping(db, "qxc", ["1", "2", "3", "4", "5", "7"], ["3"])
    assert high["ticket"]["pattern"] == "1升5平0降"
    assert high["special_ticket"]["pattern"] == "0升0平1降"
    assert high["special_ticket"]["note"] == "升的个数 0（0升0平1降），还没有历史可对照。仅供娱乐，不构成投注建议。"


def test_empty_history_parameter_clamp_and_common_cap(db):
    empty = shengping_summary(db, "kl8", limit="no", short=None, long="bad")
    assert empty["lottery_type"] == "kl8"
    assert empty["sample_size"] == 0
    assert empty["short"] == 10
    assert empty["long"] == 50
    assert empty["distribution"] == []
    assert empty["common"] == []
    assert empty["mean"] is None
    assert empty["latest_draw"] is None
    assert empty["special"] is None
    assert empty["data_status"] == "seed"
    assert empty["basis"] == "main"
    assert "升序" in empty["note"]

    scored = score_shengping(db, "kl8", ["01"])
    assert scored["ticket"] == _empty_ticket()
    assert scored["special_ticket"] == _empty_ticket()

    clamped = shengping_summary(db, "kl8", limit=1, short=1, long=1)
    assert clamped["short"] == 5
    assert clamped["long"] == 20

    opened = shengping_summary(db, "kl8", short=30, long=20)
    assert opened["short"] == 30
    assert opened["long"] == 31

    states = [
        ["5", "5", "5"],
        ["4", "4", "4"],
        ["3", "3", "4"],
        ["2", "2", "5"],
        ["1", "2", "5"],
        ["0", "2", "6"],
        ["0", "2", "7"],
        ["0", "3", "8"],
        ["1", "4", "7"],
        ["2", "5", "8"],
    ]
    for index, balls in enumerate(states, start=1):
        _draw(db, "fc3d", f"2028{index:03d}", balls)
    capped = shengping_summary(db, "fc3d")
    assert capped["sample_size"] == 9
    assert len(capped["common"]) == 8
    assert [item["pattern"] for item in capped["common"]] == [
        "0升0平3降",
        "0升1平2降",
        "0升2平1降",
        "1升0平2降",
        "1升1平1降",
        "1升2平0降",
        "2升0平1降",
        "2升1平0降",
    ]
    assert all(item["count"] == 1 and item["rate"] == pytest.approx(0.1111) for item in capped["common"])
    assert "3升0平0降" not in [item["pattern"] for item in capped["common"]]
    assert _bucket(capped["distribution"], 0)["count"] == 3
    assert _bucket(capped["distribution"], 3)["count"] == 1

    with pytest.raises(ValueError, match="未知彩种"):
        shengping_summary(db, "nope")
    with pytest.raises(ValueError, match="未知彩种"):
        score_shengping(db, "nope", ["01"])
    with pytest.raises(ValueError):
        score_shengping(db, "ssq", ["01", "01", "03", "04", "05", "06"], ["01"])
    with pytest.raises(ValueError):
        score_shengping(db, "fc3d", ["1", "2"])
    with pytest.raises(ValueError):
        score_shengping(db, "kl8", ["01", "02"], ["03"])


def test_ensemble_includes_shengping_at_equal_weight(db):
    _draw(db, "ssq", "2026001", ["01", "08", "18", "19", "20", "33"], ["09"])
    _draw(db, "ssq", "2026002", ["02", "09", "18", "19", "21", "32"], ["10"])
    scored = score_ticket(db, "ssq", ["03", "08", "14", "19", "25", "31"], ["09"])
    assert [item["module"] for item in scored["breakdown"]][-1] == "shengping"
    row = next(item for item in scored["breakdown"] if item["module"] == "shengping")
    assert row["label"] == "升平降"
    assert row["weight"] == 1.0
    assert row["score"] is not None
    assert "升" in row["note"]
    assert {item["weight"] for item in scored["breakdown"]} == {1.0}


def test_shengping_endpoints_bounds_and_old_contracts(client, db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["08"], draw_date="2026-04-01")
    _draw(
        db,
        "ssq",
        "2026002",
        ["02", "03", "04", "05", "06", "07"],
        ["09"],
        source="crawl",
        draw_date="2026-04-03",
    )

    res = client.get("/api/analysis/ssq/shengping")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == GET_KEYS
    assert body["sample_size"] == 1
    assert body["short"] == 10
    assert body["long"] == 50
    assert body["basis"] == "main"
    assert body["disclaimer"] == DISCLAIMER
    assert "仅供娱乐" in body["disclaimer"]
    assert body["data_status"] == "mixed"
    assert body["latest_draw"]["pattern"] == "6升0平0降"
    assert body["latest_draw"]["special_pattern"] == "1升0平0降"
    assert body["mean"] == 6
    assert body["pulse"] == 0.0
    assert body["drift"] == "flat"
    assert body["special"]["sample_size"] == 1
    assert "big_count" not in body
    assert "odd_count" not in body
    assert [item["rise_count"] for item in body["distribution"]] == list(range(7))

    custom = client.get("/api/analysis/ssq/shengping", params={"limit": 80, "short": 5, "long": 20})
    assert custom.status_code == 200
    assert custom.json()["short"] == 5
    assert custom.json()["long"] == 20

    widened = client.get("/api/analysis/ssq/shengping", params={"short": 30, "long": 20})
    assert widened.status_code == 200
    assert widened.json()["short"] == 30
    assert widened.json()["long"] == 31

    assert client.get("/api/analysis/ssq/shengping", params={"limit": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/shengping", params={"limit": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/shengping", params={"short": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/shengping", params={"short": 31}).status_code == 422
    assert client.get("/api/analysis/ssq/shengping", params={"long": 19}).status_code == 422
    assert client.get("/api/analysis/ssq/shengping", params={"long": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/shengping", params={"limit": 5, "short": 5, "long": 20}).status_code == 200
    assert client.get("/api/analysis/ssq/shengping", params={"limit": 200, "short": 30, "long": 200}).status_code == 200

    unknown = client.get("/api/analysis/nope/shengping")
    assert unknown.status_code == 400
    assert "未知彩种" in unknown.json()["detail"]

    empty = client.get("/api/analysis/kl8/shengping")
    assert empty.status_code == 200
    assert empty.json()["sample_size"] == 0
    assert empty.json()["latest_draw"] is None
    assert empty.json()["distribution"] == []
    assert empty.json()["drift"] is None

    alias = client.get("/api/analysis/3d/shengping")
    assert alias.status_code == 200
    assert alias.json()["lottery_type"] == "fc3d"
    assert alias.json()["mode"] == "digit"
    assert alias.json()["basis"] == "digits"

    posted = client.post(
        "/api/analysis/ssq/shengping/score",
        json={"main": "02 03 04 05 06 07", "special": "09", "limit": 80, "short": 10, "long": 50},
    )
    assert posted.status_code == 200, posted.text
    scored = posted.json()
    assert set(scored) == POST_KEYS
    assert scored["query"] == {"main": ["02", "03", "04", "05", "06", "07"], "special": ["09"]}
    assert scored["ticket"]["pattern"] == "0升6平0降"
    assert scored["ticket"]["rarity"] == "rare"
    assert scored["ticket"]["alignment"] == "neutral"
    assert scored["special_ticket"]["pattern"] == "0升1平0降"
    assert "仅供娱乐" in scored["ticket"]["note"]
    assert "升的个数 0" in scored["ticket"]["note"]

    spaced = client.post("/api/analysis/3d/shengping/score", json={"main": ["3", "1", "2"], "short": 5, "long": 20})
    assert spaced.status_code == 200
    assert spaced.json()["lottery_type"] == "fc3d"
    assert spaced.json()["mode"] == "digit"

    bad = client.post("/api/analysis/ssq/shengping/score", json={"main": ["99"], "special": ["01"]})
    assert bad.status_code == 400
    duplicate = client.post(
        "/api/analysis/ssq/shengping/score",
        json={"main": ["01", "01", "03", "04", "05", "06"], "special": ["01"]},
    )
    assert duplicate.status_code == 400
    short = client.post("/api/analysis/fc3d/shengping/score", json={"main": ["1", "2"]})
    assert short.status_code == 400
    extra = client.post("/api/analysis/kl8/shengping/score", json={"main": ["01", "02"], "special": ["03"]})
    assert extra.status_code == 400
    unknown_post = client.post("/api/analysis/nope/shengping/score", json={"main": ["01"]})
    assert unknown_post.status_code == 400
    assert client.post("/api/analysis/ssq/shengping/score", json={"main": ["01"], "limit": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/shengping/score", json={"main": ["01"], "short": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/shengping/score", json={"main": ["01"], "long": 201}).status_code == 422

    analysis = client.get("/api/analysis/ssq")
    assert analysis.status_code == 200
    assert "shengping" not in analysis.json()
    assert "rise_count" not in analysis.json()

    pulse = client.post("/api/predict", json={"lottery_type": "ssq", "strategy": "pulse", "count": 1})
    assert pulse.status_code == 200
    modules = pulse.json()["modules"]
    assert "shengping" in modules
    assert modules[-1] == "shengping"
    breakdown = pulse.json()["recommendations"][0]["breakdown"]
    assert any(item["module"] == "shengping" and item["weight"] == 1.0 for item in breakdown)

    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    weights = spec.json()["components"]["schemas"]["PredictIn"]["properties"]["weights"]["description"]
    assert "shengping" in weights
    assert "daxiao" in weights
    paths = spec.json()["paths"]
    assert "/api/analysis/{lottery_type}/shengping" in paths
    assert "/api/analysis/{lottery_type}/shengping/score" in paths
    assert "ShengpingOut" in spec.json()["components"]["schemas"]
    assert "ShengpingScoreOut" in spec.json()["components"]["schemas"]
