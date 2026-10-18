"""大小脉动：主号大号个数的历史分布，以及短窗相对长窗的升降。

乐透按号码池中点分界，小于等于中点为小，大于中点为大，主号去重。
数字彩 0–4 为小、5–9 为大，重复数字保留。特别号不并进主号，有特别号时另算。
空白主号跳过，不占窗口名额。短窗、长窗用实际算出大号个数的期数求平均，缺口不当成 0。
这不是三区比，也不是奇偶个数，也不是号码形态里的静态大小表。
只读本地开奖，不改其他分析接口的返回形状。
"""
from __future__ import annotations

import json

import pytest

from app.models import Draw
from app.services.daxiao import (
    COMMON_LIMIT,
    DIGIT_NOTE,
    DISCLAIMER,
    THRESHOLD,
    daxiao_summary,
    score_daxiao,
)
from app.services.parity import parity_summary
from app.services.pulse_ensemble import PULSE_MODULES, _MEMO_TARGETS, score_ticket
from app.services.shape import shape_stats
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
    "boundary",
    "note",
    "latest_draw",
    "special",
    "data_status",
    "disclaimer",
}

POST_KEYS = GET_KEYS | {"query", "ticket", "special_ticket"}

BUCKET_KEYS = {"big_count", "count", "rate"}
COMMON_KEYS = {"big_count", "small_count", "ratio", "count", "rate"}
TICKET_KEYS = {"big_count", "small_count", "percentile", "typicality", "rarity", "alignment", "note"}
LATEST_KEYS = {
    "issue",
    "draw_date",
    "main",
    "special",
    "big_count",
    "small_count",
    "special_big_count",
    "special_small_count",
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
    "boundary",
}
BOUNDARY_KEYS = {"lo", "hi", "mid"}


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


def _bucket(rows, big_count):
    found = [item for item in rows if item["big_count"] == big_count]
    assert len(found) == 1
    return found[0]


def _empty_ticket():
    return {
        "big_count": None,
        "small_count": None,
        "percentile": None,
        "typicality": None,
        "rarity": None,
        "alignment": None,
        "note": "",
    }


def test_daxiao_constants_and_equal_weight_registry():
    assert THRESHOLD == 0.5
    assert COMMON_LIMIT == 8
    assert "仅供娱乐" in DISCLAIMER
    assert "不构成投注建议" in DISCLAIMER
    assert "大号" in DISCLAIMER
    assert "0–4" in DIGIT_NOTE and "5–9" in DIGIT_NOTE
    keys = [item.key for item in PULSE_MODULES]
    assert "daxiao" in keys
    assert [item.label for item in PULSE_MODULES if item.key == "daxiao"] == ["大小"]
    assert ("app.services.daxiao", "daxiao_summary") in _MEMO_TARGETS
    assert len(keys) == len(set(keys))


def test_set_midpoint_ssq_dlt_and_digit_fc3d(db):
    _draw(db, "ssq", "2026001", ["17"], ["08"])
    _draw(db, "ssq", "2026002", ["18"], ["09"])
    ssq = daxiao_summary(db, "ssq", limit=5)
    assert ssq["boundary"] == {"lo": 1, "hi": 33, "mid": 17}
    assert ssq["latest_draw"]["main"] == ["18"]
    assert ssq["latest_draw"]["big_count"] == 1
    assert ssq["latest_draw"]["small_count"] == 0
    assert ssq["latest_draw"]["special_big_count"] == 1
    assert ssq["latest_draw"]["special_small_count"] == 0
    older = [item for item in ssq["distribution"] if item["big_count"] == 0][0]
    assert older["count"] == 1
    assert "1–17" in ssq["note"] and "18–33" in ssq["note"]
    assert ssq["special"]["boundary"] == {"lo": 1, "hi": 16, "mid": 8}
    assert ssq["special"]["label"] == "蓝球"

    _draw(db, "dlt", "2026101", ["18"], ["06"])
    _draw(db, "dlt", "2026102", ["19"], ["07"])
    dlt = daxiao_summary(db, "dlt", limit=5)
    assert dlt["boundary"] == {"lo": 1, "hi": 35, "mid": 18}
    assert dlt["latest_draw"]["big_count"] == 1
    assert dlt["latest_draw"]["small_count"] == 0
    assert dlt["latest_draw"]["special"] == ["07"]
    assert dlt["latest_draw"]["special_big_count"] == 1
    assert "1–18" in dlt["note"] and "19–35" in dlt["note"]
    assert dlt["special"]["boundary"] == {"lo": 1, "hi": 12, "mid": 6}
    assert _bucket(dlt["distribution"], 0)["count"] == 1
    assert _bucket(dlt["distribution"], 1)["count"] == 1

    _draw(db, "fc3d", "2026201", ["4", "4", "4"])
    _draw(db, "fc3d", "2026202", ["5", "5", "5"])
    digit = daxiao_summary(db, "fc3d", limit=5)
    assert digit["mode"] == "digit"
    assert digit["basis"] == "digits"
    assert digit["boundary"] == {"lo": 0, "hi": 9, "mid": 4}
    assert digit["note"] == DIGIT_NOTE
    assert digit["latest_draw"]["main"] == ["5", "5", "5"]
    assert digit["latest_draw"]["big_count"] == 3
    assert digit["latest_draw"]["small_count"] == 0
    assert digit["latest_draw"]["special_big_count"] is None
    assert digit["special"] is None
    assert _bucket(digit["distribution"], 0)["count"] == 1
    assert _bucket(digit["distribution"], 3)["count"] == 1
    assert [item["big_count"] for item in digit["distribution"]] == [0, 1, 2, 3]


