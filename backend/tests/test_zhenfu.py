"""振幅脉动：相邻两期同位绝对差之和，看短窗相对长窗是走高还是走低。

乐透主号去重升序，按该彩种标准个数对齐；任一侧不足则跳过该期。
数字彩按位比较，保留重复和位置，不排序。0 与最大号不绕圈。
特别号不并进主号。乐透特别号升序对齐；没有特别号的数字彩不做 special。
空白主号跳过，不占窗口名额。最早一期没有上期，不能计算。
这不是升平降的升的个数，也不是同期跨度，也不是邻号±1，也不是重号个数。
只读本地开奖，不改其他分析接口的返回形状。
"""
from __future__ import annotations

import json

import pytest

from app.models import Draw
from app.services.neighbor import neighbor_summary
from app.services.pulse_ensemble import PULSE_MODULES, _MEMO_TARGETS, score_ticket
from app.services.repeat import repeat_pulse
from app.services.shengping import shengping_summary
from app.services.span import span_summary
from app.services.zhenfu import (
    COMMON_LIMIT,
    DIGIT_NOTE,
    DISCLAIMER,
    SET_NOTE,
    THRESHOLD,
    score_zhenfu,
    zhenfu_summary,
)
import app.services.zhenfu as zhenfu_module

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

BUCKET_KEYS = {"amplitude_sum", "count", "rate"}
COMMON_KEYS = {"amplitude_sum", "count", "rate"}
TICKET_KEYS = {
    "amplitude_sum",
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
    "amplitude_sum",
    "special_amplitude_sum",
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


def _bucket(rows, amplitude_sum):
    found = [item for item in rows if item["amplitude_sum"] == amplitude_sum]
    assert len(found) == 1
    return found[0]


def _empty_ticket():
    return {
        "amplitude_sum": None,
        "percentile": None,
        "typicality": None,
        "rarity": None,
        "alignment": None,
        "note": "",
    }


def test_zhenfu_constants_and_equal_weight_registry():
    assert THRESHOLD == 0.5
    assert COMMON_LIMIT == 8
    assert "仅供娱乐" in DISCLAIMER
    assert "不构成投注建议" in DISCLAIMER
    assert "振幅" in DISCLAIMER
    assert "按位" in DIGIT_NOTE and "不排序" in DIGIT_NOTE
    assert "升序" in SET_NOTE
    text = zhenfu_module.__doc__ or ""
    for word in ("升平降", "跨度", "邻号", "重号", "不绕圈"):
        assert word in text
        assert word in DIGIT_NOTE
        assert word in SET_NOTE
    keys = [item.key for item in PULSE_MODULES]
    assert keys[-3] == "zhenfu"
    assert keys[-4] == "shengping"
    assert [item.label for item in PULSE_MODULES if item.key == "zhenfu"] == ["振幅"]
    assert ("app.services.zhenfu", "zhenfu_summary") in _MEMO_TARGETS
    assert len(keys) == len(set(keys))


def test_set_sorts_before_compare_and_digit_keeps_position(db):
    _draw(db, "ssq", "2026001", ["06", "05", "04", "03", "02", "01"], ["01"])
    _draw(db, "ssq", "2026002", ["07", "01", "02", "03", "04", "05"], ["02"])
    body = zhenfu_summary(db, "ssq", limit=5)
    assert body["mode"] == "set"
    assert body["basis"] == "main"
    assert body["sample_size"] == 1
    assert body["latest_draw"]["main"] == ["07", "01", "02", "03", "04", "05"]
    assert body["latest_draw"]["amplitude_sum"] == 1
    assert body["latest_draw"]["special_amplitude_sum"] == 1
    assert "升平降" in body["note"] and "跨度" in body["note"]
    assert body["special"]["label"] == "蓝球"
    assert body["special"]["sample_size"] == 1
    assert body["special"]["mean"] == 1

    _draw(db, "fc3d", "2026201", ["1", "3", "2"])
    _draw(db, "fc3d", "2026202", ["3", "1", "2"])
    digit = zhenfu_summary(db, "fc3d", limit=5)
    assert digit["mode"] == "digit"
    assert digit["basis"] == "digits"
    assert digit["note"] == DIGIT_NOTE
    assert digit["latest_draw"]["main"] == ["3", "1", "2"]
    assert digit["latest_draw"]["amplitude_sum"] == 4
    assert digit["special"] is None
    assert digit["latest_draw"]["special_amplitude_sum"] is None


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

    body = zhenfu_summary(db, "ssq", limit=80, short=10, long=50)
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
    assert body["latest_draw"]["amplitude_sum"] == 0
    assert body["latest_draw"]["special"] == ["16"]
    assert body["latest_draw"]["special_amplitude_sum"] == 8
    assert [item["amplitude_sum"] for item in body["distribution"]] == [0]
    assert all(set(item) == BUCKET_KEYS for item in body["distribution"])
    assert _bucket(body["distribution"], 0) == {"amplitude_sum": 0, "count": 1, "rate": 1.0}
    assert body["common"] == [{"amplitude_sum": 0, "count": 1, "rate": 1.0}]
    assert all(set(item) == COMMON_KEYS for item in body["common"])

    special = body["special"]
    assert set(special) == SPECIAL_KEYS
    assert special["label"] == "蓝球"
    assert special["sample_size"] == 1
    assert [item["amplitude_sum"] for item in special["distribution"]] == [8]
    assert _bucket(special["distribution"], 8)["count"] == 1
    assert special["common"][0]["amplitude_sum"] == 8
    assert 16 not in [int(item) for item in body["latest_draw"]["main"]]
    assert 33 in [int(item) for item in body["latest_draw"]["main"]]


def test_short_row_is_skipped_and_first_period_has_no_previous(db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["08"])
    alone = zhenfu_summary(db, "ssq")
    assert alone["sample_size"] == 0
    assert alone["distribution"] == []
    assert alone["common"] == []
    assert alone["mean"] is None
    assert alone["pulse"] is None
    assert alone["drift"] is None
    assert alone["latest_draw"]["issue"] == "2026001"
    assert alone["latest_draw"]["amplitude_sum"] is None
    assert alone["latest_draw"]["special_amplitude_sum"] is None
    assert alone["special"] is None

    _draw(db, "ssq", "2026002", ["11", "12", "13", "14", "15"], ["09"])
    _draw(db, "ssq", "2026003", ["21", "22", "23", "24", "25", "26"], ["10"])
    skipped = zhenfu_summary(db, "ssq")
    assert skipped["sample_size"] == 0
    assert skipped["latest_draw"]["issue"] == "2026003"
    assert skipped["latest_draw"]["amplitude_sum"] is None
    assert skipped["special"]["sample_size"] == 2
    assert skipped["latest_draw"]["special_amplitude_sum"] == 1
    assert skipped["special"]["mean"] == 1.0


def test_zhenfu_is_not_shengping_span_neighbor_or_repeat(db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["16"])
    _draw(db, "ssq", "2026002", ["03", "04", "05", "06", "07", "20"], ["01"])
    body = zhenfu_summary(db, "ssq")
    assert body["latest_draw"]["amplitude_sum"] == 24
    assert body["latest_draw"]["special_amplitude_sum"] == 15
    assert "rise_count" not in body
    assert "pattern" not in body
    assert "span" not in body
    assert "pulled_count" not in body
    assert "overlap" not in body
    shengping = shengping_summary(db, "ssq")
    span = span_summary(db, "ssq")
    neighbor = neighbor_summary(db, "ssq")
    repeat = repeat_pulse(db, "ssq")
    assert shengping["latest_draw"]["rise_count"] == 6
    assert span["latest_draw"]["span"] == 17
    assert "amplitude_sum" not in shengping
    assert "amplitude_sum" not in span
    assert "amplitude_sum" not in neighbor
    assert "amplitude_sum" not in repeat


def test_zero_and_max_do_not_wrap(db):
    _draw(db, "fc3d", "2026001", ["0", "0", "0"])
    _draw(db, "fc3d", "2026002", ["9", "9", "9"])
    digit = zhenfu_summary(db, "fc3d")
    assert digit["latest_draw"]["amplitude_sum"] == 27

    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["01"])
    _draw(db, "ssq", "2026002", ["28", "29", "30", "31", "32", "33"], ["16"])
    body = zhenfu_summary(db, "ssq")
    assert body["latest_draw"]["amplitude_sum"] == 162
    assert body["latest_draw"]["special_amplitude_sum"] == 15


