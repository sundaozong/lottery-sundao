"""和尾脉动：主号和值个位的历史分布，以及短窗相对长窗的升降。

乐透按主号集合去重后求和，再取个位。数字彩按整注各位求和取个位，重复数字保留，
0 与 9 不绕圈。特别号不并进主号；至少有一个特别号时另算 special_hewei。
空白主号跳过，不占窗口名额。这不是原始和值，也不是不重复尾数的种类数。
短窗、长窗用实际算出和尾的期数求平均，缺口不当成 0。
只读本地开奖，不改其他分析接口的返回形状。
"""
from __future__ import annotations

import json

import pytest

from app.models import Draw
from app.services.hewei import (
    COMMON_LIMIT,
    DIGIT_NOTE,
    DISCLAIMER,
    SET_NOTE,
    THRESHOLD,
    hewei_summary,
    score_hewei,
)
from app.services.pulse_ensemble import PULSE_MODULES, _MEMO_TARGETS
from app.services.shape import shape_stats
from app.services.sum_pulse import sum_summary
from app.services.tail import tail_summary

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

BUCKET_KEYS = {"hewei", "count", "rate"}
COMMON_KEYS = {"hewei", "count", "rate"}
TICKET_KEYS = {"hewei", "percentile", "typicality", "rarity", "alignment", "note"}
LATEST_KEYS = {"issue", "draw_date", "main", "special", "hewei", "special_hewei"}
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


def _bucket(rows, hewei):
    found = [item for item in rows if item["hewei"] == hewei]
    assert len(found) == 1
    return found[0]


def _empty_ticket():
    return {
        "hewei": None,
        "percentile": None,
        "typicality": None,
        "rarity": None,
        "alignment": None,
        "note": "",
    }


def test_hewei_constants_distinguish_the_metric():
    assert THRESHOLD == 0.5
    assert COMMON_LIMIT == 8
    assert "仅供娱乐" in DISCLAIMER
    assert "不构成投注建议" in DISCLAIMER
    assert "和尾" in DISCLAIMER
    assert "特别号" in SET_NOTE
    assert "和值" in SET_NOTE
    assert "尾数" in SET_NOTE
    assert "0" in DIGIT_NOTE and "9" in DIGIT_NOTE
    keys = [item.key for item in PULSE_MODULES]
    assert keys[-2] == "hewei"
    assert keys[-1] == "daxiao"
    assert [item.label for item in PULSE_MODULES if item.key == "hewei"] == ["和尾"]
    assert ("app.services.hewei", "hewei_summary") in _MEMO_TARGETS


def test_known_sums_take_units_digit_and_keep_single_mains(db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["16"])
    first = hewei_summary(db, "ssq")
    assert first["latest_draw"]["hewei"] == 1
    assert first["latest_draw"]["special_hewei"] == 6

    _draw(db, "ssq", "2026002", ["01", "02", "04"], ["08"])
    second = hewei_summary(db, "ssq")
    assert second["latest_draw"]["hewei"] == 7
    assert second["latest_draw"]["special_hewei"] == 8

    _draw(db, "ssq", "2026003", ["01", "05", "08", "12", "20", "33"], ["09"])
    third = hewei_summary(db, "ssq")
    assert third["latest_draw"]["hewei"] == 9
    assert third["latest_draw"]["special_hewei"] == 9
    assert "sum" not in third["latest_draw"]
    assert "unique_tail_count" not in third["latest_draw"]
    assert "ac_value" not in third["latest_draw"]

    _draw(db, "ssq", "2026004", ["01"], ["02"])
    body = hewei_summary(db, "ssq", limit=5)
    assert body["latest_draw"]["issue"] == "2026004"
    assert body["latest_draw"]["main"] == ["01"]
    assert body["latest_draw"]["hewei"] == 1
    assert body["latest_draw"]["special_hewei"] == 2
    assert body["sample_size"] == 4
    assert body["mean"] == 4.5
    assert [item["hewei"] for item in body["distribution"]] == list(range(10))
    assert _bucket(body["distribution"], 1)["count"] == 2
    assert _bucket(body["distribution"], 7)["count"] == 1
    assert _bucket(body["distribution"], 9)["count"] == 1
    assert all(item["count"] == 0 for item in body["distribution"] if item["hewei"] not in (1, 7, 9))