def test_set_big_count_dedupes_and_keeps_special_apart(db):
    _draw(db, "ssq", "2026005", ["01", "18", "19"], ["16"], source="crawl", draw_date="2026-01-09")
    _draw(db, "ssq", "2026004", ["02", "04"], ["03"])
    _draw(db, "ssq", "2026003", [], ["01"])
    _draw(db, "ssq", "2026002", ["18", "18", "33"], ["09"])
    _draw(db, "ssq", "2026001", ["x", "17", "33"], ["08"])

    body = daxiao_summary(db, "ssq", limit=80, short=10, long=50)
    assert set(body) == GET_KEYS
    assert body["lottery_type"] == "ssq"
    assert body["mode"] == "set"
    assert body["basis"] == "main"
    assert body["sample_size"] == 4
    assert body["short"] == 10
    assert body["long"] == 50
    assert body["threshold"] == 0.5
    assert body["data_status"] == "mixed"
    assert body["disclaimer"] == DISCLAIMER
    assert "三区" in body["note"] and "奇偶" in body["note"]
    assert body["boundary"] == {"lo": 1, "hi": 33, "mid": 17}
    assert set(body["boundary"]) == BOUNDARY_KEYS
    assert body["mean"] == 1.25
    assert body["median"] == 1.5
    assert body["short_avg"] == 1.25
    assert body["long_avg"] == 1.25
    assert body["pulse"] == 0.0
    assert body["drift"] == "flat"
    assert set(body["latest_draw"]) == LATEST_KEYS
    assert body["latest_draw"]["issue"] == "2026005"
    assert body["latest_draw"]["main"] == ["01", "18", "19"]
    assert body["latest_draw"]["special"] == ["16"]
    assert body["latest_draw"]["big_count"] == 2
    assert body["latest_draw"]["small_count"] == 1
    assert body["latest_draw"]["special_big_count"] == 1
    assert body["latest_draw"]["special_small_count"] == 0
    assert [item["big_count"] for item in body["distribution"]] == [0, 1, 2, 3]
    assert all(set(item) == BUCKET_KEYS for item in body["distribution"])
    assert _bucket(body["distribution"], 0) == {"big_count": 0, "count": 1, "rate": 0.25}
    assert _bucket(body["distribution"], 1) == {"big_count": 1, "count": 1, "rate": 0.25}
    assert _bucket(body["distribution"], 2) == {"big_count": 2, "count": 2, "rate": 0.5}
    assert _bucket(body["distribution"], 3)["count"] == 0
    assert body["common"] == [
        {"big_count": 0, "small_count": 2, "ratio": "0大2小", "count": 1, "rate": 0.25},
        {"big_count": 1, "small_count": 1, "ratio": "1大1小", "count": 1, "rate": 0.25},
        {"big_count": 2, "small_count": 0, "ratio": "2大0小", "count": 1, "rate": 0.25},
        {"big_count": 2, "small_count": 1, "ratio": "2大1小", "count": 1, "rate": 0.25},
    ]
    assert all(set(item) == COMMON_KEYS for item in body["common"])

    special = body["special"]
    assert set(special) == SPECIAL_KEYS
    assert special["label"] == "蓝球"
    assert special["sample_size"] == 4
    assert special["boundary"] == {"lo": 1, "hi": 16, "mid": 8}
    assert special["mean"] == 0.5
    assert special["median"] == 0.5
    assert [item["big_count"] for item in special["distribution"]] == [0, 1]
    assert _bucket(special["distribution"], 1)["count"] == 2
    assert _bucket(special["distribution"], 0)["count"] == 2
    assert special["common"][0]["ratio"] == "0大1小"

    shape = shape_stats(db, "ssq", limit=50)
    labels = {row["label"] for row in shape["big_small"]}
    assert "3大0小" in labels
    assert "2大0小" in labels
    assert "1大1小" not in labels
    assert "big_count" not in shape
    assert "pulse" not in shape


