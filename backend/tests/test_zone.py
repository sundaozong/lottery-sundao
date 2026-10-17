"""区位脉动：主号按数值区间分成三区，看个数配比和区位偏度的短长窗升降。

乐透按主号集合去重，特别号不计入主号；有特别号时按特别号自己的区间另计。
数字彩按整注各位分成 0–3 / 4–6 / 7–9，0 与 9 不绕圈。
区位偏度 = 三区个数的最大减最小，不是除以 3 的余数，也不是跨度。
短窗、长窗用实际有的期数求平均，缺口不当成偏度 0。
只读本地开奖，不改形态统计里的静态分区，也不改其他分析接口的返回形状。
"""
from __future__ import annotations

import json

import pytest

from app.models import Draw
from app.services.road import road_summary
from app.services.shape import shape_stats
from app.services.span import span_summary
from app.services.zone import (
    COMMON_LIMIT,
    DIGIT_NOTE,
    DISCLAIMER,
    SET_NOTE,
    THRESHOLD,
    score_zone,
    zone_summary,
)

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
    "avg_zone_counts",
    "zones",
    "note",
    "latest_draw",
    "special",
    "data_status",
    "disclaimer",
}

POST_KEYS = GET_KEYS | {"query", "ticket", "special_ticket"}

BUCKET_KEYS = {"imbalance", "count", "rate"}
RATIO_KEYS = {"zone_counts", "ratio", "count", "rate"}
COUNT_KEYS = {"1", "2", "3"}
ZONE_KEYS = {"key", "name", "lo", "hi"}
TICKET_KEYS = {
    "zone_counts",
    "ratio",
    "imbalance",
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
    "zone_counts",
    "ratio",
    "imbalance",
    "special_zone_counts",
    "special_ratio",
    "special_imbalance",
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
    "avg_zone_counts",
    "zones",
}

SSQ_ZONES = [
    {"key": "1", "name": "一区", "lo": 1, "hi": 11},
    {"key": "2", "name": "二区", "lo": 12, "hi": 22},
    {"key": "3", "name": "三区", "lo": 23, "hi": 33},
]
DLT_ZONES = [
    {"key": "1", "name": "一区", "lo": 1, "hi": 12},
    {"key": "2", "name": "二区", "lo": 13, "hi": 24},
    {"key": "3", "name": "三区", "lo": 25, "hi": 35},
]
QLC_ZONES = [
    {"key": "1", "name": "一区", "lo": 1, "hi": 10},
    {"key": "2", "name": "二区", "lo": 11, "hi": 20},
    {"key": "3", "name": "三区", "lo": 21, "hi": 30},
]
KL8_ZONES = [
    {"key": "1", "name": "一区", "lo": 1, "hi": 27},
    {"key": "2", "name": "二区", "lo": 28, "hi": 54},
    {"key": "3", "name": "三区", "lo": 55, "hi": 80},
]
DIGIT_ZONES = [
    {"key": "1", "name": "低区", "lo": 0, "hi": 3},
    {"key": "2", "name": "中区", "lo": 4, "hi": 6},
    {"key": "3", "name": "高区", "lo": 7, "hi": 9},
]
SSQ_SPECIAL_ZONES = [
    {"key": "1", "name": "一区", "lo": 1, "hi": 6},
    {"key": "2", "name": "二区", "lo": 7, "hi": 12},
    {"key": "3", "name": "三区", "lo": 13, "hi": 16},
]
DLT_SPECIAL_ZONES = [
    {"key": "1", "name": "一区", "lo": 1, "hi": 4},
    {"key": "2", "name": "二区", "lo": 5, "hi": 8},
    {"key": "3", "name": "三区", "lo": 9, "hi": 12},
]


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


def _bucket(rows, imbalance):
    found = [item for item in rows if item["imbalance"] == imbalance]
    assert len(found) == 1
    return found[0]


def _counts(a, b, c):
    return {"1": a, "2": b, "3": c}


def _empty_ticket():
    return {
        "zone_counts": None,
        "ratio": None,
        "imbalance": None,
        "percentile": None,
        "typicality": None,
        "rarity": None,
        "alignment": None,
        "note": "",
    }