def test_set_hewei_dedupes_main_and_keeps_special_apart(db):
    _draw(db, "ssq", "2026005", ["01", "11", "21"], ["16"], source="crawl", draw_date="2026-01-09")
    _draw(db, "ssq", "2026004", ["02", "04", "07"], ["03"])
    _draw(db, "ssq", "2026003", [], ["01"])
    _draw(db, "ssq", "2026002", ["05", "05"], ["02"])
    _draw(db, "ssq", "2026001", ["x", "03", "13", "16"], ["04"])

    body = hewei_summary(db, "ssq", limit=80, short=10, long=50)
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
    assert body["mean"] == 3.25
    assert body["median"] == 3.0
    assert body["short_avg"] == 3.25
    assert body["long_avg"] == 3.25
    assert body["pulse"] == 0.0
    assert body["drift"] == "flat"
    assert set(body["latest_draw"]) == LATEST_KEYS
    assert body["latest_draw"]["issue"] == "2026005"
    assert body["latest_draw"]["main"] == ["01", "11", "21"]
    assert body["latest_draw"]["special"] == ["16"]
    assert body["latest_draw"]["hewei"] == 3
    assert body["latest_draw"]["special_hewei"] == 6
    assert [item["hewei"] for item in body["distribution"]] == list(range(10))
    assert all(set(item) == BUCKET_KEYS for item in body["distribution"])
    assert _bucket(body["distribution"], 2) == {"hewei": 2, "count": 1, "rate": 0.25}
    assert _bucket(body["distribution"], 3) == {"hewei": 3, "count": 2, "rate": 0.5}
    assert _bucket(body["distribution"], 5) == {"hewei": 5, "count": 1, "rate": 0.25}
    assert _bucket(body["distribution"], 0)["count"] == 0
    assert body["common"] == [
        {"hewei": 3, "count": 2, "rate": 0.5},
        {"hewei": 2, "count": 1, "rate": 0.25},
        {"hewei": 5, "count": 1, "rate": 0.25},
    ]
    assert all(set(item) == COMMON_KEYS for item in body["common"])

    special = body["special"]
    assert set(special) == SPECIAL_KEYS
    assert special["label"] == "蓝球"
    assert special["sample_size"] == 4
    assert special["mean"] == 3.75
    assert special["median"] == 3.5
    assert _bucket(special["distribution"], 6)["count"] == 1
    assert special["common"][0]["hewei"] == 2


def test_hewei_is_not_sum_or_tail(db):
    _draw(db, "ssq", "2026001", ["10", "20", "23", "33"], ["09"])
    body = hewei_summary(db, "ssq")
    assert body["latest_draw"]["hewei"] == 6
    assert body["latest_draw"]["special_hewei"] == 9

    summed = sum_summary(db, "ssq")
    tail = tail_summary(db, "ssq")
    assert summed["latest_draw"]["sum"] == 86
    assert tail["latest_draw"]["unique_tail_count"] == 2
    assert body["latest_draw"]["hewei"] != summed["latest_draw"]["sum"]
    assert body["latest_draw"]["hewei"] != tail["latest_draw"]["unique_tail_count"]
    assert "hewei" not in summed
    assert "hewei" not in tail
    assert "sum" not in body
    assert "unique_tail_count" not in body