def test_seventeen_is_small_on_ssq_but_shape_table_stays(db):
    _draw(db, "ssq", "2026001", ["17"], ["16"])
    body = daxiao_summary(db, "ssq")
    assert body["latest_draw"]["big_count"] == 0
    assert body["latest_draw"]["small_count"] == 1
    assert body["latest_draw"]["special_big_count"] == 1
    shape = shape_stats(db, "ssq")
    assert shape["big_small"] == [{"label": "1大0小", "big": 1, "small": 0, "count": 1}]
    assert "distribution" not in shape
    assert "drift" not in shape


def test_daxiao_is_not_parity_or_zone(db):
    _draw(db, "ssq", "2026001", ["01", "02", "18"], ["09"])
    body = daxiao_summary(db, "ssq")
    assert body["latest_draw"]["big_count"] == 1
    assert body["latest_draw"]["small_count"] == 2
    parity = parity_summary(db, "ssq")
    zone = zone_summary(db, "ssq")
    assert parity["latest_draw"]["odd_count"] == 1
    assert "big_count" not in parity
    assert "big_count" not in parity["latest_draw"]
    assert "big_count" not in zone
    assert "odd_count" not in body
    assert "imbalance" not in body
    assert "zone_counts" not in body
    assert "hewei" not in body


def test_pulse_rises_when_recent_big_counts_are_higher(db):
    for index, balls in enumerate([["18", "19", "20"]] * 5 + [["01", "02", "03"]] * 5):
        _draw(db, "ssq", f"{2026010 - index:07d}", balls, ["08"])

    body = daxiao_summary(db, "ssq", short=5, long=10)
    assert body["sample_size"] == 10
    assert body["short_avg"] == 3.0
    assert body["long_avg"] == 1.5
    assert body["pulse"] == 1.5
    assert body["drift"] == "rising"
    assert body["mean"] == 1.5
    assert body["median"] == 1.5
    assert [item["big_count"] for item in body["distribution"]] == [0, 1, 2, 3]
    assert _bucket(body["distribution"], 0)["count"] == 5
    assert _bucket(body["distribution"], 3)["count"] == 5
    assert _bucket(body["distribution"], 1)["count"] == 0
    assert _bucket(body["distribution"], 2)["count"] == 0
    assert body["common"][0]["ratio"] == "0大3小"
    assert body["common"][1]["ratio"] == "3大0小"
    assert body["latest_draw"]["big_count"] == 3
    assert body["latest_draw"]["special_big_count"] == 0
    assert body["special"]["drift"] == "flat"
    assert body["special"]["pulse"] == 0.0


def test_pulse_threshold_edges(db):
    for index, balls in enumerate([["18", "19"]] * 5 + [["01"]]):
        _draw(db, "ssq", f"{2026106 - index}", balls)
    flat = daxiao_summary(db, "ssq", short=5, long=20)
    assert flat["sample_size"] == 6
    assert flat["short_avg"] == 2.0
    assert flat["long_avg"] == pytest.approx(1.6667)
    assert flat["pulse"] == pytest.approx(0.3333)
    assert flat["drift"] == "flat"

    for index, balls in enumerate([["19", "20", "21"]] * 5 + [["01"]]):
        _draw(db, "dlt", f"{2026206 - index}", balls)
    rising = daxiao_summary(db, "dlt", short=5, long=20)
    assert rising["basis"] == "main"
    assert rising["boundary"]["mid"] == 18
    assert rising["short_avg"] == 3.0
    assert rising["long_avg"] == 2.5
    assert rising["pulse"] == 0.5
    assert rising["drift"] == "rising"

    for index, balls in enumerate([["0", "1", "2"]] * 5 + [["5", "6", "7"]]):
        _draw(db, "fc3d", f"{2026306 - index}", balls)
    falling = daxiao_summary(db, "fc3d", short=5, long=20)
    assert falling["basis"] == "digits"
    assert falling["short_avg"] == 0.0
    assert falling["long_avg"] == 0.5
    assert falling["pulse"] == -0.5
    assert falling["drift"] == "falling"