def test_pulse_rises_when_recent_amplitudes_are_higher(db):
    series = [
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["03", "04", "05", "06", "07", "08"],
        ["05", "06", "07", "08", "09", "10"],
        ["07", "08", "09", "10", "11", "12"],
        ["09", "10", "11", "12", "13", "14"],
        ["11", "12", "13", "14", "15", "16"],
    ]
    for index, balls in enumerate(series, start=1):
        _draw(db, "ssq", f"2026{index:03d}", balls, ["08"])

    body = zhenfu_summary(db, "ssq", short=5, long=10)
    assert body["sample_size"] == 10
    assert body["short_avg"] == 12.0
    assert body["long_avg"] == 6.0
    assert body["pulse"] == 6.0
    assert body["drift"] == "rising"
    assert body["mean"] == 6.0
    assert body["median"] == 6.0
    assert [item["amplitude_sum"] for item in body["distribution"]] == list(range(0, 13))
    assert _bucket(body["distribution"], 0)["count"] == 5
    assert _bucket(body["distribution"], 12)["count"] == 5
    assert _bucket(body["distribution"], 1)["count"] == 0
    assert body["common"][0]["amplitude_sum"] == 0
    assert body["common"][1]["amplitude_sum"] == 12
    assert body["latest_draw"]["amplitude_sum"] == 12
    assert body["special"]["drift"] == "flat"
    assert body["special"]["pulse"] == 0.0
    assert body["special"]["common"][0]["amplitude_sum"] == 0


