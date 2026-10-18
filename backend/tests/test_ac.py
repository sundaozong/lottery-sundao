"""AC值脉动：主号算术复杂度的历史分布，以及短窗相对长窗的升降。

乐透按主号集合去重后从小到大排列。数字彩按整注各位数字排列，0 与 9 不绕圈。
两两绝对差的不重复个数减去号码个数减一，得到 AC。少于两个号的那期跳过，不记成 0。
特别号单独用同一公式，不并进主号。这不是跨度、连号簇、012 路、区位、尾数或邻号。
短窗、长窗用实际有 AC 的期数求平均，缺口不当成 0。
只读本地开奖，不改其他分析接口的返回形状。
"""
from __future__ import annotations

import json

import pytest

from app.models import Draw
from app.services.ac import (
    COMMON_LIMIT,
    DIGIT_NOTE,
    DISCLAIMER,
    SET_NOTE,
    THRESHOLD,
    ac_summary,
    score_ac,
)
from app.services.pulse_ensemble import PULSE_MODULES, _MEMO_TARGETS
from app.services.road import road_summary
from app.services.shape import shape_stats
from app.services.span import span_summary
from app.services.sum_pulse import sum_summary
from app.services.tail import tail_summary
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

BUCKET_KEYS = {"ac_value", "count", "rate"}
COMMON_KEYS = {"ac_value", "count", "rate"}
TICKET_KEYS = {"ac_value", "percentile", "typicality", "rarity", "alignment", "note"}
LATEST_KEYS = {"issue", "draw_date", "main", "special", "ac_value", "special_ac_value"}
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


def _bucket(rows, ac_value):
    found = [item for item in rows if item["ac_value"] == ac_value]
    assert len(found) == 1
    return found[0]


def _empty_ticket():
    return {
        "ac_value": None,
        "percentile": None,
        "typicality": None,
        "rarity": None,
        "alignment": None,
        "note": "",
    }


def test_ac_constants_distinguish_the_metric():
    assert THRESHOLD == 0.5
    assert COMMON_LIMIT == 8
    assert "仅供娱乐" in DISCLAIMER
    assert "不构成投注建议" in DISCLAIMER
    assert "算术复杂度" in DISCLAIMER
    assert "特别号" in SET_NOTE
    assert "0" in DIGIT_NOTE and "9" in DIGIT_NOTE
    keys = [item.key for item in PULSE_MODULES]
    assert "ac" in keys
    assert [item.label for item in PULSE_MODULES if item.key == "ac"] == ["AC值"]
    assert ("app.services.ac", "ac_summary") in _MEMO_TARGETS


def test_known_sets_match_hand_ac_and_skip_short_mains(db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["16"])
    arithmetic = ac_summary(db, "ssq")
    assert arithmetic["latest_draw"]["ac_value"] == 0
    assert arithmetic["latest_draw"]["special_ac_value"] is None

    _draw(db, "ssq", "2026002", ["01", "02", "04"], ["08"])
    one = ac_summary(db, "ssq")
    assert one["latest_draw"]["ac_value"] == 1

    _draw(db, "ssq", "2026003", ["01", "05", "08", "12", "20", "33"], ["09"])
    eight = ac_summary(db, "ssq")
    assert eight["latest_draw"]["ac_value"] == 8
    assert eight["latest_draw"]["special_ac_value"] is None
    assert "unique_tail_count" not in eight["latest_draw"]
    assert "sum" not in eight["latest_draw"]
    assert "span" not in eight["latest_draw"]

    _draw(db, "ssq", "2026004", ["01"], ["02"])
    skipped = ac_summary(db, "ssq", limit=5)
    assert skipped["latest_draw"]["issue"] == "2026004"
    assert skipped["latest_draw"]["main"] == ["01"]
    assert skipped["latest_draw"]["ac_value"] is None
    assert skipped["sample_size"] == 3
    assert skipped["mean"] == 3.0
    assert _bucket(skipped["distribution"], 0)["count"] == 1
    assert _bucket(skipped["distribution"], 1)["count"] == 1
    assert _bucket(skipped["distribution"], 8)["count"] == 1
    assert all(item["count"] == 0 for item in skipped["distribution"] if item["ac_value"] not in (0, 1, 8))