def test_dlt_special_big_count_stays_out_of_main(db):
    _draw(db, "dlt", "2026003", ["01", "05", "19"], ["07", "08"], draw_date="2026-02-03")
    _draw(db, "dlt", "2026002", ["03", "04"], ["02", "03"])
    _draw(db, "dlt", "2026001", ["08", "10"], ["06"])
    _draw(db, "dlt", "2026000", ["20", "21"], ["01", "12"])

    body = daxiao_summary(db, "dlt", short=5, long=20)
    assert body["basis"] == "main"
    assert body["sample_size"] == 4
    assert body["mean"] == 0.75
    assert body["median"] == 0.5
    assert body["latest_draw"]["big_count"] == 1
    assert body["latest_draw"]["small_count"] == 2
    assert body["latest_draw"]["special"] == ["07", "08"]
    assert body["latest_draw"]["special_big_count"] == 2
    assert body["latest_draw"]["special_small_count"] == 0
    assert 7 not in [int(item) for item in body["latest_draw"]["main"]]
    assert _bucket(body["distribution"], 0)["count"] == 2
    assert _bucket(body["distribution"], 1)["count"] == 1
    assert _bucket(body["distribution"], 2)["count"] == 1

    special = body["special"]
    assert set(special) == SPECIAL_KEYS
    assert special["label"] == "后区"
    assert special["sample_size"] == 4
    assert special["boundary"] == {"lo": 1, "hi": 12, "mid": 6}
    assert special["mean"] == 0.75
    assert special["median"] == 0.5
    assert [item["big_count"] for item in special["distribution"]] == [0, 1, 2]
    assert _bucket(special["distribution"], 2)["count"] == 1
    assert _bucket(special["distribution"], 1)["count"] == 1
    assert _bucket(special["distribution"], 0)["count"] == 2
    assert special["common"][0]["ratio"] == "0大1小"

    _draw(db, "qlc", "2026001", ["01", "16", "30"], ["15"])
    single = daxiao_summary(db, "qlc")
    assert single["boundary"] == {"lo": 1, "hi": 30, "mid": 15}
    assert single["latest_draw"]["big_count"] == 2
    assert single["latest_draw"]["small_count"] == 1
    assert single["special"]["label"] == "特别号"
    assert single["special"]["sample_size"] == 1
    assert single["special"]["boundary"]["mid"] == 15
    assert single["latest_draw"]["special_big_count"] == 0
    assert single["latest_draw"]["special_small_count"] == 1


def test_digit_keeps_repeats_and_qxc_special_uses_digit_rule(db):
    _draw(db, "fc3d", "2026004", ["0", "9", "1"], draw_date="2026-03-04")
    _draw(db, "fc3d", "2026003", ["1", "2", "3"])
    _draw(db, "fc3d", "2026002", ["5", "5", "5"])
    _draw(db, "fc3d", "2026001", ["4", "0", "0"])
    _draw(db, "fc3d", "2026000", [], ["5"])
    _draw(db, "qxc", "2026008", ["1", "2", "3", "4", "5", "9"], ["14"])
    _draw(db, "pl5", "2026008", ["0", "1", "2", "3", "4"])

    body = daxiao_summary(db, "fc3d")
    assert body["lottery_type"] == "fc3d"
    assert body["mode"] == "digit"
    assert body["basis"] == "digits"
    assert body["note"] == DIGIT_NOTE
    assert body["sample_size"] == 4
    assert body["special"] is None
    assert body["mean"] == 1.0
    assert body["median"] == 0.5
    assert body["latest_draw"]["big_count"] == 1
    assert body["latest_draw"]["small_count"] == 2
    assert body["latest_draw"]["main"] == ["0", "9", "1"]
    assert [item["big_count"] for item in body["distribution"]] == [0, 1, 2, 3]
    assert _bucket(body["distribution"], 0) == {"big_count": 0, "count": 2, "rate": 0.5}
    assert _bucket(body["distribution"], 1) == {"big_count": 1, "count": 1, "rate": 0.25}
    assert _bucket(body["distribution"], 3) == {"big_count": 3, "count": 1, "rate": 0.25}
    assert body["common"][0] == {"big_count": 0, "small_count": 3, "ratio": "0大3小", "count": 2, "rate": 0.5}

    qxc = daxiao_summary(db, "qxc")
    assert qxc["basis"] == "digits"
    assert qxc["latest_draw"]["big_count"] == 2
    assert qxc["latest_draw"]["small_count"] == 4
    assert qxc["latest_draw"]["special"] == ["14"]
    assert qxc["latest_draw"]["special_big_count"] == 1
    assert qxc["latest_draw"]["special_small_count"] == 0
    assert qxc["special"]["boundary"] == {"lo": 0, "hi": 9, "mid": 4}
    assert qxc["special"]["sample_size"] == 1
    assert qxc["special"]["mean"] == 1.0

    pl5 = daxiao_summary(db, "pl5")
    assert pl5["basis"] == "digits"
    assert pl5["special"] is None
    assert pl5["latest_draw"]["big_count"] == 0
    assert pl5["latest_draw"]["small_count"] == 5
    assert pl5["latest_draw"]["main"] == ["0", "1", "2", "3", "4"]


def test_blank_main_does_not_consume_the_analysis_window(db):
    _draw(db, "ssq", "2026001", ["18", "19", "20"])
    _draw(db, "ssq", "2026002", ["18", "19"])
    _draw(db, "ssq", "2026003", ["33"])
    _draw(db, "ssq", "2026004", ["01"])
    _draw(db, "ssq", "2026005", [])
    _draw(db, "ssq", "2026006", ["01", "02", "18"])

    body = daxiao_summary(db, "ssq", limit=5, short=5, long=20)
    assert body["sample_size"] == 4
    assert body["latest_draw"]["issue"] == "2026006"
    assert body["latest_draw"]["big_count"] == 1
    assert body["mean"] == 1.0
    assert body["latest_draw"]["issue"] != "2026001"