def test_zone_constants_and_range_bounds_are_not_modulo(db):
    assert THRESHOLD == 0.5
    assert COMMON_LIMIT == 8
    assert DISCLAIMER == "区位脉动看主号三区个数配比和区位偏度，以及短窗相对长窗是更偏还是更匀，仅供娱乐，不构成投注建议。"
    assert zone_summary(db, "ssq")["zones"] == SSQ_ZONES
    assert zone_summary(db, "dlt")["zones"] == DLT_ZONES
    assert zone_summary(db, "qlc")["zones"] == QLC_ZONES
    assert zone_summary(db, "kl8")["zones"] == KL8_ZONES
    assert zone_summary(db, "fc3d")["zones"] == DIGIT_ZONES
    assert zone_summary(db, "pl3")["zones"] == DIGIT_ZONES
    assert zone_summary(db, "pl5")["zones"] == DIGIT_ZONES
    assert zone_summary(db, "qxc")["zones"] == DIGIT_ZONES
    for body in (
        zone_summary(db, "ssq"),
        zone_summary(db, "dlt"),
        zone_summary(db, "qlc"),
        zone_summary(db, "kl8"),
        zone_summary(db, "fc3d"),
    ):
        assert all(set(item) == ZONE_KEYS for item in body["zones"])


def test_set_zone_dedupes_main_and_keeps_special_apart(db):
    _draw(db, "ssq", "2026005", ["01", "08", "09"], ["16"], source="crawl", draw_date="2026-01-09")
    _draw(db, "ssq", "2026004", ["02", "04"], ["03"])
    _draw(db, "ssq", "2026003", [], ["01"])
    _draw(db, "ssq", "2026002", ["05", "05", "07"], ["02"])
    _draw(db, "ssq", "2026001", ["x", "03", "06"], ["04"])

    body = zone_summary(db, "ssq", limit=80, short=10, long=50)
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
    assert "仅供娱乐" in body["disclaimer"]
    assert "不构成投注建议" in body["disclaimer"]
    assert body["note"] == SET_NOTE
    assert body["zones"] == SSQ_ZONES
    assert body["mean"] == 2.25
    assert body["median"] == 2.0
    assert body["short_avg"] == 2.25
    assert body["long_avg"] == 2.25
    assert body["pulse"] == 0.0
    assert body["drift"] == "flat"
    assert body["avg_zone_counts"] == _counts(2.25, 0.0, 0.0)
    assert set(body["avg_zone_counts"]) == COUNT_KEYS
    assert body["latest_draw"] == {
        "issue": "2026005",
        "draw_date": "2026-01-09",
        "main": ["01", "08", "09"],
        "special": ["16"],
        "zone_counts": _counts(3, 0, 0),
        "ratio": "3:0:0",
        "imbalance": 3,
        "special_zone_counts": _counts(0, 0, 1),
        "special_ratio": "0:0:1",
        "special_imbalance": 1,
    }
    assert set(body["latest_draw"]) == LATEST_KEYS
    assert "counts" not in body["latest_draw"]
    assert "prime_count" not in body["latest_draw"]
    assert "odd_count" not in body["latest_draw"]

    distribution = body["distribution"]
    assert [item["imbalance"] for item in distribution] == [2, 3]
    assert all(set(item) == BUCKET_KEYS for item in distribution)
    assert _bucket(distribution, 2) == {"imbalance": 2, "count": 3, "rate": 0.75}
    assert _bucket(distribution, 3) == {"imbalance": 3, "count": 1, "rate": 0.25}
    assert body["common"] == [
        {"zone_counts": _counts(2, 0, 0), "ratio": "2:0:0", "count": 3, "rate": 0.75},
        {"zone_counts": _counts(3, 0, 0), "ratio": "3:0:0", "count": 1, "rate": 0.25},
    ]
    assert all(set(item) == RATIO_KEYS for item in body["common"])

    special = body["special"]
    assert set(special) == SPECIAL_KEYS
    assert special["label"] == "蓝球"
    assert special["zones"] == SSQ_SPECIAL_ZONES
    assert special["sample_size"] == 4
    assert special["mean"] == 1.0
    assert special["median"] == 1.0
    assert special["short_avg"] == 1.0
    assert special["long_avg"] == 1.0
    assert special["pulse"] == 0.0
    assert special["drift"] == "flat"
    assert special["avg_zone_counts"] == _counts(0.75, 0.0, 0.25)
    assert special["distribution"] == [{"imbalance": 1, "count": 4, "rate": 1.0}]
    assert special["common"] == [
        {"zone_counts": _counts(1, 0, 0), "ratio": "1:0:0", "count": 3, "rate": 0.75},
        {"zone_counts": _counts(0, 0, 1), "ratio": "0:0:1", "count": 1, "rate": 0.25},
    ]

    road = road_summary(db, "ssq", limit=80, short=10, long=50)
    assert road["latest_draw"]["imbalance"] == 0
    assert body["latest_draw"]["imbalance"] == 3
    assert "zone_counts" not in road
    assert "avg_zone_counts" not in road