def test_pulse_rises_when_recent_hewei_is_higher(db):
    for index, balls in enumerate([["09"]] * 5 + [["01"]] * 5):
        _draw(db, "ssq", f"{2026010 - index:07d}", balls)

    body = hewei_summary(db, "ssq", short=5, long=10)
    assert body["sample_size"] == 10
    assert body["short_avg"] == 9.0
    assert body["long_avg"] == 5.0
    assert body["pulse"] == 4.0
    assert body["drift"] == "rising"
    assert body["mean"] == 5.0
    assert body["median"] == 5.0
    assert _bucket(body["distribution"], 1)["count"] == 5
    assert _bucket(body["distribution"], 9)["count"] == 5
    assert _bucket(body["distribution"], 0)["count"] == 0
    assert body["common"] == [
        {"hewei": 1, "count": 5, "rate": 0.5},
        {"hewei": 9, "count": 5, "rate": 0.5},
    ]
    assert body["latest_draw"]["hewei"] == 9
    assert body["latest_draw"]["special_hewei"] is None

    tail = tail_summary(db, "ssq", short=5, long=10)
    assert tail["latest_draw"]["unique_tail_count"] == 1
    assert tail["pulse"] == 0.0
    assert tail["drift"] == "flat"
    summed = sum_summary(db, "ssq", short=5, long=10)
    assert summed["latest_draw"]["sum"] == 9
    assert summed["pulse"] == 4.0


def test_pulse_threshold_edges(db):
    for index, balls in enumerate([["02"]] * 5 + [["10"]]):
        _draw(db, "ssq", f"{2026106 - index}", balls)
    flat = hewei_summary(db, "ssq", short=5, long=20)
    assert flat["sample_size"] == 6
    assert flat["short_avg"] == 2.0
    assert flat["long_avg"] == pytest.approx(1.6667)
    assert flat["pulse"] == pytest.approx(0.3333)
    assert flat["drift"] == "flat"

    for index, balls in enumerate([["03"]] * 5 + [["10"]]):
        _draw(db, "dlt", f"{2026206 - index}", balls)
    rising = hewei_summary(db, "dlt", short=5, long=20)
    assert rising["basis"] == "main"
    assert rising["short_avg"] == 3.0
    assert rising["long_avg"] == 2.5
    assert rising["pulse"] == 0.5
    assert rising["drift"] == "rising"

    for index, balls in enumerate([["0", "0", "0", "0", "0"]] * 5 + [["0", "0", "0", "0", "3"]]):
        _draw(db, "pl5", f"{2026306 - index}", balls)
    falling = hewei_summary(db, "pl5", short=5, long=20)
    assert falling["basis"] == "digits"
    assert falling["short_avg"] == 0.0
    assert falling["long_avg"] == 0.5
    assert falling["pulse"] == -0.5
    assert falling["drift"] == "falling"


def test_dlt_special_hewei_counts_a_single_ball(db):
    _draw(db, "dlt", "2026003", ["01", "02", "04"], ["01", "12"], draw_date="2026-02-03")
    _draw(db, "dlt", "2026002", ["01", "02", "03"], ["02", "03"])
    _draw(db, "dlt", "2026001", ["08", "18"], ["05"])
    _draw(db, "dlt", "2026000", ["01", "02", "04", "07"], ["01", "02", "04"])

    body = hewei_summary(db, "dlt", short=5, long=20)
    assert body["basis"] == "main"
    assert body["sample_size"] == 4
    assert body["latest_draw"]["main"] == ["01", "02", "04"]
    assert body["latest_draw"]["special"] == ["01", "12"]
    assert body["latest_draw"]["hewei"] == 7
    assert body["latest_draw"]["special_hewei"] == 3
    assert 12 not in [int(item) for item in body["latest_draw"]["main"]]
    assert body["mean"] == 5.75
    assert body["median"] == 6.0

    special = body["special"]
    assert set(special) == SPECIAL_KEYS
    assert special["label"] == "后区"
    assert special["sample_size"] == 4
    assert special["mean"] == 5.0
    assert special["median"] == 5.0
    assert special["short_avg"] == 5.0
    assert special["long_avg"] == 5.0
    assert special["pulse"] == 0.0
    assert special["drift"] == "flat"
    assert [item["hewei"] for item in special["distribution"]] == list(range(10))
    assert _bucket(special["distribution"], 3)["count"] == 1
    assert _bucket(special["distribution"], 5)["count"] == 2
    assert _bucket(special["distribution"], 7)["count"] == 1
    assert special["common"][0]["hewei"] == 5

    _draw(db, "qlc", "2026001", ["01", "03", "09"], ["04"])
    single = hewei_summary(db, "qlc")
    assert single["special"]["label"] == "特别号"
    assert single["special"]["sample_size"] == 1
    assert single["special"]["mean"] == 4.0
    assert single["latest_draw"]["hewei"] == 3
    assert single["latest_draw"]["special_hewei"] == 4

    _draw(db, "qlc", "2026002", ["01", "02", "04", "08"], [])
    bare = hewei_summary(db, "qlc", limit=5)
    assert bare["sample_size"] == 2
    assert bare["latest_draw"]["issue"] == "2026002"
    assert bare["latest_draw"]["hewei"] == 5
    assert bare["latest_draw"]["special_hewei"] is None
    assert bare["special"]["sample_size"] == 1