def test_score_aligns_with_pulse_and_marks_rarity(db):
    for index, balls in enumerate([["18", "19", "20"]] * 5 + [["01", "02", "03"]] * 5):
        _draw(db, "ssq", f"{2026010 - index:07d}", balls, ["08"])

    wide = score_daxiao(db, "ssq", ["18", "19", "20"], ["09"], short=5, long=10)
    assert set(wide) == POST_KEYS
    assert wide["query"] == {"main": ["18", "19", "20"], "special": ["09"]}
    assert set(wide["ticket"]) == TICKET_KEYS
    assert wide["ticket"]["big_count"] == 3
    assert wide["ticket"]["small_count"] == 0
    assert wide["ticket"]["percentile"] == 1.0
    assert wide["ticket"]["typicality"] == 0.5
    assert wide["ticket"]["rarity"] == "common"
    assert wide["ticket"]["alignment"] == "aligned"
    assert wide["ticket"]["note"] == (
        "大号个数 3（3大0小），历史分位 100%，出现率 50%，常见，"
        "短窗 3 比长窗 1.5 走高，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert wide["special_ticket"]["big_count"] == 1
    assert wide["special_ticket"]["small_count"] == 0
    assert wide["special_ticket"]["percentile"] == 1.0
    assert wide["special_ticket"]["typicality"] == 0.0
    assert wide["special_ticket"]["rarity"] == "rare"
    assert wide["special_ticket"]["alignment"] == "neutral"
    assert wide["special_ticket"]["note"] == (
        "大号个数 1（1大0小），历史分位 100%，出现率 0%，少见，"
        "短窗 0 和长窗 0 差不多，没有明显顺逆。仅供娱乐，不构成投注建议。"
    )
    assert wide["drift"] == "rising"
    assert wide["special"]["drift"] == "flat"

    narrow = score_daxiao(db, "ssq", "01 02 03", special="16", short=5, long=10)
    assert narrow["ticket"]["big_count"] == 0
    assert narrow["ticket"]["small_count"] == 3
    assert narrow["ticket"]["percentile"] == 0.5
    assert narrow["ticket"]["typicality"] == 0.5
    assert narrow["ticket"]["rarity"] == "common"
    assert narrow["ticket"]["alignment"] == "against"
    assert narrow["ticket"]["note"] == (
        "大号个数 0（0大3小），历史分位 50%，出现率 50%，常见，"
        "短窗 3 比长窗 1.5 走高，和短窗脉动反向。仅供娱乐，不构成投注建议。"
    )
    assert narrow["special_ticket"]["big_count"] == 1
    assert narrow["special_ticket"]["rarity"] == "rare"

    rare = score_daxiao(db, "ssq", ["18", "19", "20", "21", "22", "23"], ["08"], short=5, long=10)
    assert rare["ticket"]["big_count"] == 6
    assert rare["ticket"]["small_count"] == 0
    assert rare["ticket"]["percentile"] == 1.0
    assert rare["ticket"]["typicality"] == 0.0
    assert rare["ticket"]["rarity"] == "rare"
    assert rare["ticket"]["alignment"] == "aligned"
    assert "少见" in rare["ticket"]["note"]
    assert "仅供娱乐" in rare["ticket"]["note"]
    assert rare["special_ticket"]["big_count"] == 0
    assert rare["special_ticket"]["rarity"] == "common"
    assert rare["special_ticket"]["alignment"] == "neutral"

    for index, pair in enumerate(
        [(["01", "02", "03", "04", "05"], ["07", "08"])] * 5
        + [(["19", "20", "21", "22", "23"], ["01", "02"])] * 5
    ):
        main, special = pair
        _draw(db, "dlt", f"{2027010 - index:07d}", main, special)

    tight = score_daxiao(db, "dlt", ["01", "02", "03", "04", "05"], ["07", "08"], short=5, long=10)
    assert tight["drift"] == "falling"
    assert tight["ticket"]["big_count"] == 0
    assert tight["ticket"]["small_count"] == 5
    assert tight["ticket"]["alignment"] == "aligned"
    assert tight["ticket"]["note"] == (
        "大号个数 0（0大5小），历史分位 50%，出现率 50%，常见，"
        "短窗 0 比长窗 2.5 走低，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert tight["special"]["drift"] == "rising"
    assert tight["special"]["short_avg"] == 2.0
    assert tight["special"]["long_avg"] == 1.0
    assert tight["special_ticket"]["big_count"] == 2
    assert tight["special_ticket"]["small_count"] == 0
    assert tight["special_ticket"]["alignment"] == "aligned"
    assert tight["special_ticket"]["rarity"] == "common"
    assert "不构成投注建议" in tight["special_ticket"]["note"]
    assert 7 not in [int(item) for item in tight["query"]["main"]]

    wide_back = score_daxiao(db, "dlt", ["19", "20", "21", "22", "23"], ["01", "02"], short=5, long=10)
    assert wide_back["ticket"]["big_count"] == 5
    assert wide_back["ticket"]["alignment"] == "against"
    assert wide_back["special_ticket"]["big_count"] == 0
    assert wide_back["special_ticket"]["alignment"] == "against"
    assert wide_back["special_ticket"]["percentile"] == 0.5
    assert wide_back["special_ticket"]["typicality"] == 0.5


def test_digit_score_keeps_repeats(db):
    _draw(db, "fc3d", "2026004", ["0", "9", "1"])
    _draw(db, "fc3d", "2026003", ["1", "2", "3"])
    _draw(db, "fc3d", "2026002", ["5", "5", "5"])
    _draw(db, "fc3d", "2026001", ["4", "0", "0"])

    body = score_daxiao(db, "fc3d", ["0", "9", "1"])
    assert body["basis"] == "digits"
    assert body["ticket"]["big_count"] == 1
    assert body["ticket"]["small_count"] == 2
    assert body["ticket"]["percentile"] == 0.75
    assert body["ticket"]["typicality"] == 0.25
    assert body["ticket"]["rarity"] == "typical"
    assert body["ticket"]["alignment"] == "neutral"
    assert body["ticket"]["note"] == (
        "大号个数 1（1大2小），历史分位 75%，出现率 25%，居中，"
        "短窗 1 和长窗 1 差不多，没有明显顺逆。仅供娱乐，不构成投注建议。"
    )
    assert body["special_ticket"] == _empty_ticket()

    repeated = score_daxiao(db, "fc3d", ["5", "5", "5"])
    assert repeated["ticket"]["big_count"] == 3
    assert repeated["ticket"]["small_count"] == 0
    assert repeated["ticket"]["percentile"] == 1.0
    assert repeated["ticket"]["typicality"] == 0.25
    assert repeated["ticket"]["rarity"] == "rare"
    assert "少见" in repeated["ticket"]["note"]

    low = score_daxiao(db, "pl3", [0, 1, 4])
    assert low["sample_size"] == 0
    assert low["ticket"]["big_count"] == 0
    assert low["ticket"]["small_count"] == 3
    assert low["ticket"]["percentile"] is None
    assert low["ticket"]["rarity"] is None
    assert low["ticket"]["alignment"] is None
    assert low["ticket"]["note"] == "大号个数 0（0大3小），还没有历史可对照。仅供娱乐，不构成投注建议。"

    high = score_daxiao(db, "qxc", ["5", "6", "7", "8", "9", "4"], ["3"])
    assert high["ticket"]["big_count"] == 5
    assert high["ticket"]["small_count"] == 1
    assert high["special_ticket"]["big_count"] == 0
    assert high["special_ticket"]["small_count"] == 1
    assert high["special_ticket"]["note"] == "大号个数 0（0大1小），还没有历史可对照。仅供娱乐，不构成投注建议。"


def test_empty_history_parameter_clamp_and_common_cap(db):
    empty = daxiao_summary(db, "kl8", limit="no", short=None, long="bad")
    assert empty["lottery_type"] == "kl8"
    assert empty["sample_size"] == 0
    assert empty["short"] == 10
    assert empty["long"] == 50
    assert empty["distribution"] == []
    assert empty["common"] == []
    assert empty["mean"] is None
    assert empty["median"] is None
    assert empty["short_avg"] is None
    assert empty["long_avg"] is None
    assert empty["pulse"] is None
    assert empty["drift"] is None
    assert empty["latest_draw"] is None
    assert empty["special"] is None
    assert empty["data_status"] == "seed"
    assert empty["basis"] == "main"
    assert empty["boundary"] == {"lo": 1, "hi": 80, "mid": 40}
    assert "1–40" in empty["note"] and "41–80" in empty["note"]

    scored = score_daxiao(db, "kl8", ["01", "02", "19"])
    assert scored["ticket"]["big_count"] == 0
    assert scored["ticket"]["small_count"] == 3
    assert scored["ticket"]["percentile"] is None
    assert scored["ticket"]["note"] == "大号个数 0（0大3小），还没有历史可对照。仅供娱乐，不构成投注建议。"
    assert scored["special_ticket"] == _empty_ticket()

    one = score_daxiao(db, "kl8", ["41"])
    assert one["ticket"]["big_count"] == 1
    assert one["ticket"]["small_count"] == 0

    for index in range(1, 7):
        _draw(db, "kl8", f"202600{index}", [f"{40 + index:02d}"])
    clamped = daxiao_summary(db, "kl8", limit=1, short=1, long=1)
    assert clamped["short"] == 5
    assert clamped["long"] == 20
    assert clamped["sample_size"] == 5
    assert clamped["latest_draw"]["big_count"] == 1

    opened = daxiao_summary(db, "kl8", short=30, long=20)
    assert opened["short"] == 30
    assert opened["long"] == 31
    assert opened["sample_size"] == 6

    for total in range(1, 10):
        balls = [f"{40 + n:02d}" for n in range(1, total + 1)]
        _draw(db, "ssq", f"202610{total}", balls)
    capped = daxiao_summary(db, "ssq")
    assert capped["sample_size"] == 9
    assert len(capped["common"]) == 8
    assert [item["ratio"] for item in capped["common"]] == [f"{n}大0小" for n in range(1, 9)]
    assert all(item["count"] == 1 and item["rate"] == pytest.approx(0.1111) for item in capped["common"])
    assert capped["distribution"][0]["big_count"] == 0
    assert capped["distribution"][0]["count"] == 0
    assert capped["distribution"][-1]["big_count"] == 9

    with pytest.raises(ValueError, match="未知彩种"):
        daxiao_summary(db, "nope")
    with pytest.raises(ValueError, match="未知彩种"):
        score_daxiao(db, "nope", ["01"])
    with pytest.raises(ValueError):
        score_daxiao(db, "ssq", ["01", "01", "03", "04", "05", "06"], ["01"])
    with pytest.raises(ValueError):
        score_daxiao(db, "fc3d", ["1", "2"])
    with pytest.raises(ValueError):
        score_daxiao(db, "kl8", ["01", "02"], ["03"])


def test_ensemble_includes_daxiao_at_equal_weight(db):
    _draw(db, "ssq", "2026001", ["01", "08", "18", "19", "20", "33"], ["09"])
    scored = score_ticket(db, "ssq", ["03", "08", "14", "19", "25", "31"], ["09"])
    assert any(item["module"] == "daxiao" for item in scored["breakdown"])
    row = next(item for item in scored["breakdown"] if item["module"] == "daxiao")
    assert row["label"] == "大小"
    assert row["weight"] == 1.0
    assert row["score"] is not None
    assert "大号" in row["note"]
    assert {item["weight"] for item in scored["breakdown"]} == {1.0}


def test_daxiao_endpoints_bounds_and_old_contracts(client, db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["08"], draw_date="2026-04-01")
    _draw(db, "ssq", "2026002", ["18", "19", "20", "21", "22", "33"], ["09"], source="crawl", draw_date="2026-04-03")

    res = client.get("/api/analysis/ssq/daxiao")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == GET_KEYS
    assert body["sample_size"] == 2
    assert body["short"] == 10
    assert body["long"] == 50
    assert body["basis"] == "main"
    assert body["boundary"] == {"lo": 1, "hi": 33, "mid": 17}
    assert body["disclaimer"] == DISCLAIMER
    assert "仅供娱乐" in body["disclaimer"]
    assert "不构成投注建议" in body["disclaimer"]
    assert body["data_status"] == "mixed"
    assert body["latest_draw"]["big_count"] == 6
    assert body["latest_draw"]["small_count"] == 0
    assert body["latest_draw"]["special_big_count"] == 1
    assert body["mean"] == 3.0
    assert body["pulse"] == 0.0
    assert body["drift"] == "flat"
    assert body["special"]["sample_size"] == 2
    assert body["special"]["boundary"]["mid"] == 8
    assert "odd_count" not in body
    assert "hewei" not in body
    assert "imbalance" not in body
    assert [item["big_count"] for item in body["distribution"]] == list(range(7))
    assert _bucket(body["distribution"], 6)["count"] == 1
    assert _bucket(body["distribution"], 0)["count"] == 1

    custom = client.get("/api/analysis/ssq/daxiao", params={"limit": 80, "short": 5, "long": 20})
    assert custom.status_code == 200
    assert custom.json()["short"] == 5
    assert custom.json()["long"] == 20

    widened = client.get("/api/analysis/ssq/daxiao", params={"short": 30, "long": 20})
    assert widened.status_code == 200
    assert widened.json()["short"] == 30
    assert widened.json()["long"] == 31

    assert client.get("/api/analysis/ssq/daxiao", params={"limit": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/daxiao", params={"limit": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/daxiao", params={"short": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/daxiao", params={"short": 31}).status_code == 422
    assert client.get("/api/analysis/ssq/daxiao", params={"long": 19}).status_code == 422
    assert client.get("/api/analysis/ssq/daxiao", params={"long": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/daxiao", params={"limit": 5, "short": 5, "long": 20}).status_code == 200
    assert client.get("/api/analysis/ssq/daxiao", params={"limit": 200, "short": 30, "long": 200}).status_code == 200

    unknown = client.get("/api/analysis/nope/daxiao")
    assert unknown.status_code == 400
    assert "未知彩种" in unknown.json()["detail"]

    empty = client.get("/api/analysis/kl8/daxiao")
    assert empty.status_code == 200
    assert empty.json()["sample_size"] == 0
    assert empty.json()["latest_draw"] is None
    assert empty.json()["distribution"] == []
    assert empty.json()["drift"] is None
    assert empty.json()["boundary"]["mid"] == 40

    alias = client.get("/api/analysis/3d/daxiao")
    assert alias.status_code == 200
    assert alias.json()["lottery_type"] == "fc3d"
    assert alias.json()["mode"] == "digit"
    assert alias.json()["basis"] == "digits"
    assert alias.json()["boundary"] == {"lo": 0, "hi": 9, "mid": 4}

    posted = client.post(
        "/api/analysis/ssq/daxiao/score",
        json={"main": "18 19 20 21 22 33", "special": "09", "limit": 80, "short": 10, "long": 50},
    )
    assert posted.status_code == 200, posted.text
    scored = posted.json()
    assert set(scored) == POST_KEYS
    assert scored["query"] == {"main": ["18", "19", "20", "21", "22", "33"], "special": ["09"]}
    assert scored["ticket"]["big_count"] == 6
    assert scored["ticket"]["small_count"] == 0
    assert scored["ticket"]["rarity"] == "common"
    assert scored["ticket"]["alignment"] == "neutral"
    assert scored["special_ticket"]["big_count"] == 1
    assert scored["special_ticket"]["rarity"] == "common"
    assert "仅供娱乐" in scored["ticket"]["note"]
    assert "大号个数 6" in scored["ticket"]["note"]

    unseen = client.post("/api/analysis/ssq/daxiao/score", json={"main": ["01"], "special": ["16"]})
    assert unseen.status_code == 200
    assert unseen.json()["ticket"]["big_count"] == 0
    assert unseen.json()["special_ticket"]["big_count"] == 1
    assert unseen.json()["special_ticket"]["rarity"] == "common"

    spaced = client.post("/api/analysis/3d/daxiao/score", json={"main": ["5", "5", "4"], "short": 5, "long": 20})
    assert spaced.status_code == 200
    assert spaced.json()["lottery_type"] == "fc3d"
    assert spaced.json()["ticket"]["big_count"] == 2
    assert spaced.json()["ticket"]["small_count"] == 1
    assert spaced.json()["mode"] == "digit"

    bad = client.post("/api/analysis/ssq/daxiao/score", json={"main": ["99"], "special": ["01"]})
    assert bad.status_code == 400
    duplicate = client.post(
        "/api/analysis/ssq/daxiao/score",
        json={"main": ["01", "01", "03", "04", "05", "06"], "special": ["01"]},
    )
    assert duplicate.status_code == 400
    short = client.post("/api/analysis/fc3d/daxiao/score", json={"main": ["1", "2"]})
    assert short.status_code == 400
    extra = client.post("/api/analysis/kl8/daxiao/score", json={"main": ["01", "02"], "special": ["03"]})
    assert extra.status_code == 400
    unknown_post = client.post("/api/analysis/nope/daxiao/score", json={"main": ["01"]})
    assert unknown_post.status_code == 400
    assert client.post("/api/analysis/ssq/daxiao/score", json={"main": ["01"], "limit": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/daxiao/score", json={"main": ["01"], "short": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/daxiao/score", json={"main": ["01"], "long": 201}).status_code == 422

    analysis = client.get("/api/analysis/ssq")
    assert analysis.status_code == 200
    assert "daxiao" not in analysis.json()
    assert "big_count" not in analysis.json()
    assert "pulse" not in analysis.json()

    shape = client.get("/api/analysis/ssq/shape")
    assert shape.status_code == 200
    shape_body = shape.json()
    assert "big_count" not in shape_body
    assert "pulse" not in shape_body
    assert "drift" not in shape_body
    labels = [row["label"] for row in shape_body["big_small"]]
    assert "0大6小" in labels
    assert "6大0小" in labels

    parity = client.get("/api/analysis/ssq/parity")
    assert parity.status_code == 200
    assert "big_count" not in parity.json()

    zone = client.get("/api/analysis/ssq/zone")
    assert zone.status_code == 200
    assert "big_count" not in zone.json()

    pulse = client.post("/api/predict", json={"lottery_type": "ssq", "strategy": "pulse", "count": 1})
    assert pulse.status_code == 200
    modules = pulse.json()["modules"]
    assert "daxiao" in modules
    assert "daxiao" in modules
    breakdown = pulse.json()["recommendations"][0]["breakdown"]
    assert any(item["module"] == "daxiao" and item["weight"] == 1.0 for item in breakdown)

    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    weights = spec.json()["components"]["schemas"]["PredictIn"]["properties"]["weights"]["description"]
    assert "daxiao" in weights
    assert "hewei" in weights
    paths = spec.json()["paths"]
    assert "/api/analysis/{lottery_type}/daxiao" in paths
    assert "/api/analysis/{lottery_type}/daxiao/score" in paths
    assert "DaxiaoOut" in spec.json()["components"]["schemas"]
    assert "DaxiaoScoreOut" in spec.json()["components"]["schemas"]
