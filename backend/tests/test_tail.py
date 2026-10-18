"""尾数脉动：主号不重复个位的种类数，以及短窗相对长窗是更散还是更集中。

乐透按主号集合去重后取个位，23 的尾数是 3；同一尾数的不同号码只算一种。
数字彩各位本身就是尾数，0 与 9 不绕圈。特别号单独统计，不并进主号。
尾数种类不是除以 3 的余数，不是数值区间，也不是跨度或和值。
短窗、长窗用实际有的期数求平均，缺口不当成种类数 0。
只读本地开奖，不改其他分析接口的返回形状。
"""
from __future__ import annotations

import json

import pytest

from app.models import Draw
from app.services.pulse_ensemble import PULSE_MODULES, _MEMO_TARGETS
from app.services.road import road_summary
from app.services.shape import shape_stats
from app.services.span import span_summary
from app.services.sum_pulse import sum_summary
from app.services.tail import (
    COMMON_LIMIT,
    DIGIT_NOTE,
    DISCLAIMER,
    SET_NOTE,
    THRESHOLD,
    score_tail,
    tail_summary,
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

BUCKET_KEYS = {"unique_tail_count", "count", "rate"}
COMBO_KEYS = {"tails", "pattern", "unique_tail_count", "count", "rate"}
TICKET_KEYS = {
    "tails",
    "pattern",
    "unique_tail_count",
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
    "tails",
    "pattern",
    "unique_tail_count",
    "special_tails",
    "special_pattern",
    "special_unique_tail_count",
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


def _bucket(rows, unique_tail_count):
    found = [item for item in rows if item["unique_tail_count"] == unique_tail_count]
    assert len(found) == 1
    return found[0]


def _combo(tails, count, rate):
    digits = [str(item) for item in tails]
    return {
        "tails": digits,
        "pattern": ",".join(digits),
        "unique_tail_count": len(digits),
        "count": count,
        "rate": rate,
    }


def _empty_ticket():
    return {
        "tails": None,
        "pattern": None,
        "unique_tail_count": None,
        "percentile": None,
        "typicality": None,
        "rarity": None,
        "alignment": None,
        "note": "",
    }


def test_tail_constants_distinguish_the_metric():
    assert THRESHOLD == 0.5
    assert COMMON_LIMIT == 8
    assert "仅供娱乐" in DISCLAIMER
    assert "不构成投注建议" in DISCLAIMER
    assert "尾数" in SET_NOTE and "特别号" in SET_NOTE
    assert "0" in DIGIT_NOTE and "9" in DIGIT_NOTE
    keys = [item.key for item in PULSE_MODULES]
    assert "tail" in keys
    assert [item.label for item in PULSE_MODULES if item.key == "tail"] == ["尾数"]
    assert ("app.services.tail", "tail_summary") in _MEMO_TARGETS


def test_set_tail_collapses_same_last_digit_and_keeps_special_apart(db):
    _draw(db, "ssq", "2026005", ["01", "11", "21"], ["16"], source="crawl", draw_date="2026-01-09")
    _draw(db, "ssq", "2026004", ["02", "04"], ["03"])
    _draw(db, "ssq", "2026003", [], ["01"])
    _draw(db, "ssq", "2026002", ["05", "05", "07"], ["02"])
    _draw(db, "ssq", "2026001", ["x", "03", "13"], ["04"])

    body = tail_summary(db, "ssq", limit=80, short=10, long=50)
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
    assert body["note"] == SET_NOTE
    assert body["mean"] == 1.5
    assert body["median"] == 1.5
    assert body["short_avg"] == 1.5
    assert body["long_avg"] == 1.5
    assert body["pulse"] == 0.0
    assert body["drift"] == "flat"
    assert body["latest_draw"] == {
        "issue": "2026005",
        "draw_date": "2026-01-09",
        "main": ["01", "11", "21"],
        "special": ["16"],
        "tails": ["1"],
        "pattern": "1",
        "unique_tail_count": 1,
        "special_tails": ["6"],
        "special_pattern": "6",
        "special_unique_tail_count": 1,
    }
    assert set(body["latest_draw"]) == LATEST_KEYS
    assert "zone_counts" not in body["latest_draw"]
    assert "imbalance" not in body["latest_draw"]
    assert "prime_count" not in body["latest_draw"]

    distribution = body["distribution"]
    assert [item["unique_tail_count"] for item in distribution] == [1, 2]
    assert all(set(item) == BUCKET_KEYS for item in distribution)
    assert _bucket(distribution, 1) == {"unique_tail_count": 1, "count": 2, "rate": 0.5}
    assert _bucket(distribution, 2) == {"unique_tail_count": 2, "count": 2, "rate": 0.5}
    assert body["common"] == [
        _combo([1], 1, 0.25),
        _combo([2, 4], 1, 0.25),
        _combo([3], 1, 0.25),
        _combo([5, 7], 1, 0.25),
    ]
    assert all(set(item) == COMBO_KEYS for item in body["common"])

    special = body["special"]
    assert set(special) == SPECIAL_KEYS
    assert special["label"] == "蓝球"
    assert special["sample_size"] == 4
    assert special["mean"] == 1.0
    assert special["median"] == 1.0
    assert special["short_avg"] == 1.0
    assert special["long_avg"] == 1.0
    assert special["pulse"] == 0.0
    assert special["drift"] == "flat"
    assert special["distribution"] == [{"unique_tail_count": 1, "count": 4, "rate": 1.0}]
    assert special["common"] == [
        _combo([2], 1, 0.25),
        _combo([3], 1, 0.25),
        _combo([4], 1, 0.25),
        _combo([6], 1, 0.25),
    ]

    road = road_summary(db, "ssq", limit=80, short=10, long=50)
    assert road["latest_draw"]["imbalance"] == 0
    assert body["latest_draw"]["unique_tail_count"] == 1
    assert "unique_tail_count" not in road
    assert "tails" not in road["latest_draw"]


def test_zero_and_nine_stay_apart_and_differ_from_road_zone_span_sum(db):
    _draw(db, "ssq", "2026001", ["10", "20", "23", "33"], ["09"])
    body = tail_summary(db, "ssq")
    assert body["latest_draw"]["tails"] == ["0", "3"]
    assert body["latest_draw"]["pattern"] == "0,3"
    assert body["latest_draw"]["unique_tail_count"] == 2
    assert body["latest_draw"]["special_tails"] == ["9"]
    assert body["latest_draw"]["special_unique_tail_count"] == 1

    road = road_summary(db, "ssq")
    zone = zone_summary(db, "ssq")
    span = span_summary(db, "ssq")
    summed = sum_summary(db, "ssq")
    assert road["latest_draw"]["imbalance"] == 1
    assert zone["latest_draw"]["imbalance"] == 1
    assert zone["latest_draw"]["ratio"] == "1:1:2"
    assert span["latest_draw"]["span"] == 23
    assert summed["latest_draw"]["sum"] == 86
    assert body["pulse"] == 0.0
    assert "unique_tail_count" not in zone
    assert "unique_tail_count" not in span
    assert "unique_tail_count" not in summed


def test_pulse_rises_when_recent_tails_are_more_diverse(db):
    for index, balls in enumerate([["01", "02", "03"]] * 5 + [["01", "11", "21"]] * 5):
        _draw(db, "ssq", f"{2026010 - index:07d}", balls)

    body = tail_summary(db, "ssq", short=5, long=10)
    assert body["sample_size"] == 10
    assert body["short_avg"] == 3.0
    assert body["long_avg"] == 2.0
    assert body["pulse"] == 1.0
    assert body["drift"] == "rising"
    assert body["mean"] == 2.0
    assert body["median"] == 2.0
    assert body["special"] is None
    assert _bucket(body["distribution"], 1)["count"] == 5
    assert _bucket(body["distribution"], 2)["count"] == 0
    assert _bucket(body["distribution"], 3)["count"] == 5
    assert body["common"] == [
        _combo([1], 5, 0.5),
        _combo([1, 2, 3], 5, 0.5),
    ]
    assert body["latest_draw"]["pattern"] == "1,2,3"
    assert body["latest_draw"]["unique_tail_count"] == 3
    assert body["latest_draw"]["special_tails"] is None
    assert body["latest_draw"]["special_pattern"] is None
    assert body["latest_draw"]["special_unique_tail_count"] is None

    road = road_summary(db, "ssq", short=5, long=10)
    assert road["pulse"] == 0.0
    assert road["drift"] == "flat"
    span = span_summary(db, "ssq", short=5, long=10)
    assert span["drift"] == "falling"
    assert span["pulse"] < 0
    zone = zone_summary(db, "ssq", short=5, long=10)
    assert zone["pulse"] == 0.5
    assert body["pulse"] != zone["pulse"]
    summed = sum_summary(db, "ssq", short=5, long=10)
    assert summed["drift"] == "falling"


def test_pulse_threshold_edges(db):
    for index, balls in enumerate([["01", "02", "03"]] * 5 + [["01", "11"]]):
        _draw(db, "ssq", f"{2026106 - index}", balls)
    flat = tail_summary(db, "ssq", short=5, long=20)
    assert flat["sample_size"] == 6
    assert flat["short_avg"] == 3.0
    assert flat["long_avg"] == 2.6667
    assert flat["pulse"] == 0.3333
    assert flat["drift"] == "flat"

    for index, balls in enumerate([["01", "02", "03", "04"]] * 5 + [["01", "11"]]):
        _draw(db, "dlt", f"{2026206 - index}", balls)
    rising = tail_summary(db, "dlt", short=5, long=20)
    assert rising["basis"] == "main"
    assert rising["short_avg"] == 4.0
    assert rising["long_avg"] == 3.5
    assert rising["pulse"] == 0.5
    assert rising["drift"] == "rising"

    for index, balls in enumerate([["1", "1", "1"]] * 5 + [["0", "1", "2", "3"]]):
        _draw(db, "pl5", f"{2026306 - index}", balls)
    falling = tail_summary(db, "pl5", short=5, long=20)
    assert falling["basis"] == "digits"
    assert falling["short_avg"] == 1.0
    assert falling["long_avg"] == 1.5
    assert falling["pulse"] == -0.5
    assert falling["drift"] == "falling"


def test_dlt_special_tails_stay_out_of_main(db):
    _draw(db, "dlt", "2026003", ["01", "11", "20"], ["01", "12"], draw_date="2026-02-03")
    _draw(db, "dlt", "2026002", ["03", "13"], ["02", "03"])
    _draw(db, "dlt", "2026001", ["08", "18"], ["05"])
    _draw(db, "dlt", "2026000", ["01", "02"], ["03", "13"])

    body = tail_summary(db, "dlt", short=5, long=20)
    assert body["basis"] == "main"
    assert body["sample_size"] == 4
    assert body["mean"] == 1.5
    assert body["median"] == 1.5
    assert body["short_avg"] == 1.5
    assert body["latest_draw"]["tails"] == ["0", "1"]
    assert body["latest_draw"]["pattern"] == "0,1"
    assert body["latest_draw"]["unique_tail_count"] == 2
    assert body["latest_draw"]["special_tails"] == ["1", "2"]
    assert body["latest_draw"]["special_pattern"] == "1,2"
    assert body["latest_draw"]["special_unique_tail_count"] == 2
    assert body["latest_draw"]["special"] == ["01", "12"]
    assert 12 not in [int(item) for item in body["latest_draw"]["main"]]

    special = body["special"]
    assert set(special) == SPECIAL_KEYS
    assert special["label"] == "后区"
    assert special["sample_size"] == 4
    assert special["mean"] == 1.5
    assert special["median"] == 1.5
    assert special["short_avg"] == 1.5
    assert special["long_avg"] == 1.5
    assert special["pulse"] == 0.0
    assert special["drift"] == "flat"
    assert special["common"] == [
        _combo([1, 2], 1, 0.25),
        _combo([2, 3], 1, 0.25),
        _combo([3], 1, 0.25),
        _combo([5], 1, 0.25),
    ]

    _draw(db, "qlc", "2026001", ["01", "03", "09"], ["04"])
    single = tail_summary(db, "qlc")
    assert single["special"]["label"] == "特别号"
    assert single["special"]["sample_size"] == 1
    assert single["latest_draw"]["pattern"] == "1,3,9"
    assert single["latest_draw"]["unique_tail_count"] == 3
    assert single["latest_draw"]["special_pattern"] == "4"
    assert single["latest_draw"]["special_unique_tail_count"] == 1

    _draw(db, "qlc", "2026002", ["11", "21"], [])
    both = tail_summary(db, "qlc", limit=5)
    assert both["sample_size"] == 2
    assert both["latest_draw"]["issue"] == "2026002"
    assert both["latest_draw"]["pattern"] == "1"
    assert both["latest_draw"]["unique_tail_count"] == 1
    assert both["latest_draw"]["special_tails"] is None
    assert both["special"]["sample_size"] == 1


def test_digit_tails_do_not_wrap_zero_and_nine(db):
    _draw(db, "fc3d", "2026004", ["0", "9", "1"], draw_date="2026-03-04")
    _draw(db, "fc3d", "2026003", ["1", "2", "3"])
    _draw(db, "fc3d", "2026002", ["5", "5", "5"])
    _draw(db, "fc3d", "2026001", ["9", "0", "0"])
    _draw(db, "fc3d", "2026000", [], ["1"])
    _draw(db, "qxc", "2026008", ["1", "2", "3", "4", "5", "9"], ["14"])
    _draw(db, "qxc", "2026007", ["7", "7", "7", "7", "7", "7"], ["4"])
    _draw(db, "pl5", "2026008", ["0", "1", "2", "3", "4"])

    body = tail_summary(db, "fc3d")
    assert body["lottery_type"] == "fc3d"
    assert body["mode"] == "digit"
    assert body["basis"] == "digits"
    assert body["note"] == DIGIT_NOTE
    assert body["sample_size"] == 4
    assert body["special"] is None
    assert body["mean"] == 2.25
    assert body["median"] == 2.5
    assert body["short_avg"] == 2.25
    assert body["drift"] == "flat"
    assert body["latest_draw"]["tails"] == ["0", "1", "9"]
    assert body["latest_draw"]["pattern"] == "0,1,9"
    assert body["latest_draw"]["unique_tail_count"] == 3
    assert body["latest_draw"]["main"] == ["0", "9", "1"]
    assert body["latest_draw"]["special_tails"] is None
    assert _bucket(body["distribution"], 1) == {"unique_tail_count": 1, "count": 1, "rate": 0.25}
    assert _bucket(body["distribution"], 2) == {"unique_tail_count": 2, "count": 1, "rate": 0.25}
    assert _bucket(body["distribution"], 3) == {"unique_tail_count": 3, "count": 2, "rate": 0.5}
    assert body["common"] == [
        _combo([0, 1, 9], 1, 0.25),
        _combo([0, 9], 1, 0.25),
        _combo([1, 2, 3], 1, 0.25),
        _combo([5], 1, 0.25),
    ]

    qxc = tail_summary(db, "qxc")
    assert qxc["basis"] == "digits"
    assert qxc["special"]["label"] == "特别号"
    assert qxc["latest_draw"]["pattern"] == "1,2,3,4,5,9"
    assert qxc["latest_draw"]["unique_tail_count"] == 6
    assert qxc["latest_draw"]["special"] == ["14"]
    assert qxc["latest_draw"]["special_tails"] == ["4"]
    assert qxc["latest_draw"]["special_pattern"] == "4"
    assert qxc["latest_draw"]["special_unique_tail_count"] == 1
    assert qxc["special"]["sample_size"] == 2
    assert qxc["special"]["common"] == [
        _combo([4], 2, 1.0),
    ]

    pl5 = tail_summary(db, "pl5")
    assert pl5["basis"] == "digits"
    assert pl5["special"] is None
    assert pl5["latest_draw"]["pattern"] == "0,1,2,3,4"
    assert pl5["latest_draw"]["unique_tail_count"] == 5
    assert pl5["latest_draw"]["main"] == ["0", "1", "2", "3", "4"]


def test_blank_main_does_not_consume_the_query_window(db):
    _draw(db, "ssq", "2026001", ["01", "12", "23"])
    _draw(db, "ssq", "2026002", ["01", "12"])
    _draw(db, "ssq", "2026003", ["23"])
    _draw(db, "ssq", "2026004", ["12"])
    _draw(db, "ssq", "2026005", [])
    _draw(db, "ssq", "2026006", ["01"])

    body = tail_summary(db, "ssq", limit=5, short=5, long=20)
    assert body["sample_size"] == 4
    assert body["latest_draw"]["issue"] == "2026006"
    assert body["latest_draw"]["pattern"] == "1"
    assert body["latest_draw"]["unique_tail_count"] == 1
    assert body["mean"] == 1.25


def test_score_aligns_with_pulse_and_marks_rarity(db):
    for index, balls in enumerate([["01", "02", "03"]] * 5 + [["01", "11", "21"]] * 5):
        _draw(db, "ssq", f"{2026010 - index:07d}", balls)

    wide = score_tail(db, "ssq", ["01", "02", "03"], ["08"], short=5, long=10)
    assert set(wide) == POST_KEYS
    assert wide["query"] == {"main": ["01", "02", "03"], "special": ["08"]}
    assert set(wide["ticket"]) == TICKET_KEYS
    assert wide["ticket"]["tails"] == ["1", "2", "3"]
    assert wide["ticket"]["pattern"] == "1,2,3"
    assert wide["ticket"]["unique_tail_count"] == 3
    assert wide["ticket"]["percentile"] == 1.0
    assert wide["ticket"]["typicality"] == 0.5
    assert wide["ticket"]["rarity"] == "common"
    assert wide["ticket"]["alignment"] == "aligned"
    assert wide["ticket"]["note"] == (
        "尾数种类 3，尾数组合 1、2、3，历史分位 100%，出现率 50%，常见，"
        "短窗 3 比长窗 2 更散，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert wide["special"] is None
    assert wide["special_ticket"]["tails"] == ["8"]
    assert wide["special_ticket"]["pattern"] == "8"
    assert wide["special_ticket"]["unique_tail_count"] == 1
    assert wide["special_ticket"]["percentile"] is None
    assert wide["special_ticket"]["alignment"] is None
    assert wide["special_ticket"]["note"] == (
        "尾数种类 1，尾数组合 8，还没有历史可对照。仅供娱乐，不构成投注建议。"
    )
    assert wide["drift"] == "rising"

    narrow = score_tail(db, "ssq", "01 11 21", special="16", short=5, long=10)
    assert narrow["ticket"]["pattern"] == "1"
    assert narrow["ticket"]["unique_tail_count"] == 1
    assert narrow["ticket"]["percentile"] == 0.5
    assert narrow["ticket"]["typicality"] == 0.5
    assert narrow["ticket"]["rarity"] == "common"
    assert narrow["ticket"]["alignment"] == "against"
    assert narrow["ticket"]["note"] == (
        "尾数种类 1，尾数组合 1，历史分位 50%，出现率 50%，常见，"
        "短窗 3 比长窗 2 更散，和短窗脉动反向。仅供娱乐，不构成投注建议。"
    )
    assert narrow["special_ticket"]["pattern"] == "6"

    rare = score_tail(db, "ssq", ["23", "24", "25", "26", "27", "28"], ["16"], short=5, long=10)
    assert rare["ticket"]["pattern"] == "3,4,5,6,7,8"
    assert rare["ticket"]["unique_tail_count"] == 6
    assert rare["ticket"]["percentile"] == 1.0
    assert rare["ticket"]["typicality"] == 0.0
    assert rare["ticket"]["rarity"] == "rare"
    assert rare["ticket"]["alignment"] == "aligned"
    assert "少见" in rare["ticket"]["note"]
    assert "仅供娱乐" in rare["ticket"]["note"]

    for index, pair in enumerate([(["01", "11"], ["01", "11"])] * 5 + [(["01", "02", "03", "04"], ["01", "02"])] * 5):
        main, special = pair
        _draw(db, "dlt", f"{2027010 - index:07d}", main, special)

    tight = score_tail(db, "dlt", ["01", "11"], ["01", "11"], short=5, long=10)
    assert tight["drift"] == "falling"
    assert tight["ticket"]["unique_tail_count"] == 1
    assert tight["ticket"]["alignment"] == "aligned"
    assert tight["ticket"]["note"] == (
        "尾数种类 1，尾数组合 1，历史分位 50%，出现率 50%，常见，"
        "短窗 1 比长窗 2.5 更集中，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert tight["special"]["drift"] == "falling"
    assert tight["special"]["short_avg"] == 1.0
    assert tight["special"]["long_avg"] == 1.5
    assert tight["special_ticket"]["pattern"] == "1"
    assert tight["special_ticket"]["unique_tail_count"] == 1
    assert tight["special_ticket"]["alignment"] == "aligned"
    assert tight["special_ticket"]["rarity"] == "common"
    assert "不构成投注建议" in tight["special_ticket"]["note"]

    wide_back = score_tail(db, "dlt", ["01", "02", "03", "04"], ["01", "02"], short=5, long=10)
    assert wide_back["ticket"]["pattern"] == "1,2,3,4"
    assert wide_back["ticket"]["alignment"] == "against"
    assert wide_back["special_ticket"]["pattern"] == "1,2"
    assert wide_back["special_ticket"]["unique_tail_count"] == 2
    assert wide_back["special_ticket"]["alignment"] == "against"
    assert wide_back["special_ticket"]["percentile"] == 1.0
    assert wide_back["special_ticket"]["typicality"] == 0.5

    one_back = score_tail(db, "dlt", ["01", "11"], ["03"], short=5, long=10)
    assert one_back["special_ticket"]["pattern"] == "3"
    assert one_back["special_ticket"]["unique_tail_count"] == 1
    assert one_back["special_ticket"]["alignment"] == "aligned"
    assert one_back["special_ticket"] != _empty_ticket()


def test_digit_score_uses_whole_ticket_not_wrap(db):
    _draw(db, "fc3d", "2026004", ["0", "9", "1"])
    _draw(db, "fc3d", "2026003", ["1", "2", "3"])
    _draw(db, "fc3d", "2026002", ["5", "5", "5"])
    _draw(db, "fc3d", "2026001", ["9", "0", "0"])

    body = score_tail(db, "fc3d", ["0", "9", "1"])
    assert body["basis"] == "digits"
    assert body["ticket"]["tails"] == ["0", "1", "9"]
    assert body["ticket"]["pattern"] == "0,1,9"
    assert body["ticket"]["unique_tail_count"] == 3
    assert body["ticket"]["percentile"] == 1.0
    assert body["ticket"]["typicality"] == 0.5
    assert body["ticket"]["rarity"] == "common"
    assert body["ticket"]["alignment"] == "neutral"
    assert body["ticket"]["note"] == (
        "尾数种类 3，尾数组合 0、1、9，历史分位 100%，出现率 50%，常见，"
        "短窗 2.25 和长窗 2.25 差不多，没有明显顺逆。仅供娱乐，不构成投注建议。"
    )
    assert body["special_ticket"] == _empty_ticket()

    low = score_tail(db, "pl3", [1, 3, 5])
    assert low["sample_size"] == 0
    assert low["ticket"]["pattern"] == "1,3,5"
    assert low["ticket"]["unique_tail_count"] == 3
    assert low["ticket"]["percentile"] is None
    assert low["ticket"]["rarity"] is None
    assert low["ticket"]["alignment"] is None
    assert low["ticket"]["note"] == "尾数种类 3，尾数组合 1、3、5，还没有历史可对照。仅供娱乐，不构成投注建议。"

    for index in range(3):
        _draw(db, "fc3d", f"202600{7 - index}", ["1", "1", "1"])
    mid = score_tail(db, "fc3d", ["9", "0", "0"])
    assert mid["ticket"]["unique_tail_count"] == 2
    assert mid["ticket"]["pattern"] == "0,9"
    assert mid["ticket"]["percentile"] == 0.7143
    assert mid["ticket"]["typicality"] == 0.1429
    assert mid["ticket"]["rarity"] == "typical"
    assert mid["ticket"]["alignment"] == "neutral"
    assert "居中" in mid["ticket"]["note"]
    assert "差不多" in mid["ticket"]["note"]


def test_empty_history_parameter_clamp_and_common_cap(db):
    empty = tail_summary(db, "kl8", limit="no", short=None, long="bad")
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
    assert empty["note"] == SET_NOTE

    scored = score_tail(db, "kl8", ["01", "28"])
    assert scored["ticket"]["pattern"] == "1,8"
    assert scored["ticket"]["unique_tail_count"] == 2
    assert scored["ticket"]["percentile"] is None
    assert scored["ticket"]["note"] == "尾数种类 2，尾数组合 1、8，还没有历史可对照。仅供娱乐，不构成投注建议。"
    assert scored["special_ticket"] == _empty_ticket()

    for total in range(1, 7):
        _draw(db, "kl8", f"202600{total}", [f"{n:02d}" for n in range(1, total + 1)])
    clamped = tail_summary(db, "kl8", limit=1, short=1, long=1)
    assert clamped["short"] == 5
    assert clamped["long"] == 20
    assert clamped["sample_size"] == 5
    assert clamped["latest_draw"]["pattern"] == "1,2,3,4,5,6"
    assert clamped["latest_draw"]["unique_tail_count"] == 6
    assert clamped["mean"] == 4.0

    opened = tail_summary(db, "kl8", short=30, long=20)
    assert opened["short"] == 30
    assert opened["long"] == 31
    assert opened["sample_size"] == 6
    assert opened["mean"] == 3.5

    for index, digit in enumerate(range(1, 10)):
        _draw(db, "ssq", f"202610{index}", [f"{digit:02d}"])
    capped = tail_summary(db, "ssq")
    assert capped["sample_size"] == 9
    assert len(capped["common"]) == 8
    assert all(item["count"] == 1 and item["rate"] == 0.1111 for item in capped["common"])
    assert capped["common"][0]["pattern"] == "1"
    assert "9" not in [item["pattern"] for item in capped["common"]]

    with pytest.raises(ValueError, match="未知彩种"):
        tail_summary(db, "nope")
    with pytest.raises(ValueError, match="未知彩种"):
        score_tail(db, "nope", ["01"])
    with pytest.raises(ValueError):
        score_tail(db, "ssq", ["01", "01", "03", "04", "05", "06"], ["01"])
    with pytest.raises(ValueError):
        score_tail(db, "fc3d", ["1", "2"])
    with pytest.raises(ValueError):
        score_tail(db, "kl8", ["01", "02"], ["03"])


def test_tail_endpoints_bounds_and_old_contracts(client, db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "12", "23", "33"], ["16"], draw_date="2026-04-01")
    _draw(db, "ssq", "2026002", ["05", "07", "09", "11", "13", "15"], ["02"], source="crawl", draw_date="2026-04-03")

    res = client.get("/api/analysis/ssq/tail")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == GET_KEYS
    assert body["sample_size"] == 2
    assert body["short"] == 10
    assert body["long"] == 50
    assert body["basis"] == "main"
    assert body["disclaimer"] == DISCLAIMER
    assert "仅供娱乐" in body["disclaimer"]
    assert body["data_status"] == "mixed"
    assert body["latest_draw"]["pattern"] == "1,3,5,7,9"
    assert body["latest_draw"]["unique_tail_count"] == 5
    assert body["latest_draw"]["special_pattern"] == "2"
    assert body["mean"] == 4.0
    assert body["special"]["label"] == "蓝球"
    assert "sum" not in body
    assert "odd_count" not in body
    assert "prime_count" not in body
    assert "zone_counts" not in body
    assert "avg_road_counts" not in body
    assert body["common"][0]["pattern"] == "1,2,3"

    custom = client.get("/api/analysis/ssq/tail", params={"limit": 80, "short": 5, "long": 20})
    assert custom.status_code == 200
    assert custom.json()["short"] == 5
    assert custom.json()["long"] == 20

    widened = client.get("/api/analysis/ssq/tail", params={"short": 30, "long": 20})
    assert widened.status_code == 200
    assert widened.json()["short"] == 30
    assert widened.json()["long"] == 31

    assert client.get("/api/analysis/ssq/tail", params={"limit": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/tail", params={"limit": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/tail", params={"short": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/tail", params={"short": 31}).status_code == 422
    assert client.get("/api/analysis/ssq/tail", params={"long": 19}).status_code == 422
    assert client.get("/api/analysis/ssq/tail", params={"long": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/tail", params={"limit": 5, "short": 5, "long": 20}).status_code == 200
    assert client.get("/api/analysis/ssq/tail", params={"limit": 200, "short": 30, "long": 200}).status_code == 200

    unknown = client.get("/api/analysis/nope/tail")
    assert unknown.status_code == 400
    assert "未知彩种" in unknown.json()["detail"]

    empty = client.get("/api/analysis/kl8/tail")
    assert empty.status_code == 200
    assert empty.json()["sample_size"] == 0
    assert empty.json()["latest_draw"] is None
    assert empty.json()["distribution"] == []
    assert empty.json()["drift"] is None

    alias = client.get("/api/analysis/3d/tail")
    assert alias.status_code == 200
    assert alias.json()["lottery_type"] == "fc3d"
    assert alias.json()["mode"] == "digit"
    assert alias.json()["basis"] == "digits"

    posted = client.post(
        "/api/analysis/ssq/tail/score",
        json={"main": "01 02 03 12 23 33", "special": "16", "limit": 80, "short": 10, "long": 50},
    )
    assert posted.status_code == 200, posted.text
    scored = posted.json()
    assert set(scored) == POST_KEYS
    assert scored["query"] == {"main": ["01", "02", "03", "12", "23", "33"], "special": ["16"]}
    assert scored["ticket"]["pattern"] == "1,2,3"
    assert scored["ticket"]["unique_tail_count"] == 3
    assert scored["ticket"]["rarity"] == "common"
    assert scored["ticket"]["alignment"] == "neutral"
    assert scored["special_ticket"]["pattern"] == "6"
    assert "仅供娱乐" in scored["ticket"]["note"]

    spaced = client.post("/api/analysis/3d/tail/score", json={"main": ["0", "9", "1"], "short": 5, "long": 20})
    assert spaced.status_code == 200
    assert spaced.json()["lottery_type"] == "fc3d"
    assert spaced.json()["ticket"]["pattern"] == "0,1,9"
    assert spaced.json()["ticket"]["unique_tail_count"] == 3
    assert spaced.json()["mode"] == "digit"

    bad = client.post("/api/analysis/ssq/tail/score", json={"main": ["99"], "special": ["01"]})
    assert bad.status_code == 400
    duplicate = client.post(
        "/api/analysis/ssq/tail/score",
        json={"main": ["01", "01", "03", "04", "05", "06"], "special": ["01"]},
    )
    assert duplicate.status_code == 400
    short = client.post("/api/analysis/fc3d/tail/score", json={"main": ["1", "2"]})
    assert short.status_code == 400
    extra = client.post("/api/analysis/kl8/tail/score", json={"main": ["01", "02"], "special": ["03"]})
    assert extra.status_code == 400
    unknown_post = client.post("/api/analysis/nope/tail/score", json={"main": ["01"]})
    assert unknown_post.status_code == 400
    assert client.post("/api/analysis/ssq/tail/score", json={"main": ["01"], "limit": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/tail/score", json={"main": ["01"], "short": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/tail/score", json={"main": ["01"], "long": 201}).status_code == 422

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
    assert "unique_tail_count" not in analysis.json()
    assert "tails" not in analysis.json()

    shape = client.get("/api/analysis/ssq/shape")
    assert shape.status_code == 200
    shape_body = shape.json()
    assert "pulse" not in shape_body
    assert "unique_tail_count" not in shape_body
    assert "drift" not in shape_body
    direct = shape_stats(db, "ssq", limit=50)
    assert "unique_tail_count" not in direct
    assert "pulse" not in direct

    zone = client.get("/api/analysis/ssq/zone")
    assert zone.status_code == 200
    assert "unique_tail_count" not in zone.json()
    assert "tails" not in zone.json()["latest_draw"]

    road = client.get("/api/analysis/ssq/road")
    assert road.status_code == 200
    assert "unique_tail_count" not in road.json()

    parity = client.get("/api/analysis/ssq/parity")
    assert parity.status_code == 200
    assert "unique_tail_count" not in parity.json()

    prime = client.get("/api/analysis/ssq/prime")
    assert prime.status_code == 200
    assert "unique_tail_count" not in prime.json()