def test_pulse_threshold_edges(db):
    flat_series = [
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "08"],
        ["01", "02", "03", "04", "05", "10"],
        ["01", "02", "03", "04", "05", "12"],
        ["01", "02", "03", "04", "05", "14"],
        ["01", "02", "03", "04", "05", "16"],
    ]
    for index, balls in enumerate(flat_series, start=1):
        _draw(db, "ssq", f"2026{index:03d}", balls, ["08"])
    flat = zhenfu_summary(db, "ssq", short=5, long=20)
    assert flat["sample_size"] == 6
    assert flat["short_avg"] == 2.0
    assert flat["long_avg"] == pytest.approx(1.6667)
    assert flat["pulse"] == pytest.approx(0.3333)
    assert flat["drift"] == "flat"

    rising_series = [
        ["01", "02", "03", "04", "05"],
        ["01", "02", "03", "04", "05"],
        ["01", "02", "03", "04", "08"],
        ["01", "02", "03", "04", "11"],
        ["01", "02", "03", "04", "14"],
        ["01", "02", "03", "04", "17"],
        ["01", "02", "03", "04", "20"],
    ]
    for index, balls in enumerate(rising_series, start=1):
        _draw(db, "dlt", f"2026{index:03d}", balls, ["01", "02"])
    rising = zhenfu_summary(db, "dlt", short=5, long=20)
    assert rising["basis"] == "main"
    assert rising["short_avg"] == 3.0
    assert rising["long_avg"] == 2.5
    assert rising["pulse"] == 0.5
    assert rising["drift"] == "rising"
    assert rising["special"]["drift"] == "flat"

    falling_series = [
        ["1", "1", "1"],
        ["2", "2", "2"],
        ["2", "2", "2"],
        ["2", "2", "2"],
        ["2", "2", "2"],
        ["2", "2", "2"],
        ["2", "2", "2"],
    ]
    for index, balls in enumerate(falling_series, start=1):
        _draw(db, "fc3d", f"2026{index:03d}", balls)
    falling = zhenfu_summary(db, "fc3d", short=5, long=20)
    assert falling["basis"] == "digits"
    assert falling["short_avg"] == 0.0
    assert falling["long_avg"] == 0.5
    assert falling["pulse"] == -0.5
    assert falling["drift"] == "falling"
    assert falling["special"] is None