def test_pulse_rises_when_recent_zones_are_more_lopsided(db):
    for index, balls in enumerate([["01", "02", "03"]] * 5 + [["01", "12", "23"]] * 5):
        _draw(db, "ssq", f"{2026010 - index:07d}", balls)

    body = zone_summary(db, "ssq", short=5, long=10)
    assert body["sample_size"] == 10
    assert body["short_avg"] == 3.0
    assert body["long_avg"] == 1.5
    assert body["pulse"] == 1.5
    assert body["drift"] == "rising"
    assert body["mean"] == 1.5
    assert body["median"] == 1.5
    assert body["special"] is None
    assert body["avg_zone_counts"] == _counts(2.0, 0.5, 0.5)
    assert _bucket(body["distribution"], 0)["count"] == 5
    assert _bucket(body["distribution"], 3)["count"] == 5
    assert _bucket(body["distribution"], 1)["count"] == 0
    assert _bucket(body["distribution"], 2)["count"] == 0
    assert body["common"][0]["ratio"] == "1:1:1"
    assert body["common"][1]["ratio"] == "3:0:0"
    assert body["latest_draw"]["ratio"] == "3:0:0"
    assert body["latest_draw"]["special_zone_counts"] is None
    assert body["latest_draw"]["special_ratio"] is None
    assert body["latest_draw"]["special_imbalance"] is None

    road = road_summary(db, "ssq", short=5, long=10)
    assert road["pulse"] == 0.0
    assert road["drift"] == "flat"
    span = span_summary(db, "ssq", short=5, long=10)
    assert span["drift"] == "falling"
    assert span["pulse"] < 0


def test_pulse_threshold_edges(db):
    for index, balls in enumerate([["01", "02", "03", "04"]] * 5 + [["01", "02"]]):
        _draw(db, "ssq", f"{2026106 - index}", balls)
    flat = zone_summary(db, "ssq", short=5, long=20)
    assert flat["sample_size"] == 6
    assert flat["short_avg"] == 4.0
    assert flat["long_avg"] == 3.6667
    assert flat["pulse"] == 0.3333
    assert flat["drift"] == "flat"

    for index, balls in enumerate([["1", "2", "3"]] * 5 + [["0", "4", "7"]]):
        _draw(db, "fc3d", f"{2026206 - index}", balls)
    rising = zone_summary(db, "fc3d", short=5, long=20)
    assert rising["basis"] == "digits"
    assert rising["zones"] == DIGIT_ZONES
    assert rising["short_avg"] == 3.0
    assert rising["long_avg"] == 2.5
    assert rising["pulse"] == 0.5
    assert rising["drift"] == "rising"

    for index, balls in enumerate([["0", "4", "7"]] * 5 + [["1", "2", "3"]]):
        _draw(db, "pl3", f"{2026306 - index}", balls)
    falling = zone_summary(db, "pl3", short=5, long=20)
    assert falling["short_avg"] == 0.0
    assert falling["long_avg"] == 0.5
    assert falling["pulse"] == -0.5
    assert falling["drift"] == "falling"


def test_dlt_special_zone_uses_its_own_bounds(db):
    _draw(db, "dlt", "2026003", ["01", "05", "20"], ["01", "12"], draw_date="2026-02-03")
    _draw(db, "dlt", "2026002", ["03", "04"], ["02", "03"])
    _draw(db, "dlt", "2026001", ["08", "10"], ["05"])
    _draw(db, "dlt", "2026000", ["01", "02"], ["03", "03"])

    body = zone_summary(db, "dlt", short=5, long=20)
    assert body["basis"] == "main"
    assert body["zones"] == DLT_ZONES
    assert body["sample_size"] == 4
    assert body["mean"] == 2.0
    assert body["median"] == 2.0
    assert body["short_avg"] == 2.0
    assert body["latest_draw"]["zone_counts"] == _counts(2, 1, 0)
    assert body["latest_draw"]["ratio"] == "2:1:0"
    assert body["latest_draw"]["imbalance"] == 2
    assert body["latest_draw"]["special_zone_counts"] == _counts(1, 0, 1)
    assert body["latest_draw"]["special_ratio"] == "1:0:1"
    assert body["latest_draw"]["special_imbalance"] == 1
    assert body["latest_draw"]["special"] == ["01", "12"]
    assert 12 not in [int(item) for item in body["latest_draw"]["main"]]

    special = body["special"]
    assert set(special) == SPECIAL_KEYS
    assert special["label"] == "后区"
    assert special["zones"] == DLT_SPECIAL_ZONES
    assert special["sample_size"] == 4
    assert special["mean"] == 1.25
    assert special["median"] == 1.0
    assert special["short_avg"] == 1.25
    assert special["long_avg"] == 1.25
    assert special["pulse"] == 0.0
    assert special["drift"] == "flat"
    assert special["avg_zone_counts"] == _counts(1.0, 0.25, 0.25)
    assert special["common"] == [
        {"zone_counts": _counts(0, 1, 0), "ratio": "0:1:0", "count": 1, "rate": 0.25},
        {"zone_counts": _counts(1, 0, 0), "ratio": "1:0:0", "count": 1, "rate": 0.25},
        {"zone_counts": _counts(1, 0, 1), "ratio": "1:0:1", "count": 1, "rate": 0.25},
        {"zone_counts": _counts(2, 0, 0), "ratio": "2:0:0", "count": 1, "rate": 0.25},
    ]

    _draw(db, "qlc", "2026001", ["01", "03", "09"], ["04"])
    single = zone_summary(db, "qlc")
    assert single["zones"] == QLC_ZONES
    assert single["special"]["label"] == "特别号"
    assert single["special"]["zones"] == QLC_ZONES
    assert single["special"]["sample_size"] == 1
    assert single["latest_draw"]["ratio"] == "3:0:0"
    assert single["latest_draw"]["special_ratio"] == "1:0:0"

    _draw(db, "qlc", "2026002", ["11", "21"], [])
    both = zone_summary(db, "qlc", limit=5)
    assert both["sample_size"] == 2
    assert both["latest_draw"]["issue"] == "2026002"
    assert both["latest_draw"]["ratio"] == "0:1:1"
    assert both["latest_draw"]["special_zone_counts"] is None
    assert both["special"]["sample_size"] == 1