def test_set_ac_dedupes_main_and_keeps_special_apart(db):
    _draw(db, "ssq", "2026005", ["01", "11", "21"], ["16"], source="crawl", draw_date="2026-01-09")
    _draw(db, "ssq", "2026004", ["02", "04", "07"], ["03"])
    _draw(db, "ssq", "2026003", [], ["01"])
    _draw(db, "ssq", "2026002", ["05", "05"], ["02"])
    _draw(db, "ssq", "2026001", ["x", "03", "13", "16"], ["04"])

    body = ac_summary(db, "ssq", limit=80, short=10, long=50)
    assert set(body) == GET_KEYS
    assert body["lottery_type"] == "ssq"
    assert body["mode"] == "set"
    assert body["basis"] == "main"
    assert body["sample_size"] == 3
    assert body["short"] == 10
    assert body["long"] == 50
    assert body["threshold"] == 0.5
    assert body["data_status"] == "mixed"
    assert body["disclaimer"] == DISCLAIMER
    assert body["note"] == SET_NOTE
    assert body["mean"] == pytest.approx(0.6667)
    assert body["median"] == 1
    assert body["short_avg"] == pytest.approx(0.6667)
    assert body["long_avg"] == pytest.approx(0.6667)
    assert body["pulse"] == 0.0
    assert body["drift"] == "flat"
    assert set(body["latest_draw"]) == LATEST_KEYS
    assert body["latest_draw"]["issue"] == "2026005"
    assert body["latest_draw"]["main"] == ["01", "11", "21"]
    assert body["latest_draw"]["special"] == ["16"]
    assert body["latest_draw"]["ac_value"] == 0
    assert body["latest_draw"]["special_ac_value"] is None
    assert body["special"] is None
    assert [item["ac_value"] for item in body["distribution"]] == [0, 1]
    assert all(set(item) == BUCKET_KEYS for item in body["distribution"])
    assert _bucket(body["distribution"], 0) == {"ac_value": 0, "count": 1, "rate": pytest.approx(0.3333)}
    assert _bucket(body["distribution"], 1) == {"ac_value": 1, "count": 2, "rate": pytest.approx(0.6667)}
    assert body["common"] == [
        {"ac_value": 1, "count": 2, "rate": pytest.approx(0.6667)},
        {"ac_value": 0, "count": 1, "rate": pytest.approx(0.3333)},
    ]
    assert all(set(item) == COMMON_KEYS for item in body["common"])


def test_ac_is_not_span_zone_road_sum_or_tail(db):
    _draw(db, "ssq", "2026001", ["10", "20", "23", "33"], ["09"])
    body = ac_summary(db, "ssq")
    assert body["latest_draw"]["ac_value"] == 1
    assert body["latest_draw"]["special_ac_value"] is None

    road = road_summary(db, "ssq")
    zone = zone_summary(db, "ssq")
    span = span_summary(db, "ssq")
    summed = sum_summary(db, "ssq")
    tail = tail_summary(db, "ssq")
    assert span["latest_draw"]["span"] == 23
    assert summed["latest_draw"]["sum"] == 86
    assert zone["latest_draw"]["ratio"] == "1:1:2"
    assert zone["latest_draw"]["imbalance"] == 1
    assert road["latest_draw"]["imbalance"] == 1
    assert tail["latest_draw"]["unique_tail_count"] == 2
    assert body["latest_draw"]["ac_value"] != span["latest_draw"]["span"]
    assert body["latest_draw"]["ac_value"] != summed["latest_draw"]["sum"]
    assert body["latest_draw"]["ac_value"] != tail["latest_draw"]["unique_tail_count"]
    assert "ac_value" not in span
    assert "ac_value" not in summed
    assert "ac_value" not in zone
    assert "ac_value" not in road
    assert "ac_value" not in tail


def test_pulse_rises_when_recent_ac_is_higher(db):
    for index, balls in enumerate([["01", "02", "04"]] * 5 + [["01", "02", "03"]] * 5):
        _draw(db, "ssq", f"{2026010 - index:07d}", balls)

    body = ac_summary(db, "ssq", short=5, long=10)
    assert body["sample_size"] == 10
    assert body["short_avg"] == 1.0
    assert body["long_avg"] == 0.5
    assert body["pulse"] == 0.5
    assert body["drift"] == "rising"
    assert body["mean"] == 0.5
    assert body["median"] == 0.5
    assert body["special"] is None
    assert _bucket(body["distribution"], 0)["count"] == 5
    assert _bucket(body["distribution"], 1)["count"] == 5
    assert body["common"] == [
        {"ac_value": 0, "count": 5, "rate": 0.5},
        {"ac_value": 1, "count": 5, "rate": 0.5},
    ]
    assert body["latest_draw"]["ac_value"] == 1
    assert body["latest_draw"]["special_ac_value"] is None

    span = span_summary(db, "ssq", short=5, long=10)
    assert span["latest_draw"]["span"] == 3
    assert span["pulse"] == 0.5
    tail = tail_summary(db, "ssq", short=5, long=10)
    assert tail["latest_draw"]["unique_tail_count"] == 3
    assert tail["pulse"] == 0.0
    assert tail["drift"] == "flat"