def test_dlt_special_sorted_and_qlc_single_ball(db):
    _draw(db, "dlt", "2026001", ["01", "02", "03", "04", "05"], ["07", "01"])
    _draw(db, "dlt", "2026002", ["01", "02", "03", "04", "05"], ["02", "07"], draw_date="2026-02-02")
    body = zhenfu_summary(db, "dlt", short=5, long=20)
    assert body["latest_draw"]["amplitude_sum"] == 0
    assert body["latest_draw"]["special"] == ["02", "07"]
    assert body["latest_draw"]["special_amplitude_sum"] == 1
    assert 7 not in [int(item) for item in body["latest_draw"]["main"]]
    assert body["special"]["label"] == "后区"
    assert [item["amplitude_sum"] for item in body["special"]["distribution"]] == [1]
    assert body["special"]["common"][0]["amplitude_sum"] == 1

    _draw(db, "qlc", "2026001", ["01", "02", "03", "04", "05", "06", "07"], ["09"])
    _draw(db, "qlc", "2026002", ["02", "03", "04", "05", "06", "07", "08"], ["04"])
    single = zhenfu_summary(db, "qlc")
    assert single["latest_draw"]["amplitude_sum"] == 7
    assert single["special"]["label"] == "特别号"
    assert single["latest_draw"]["special_amplitude_sum"] == 5
    assert single["special"]["sample_size"] == 1


def test_digit_keeps_repeats_and_qxc_special_is_positional(db):
    _draw(db, "fc3d", "2026001", ["5", "5", "5"])
    _draw(db, "fc3d", "2026002", ["5", "4", "6"], draw_date="2026-03-02")
    body = zhenfu_summary(db, "fc3d")
    assert body["sample_size"] == 1
    assert body["latest_draw"]["main"] == ["5", "4", "6"]
    assert body["latest_draw"]["amplitude_sum"] == 2
    assert body["special"] is None
    assert [item["amplitude_sum"] for item in body["distribution"]] == [2]

    _draw(db, "qxc", "2026001", ["1", "2", "3", "4", "9", "5"], ["3"])
    _draw(db, "qxc", "2026002", ["1", "2", "3", "4", "5", "9"], ["5"])
    qxc = zhenfu_summary(db, "qxc")
    assert qxc["basis"] == "digits"
    assert qxc["latest_draw"]["amplitude_sum"] == 8
    assert qxc["latest_draw"]["special"] == ["5"]
    assert qxc["latest_draw"]["special_amplitude_sum"] == 2
    assert qxc["special"]["sample_size"] == 1
    assert qxc["special"]["mean"] == 2.0

    _draw(db, "pl5", "2026001", ["1", "2", "3", "4", "5"])
    _draw(db, "pl5", "2026002", ["1", "2", "3", "4", "4"])
    pl5 = zhenfu_summary(db, "pl5")
    assert pl5["special"] is None
    assert pl5["latest_draw"]["amplitude_sum"] == 1
    assert pl5["latest_draw"]["special_amplitude_sum"] is None