def test_digit_zones_do_not_wrap_zero_and_nine(db):
    _draw(db, "fc3d", "2026004", ["0", "9", "1"], draw_date="2026-03-04")
    _draw(db, "fc3d", "2026003", ["1", "2", "3"])
    _draw(db, "fc3d", "2026002", ["5", "5", "5"])
    _draw(db, "fc3d", "2026001", ["9", "0", "0"])
    _draw(db, "fc3d", "2026000", [], ["1"])
    _draw(db, "qxc", "2026008", ["1", "2", "3", "4", "5", "9"], ["14"])
    _draw(db, "qxc", "2026007", ["7", "7", "7", "7", "7", "7"], ["4"])
    _draw(db, "pl5", "2026008", ["0", "1", "2", "3", "4"])

    body = zone_summary(db, "fc3d")
    assert body["lottery_type"] == "fc3d"
    assert body["mode"] == "digit"
    assert body["basis"] == "digits"
    assert body["note"] == DIGIT_NOTE
    assert "0" in body["note"] and "9" in body["note"]
    assert body["zones"] == DIGIT_ZONES
    assert body["sample_size"] == 4
    assert body["special"] is None
    assert body["mean"] == 2.5
    assert body["median"] == 2.5
    assert body["short_avg"] == 2.5
    assert body["drift"] == "flat"
    assert body["avg_zone_counts"] == _counts(1.75, 0.75, 0.5)
    assert body["latest_draw"]["zone_counts"] == _counts(2, 0, 1)
    assert body["latest_draw"]["ratio"] == "2:0:1"
    assert body["latest_draw"]["imbalance"] == 2
    assert body["latest_draw"]["main"] == ["0", "9", "1"]
    assert body["latest_draw"]["special_zone_counts"] is None
    assert _bucket(body["distribution"], 2) == {"imbalance": 2, "count": 2, "rate": 0.5}
    assert _bucket(body["distribution"], 3) == {"imbalance": 3, "count": 2, "rate": 0.5}
    assert body["common"][0] == {
        "zone_counts": _counts(2, 0, 1),
        "ratio": "2:0:1",
        "count": 2,
        "rate": 0.5,
    }
    assert [item["ratio"] for item in body["common"][1:]] == ["0:3:0", "3:0:0"]

    qxc = zone_summary(db, "qxc")
    assert qxc["basis"] == "digits"
    assert qxc["special"]["zones"] == DIGIT_ZONES
    assert qxc["special"]["label"] == "特别号"
    assert qxc["latest_draw"]["zone_counts"] == _counts(3, 2, 1)
    assert qxc["latest_draw"]["ratio"] == "3:2:1"
    assert qxc["latest_draw"]["special"] == ["14"]
    assert qxc["latest_draw"]["special_zone_counts"] == _counts(0, 0, 1)
    assert qxc["latest_draw"]["special_ratio"] == "0:0:1"
    assert qxc["special"]["sample_size"] == 2
    assert qxc["special"]["common"][0]["ratio"] in {"0:0:1", "0:1:0"}
    older = [item for item in qxc["special"]["common"] if item["ratio"] == "0:1:0"]
    assert older and older[0]["zone_counts"] == _counts(0, 1, 0)

    pl5 = zone_summary(db, "pl5")
    assert pl5["basis"] == "digits"
    assert pl5["special"] is None
    assert pl5["latest_draw"]["zone_counts"] == _counts(4, 1, 0)
    assert pl5["latest_draw"]["ratio"] == "4:1:0"
    assert pl5["latest_draw"]["main"] == ["0", "1", "2", "3", "4"]