def test_pulse_threshold_edges(db):
    for index, balls in enumerate([["01", "02", "04", "07"]] * 5 + [["01", "02", "03", "04"]]):
        _draw(db, "ssq", f"{2026106 - index}", balls)
    flat = ac_summary(db, "ssq", short=5, long=20)
    assert flat["sample_size"] == 6
    assert flat["short_avg"] == 2.0
    assert flat["long_avg"] == pytest.approx(1.6667)
    assert flat["pulse"] == pytest.approx(0.3333)
    assert flat["drift"] == "flat"

    for index, balls in enumerate([["01", "02", "04", "08"]] * 5 + [["01", "02", "03", "04"]]):
        _draw(db, "dlt", f"{2026206 - index}", balls)
    rising = ac_summary(db, "dlt", short=5, long=20)
    assert rising["basis"] == "main"
    assert rising["short_avg"] == 3.0
    assert rising["long_avg"] == 2.5
    assert rising["pulse"] == 0.5
    assert rising["drift"] == "rising"

    for index, balls in enumerate([["0", "1", "2", "3", "4"]] * 5 + [["0", "1", "2", "3", "7"]]):
        _draw(db, "pl5", f"{2026306 - index}", balls)
    falling = ac_summary(db, "pl5", short=5, long=20)
    assert falling["basis"] == "digits"
    assert falling["short_avg"] == 0.0
    assert falling["long_avg"] == 0.5
    assert falling["pulse"] == -0.5
    assert falling["drift"] == "falling"


def test_dlt_special_ac_stays_out_of_main(db):
    _draw(db, "dlt", "2026003", ["01", "02", "04"], ["01", "12"], draw_date="2026-02-03")
    _draw(db, "dlt", "2026002", ["01", "02", "03"], ["02", "03"])
    _draw(db, "dlt", "2026001", ["08", "18"], ["05"])
    _draw(db, "dlt", "2026000", ["01", "02", "04", "07"], ["01", "02", "04"])

    body = ac_summary(db, "dlt", short=5, long=20)
    assert body["basis"] == "main"
    assert body["sample_size"] == 4
    assert body["latest_draw"]["main"] == ["01", "02", "04"]
    assert body["latest_draw"]["special"] == ["01", "12"]
    assert body["latest_draw"]["ac_value"] == 1
    assert body["latest_draw"]["special_ac_value"] == 0
    assert 12 not in [int(item) for item in body["latest_draw"]["main"]]

    special = body["special"]
    assert set(special) == SPECIAL_KEYS
    assert special["label"] == "后区"
    assert special["sample_size"] == 3
    assert special["mean"] == pytest.approx(0.3333)
    assert special["median"] == 0
    assert special["short_avg"] == pytest.approx(0.3333)
    assert special["long_avg"] == pytest.approx(0.3333)
    assert special["pulse"] == 0.0
    assert special["drift"] == "flat"
    assert special["distribution"] == [
        {"ac_value": 0, "count": 2, "rate": pytest.approx(0.6667)},
        {"ac_value": 1, "count": 1, "rate": pytest.approx(0.3333)},
    ]
    assert special["common"][0]["ac_value"] == 0

    _draw(db, "qlc", "2026001", ["01", "03", "09"], ["04"])
    single = ac_summary(db, "qlc")
    assert single["special"] is None
    assert single["latest_draw"]["ac_value"] == 1
    assert single["latest_draw"]["special_ac_value"] is None

    _draw(db, "qlc", "2026002", ["01", "02", "04", "08"], ["01", "02", "04"])
    both = ac_summary(db, "qlc", limit=5)
    assert both["sample_size"] == 2
    assert both["latest_draw"]["issue"] == "2026002"
    assert both["latest_draw"]["ac_value"] == 3
    assert both["latest_draw"]["special_ac_value"] == 1
    assert both["special"]["label"] == "特别号"
    assert both["special"]["sample_size"] == 1
    assert both["special"]["mean"] == 1.0