def test_digit_hewei_keeps_repeats_and_does_not_wrap(db):
    _draw(db, "fc3d", "2026004", ["0", "9", "1"], draw_date="2026-03-04")
    _draw(db, "fc3d", "2026003", ["1", "2", "3"])
    _draw(db, "fc3d", "2026002", ["5", "5", "5"])
    _draw(db, "fc3d", "2026001", ["9", "0", "0"])
    _draw(db, "fc3d", "2026000", [], ["1"])
    _draw(db, "qxc", "2026008", ["1", "2", "3", "4", "5", "9"], ["14"])
    _draw(db, "pl5", "2026008", ["0", "1", "2", "3", "4"])

    body = hewei_summary(db, "fc3d")
    assert body["lottery_type"] == "fc3d"
    assert body["mode"] == "digit"
    assert body["basis"] == "digits"
    assert body["note"] == DIGIT_NOTE
    assert body["sample_size"] == 4
    assert body["special"] is None
    assert body["mean"] == 5.0
    assert body["median"] == 5.5
    assert body["short_avg"] == 5.0
    assert body["drift"] == "flat"
    assert body["latest_draw"]["main"] == ["0", "9", "1"]
    assert body["latest_draw"]["hewei"] == 0
    assert body["latest_draw"]["special_hewei"] is None
    assert _bucket(body["distribution"], 0) == {"hewei": 0, "count": 1, "rate": 0.25}
    assert _bucket(body["distribution"], 5) == {"hewei": 5, "count": 1, "rate": 0.25}
    assert _bucket(body["distribution"], 6) == {"hewei": 6, "count": 1, "rate": 0.25}
    assert _bucket(body["distribution"], 9) == {"hewei": 9, "count": 1, "rate": 0.25}
    assert body["common"] == [
        {"hewei": 0, "count": 1, "rate": 0.25},
        {"hewei": 5, "count": 1, "rate": 0.25},
        {"hewei": 6, "count": 1, "rate": 0.25},
        {"hewei": 9, "count": 1, "rate": 0.25},
    ]

    qxc = hewei_summary(db, "qxc")
    assert qxc["basis"] == "digits"
    assert qxc["latest_draw"]["hewei"] == 4
    assert qxc["latest_draw"]["special"] == ["14"]
    assert qxc["latest_draw"]["special_hewei"] == 4
    assert qxc["special"]["sample_size"] == 1
    assert qxc["special"]["mean"] == 4.0

    pl5 = hewei_summary(db, "pl5")
    assert pl5["basis"] == "digits"
    assert pl5["special"] is None
    assert pl5["latest_draw"]["hewei"] == 0
    assert pl5["latest_draw"]["main"] == ["0", "1", "2", "3", "4"]


def test_blank_main_does_not_consume_the_analysis_window(db):
    _draw(db, "ssq", "2026001", ["01", "12", "23"])
    _draw(db, "ssq", "2026002", ["01", "12"])
    _draw(db, "ssq", "2026003", ["23"])
    _draw(db, "ssq", "2026004", ["12"])
    _draw(db, "ssq", "2026005", [])
    _draw(db, "ssq", "2026006", ["01", "02", "04"])

    body = hewei_summary(db, "ssq", limit=5, short=5, long=20)
    assert body["sample_size"] == 4
    assert body["latest_draw"]["issue"] == "2026006"
    assert body["latest_draw"]["hewei"] == 7
    assert body["mean"] == 3.75
    assert body["latest_draw"]["issue"] != "2026001"