def test_blank_main_does_not_consume_the_query_window(db):
    _draw(db, "ssq", "2026001", ["01", "12", "23"])
    _draw(db, "ssq", "2026002", ["01", "12"])
    _draw(db, "ssq", "2026003", ["23"])
    _draw(db, "ssq", "2026004", ["12"])
    _draw(db, "ssq", "2026005", [])
    _draw(db, "ssq", "2026006", ["01"])

    body = zone_summary(db, "ssq", limit=5, short=5, long=20)
    assert body["sample_size"] == 4
    assert body["latest_draw"]["issue"] == "2026006"
    assert body["latest_draw"]["ratio"] == "1:0:0"
    assert "1:1:1" not in [item["ratio"] for item in body["common"]]
    assert body["mean"] == 1.0


def test_score_aligns_with_pulse_and_marks_rarity(db):
    for index, balls in enumerate([["01", "02", "03"]] * 5 + [["01", "12", "23"]] * 5):
        _draw(db, "ssq", f"{2026010 - index:07d}", balls)

    wide = score_zone(db, "ssq", ["01", "02", "03"], ["08"], short=5, long=10)
    assert set(wide) == POST_KEYS
    assert wide["query"] == {"main": ["01", "02", "03"], "special": ["08"]}
    assert set(wide["ticket"]) == TICKET_KEYS
    assert wide["ticket"]["zone_counts"] == _counts(3, 0, 0)
    assert wide["ticket"]["ratio"] == "3:0:0"
    assert wide["ticket"]["imbalance"] == 3
    assert wide["ticket"]["percentile"] == 1.0
    assert wide["ticket"]["typicality"] == 0.5
    assert wide["ticket"]["rarity"] == "common"
    assert wide["ticket"]["alignment"] == "aligned"
    assert wide["ticket"]["note"] == (
        "区位偏度 3，三区比 3:0:0，历史分位 100%，出现率 50%，常见，"
        "短窗 3 比长窗 1.5 更偏，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert wide["special"] is None
    assert wide["special_ticket"]["zone_counts"] == _counts(0, 1, 0)
    assert wide["special_ticket"]["ratio"] == "0:1:0"
    assert wide["special_ticket"]["imbalance"] == 1
    assert wide["special_ticket"]["percentile"] is None
    assert wide["special_ticket"]["alignment"] is None
    assert wide["special_ticket"]["note"] == (
        "区位偏度 1，三区比 0:1:0，还没有历史可对照。仅供娱乐，不构成投注建议。"
    )
    assert wide["drift"] == "rising"

    narrow = score_zone(db, "ssq", "01 12 23", special="16", short=5, long=10)
    assert narrow["ticket"]["zone_counts"] == _counts(1, 1, 1)
    assert narrow["ticket"]["ratio"] == "1:1:1"
    assert narrow["ticket"]["imbalance"] == 0
    assert narrow["ticket"]["percentile"] == 0.5
    assert narrow["ticket"]["typicality"] == 0.5
    assert narrow["ticket"]["rarity"] == "common"
    assert narrow["ticket"]["alignment"] == "against"
    assert "更偏" in narrow["ticket"]["note"]
    assert "反向" in narrow["ticket"]["note"]
    assert "仅供娱乐" in narrow["ticket"]["note"]
    assert narrow["special_ticket"]["ratio"] == "0:0:1"

    rare = score_zone(db, "ssq", ["23", "24", "25", "26", "27", "28"], ["16"], short=5, long=10)
    assert rare["ticket"]["zone_counts"] == _counts(0, 0, 6)
    assert rare["ticket"]["ratio"] == "0:0:6"
    assert rare["ticket"]["imbalance"] == 6
    assert rare["ticket"]["percentile"] == 1.0
    assert rare["ticket"]["typicality"] == 0.0
    assert rare["ticket"]["rarity"] == "rare"
    assert rare["ticket"]["alignment"] == "aligned"
    assert "少见" in rare["ticket"]["note"]

    for index, pair in enumerate([(["01", "13", "25"], ["01", "05"])] * 5 + [(["01", "02", "03"], ["01", "02"])] * 5):
        main, special = pair
        _draw(db, "dlt", f"{2027010 - index:07d}", main, special)

    tight = score_zone(db, "dlt", ["01", "13", "25"], ["01", "05"], short=5, long=10)
    assert tight["drift"] == "falling"
    assert tight["ticket"]["ratio"] == "1:1:1"
    assert tight["ticket"]["imbalance"] == 0
    assert tight["ticket"]["alignment"] == "aligned"
    assert "更匀" in tight["ticket"]["note"]
    assert "同向" in tight["ticket"]["note"]
    assert tight["special"]["zones"] == DLT_SPECIAL_ZONES
    assert tight["special"]["drift"] == "falling"
    assert tight["special"]["short_avg"] == 1.0
    assert tight["special"]["long_avg"] == 1.5
    assert tight["special_ticket"]["zone_counts"] == _counts(1, 1, 0)
    assert tight["special_ticket"]["ratio"] == "1:1:0"
    assert tight["special_ticket"]["imbalance"] == 1
    assert tight["special_ticket"]["alignment"] == "aligned"
    assert tight["special_ticket"]["rarity"] == "common"
    assert "不构成投注建议" in tight["special_ticket"]["note"]

    wide_back = score_zone(db, "dlt", ["01", "02", "03"], ["01", "02"], short=5, long=10)
    assert wide_back["ticket"]["ratio"] == "3:0:0"
    assert wide_back["ticket"]["alignment"] == "against"
    assert wide_back["special_ticket"]["ratio"] == "2:0:0"
    assert wide_back["special_ticket"]["alignment"] == "against"
    assert wide_back["special_ticket"]["percentile"] == 1.0
    assert wide_back["special_ticket"]["typicality"] == 0.5

    one_back = score_zone(db, "dlt", ["01", "13", "25"], ["03"], short=5, long=10)
    assert one_back["special_ticket"]["ratio"] == "1:0:0"
    assert one_back["special_ticket"]["imbalance"] == 1
    assert one_back["special_ticket"]["alignment"] == "aligned"
    assert one_back["special_ticket"] != _empty_ticket()


def test_digit_score_uses_whole_ticket_not_wrap(db):
    _draw(db, "fc3d", "2026004", ["0", "9", "1"])
    _draw(db, "fc3d", "2026003", ["1", "2", "3"])
    _draw(db, "fc3d", "2026002", ["5", "5", "5"])
    _draw(db, "fc3d", "2026001", ["9", "0", "0"])

    body = score_zone(db, "fc3d", ["0", "9", "1"])
    assert body["basis"] == "digits"
    assert body["ticket"]["zone_counts"] == _counts(2, 0, 1)
    assert body["ticket"]["ratio"] == "2:0:1"
    assert body["ticket"]["imbalance"] == 2
    assert body["ticket"]["percentile"] == 0.5
    assert body["ticket"]["typicality"] == 0.5
    assert body["ticket"]["rarity"] == "common"
    assert body["ticket"]["alignment"] == "neutral"
    assert body["ticket"]["note"] == (
        "区位偏度 2，三区比 2:0:1，历史分位 50%，出现率 50%，常见，"
        "短窗 2.5 和长窗 2.5 差不多，没有明显顺逆。仅供娱乐，不构成投注建议。"
    )
    assert body["special_ticket"] == _empty_ticket()

    low = score_zone(db, "pl3", [1, 3, 5])
    assert low["sample_size"] == 0
    assert low["ticket"]["zone_counts"] == _counts(2, 1, 0)
    assert low["ticket"]["ratio"] == "2:1:0"
    assert low["ticket"]["imbalance"] == 2
    assert low["ticket"]["percentile"] is None
    assert low["ticket"]["rarity"] is None
    assert low["ticket"]["alignment"] is None
    assert low["ticket"]["note"] == "区位偏度 2，三区比 2:1:0，还没有历史可对照。仅供娱乐，不构成投注建议。"

    for index in range(3):
        _draw(db, "fc3d", f"202600{7 - index}", ["1", "1", "1"])
    mid = score_zone(db, "fc3d", ["0", "9", "1"])
    assert mid["ticket"]["imbalance"] == 2
    assert mid["ticket"]["percentile"] == 0.2857
    assert mid["ticket"]["typicality"] == 0.2857
    assert mid["ticket"]["rarity"] == "typical"
    assert mid["ticket"]["alignment"] == "neutral"
    assert "居中" in mid["ticket"]["note"]


def test_empty_history_parameter_clamp_and_common_cap(db):
    empty = zone_summary(db, "kl8", limit="no", short=None, long="bad")
    assert empty["lottery_type"] == "kl8"
    assert empty["sample_size"] == 0
    assert empty["short"] == 10
    assert empty["long"] == 50
    assert empty["zones"] == KL8_ZONES
    assert empty["distribution"] == []
    assert empty["common"] == []
    assert empty["mean"] is None
    assert empty["median"] is None
    assert empty["short_avg"] is None
    assert empty["long_avg"] is None
    assert empty["pulse"] is None
    assert empty["drift"] is None
    assert empty["avg_zone_counts"] is None
    assert empty["latest_draw"] is None
    assert empty["special"] is None
    assert empty["data_status"] == "seed"
    assert empty["basis"] == "main"

    scored = score_zone(db, "kl8", ["01", "28"])
    assert scored["ticket"]["zone_counts"] == _counts(1, 1, 0)
    assert scored["ticket"]["ratio"] == "1:1:0"
    assert scored["ticket"]["imbalance"] == 1
    assert scored["ticket"]["percentile"] is None
    assert scored["ticket"]["note"] == "区位偏度 1，三区比 1:1:0，还没有历史可对照。仅供娱乐，不构成投注建议。"
    assert scored["special_ticket"] == _empty_ticket()

    for total in range(1, 7):
        _draw(db, "kl8", f"202600{total}", [f"{n:02d}" for n in range(1, total + 1)])
    clamped = zone_summary(db, "kl8", limit=1, short=1, long=1)
    assert clamped["short"] == 5
    assert clamped["long"] == 20
    assert clamped["sample_size"] == 5
    assert clamped["latest_draw"]["ratio"] == "6:0:0"
    assert clamped["latest_draw"]["imbalance"] == 6
    assert clamped["mean"] == 4.0

    opened = zone_summary(db, "kl8", short=30, long=20)
    assert opened["short"] == 30
    assert opened["long"] == 31
    assert opened["sample_size"] == 6
    assert opened["mean"] == 3.5

    ratios = [
        ["01"],
        ["01", "12"],
        ["01", "12", "23"],
        ["01", "02"],
        ["12", "13"],
        ["23", "24"],
        ["01", "02", "03"],
        ["12", "13", "14"],
        ["23", "24", "25"],
    ]
    for index, balls in enumerate(ratios):
        _draw(db, "ssq", f"202610{index}", balls)
    capped = zone_summary(db, "ssq")
    assert capped["sample_size"] == 9
    assert len(capped["common"]) == 8
    assert all(item["count"] == 1 and item["rate"] == 0.1111 for item in capped["common"])
    assert capped["common"][0]["ratio"] == "0:0:2"
    assert "3:0:0" not in [item["ratio"] for item in capped["common"]]

    with pytest.raises(ValueError, match="未知彩种"):
        zone_summary(db, "nope")
    with pytest.raises(ValueError, match="未知彩种"):
        score_zone(db, "nope", ["01"])
    with pytest.raises(ValueError):
        score_zone(db, "ssq", ["01", "01", "03", "04", "05", "06"], ["01"])
    with pytest.raises(ValueError):
        score_zone(db, "fc3d", ["1", "2"])
    with pytest.raises(ValueError):
        score_zone(db, "kl8", ["01", "02"], ["03"])


def test_zone_endpoints_bounds_and_old_contracts(client, db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "12", "23", "33"], ["16"], draw_date="2026-04-01")
    _draw(db, "ssq", "2026002", ["05", "07", "09", "11", "13", "15"], ["02"], source="crawl", draw_date="2026-04-03")

    res = client.get("/api/analysis/ssq/zone")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == GET_KEYS
    assert body["sample_size"] == 2
    assert body["short"] == 10
    assert body["long"] == 50
    assert body["basis"] == "main"
    assert body["zones"] == SSQ_ZONES
    assert body["disclaimer"] == DISCLAIMER
    assert body["data_status"] == "mixed"
    assert body["latest_draw"]["ratio"] == "4:2:0"
    assert body["latest_draw"]["imbalance"] == 4
    assert body["latest_draw"]["special_ratio"] == "1:0:0"
    assert body["mean"] == 3.0
    assert body["special"]["zones"] == SSQ_SPECIAL_ZONES
    assert "sum" not in body
    assert "odd_count" not in body
    assert "prime_count" not in body
    assert "avg_road_counts" not in body
    assert body["common"][0]["ratio"] == "3:1:2"

    custom = client.get("/api/analysis/ssq/zone", params={"limit": 80, "short": 5, "long": 20})
    assert custom.status_code == 200
    assert custom.json()["short"] == 5
    assert custom.json()["long"] == 20

    widened = client.get("/api/analysis/ssq/zone", params={"short": 30, "long": 20})
    assert widened.status_code == 200
    assert widened.json()["short"] == 30
    assert widened.json()["long"] == 31

    assert client.get("/api/analysis/ssq/zone", params={"limit": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/zone", params={"limit": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/zone", params={"short": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/zone", params={"short": 31}).status_code == 422
    assert client.get("/api/analysis/ssq/zone", params={"long": 19}).status_code == 422
    assert client.get("/api/analysis/ssq/zone", params={"long": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/zone", params={"limit": 5, "short": 5, "long": 20}).status_code == 200
    assert client.get("/api/analysis/ssq/zone", params={"limit": 200, "short": 30, "long": 200}).status_code == 200

    unknown = client.get("/api/analysis/nope/zone")
    assert unknown.status_code == 400
    assert "未知彩种" in unknown.json()["detail"]

    empty = client.get("/api/analysis/kl8/zone")
    assert empty.status_code == 200
    assert empty.json()["sample_size"] == 0
    assert empty.json()["latest_draw"] is None
    assert empty.json()["distribution"] == []
    assert empty.json()["drift"] is None
    assert empty.json()["zones"] == KL8_ZONES

    alias = client.get("/api/analysis/3d/zone")
    assert alias.status_code == 200
    assert alias.json()["lottery_type"] == "fc3d"
    assert alias.json()["mode"] == "digit"
    assert alias.json()["basis"] == "digits"
    assert alias.json()["zones"] == DIGIT_ZONES

    posted = client.post(
        "/api/analysis/ssq/zone/score",
        json={"main": "01 02 03 12 23 33", "special": "16", "limit": 80, "short": 10, "long": 50},
    )
    assert posted.status_code == 200, posted.text
    scored = posted.json()
    assert set(scored) == POST_KEYS
    assert scored["query"] == {"main": ["01", "02", "03", "12", "23", "33"], "special": ["16"]}
    assert scored["ticket"]["ratio"] == "3:1:2"
    assert scored["ticket"]["imbalance"] == 2
    assert scored["ticket"]["rarity"] == "common"
    assert scored["ticket"]["alignment"] == "neutral"
    assert scored["special_ticket"]["ratio"] == "0:0:1"
    assert "仅供娱乐" in scored["ticket"]["note"]

    spaced = client.post("/api/analysis/3d/zone/score", json={"main": ["0", "9", "1"], "short": 5, "long": 20})
    assert spaced.status_code == 200
    assert spaced.json()["lottery_type"] == "fc3d"
    assert spaced.json()["ticket"]["ratio"] == "2:0:1"
    assert spaced.json()["ticket"]["zone_counts"] == _counts(2, 0, 1)
    assert spaced.json()["mode"] == "digit"

    bad = client.post("/api/analysis/ssq/zone/score", json={"main": ["99"], "special": ["01"]})
    assert bad.status_code == 400
    duplicate = client.post(
        "/api/analysis/ssq/zone/score",
        json={"main": ["01", "01", "03", "04", "05", "06"], "special": ["01"]},
    )
    assert duplicate.status_code == 400
    short = client.post("/api/analysis/fc3d/zone/score", json={"main": ["1", "2"]})
    assert short.status_code == 400
    extra = client.post("/api/analysis/kl8/zone/score", json={"main": ["01", "02"], "special": ["03"]})
    assert extra.status_code == 400
    unknown_post = client.post("/api/analysis/nope/zone/score", json={"main": ["01"]})
    assert unknown_post.status_code == 400
    assert client.post("/api/analysis/ssq/zone/score", json={"main": ["01"], "limit": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/zone/score", json={"main": ["01"], "short": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/zone/score", json={"main": ["01"], "long": 201}).status_code == 422

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
    assert "pulse" not in analysis.json()
    assert "zone_counts" not in analysis.json()
    assert "ratio" not in analysis.json()

    shape = client.get("/api/analysis/ssq/shape")
    assert shape.status_code == 200
    shape_body = shape.json()
    assert "pulse" not in shape_body
    assert "distribution" not in shape_body
    assert "drift" not in shape_body
    assert "imbalance" not in shape_body
    assert [item["label"] for item in shape_body["zones"]] == ["一区 01–11", "二区 12–22", "三区 23–33"]
    direct = shape_stats(db, "ssq", limit=50)
    assert [item["label"] for item in direct["zones"]] == ["一区 01–11", "二区 12–22", "三区 23–33"]
    assert "pulse" not in direct

    road = client.get("/api/analysis/ssq/road")
    assert road.status_code == 200
    assert "zone_counts" not in road.json()
    assert "avg_zone_counts" not in road.json()
    assert road.json()["latest_draw"]["counts"]["0"] == 2

    parity = client.get("/api/analysis/ssq/parity")
    assert parity.status_code == 200
    assert "zone_counts" not in parity.json()

    prime = client.get("/api/analysis/ssq/prime")
    assert prime.status_code == 200
    assert "zone_counts" not in prime.json()