def test_digit_ac_does_not_wrap_and_keeps_repeated_digits(db):
    _draw(db, "fc3d", "2026004", ["0", "9", "1"], draw_date="2026-03-04")
    _draw(db, "fc3d", "2026003", ["1", "2", "3"])
    _draw(db, "fc3d", "2026002", ["5", "5", "5"])
    _draw(db, "fc3d", "2026001", ["9", "0", "0"])
    _draw(db, "fc3d", "2026000", [], ["1"])
    _draw(db, "qxc", "2026008", ["1", "2", "3", "4", "5", "9"], ["14"])
    _draw(db, "pl5", "2026008", ["0", "1", "2", "3", "4"])

    body = ac_summary(db, "fc3d")
    assert body["lottery_type"] == "fc3d"
    assert body["mode"] == "digit"
    assert body["basis"] == "digits"
    assert body["note"] == DIGIT_NOTE
    assert body["sample_size"] == 4
    assert body["special"] is None
    assert body["mean"] == 0.0
    assert body["median"] == 0
    assert body["short_avg"] == 0.0
    assert body["drift"] == "flat"
    assert body["latest_draw"]["main"] == ["0", "9", "1"]
    assert body["latest_draw"]["ac_value"] == 1
    assert body["latest_draw"]["special_ac_value"] is None
    assert _bucket(body["distribution"], -1) == {"ac_value": -1, "count": 1, "rate": 0.25}
    assert _bucket(body["distribution"], 0) == {"ac_value": 0, "count": 2, "rate": 0.5}
    assert _bucket(body["distribution"], 1) == {"ac_value": 1, "count": 1, "rate": 0.25}
    assert body["common"] == [
        {"ac_value": 0, "count": 2, "rate": 0.5},
        {"ac_value": -1, "count": 1, "rate": 0.25},
        {"ac_value": 1, "count": 1, "rate": 0.25},
    ]

    qxc = ac_summary(db, "qxc")
    assert qxc["basis"] == "digits"
    assert qxc["special"] is None
    assert qxc["latest_draw"]["ac_value"] == 3
    assert qxc["latest_draw"]["special"] == ["14"]
    assert qxc["latest_draw"]["special_ac_value"] is None

    pl5 = ac_summary(db, "pl5")
    assert pl5["basis"] == "digits"
    assert pl5["special"] is None
    assert pl5["latest_draw"]["ac_value"] == 0
    assert pl5["latest_draw"]["main"] == ["0", "1", "2", "3", "4"]


def test_blank_main_does_not_consume_the_analysis_window(db):
    _draw(db, "ssq", "2026001", ["01", "12", "23"])
    _draw(db, "ssq", "2026002", ["01", "12"])
    _draw(db, "ssq", "2026003", ["23"])
    _draw(db, "ssq", "2026004", ["12"])
    _draw(db, "ssq", "2026005", [])
    _draw(db, "ssq", "2026006", ["01", "02", "04"])

    body = ac_summary(db, "ssq", limit=5, short=5, long=20)
    assert body["sample_size"] == 2
    assert body["latest_draw"]["issue"] == "2026006"
    assert body["latest_draw"]["ac_value"] == 1
    assert body["mean"] == 0.5
    assert "2026001" not in [body["latest_draw"]["issue"]]