def test_score_aligns_with_pulse_and_marks_rarity(db):
    for index, balls in enumerate([["04"]] * 5 + [["10"]] * 5):
        _draw(db, "ssq", f"{2026010 - index:07d}", balls)

    wide = score_hewei(db, "ssq", ["04"], ["08"], short=5, long=10)
    assert set(wide) == POST_KEYS
    assert wide["query"] == {"main": ["04"], "special": ["08"]}
    assert set(wide["ticket"]) == TICKET_KEYS
    assert wide["ticket"]["hewei"] == 4
    assert wide["ticket"]["percentile"] == 1.0
    assert wide["ticket"]["typicality"] == 0.5
    assert wide["ticket"]["rarity"] == "common"
    assert wide["ticket"]["alignment"] == "aligned"
    assert wide["ticket"]["note"] == (
        "和尾 4，历史分位 100%，出现率 50%，常见，"
        "短窗 4 比长窗 2 走高，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert wide["special"] is None
    assert wide["special_ticket"]["hewei"] == 8
    assert wide["special_ticket"]["percentile"] is None
    assert wide["special_ticket"]["alignment"] is None
    assert wide["special_ticket"]["note"] == "和尾 8，还没有历史可对照。仅供娱乐，不构成投注建议。"
    assert wide["drift"] == "rising"

    narrow = score_hewei(db, "ssq", "10", special="16", short=5, long=10)
    assert narrow["ticket"]["hewei"] == 0
    assert narrow["ticket"]["percentile"] == 0.5
    assert narrow["ticket"]["typicality"] == 0.5
    assert narrow["ticket"]["rarity"] == "common"
    assert narrow["ticket"]["alignment"] == "against"
    assert narrow["ticket"]["note"] == (
        "和尾 0，历史分位 50%，出现率 50%，常见，"
        "短窗 4 比长窗 2 走高，和短窗脉动反向。仅供娱乐，不构成投注建议。"
    )
    assert narrow["special_ticket"]["hewei"] == 6
    assert narrow["special_ticket"]["percentile"] is None

    rare = score_hewei(db, "ssq", ["09"], ["01", "03"], short=5, long=10)
    assert rare["ticket"]["hewei"] == 9
    assert rare["ticket"]["percentile"] == 1.0
    assert rare["ticket"]["typicality"] == 0.0
    assert rare["ticket"]["rarity"] == "rare"
    assert rare["ticket"]["alignment"] == "aligned"
    assert "少见" in rare["ticket"]["note"]
    assert "仅供娱乐" in rare["ticket"]["note"]
    assert rare["special_ticket"]["hewei"] == 4
    assert rare["special_ticket"]["note"] == "和尾 4，还没有历史可对照。仅供娱乐，不构成投注建议。"

    for index, pair in enumerate(
        [(["01", "02", "03", "04"], ["01", "02", "04"])] * 5
        + [(["01", "02", "04", "08"], ["01", "02", "03"])] * 5
    ):
        main, special = pair
        _draw(db, "dlt", f"{2027010 - index:07d}", main, special)

    tight = score_hewei(db, "dlt", ["01", "02", "03", "04"], ["01", "02", "04"], short=5, long=10)
    assert tight["drift"] == "falling"
    assert tight["ticket"]["hewei"] == 0
    assert tight["ticket"]["alignment"] == "aligned"
    assert tight["ticket"]["note"] == (
        "和尾 0，历史分位 50%，出现率 50%，常见，"
        "短窗 0 比长窗 2.5 走低，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert tight["special"]["drift"] == "rising"
    assert tight["special"]["short_avg"] == 7.0
    assert tight["special"]["long_avg"] == 6.5
    assert tight["special_ticket"]["hewei"] == 7
    assert tight["special_ticket"]["alignment"] == "aligned"
    assert tight["special_ticket"]["rarity"] == "common"
    assert "不构成投注建议" in tight["special_ticket"]["note"]

    wide_back = score_hewei(db, "dlt", ["01", "02", "04", "08"], ["01", "02", "03"], short=5, long=10)
    assert wide_back["ticket"]["hewei"] == 5
    assert wide_back["ticket"]["alignment"] == "against"
    assert wide_back["special_ticket"]["hewei"] == 6
    assert wide_back["special_ticket"]["alignment"] == "against"
    assert wide_back["special_ticket"]["percentile"] == 0.5
    assert wide_back["special_ticket"]["typicality"] == 0.5


def test_digit_score_uses_listed_digits(db):
    _draw(db, "fc3d", "2026004", ["0", "9", "1"])
    _draw(db, "fc3d", "2026003", ["1", "2", "3"])
    _draw(db, "fc3d", "2026002", ["5", "5", "5"])
    _draw(db, "fc3d", "2026001", ["9", "0", "0"])

    body = score_hewei(db, "fc3d", ["0", "9", "1"])
    assert body["basis"] == "digits"
    assert body["ticket"]["hewei"] == 0
    assert body["ticket"]["percentile"] == 0.25
    assert body["ticket"]["typicality"] == 0.25
    assert body["ticket"]["rarity"] == "common"
    assert body["ticket"]["alignment"] == "neutral"
    assert body["ticket"]["note"] == (
        "和尾 0，历史分位 25%，出现率 25%，常见，"
        "短窗 5 和长窗 5 差不多，没有明显顺逆。仅供娱乐，不构成投注建议。"
    )
    assert body["special_ticket"] == _empty_ticket()

    repeated = score_hewei(db, "fc3d", ["5", "5", "5"])
    assert repeated["ticket"]["hewei"] == 5
    assert repeated["ticket"]["percentile"] == 0.5
    assert repeated["ticket"]["typicality"] == 0.25
    assert repeated["ticket"]["rarity"] == "common"
    assert repeated["ticket"]["alignment"] == "neutral"
    assert "常见" in repeated["ticket"]["note"]
    assert "差不多" in repeated["ticket"]["note"]

    low = score_hewei(db, "pl3", [1, 2, 4])
    assert low["sample_size"] == 0
    assert low["ticket"]["hewei"] == 7
    assert low["ticket"]["percentile"] is None
    assert low["ticket"]["rarity"] is None
    assert low["ticket"]["alignment"] is None
    assert low["ticket"]["note"] == "和尾 7，还没有历史可对照。仅供娱乐，不构成投注建议。"

    for index, balls in enumerate([["1", "0", "0"]] * 4 + [["5", "0", "0"], ["9", "0", "0"]]):
        _draw(db, "pl3", f"{2026010 - index:07d}", balls)
    mid = score_hewei(db, "pl3", ["5", "0", "0"])
    assert mid["ticket"]["hewei"] == 5
    assert mid["ticket"]["percentile"] == pytest.approx(0.8333)
    assert mid["ticket"]["typicality"] == pytest.approx(0.1667)
    assert mid["ticket"]["rarity"] == "typical"
    assert mid["ticket"]["alignment"] == "neutral"
    assert mid["ticket"]["note"] == (
        "和尾 5，历史分位 83.33%，出现率 16.67%，居中，"
        "短窗 3 和长窗 3 差不多，没有明显顺逆。仅供娱乐，不构成投注建议。"
    )


def test_empty_history_parameter_clamp_and_common_cap(db):
    empty = hewei_summary(db, "kl8", limit="no", short=None, long="bad")
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

    scored = score_hewei(db, "kl8", ["01", "02", "04"])
    assert scored["ticket"]["hewei"] == 7
    assert scored["ticket"]["percentile"] is None
    assert scored["ticket"]["note"] == "和尾 7，还没有历史可对照。仅供娱乐，不构成投注建议。"
    assert scored["special_ticket"] == _empty_ticket()

    one = score_hewei(db, "kl8", ["01"])
    assert one["ticket"]["hewei"] == 1
    assert one["ticket"]["note"] == "和尾 1，还没有历史可对照。仅供娱乐，不构成投注建议。"

    for index, balls in enumerate([[f"{number:02d}"] for number in range(10, 20)], start=1):
        _draw(db, "kl8", f"2026{index:03d}", balls)
    clamped = hewei_summary(db, "kl8", limit=1, short=1, long=1)
    assert clamped["short"] == 5
    assert clamped["long"] == 20
    assert clamped["sample_size"] == 5
    assert clamped["latest_draw"]["hewei"] == 9

    opened = hewei_summary(db, "kl8", short=30, long=20)
    assert opened["short"] == 30
    assert opened["long"] == 31
    assert opened["sample_size"] == 10

    capped = hewei_summary(db, "kl8")
    assert capped["sample_size"] == 10
    assert len(capped["distribution"]) == 10
    assert len(capped["common"]) == 8
    assert all(item["count"] == 1 and item["rate"] == 0.1 for item in capped["common"])
    assert capped["common"][0]["hewei"] == 0
    assert 8 not in [item["hewei"] for item in capped["common"]]
    assert 9 not in [item["hewei"] for item in capped["common"]]

    with pytest.raises(ValueError, match="未知彩种"):
        hewei_summary(db, "nope")
    with pytest.raises(ValueError, match="未知彩种"):
        score_hewei(db, "nope", ["01"])
    with pytest.raises(ValueError):
        score_hewei(db, "ssq", ["01", "01", "03", "04", "05", "06"], ["01"])
    with pytest.raises(ValueError):
        score_hewei(db, "fc3d", ["1", "2"])
    with pytest.raises(ValueError):
        score_hewei(db, "kl8", ["01", "02"], ["03"])


def test_hewei_endpoints_bounds_and_old_contracts(client, db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["16"], draw_date="2026-04-01")
    _draw(db, "ssq", "2026002", ["01", "05", "08", "12", "20", "33"], ["02"], source="crawl", draw_date="2026-04-03")

    res = client.get("/api/analysis/ssq/hewei")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == GET_KEYS
    assert body["sample_size"] == 2
    assert body["short"] == 10
    assert body["long"] == 50
    assert body["basis"] == "main"
    assert body["disclaimer"] == DISCLAIMER
    assert "仅供娱乐" in body["disclaimer"]
    assert "不构成投注建议" in body["disclaimer"]
    assert body["data_status"] == "mixed"
    assert body["latest_draw"]["hewei"] == 9
    assert body["latest_draw"]["special_hewei"] == 2
    assert body["mean"] == 5.0
    assert body["pulse"] == 0.0
    assert body["drift"] == "flat"
    assert body["special"]["sample_size"] == 2
    assert "sum" not in body
    assert "unique_tail_count" not in body
    assert "ac_value" not in body
    assert "odd_count" not in body
    assert "prime_count" not in body
    assert body["distribution"][0]["hewei"] == 0
    assert _bucket(body["distribution"], 9)["count"] == 1
    assert _bucket(body["distribution"], 1)["count"] == 1

    custom = client.get("/api/analysis/ssq/hewei", params={"limit": 80, "short": 5, "long": 20})
    assert custom.status_code == 200
    assert custom.json()["short"] == 5
    assert custom.json()["long"] == 20

    widened = client.get("/api/analysis/ssq/hewei", params={"short": 30, "long": 20})
    assert widened.status_code == 200
    assert widened.json()["short"] == 30
    assert widened.json()["long"] == 31

    assert client.get("/api/analysis/ssq/hewei", params={"limit": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/hewei", params={"limit": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/hewei", params={"short": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/hewei", params={"short": 31}).status_code == 422
    assert client.get("/api/analysis/ssq/hewei", params={"long": 19}).status_code == 422
    assert client.get("/api/analysis/ssq/hewei", params={"long": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/hewei", params={"limit": 5, "short": 5, "long": 20}).status_code == 200
    assert client.get("/api/analysis/ssq/hewei", params={"limit": 200, "short": 30, "long": 200}).status_code == 200

    unknown = client.get("/api/analysis/nope/hewei")
    assert unknown.status_code == 400
    assert "未知彩种" in unknown.json()["detail"]

    empty = client.get("/api/analysis/kl8/hewei")
    assert empty.status_code == 200
    assert empty.json()["sample_size"] == 0
    assert empty.json()["latest_draw"] is None
    assert empty.json()["distribution"] == []
    assert empty.json()["drift"] is None

    alias = client.get("/api/analysis/3d/hewei")
    assert alias.status_code == 200
    assert alias.json()["lottery_type"] == "fc3d"
    assert alias.json()["mode"] == "digit"
    assert alias.json()["basis"] == "digits"

    posted = client.post(
        "/api/analysis/ssq/hewei/score",
        json={"main": "01 05 08 12 20 33", "special": "16", "limit": 80, "short": 10, "long": 50},
    )
    assert posted.status_code == 200, posted.text
    scored = posted.json()
    assert set(scored) == POST_KEYS
    assert scored["query"] == {"main": ["01", "05", "08", "12", "20", "33"], "special": ["16"]}
    assert scored["ticket"]["hewei"] == 9
    assert scored["ticket"]["rarity"] == "common"
    assert scored["ticket"]["alignment"] == "neutral"
    assert scored["special_ticket"]["hewei"] == 6
    assert scored["special_ticket"]["rarity"] == "common"
    assert scored["special_ticket"]["note"] == (
        "和尾 6，历史分位 100%，出现率 50%，常见，"
        "短窗 4 和长窗 4 差不多，没有明显顺逆。仅供娱乐，不构成投注建议。"
    )
    assert "仅供娱乐" in scored["ticket"]["note"]

    unseen = client.post("/api/analysis/ssq/hewei/score", json={"main": ["09"], "special": ["09"]})
    assert unseen.status_code == 200
    assert unseen.json()["special_ticket"]["hewei"] == 9
    assert unseen.json()["special_ticket"]["rarity"] == "rare"
    assert "少见" in unseen.json()["special_ticket"]["note"]

    spaced = client.post("/api/analysis/3d/hewei/score", json={"main": ["0", "9", "1"], "short": 5, "long": 20})
    assert spaced.status_code == 200
    assert spaced.json()["lottery_type"] == "fc3d"
    assert spaced.json()["ticket"]["hewei"] == 0
    assert spaced.json()["mode"] == "digit"

    bad = client.post("/api/analysis/ssq/hewei/score", json={"main": ["99"], "special": ["01"]})
    assert bad.status_code == 400
    duplicate = client.post(
        "/api/analysis/ssq/hewei/score",
        json={"main": ["01", "01", "03", "04", "05", "06"], "special": ["01"]},
    )
    assert duplicate.status_code == 400
    short = client.post("/api/analysis/fc3d/hewei/score", json={"main": ["1", "2"]})
    assert short.status_code == 400
    extra = client.post("/api/analysis/kl8/hewei/score", json={"main": ["01", "02"], "special": ["03"]})
    assert extra.status_code == 400
    unknown_post = client.post("/api/analysis/nope/hewei/score", json={"main": ["01"]})
    assert unknown_post.status_code == 400
    assert client.post("/api/analysis/ssq/hewei/score", json={"main": ["01"], "limit": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/hewei/score", json={"main": ["01"], "short": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/hewei/score", json={"main": ["01"], "long": 201}).status_code == 422

    analysis = client.get("/api/analysis/ssq")
    assert analysis.status_code == 200
    assert "hewei" not in analysis.json()
    assert "pulse" not in analysis.json()

    shape = client.get("/api/analysis/ssq/shape")
    assert shape.status_code == 200
    assert "hewei" not in shape.json()
    direct = shape_stats(db, "ssq", limit=50)
    assert "hewei" not in direct

    tail = client.get("/api/analysis/ssq/tail")
    assert tail.status_code == 200
    assert "hewei" not in tail.json()

    summed = client.get("/api/analysis/ssq/sum")
    assert summed.status_code == 200
    assert "hewei" not in summed.json()