def test_blank_main_does_not_consume_the_analysis_window(db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"])
    _draw(db, "ssq", "2026002", ["02", "03", "04", "05", "06", "07"])
    _draw(db, "ssq", "2026003", ["03", "04", "05", "06", "07", "08"])
    _draw(db, "ssq", "2026004", ["04", "05", "06", "07", "08", "09"])
    _draw(db, "ssq", "2026005", [])
    _draw(db, "ssq", "2026006", ["06", "07", "08", "09", "10", "11"])

    body = zhenfu_summary(db, "ssq", limit=5, short=5, long=20)
    assert body["sample_size"] == 3
    assert body["latest_draw"]["issue"] == "2026006"
    assert body["latest_draw"]["amplitude_sum"] == 12
    assert body["latest_draw"]["issue"] != "2026001"


def test_score_aligns_with_pulse_and_marks_rarity(db):
    series = [
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "06"],
        ["03", "04", "05", "06", "07", "08"],
        ["05", "06", "07", "08", "09", "10"],
        ["07", "08", "09", "10", "11", "12"],
        ["09", "10", "11", "12", "13", "14"],
        ["11", "12", "13", "14", "15", "16"],
    ]
    for index, balls in enumerate(series, start=1):
        _draw(db, "ssq", f"2026{index:03d}", balls, ["08"])

    wide = score_zhenfu(
        db,
        "ssq",
        ["13", "14", "15", "16", "17", "18"],
        ["09"],
        short=5,
        long=10,
    )
    assert set(wide) == POST_KEYS
    assert wide["query"] == {
        "main": ["13", "14", "15", "16", "17", "18"],
        "special": ["09"],
    }
    assert set(wide["ticket"]) == TICKET_KEYS
    assert wide["ticket"]["amplitude_sum"] == 12
    assert wide["ticket"]["percentile"] == 1.0
    assert wide["ticket"]["typicality"] == 0.5
    assert wide["ticket"]["rarity"] == "common"
    assert wide["ticket"]["alignment"] == "aligned"
    assert wide["ticket"]["note"] == (
        "振幅 12，历史分位 100%，出现率 50%，常见，"
        "短窗 12 比长窗 6 走高，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert wide["special_ticket"]["amplitude_sum"] == 1
    assert wide["special_ticket"]["percentile"] == 1.0
    assert wide["special_ticket"]["typicality"] == 0.0
    assert wide["special_ticket"]["rarity"] == "rare"
    assert wide["special_ticket"]["alignment"] == "neutral"
    assert wide["special_ticket"]["note"] == (
        "振幅 1，历史分位 100%，出现率 0%，少见，"
        "短窗 0 和长窗 0 差不多，没有明显顺逆。仅供娱乐，不构成投注建议。"
    )
    assert wide["drift"] == "rising"

    same = score_zhenfu(db, "ssq", "11 12 13 14 15 16", special="16", short=5, long=10)
    assert same["ticket"]["amplitude_sum"] == 0
    assert same["ticket"]["percentile"] == 0.5
    assert same["ticket"]["typicality"] == 0.5
    assert same["ticket"]["rarity"] == "common"
    assert same["ticket"]["alignment"] == "against"
    assert same["ticket"]["note"] == (
        "振幅 0，历史分位 50%，出现率 50%，常见，"
        "短窗 12 比长窗 6 走高，和短窗脉动反向。仅供娱乐，不构成投注建议。"
    )
    assert same["special_ticket"]["amplitude_sum"] == 8
    assert same["special_ticket"]["rarity"] == "rare"
    assert same["special_ticket"]["alignment"] == "neutral"

    rare = score_zhenfu(
        db,
        "ssq",
        ["11", "12", "13", "14", "15", "22"],
        ["08"],
        short=5,
        long=10,
    )
    assert rare["ticket"]["amplitude_sum"] == 6
    assert rare["ticket"]["percentile"] == 0.5
    assert rare["ticket"]["typicality"] == 0.0
    assert rare["ticket"]["rarity"] == "rare"
    assert rare["ticket"]["alignment"] == "against"
    assert "少见" in rare["ticket"]["note"]
    assert rare["special_ticket"]["amplitude_sum"] == 0
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

    tight = score_zhenfu(db, "dlt", ["26", "27", "28", "29", "30"], ["11", "12"], short=5, long=10)
    assert tight["drift"] == "falling"
    assert tight["short_avg"] == 0.0
    assert tight["long_avg"] == 12.5
    assert tight["ticket"]["amplitude_sum"] == 0
    assert tight["ticket"]["alignment"] == "aligned"
    assert tight["ticket"]["note"] == (
        "振幅 0，历史分位 50%，出现率 50%，常见，"
        "短窗 0 比长窗 12.5 走低，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert tight["special"]["drift"] == "falling"
    assert tight["special_ticket"]["amplitude_sum"] == 0
    assert tight["special_ticket"]["alignment"] == "aligned"
    assert "不构成投注建议" in tight["special_ticket"]["note"]
    assert tight["query"]["main"] == ["26", "27", "28", "29", "30"]
    assert 11 not in [int(item) for item in tight["query"]["main"]]

    far = score_zhenfu(db, "dlt", ["01", "02", "03", "04", "05"], ["01", "02"], short=5, long=10)
    assert far["ticket"]["amplitude_sum"] == 125
    assert far["ticket"]["alignment"] == "against"
    assert far["ticket"]["rarity"] == "rare"
    assert far["special_ticket"]["amplitude_sum"] == 20
    assert far["special_ticket"]["alignment"] == "against"


def test_digit_score_keeps_position_and_empty_history(db):
    _draw(db, "fc3d", "2026001", ["1", "3", "2"])
    _draw(db, "fc3d", "2026002", ["3", "1", "2"])
    body = score_zhenfu(db, "fc3d", ["3", "1", "2"])
    assert body["basis"] == "digits"
    assert body["ticket"]["amplitude_sum"] == 0
    assert body["ticket"]["percentile"] == 0.0
    assert body["ticket"]["typicality"] == 0.0
    assert body["ticket"]["rarity"] == "rare"
    assert body["ticket"]["alignment"] == "neutral"
    assert body["ticket"]["note"] == (
        "振幅 0，历史分位 0%，出现率 0%，少见，"
        "短窗 4 和长窗 4 差不多，没有明显顺逆。仅供娱乐，不构成投注建议。"
    )
    assert body["special_ticket"] == _empty_ticket()

    moved = score_zhenfu(db, "fc3d", ["2", "1", "3"])
    assert moved["ticket"]["amplitude_sum"] == 2

    wrapped = score_zhenfu(db, "fc3d", ["9", "0", "2"])
    assert wrapped["ticket"]["amplitude_sum"] == 7
    assert wrapped["ticket"]["rarity"] == "rare"

    _draw(db, "pl3", "2026101", ["1", "1", "1"])
    low = score_zhenfu(db, "pl3", [2, 2, 2])
    assert low["sample_size"] == 0
    assert low["ticket"]["amplitude_sum"] == 3
    assert low["ticket"]["percentile"] is None
    assert low["ticket"]["rarity"] is None
    assert low["ticket"]["alignment"] is None
    assert low["ticket"]["note"] == "振幅 3，还没有历史可对照。仅供娱乐，不构成投注建议。"

    _draw(db, "qxc", "2026101", ["1", "2", "3", "4", "5", "6"], ["4"])
    high = score_zhenfu(db, "qxc", ["1", "2", "3", "4", "5", "7"], ["3"])
    assert high["ticket"]["amplitude_sum"] == 1
    assert high["special_ticket"]["amplitude_sum"] == 1
    assert high["special_ticket"]["note"] == "振幅 1，还没有历史可对照。仅供娱乐，不构成投注建议。"

    states = [
        ["0", "0", "0"],
        ["1", "0", "0"],
        ["2", "0", "0"],
        ["3", "0", "0"],
        ["4", "0", "0"],
        ["5", "4", "0"],
        ["6", "8", "0"],
        ["9", "8", "6"],
    ]
    for index, balls in enumerate(states, start=1):
        _draw(db, "pl5", f"2026{index:03d}", balls + ["0", "0"])
    middle = score_zhenfu(db, "pl5", ["9", "8", "1", "0", "0"], short=5, long=20)
    assert middle["ticket"]["amplitude_sum"] == 5
    assert middle["ticket"]["percentile"] == pytest.approx(0.8571)
    assert middle["ticket"]["typicality"] == pytest.approx(0.2857)
    assert middle["ticket"]["rarity"] == "typical"
    assert middle["ticket"]["alignment"] == "aligned"
    assert middle["ticket"]["note"] == (
        "振幅 5，历史分位 85.71%，出现率 28.57%，居中，"
        "短窗 4.2 比长窗 3.2857 走高，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert middle["special_ticket"] == _empty_ticket()


def test_empty_history_parameter_clamp_and_common_cap(db):
    empty = zhenfu_summary(db, "kl8", limit="no", short=None, long="bad")
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

    scored = score_zhenfu(db, "kl8", ["01"])
    assert scored["ticket"] == _empty_ticket()
    assert scored["special_ticket"] == _empty_ticket()

    full = [f"{number:02d}" for number in range(1, 21)]
    _draw(db, "kl8", "2026001", full)
    shifted = score_zhenfu(db, "kl8", [f"{number:02d}" for number in range(2, 22)])
    assert shifted["sample_size"] == 0
    assert shifted["ticket"]["amplitude_sum"] == 20
    assert shifted["ticket"]["note"] == "振幅 20，还没有历史可对照。仅供娱乐，不构成投注建议。"
    short = score_zhenfu(db, "kl8", ["01"])
    assert short["ticket"] == _empty_ticket()

    clamped = zhenfu_summary(db, "kl8", limit=1, short=1, long=1)
    assert clamped["short"] == 5
    assert clamped["long"] == 20

    opened = zhenfu_summary(db, "kl8", short=30, long=20)
    assert opened["short"] == 30
    assert opened["long"] == 31

    states = [
        ["0", "0", "0"],
        ["0", "0", "0"],
        ["1", "0", "0"],
        ["2", "1", "0"],
        ["3", "2", "1"],
        ["5", "3", "2"],
        ["7", "5", "3"],
        ["9", "7", "5"],
        ["9", "0", "5"],
        ["9", "8", "5"],
    ]
    for index, balls in enumerate(states, start=1):
        _draw(db, "fc3d", f"2028{index:03d}", balls)
    capped = zhenfu_summary(db, "fc3d")
    assert capped["sample_size"] == 9
    assert len(capped["common"]) == 8
    assert [item["amplitude_sum"] for item in capped["common"]] == list(range(8))
    assert all(item["count"] == 1 and item["rate"] == pytest.approx(0.1111) for item in capped["common"])
    assert 8 not in [item["amplitude_sum"] for item in capped["common"]]
    assert _bucket(capped["distribution"], 0)["count"] == 1
    assert _bucket(capped["distribution"], 8)["count"] == 1

    with pytest.raises(ValueError, match="未知彩种"):
        zhenfu_summary(db, "nope")
    with pytest.raises(ValueError, match="未知彩种"):
        score_zhenfu(db, "nope", ["01"])
    with pytest.raises(ValueError):
        score_zhenfu(db, "ssq", ["01", "01", "03", "04", "05", "06"], ["01"])
    with pytest.raises(ValueError):
        score_zhenfu(db, "fc3d", ["1", "2"])
    with pytest.raises(ValueError):
        score_zhenfu(db, "kl8", ["01", "02"], ["03"])


def test_ensemble_includes_zhenfu_at_equal_weight(db):
    _draw(db, "ssq", "2026001", ["01", "08", "18", "19", "20", "33"], ["09"])
    _draw(db, "ssq", "2026002", ["02", "09", "18", "19", "21", "32"], ["10"])
    scored = score_ticket(db, "ssq", ["03", "08", "14", "19", "25", "31"], ["09"])
    assert [item["module"] for item in scored["breakdown"]][-3] == "zhenfu"
    row = next(item for item in scored["breakdown"] if item["module"] == "zhenfu")
    assert row["label"] == "振幅"
    assert row["weight"] == 1.0
    assert row["score"] is not None
    assert "振幅" in row["note"]
    assert {item["weight"] for item in scored["breakdown"]} == {1.0}


def test_zhenfu_endpoints_bounds_and_old_contracts(client, db):
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

    res = client.get("/api/analysis/ssq/zhenfu")
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
    assert body["latest_draw"]["amplitude_sum"] == 6
    assert body["latest_draw"]["special_amplitude_sum"] == 1
    assert body["mean"] == 6
    assert body["pulse"] == 0.0
    assert body["drift"] == "flat"
    assert body["special"]["sample_size"] == 1
    assert "rise_count" not in body
    assert "span" not in body
    assert [item["amplitude_sum"] for item in body["distribution"]] == [6]

    custom = client.get("/api/analysis/ssq/zhenfu", params={"limit": 80, "short": 5, "long": 20})
    assert custom.status_code == 200
    assert custom.json()["short"] == 5
    assert custom.json()["long"] == 20

    widened = client.get("/api/analysis/ssq/zhenfu", params={"short": 30, "long": 20})
    assert widened.status_code == 200
    assert widened.json()["short"] == 30
    assert widened.json()["long"] == 31

    assert client.get("/api/analysis/ssq/zhenfu", params={"limit": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/zhenfu", params={"limit": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/zhenfu", params={"short": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/zhenfu", params={"short": 31}).status_code == 422
    assert client.get("/api/analysis/ssq/zhenfu", params={"long": 19}).status_code == 422
    assert client.get("/api/analysis/ssq/zhenfu", params={"long": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/zhenfu", params={"limit": 5, "short": 5, "long": 20}).status_code == 200
    assert client.get("/api/analysis/ssq/zhenfu", params={"limit": 200, "short": 30, "long": 200}).status_code == 200

    unknown = client.get("/api/analysis/nope/zhenfu")
    assert unknown.status_code == 400
    assert "未知彩种" in unknown.json()["detail"]

    empty = client.get("/api/analysis/kl8/zhenfu")
    assert empty.status_code == 200
    assert empty.json()["sample_size"] == 0
    assert empty.json()["latest_draw"] is None
    assert empty.json()["distribution"] == []
    assert empty.json()["drift"] is None

    alias = client.get("/api/analysis/3d/zhenfu")
    assert alias.status_code == 200
    assert alias.json()["lottery_type"] == "fc3d"
    assert alias.json()["mode"] == "digit"
    assert alias.json()["basis"] == "digits"

    posted = client.post(
        "/api/analysis/ssq/zhenfu/score",
        json={"main": "02 03 04 05 06 07", "special": "09", "limit": 80, "short": 10, "long": 50},
    )
    assert posted.status_code == 200, posted.text
    scored = posted.json()
    assert set(scored) == POST_KEYS
    assert scored["query"] == {"main": ["02", "03", "04", "05", "06", "07"], "special": ["09"]}
    assert scored["ticket"]["amplitude_sum"] == 0
    assert scored["ticket"]["rarity"] == "rare"
    assert scored["ticket"]["alignment"] == "neutral"
    assert scored["special_ticket"]["amplitude_sum"] == 0
    assert "仅供娱乐" in scored["ticket"]["note"]
    assert "振幅 0" in scored["ticket"]["note"]

    spaced = client.post("/api/analysis/3d/zhenfu/score", json={"main": ["3", "1", "2"], "short": 5, "long": 20})
    assert spaced.status_code == 200
    assert spaced.json()["lottery_type"] == "fc3d"
    assert spaced.json()["mode"] == "digit"

    bad = client.post("/api/analysis/ssq/zhenfu/score", json={"main": ["99"], "special": ["01"]})
    assert bad.status_code == 400
    duplicate = client.post(
        "/api/analysis/ssq/zhenfu/score",
        json={"main": ["01", "01", "03", "04", "05", "06"], "special": ["01"]},
    )
    assert duplicate.status_code == 400
    short = client.post("/api/analysis/fc3d/zhenfu/score", json={"main": ["1", "2"]})
    assert short.status_code == 400
    extra = client.post("/api/analysis/kl8/zhenfu/score", json={"main": ["01", "02"], "special": ["03"]})
    assert extra.status_code == 400
    unknown_post = client.post("/api/analysis/nope/zhenfu/score", json={"main": ["01"]})
    assert unknown_post.status_code == 400
    assert client.post("/api/analysis/ssq/zhenfu/score", json={"main": ["01"], "limit": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/zhenfu/score", json={"main": ["01"], "short": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/zhenfu/score", json={"main": ["01"], "long": 201}).status_code == 422

    analysis = client.get("/api/analysis/ssq")
    assert analysis.status_code == 200
    assert "zhenfu" not in analysis.json()
    assert "amplitude_sum" not in analysis.json()

    pulse = client.post("/api/predict", json={"lottery_type": "ssq", "strategy": "pulse", "count": 1})
    assert pulse.status_code == 200
    modules = pulse.json()["modules"]
    assert "zhenfu" in modules
    assert modules[-3] == "zhenfu"
    breakdown = pulse.json()["recommendations"][0]["breakdown"]
    assert any(item["module"] == "zhenfu" and item["weight"] == 1.0 for item in breakdown)

    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    weights = spec.json()["components"]["schemas"]["PredictIn"]["properties"]["weights"]["description"]
    assert "zhenfu" in weights
    assert "shengping" in weights
    paths = spec.json()["paths"]
    assert "/api/analysis/{lottery_type}/zhenfu" in paths
    assert "/api/analysis/{lottery_type}/zhenfu/score" in paths
    assert "ZhenfuOut" in spec.json()["components"]["schemas"]
    assert "ZhenfuScoreOut" in spec.json()["components"]["schemas"]