def test_score_aligns_with_pulse_and_marks_rarity(db):
    for index, balls in enumerate([["01", "02", "04"]] * 5 + [["01", "02", "03"]] * 5):
        _draw(db, "ssq", f"{2026010 - index:07d}", balls)

    wide = score_ac(db, "ssq", ["01", "02", "04"], ["08"], short=5, long=10)
    assert set(wide) == POST_KEYS
    assert wide["query"] == {"main": ["01", "02", "04"], "special": ["08"]}
    assert set(wide["ticket"]) == TICKET_KEYS
    assert wide["ticket"]["ac_value"] == 1
    assert wide["ticket"]["percentile"] == 1.0
    assert wide["ticket"]["typicality"] == 0.5
    assert wide["ticket"]["rarity"] == "common"
    assert wide["ticket"]["alignment"] == "aligned"
    assert wide["ticket"]["note"] == (
        "AC值 1，历史分位 100%，出现率 50%，常见，"
        "短窗 1 比长窗 0.5 走高，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert wide["special"] is None
    assert wide["special_ticket"] == _empty_ticket()
    assert wide["drift"] == "rising"

    narrow = score_ac(db, "ssq", "01 02 03", special="16", short=5, long=10)
    assert narrow["ticket"]["ac_value"] == 0
    assert narrow["ticket"]["percentile"] == 0.5
    assert narrow["ticket"]["typicality"] == 0.5
    assert narrow["ticket"]["rarity"] == "common"
    assert narrow["ticket"]["alignment"] == "against"
    assert narrow["ticket"]["note"] == (
        "AC值 0，历史分位 50%，出现率 50%，常见，"
        "短窗 1 比长窗 0.5 走高，和短窗脉动反向。仅供娱乐，不构成投注建议。"
    )
    assert narrow["special_ticket"] == _empty_ticket()

    rare = score_ac(db, "ssq", ["01", "05", "08", "12", "20", "33"], ["01", "03"], short=5, long=10)
    assert rare["ticket"]["ac_value"] == 8
    assert rare["ticket"]["percentile"] == 1.0
    assert rare["ticket"]["typicality"] == 0.0
    assert rare["ticket"]["rarity"] == "rare"
    assert rare["ticket"]["alignment"] == "aligned"
    assert "少见" in rare["ticket"]["note"]
    assert "仅供娱乐" in rare["ticket"]["note"]
    assert rare["special_ticket"]["ac_value"] == 0
    assert rare["special_ticket"]["percentile"] is None
    assert rare["special_ticket"]["alignment"] is None
    assert rare["special_ticket"]["note"] == "AC值 0，还没有历史可对照。仅供娱乐，不构成投注建议。"

    for index, pair in enumerate(
        [(["01", "02", "03", "04"], ["01", "02", "04"])] * 5 + [(["01", "02", "04", "08"], ["01", "02", "03"])] * 5
    ):
        main, special = pair
        _draw(db, "dlt", f"{2027010 - index:07d}", main, special)

    tight = score_ac(db, "dlt", ["01", "02", "03", "04"], ["01", "02", "04"], short=5, long=10)
    assert tight["drift"] == "falling"
    assert tight["ticket"]["ac_value"] == 0
    assert tight["ticket"]["alignment"] == "aligned"
    assert tight["ticket"]["note"] == (
        "AC值 0，历史分位 50%，出现率 50%，常见，"
        "短窗 0 比长窗 1.5 走低，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert tight["special"]["drift"] == "rising"
    assert tight["special"]["short_avg"] == 1.0
    assert tight["special"]["long_avg"] == 0.5
    assert tight["special_ticket"]["ac_value"] == 1
    assert tight["special_ticket"]["alignment"] == "aligned"
    assert tight["special_ticket"]["rarity"] == "common"
    assert "不构成投注建议" in tight["special_ticket"]["note"]

    wide_back = score_ac(db, "dlt", ["01", "02", "04", "08"], ["01", "02", "03"], short=5, long=10)
    assert wide_back["ticket"]["ac_value"] == 3
    assert wide_back["ticket"]["alignment"] == "against"
    assert wide_back["special_ticket"]["ac_value"] == 0
    assert wide_back["special_ticket"]["alignment"] == "against"
    assert wide_back["special_ticket"]["percentile"] == 0.5
    assert wide_back["special_ticket"]["typicality"] == 0.5


def test_digit_score_uses_listed_digits_not_wrap(db):
    _draw(db, "fc3d", "2026004", ["0", "9", "1"])
    _draw(db, "fc3d", "2026003", ["1", "2", "3"])
    _draw(db, "fc3d", "2026002", ["5", "5", "5"])
    _draw(db, "fc3d", "2026001", ["9", "0", "0"])

    body = score_ac(db, "fc3d", ["0", "9", "1"])
    assert body["basis"] == "digits"
    assert body["ticket"]["ac_value"] == 1
    assert body["ticket"]["percentile"] == 1.0
    assert body["ticket"]["typicality"] == 0.25
    assert body["ticket"]["rarity"] == "rare"
    assert body["ticket"]["alignment"] == "neutral"
    assert body["ticket"]["note"] == (
        "AC值 1，历史分位 100%，出现率 25%，少见，"
        "短窗 0 和长窗 0 差不多，没有明显顺逆。仅供娱乐，不构成投注建议。"
    )
    assert body["special_ticket"] == _empty_ticket()

    low = score_ac(db, "pl3", [1, 2, 4])
    assert low["sample_size"] == 0
    assert low["ticket"]["ac_value"] == 1
    assert low["ticket"]["percentile"] is None
    assert low["ticket"]["rarity"] is None
    assert low["ticket"]["alignment"] is None
    assert low["ticket"]["note"] == "AC值 1，还没有历史可对照。仅供娱乐，不构成投注建议。"

    repeated = score_ac(db, "fc3d", ["5", "5", "5"])
    assert repeated["ticket"]["ac_value"] == -1
    assert repeated["ticket"]["percentile"] == 0.25
    assert repeated["ticket"]["typicality"] == 0.25
    assert repeated["ticket"]["rarity"] == "typical"
    assert repeated["ticket"]["alignment"] == "neutral"
    assert "居中" in repeated["ticket"]["note"]
    assert "差不多" in repeated["ticket"]["note"]


def test_empty_history_parameter_clamp_and_common_cap(db):
    empty = ac_summary(db, "kl8", limit="no", short=None, long="bad")
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

    scored = score_ac(db, "kl8", ["01", "02", "04"])
    assert scored["ticket"]["ac_value"] == 1
    assert scored["ticket"]["percentile"] is None
    assert scored["ticket"]["note"] == "AC值 1，还没有历史可对照。仅供娱乐，不构成投注建议。"
    assert scored["special_ticket"] == _empty_ticket()

    one = score_ac(db, "kl8", ["01"])
    assert one["ticket"] == _empty_ticket()

    sets = [
        ["01", "02", "03", "04", "05", "06"],
        ["01", "02", "03", "04", "05", "07"],
        ["01", "02", "03", "04", "05", "08"],
        ["01", "02", "03", "04", "05", "09"],
        ["01", "02", "03", "04", "05", "10"],
        ["01", "02", "03", "04", "06", "12"],
        ["01", "02", "03", "04", "07", "14"],
        ["01", "02", "03", "04", "08", "16"],
        ["01", "02", "03", "05", "10", "16"],
    ]
    for index, balls in enumerate(sets, start=1):
        _draw(db, "kl8", f"202600{index}", balls)
    clamped = ac_summary(db, "kl8", limit=1, short=1, long=1)
    assert clamped["short"] == 5
    assert clamped["long"] == 20
    assert clamped["sample_size"] == 5
    assert clamped["latest_draw"]["ac_value"] == 8

    opened = ac_summary(db, "kl8", short=30, long=20)
    assert opened["short"] == 30
    assert opened["long"] == 31
    assert opened["sample_size"] == 9

    capped = ac_summary(db, "kl8")
    assert capped["sample_size"] == 9
    assert len(capped["common"]) == 8
    assert all(item["count"] == 1 and item["rate"] == pytest.approx(0.1111) for item in capped["common"])
    assert capped["common"][0]["ac_value"] == 0
    assert 8 not in [item["ac_value"] for item in capped["common"]]

    with pytest.raises(ValueError, match="未知彩种"):
        ac_summary(db, "nope")
    with pytest.raises(ValueError, match="未知彩种"):
        score_ac(db, "nope", ["01"])
    with pytest.raises(ValueError):
        score_ac(db, "ssq", ["01", "01", "03", "04", "05", "06"], ["01"])
    with pytest.raises(ValueError):
        score_ac(db, "fc3d", ["1", "2"])
    with pytest.raises(ValueError):
        score_ac(db, "kl8", ["01", "02"], ["03"])


def test_ac_endpoints_bounds_and_old_contracts(client, db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["16"], draw_date="2026-04-01")
    _draw(db, "ssq", "2026002", ["01", "05", "08", "12", "20", "33"], ["02"], source="crawl", draw_date="2026-04-03")

    res = client.get("/api/analysis/ssq/ac")
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
    assert body["latest_draw"]["ac_value"] == 8
    assert body["latest_draw"]["special_ac_value"] is None
    assert body["mean"] == 4.0
    assert body["pulse"] == 0.0
    assert body["drift"] == "flat"
    assert body["special"] is None
    assert "sum" not in body
    assert "unique_tail_count" not in body
    assert "odd_count" not in body
    assert "prime_count" not in body
    assert "zone_counts" not in body
    assert body["distribution"][0]["ac_value"] == 0
    assert _bucket(body["distribution"], 8)["count"] == 1

    custom = client.get("/api/analysis/ssq/ac", params={"limit": 80, "short": 5, "long": 20})
    assert custom.status_code == 200
    assert custom.json()["short"] == 5
    assert custom.json()["long"] == 20

    widened = client.get("/api/analysis/ssq/ac", params={"short": 30, "long": 20})
    assert widened.status_code == 200
    assert widened.json()["short"] == 30
    assert widened.json()["long"] == 31

    assert client.get("/api/analysis/ssq/ac", params={"limit": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/ac", params={"limit": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/ac", params={"short": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/ac", params={"short": 31}).status_code == 422
    assert client.get("/api/analysis/ssq/ac", params={"long": 19}).status_code == 422
    assert client.get("/api/analysis/ssq/ac", params={"long": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/ac", params={"limit": 5, "short": 5, "long": 20}).status_code == 200
    assert client.get("/api/analysis/ssq/ac", params={"limit": 200, "short": 30, "long": 200}).status_code == 200

    unknown = client.get("/api/analysis/nope/ac")
    assert unknown.status_code == 400
    assert "未知彩种" in unknown.json()["detail"]

    empty = client.get("/api/analysis/kl8/ac")
    assert empty.status_code == 200
    assert empty.json()["sample_size"] == 0
    assert empty.json()["latest_draw"] is None
    assert empty.json()["distribution"] == []
    assert empty.json()["drift"] is None

    alias = client.get("/api/analysis/3d/ac")
    assert alias.status_code == 200
    assert alias.json()["lottery_type"] == "fc3d"
    assert alias.json()["mode"] == "digit"
    assert alias.json()["basis"] == "digits"

    posted = client.post(
        "/api/analysis/ssq/ac/score",
        json={"main": "01 05 08 12 20 33", "special": "16", "limit": 80, "short": 10, "long": 50},
    )
    assert posted.status_code == 200, posted.text
    scored = posted.json()
    assert set(scored) == POST_KEYS
    assert scored["query"] == {"main": ["01", "05", "08", "12", "20", "33"], "special": ["16"]}
    assert scored["ticket"]["ac_value"] == 8
    assert scored["ticket"]["rarity"] == "common"
    assert scored["ticket"]["alignment"] == "neutral"
    assert scored["special_ticket"]["ac_value"] is None
    assert "仅供娱乐" in scored["ticket"]["note"]

    spaced = client.post("/api/analysis/3d/ac/score", json={"main": ["0", "9", "1"], "short": 5, "long": 20})
    assert spaced.status_code == 200
    assert spaced.json()["lottery_type"] == "fc3d"
    assert spaced.json()["ticket"]["ac_value"] == 1
    assert spaced.json()["mode"] == "digit"

    bad = client.post("/api/analysis/ssq/ac/score", json={"main": ["99"], "special": ["01"]})
    assert bad.status_code == 400
    duplicate = client.post(
        "/api/analysis/ssq/ac/score",
        json={"main": ["01", "01", "03", "04", "05", "06"], "special": ["01"]},
    )
    assert duplicate.status_code == 400
    short = client.post("/api/analysis/fc3d/ac/score", json={"main": ["1", "2"]})
    assert short.status_code == 400
    extra = client.post("/api/analysis/kl8/ac/score", json={"main": ["01", "02"], "special": ["03"]})
    assert extra.status_code == 400
    unknown_post = client.post("/api/analysis/nope/ac/score", json={"main": ["01"]})
    assert unknown_post.status_code == 400
    assert client.post("/api/analysis/ssq/ac/score", json={"main": ["01"], "limit": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/ac/score", json={"main": ["01"], "short": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/ac/score", json={"main": ["01"], "long": 201}).status_code == 422

    analysis = client.get("/api/analysis/ssq")
    assert analysis.status_code == 200
    assert "pulse" not in analysis.json()
    assert "ac_value" not in analysis.json()

    shape = client.get("/api/analysis/ssq/shape")
    assert shape.status_code == 200
    assert "ac_value" not in shape.json()
    assert "pulse" not in shape.json()
    direct = shape_stats(db, "ssq", limit=50)
    assert "ac_value" not in direct

    tail = client.get("/api/analysis/ssq/tail")
    assert tail.status_code == 200
    assert "ac_value" not in tail.json()

    zone = client.get("/api/analysis/ssq/zone")
    assert zone.status_code == 200
    assert "ac_value" not in zone.json()
