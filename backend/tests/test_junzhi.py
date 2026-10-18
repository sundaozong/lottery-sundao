"""均值脉动：主号算术平均的历史分布，以及短窗相对长窗是走高还是走低。

乐透主号去重后取平均，重复只算一次，不把特别号并进主号。
数字彩按抽出的各位取平均，保留重复和位置，不排序。
有特别号的彩种另算特别号均值；没有特别号则不做 special。
空白主号跳过，不占窗口名额。阈值与其它脉动一样是 0.5，数字彩也不缩小。
这不是和值、和尾、跨度、区位或大号个数。
只读本地开奖，不改其他分析接口的返回形状。
"""
from __future__ import annotations

import json

import pytest

from app.models import Draw
from app.services.daxiao import daxiao_summary
from app.services.hewei import hewei_summary
from app.services.junzhi import (
    COMMON_LIMIT,
    DIGIT_NOTE,
    DISCLAIMER,
    DISPLAY_PLACES,
    FINE_SPAN,
    SET_NOTE,
    THRESHOLD,
    score_junzhi,
    junzhi_summary,
)
from app.services.pulse_ensemble import PULSE_MODULES, _MEMO_TARGETS, score_ticket
from app.services.span import span_summary
from app.services.sum_pulse import sum_summary
from app.services.zone import zone_summary
import app.services.junzhi as junzhi_module

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

BUCKET_KEYS = {"mean_value", "count", "rate"}
TICKET_KEYS = {
    "mean_value",
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
    "mean_value",
    "special_mean_value",
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


def _bucket(rows, mean_value):
    found = [item for item in rows if item["mean_value"] == mean_value]
    assert len(found) == 1
    return found[0]


def _empty_ticket():
    return {
        "mean_value": None,
        "percentile": None,
        "typicality": None,
        "rarity": None,
        "alignment": None,
        "note": "",
    }


def test_junzhi_constants_and_equal_weight_registry():
    assert THRESHOLD == 0.5
    assert COMMON_LIMIT == 8
    assert DISPLAY_PLACES == 2
    assert FINE_SPAN == 1.0
    assert "仅供娱乐" in DISCLAIMER
    assert "不构成投注建议" in DISCLAIMER
    assert "均值" in DISCLAIMER
    assert "保留重复" in DIGIT_NOTE and "不排序" in DIGIT_NOTE
    assert "0.5" in DIGIT_NOTE and "0.5" in SET_NOTE
    assert "去重" in SET_NOTE
    text = junzhi_module.__doc__ or ""
    for word in ("和值", "和尾", "跨度", "区位", "大小", "0.5"):
        assert word in text
        assert word in DIGIT_NOTE
        assert word in SET_NOTE
    keys = [item.key for item in PULSE_MODULES]
    assert keys[-2] == "junzhi"
    assert keys[-3] == "zhenfu"
    assert [item.label for item in PULSE_MODULES if item.key == "junzhi"] == ["均值"]
    assert ("app.services.junzhi", "junzhi_summary") in _MEMO_TARGETS
    assert len(keys) == len(set(keys))


def test_set_dedupes_and_digit_keeps_duplicates_and_order(db):
    _draw(db, "ssq", "2026001", ["06", "05", "04", "03", "02", "01"], ["16"])
    body = junzhi_summary(db, "ssq", limit=5)
    assert body["mode"] == "set"
    assert body["basis"] == "main"
    assert body["sample_size"] == 1
    assert body["latest_draw"]["main"] == ["06", "05", "04", "03", "02", "01"]
    assert body["latest_draw"]["mean_value"] == 3.5
    assert body["latest_draw"]["special_mean_value"] == 16
    assert "和值" in body["note"] and "和尾" in body["note"]
    assert body["special"]["label"] == "蓝球"
    assert body["special"]["sample_size"] == 1
    assert body["special"]["mean"] == 16

    _draw(db, "fc3d", "2026201", ["1", "1", "9"])
    digit = junzhi_summary(db, "fc3d", limit=5)
    assert digit["mode"] == "digit"
    assert digit["basis"] == "digits"
    assert digit["note"] == DIGIT_NOTE
    assert digit["latest_draw"]["main"] == ["1", "1", "9"]
    assert digit["latest_draw"]["mean_value"] == 3.67
    assert digit["special"] is None
    assert digit["latest_draw"]["special_mean_value"] is None
    assert digit["distribution"] == [{"mean_value": 3.67, "count": 1, "rate": 1.0}]


def test_set_dedupes_ignores_extra_fold_and_keeps_special_apart(db):
    _draw(
        db,
        "ssq",
        "2026002",
        ["01", "01", "02", "03", "04", "05", "06", "33"],
        ["16"],
        source="crawl",
        draw_date="2026-01-03",
    )

    body = junzhi_summary(db, "ssq", limit=80, short=10, long=50)
    assert set(body) == GET_KEYS
    assert body["lottery_type"] == "ssq"
    assert body["sample_size"] == 1
    assert body["short"] == 10
    assert body["long"] == 50
    assert body["threshold"] == 0.5
    assert body["data_status"] == "mixed"
    assert body["disclaimer"] == DISCLAIMER
    assert body["note"] == SET_NOTE
    assert body["latest_draw"]["mean_value"] == 7.71
    assert body["mean"] == pytest.approx(7.7143)
    assert body["median"] == pytest.approx(7.7143)
    assert body["short_avg"] == pytest.approx(7.7143)
    assert body["long_avg"] == pytest.approx(7.7143)
    assert body["pulse"] == 0.0
    assert body["drift"] == "flat"
    assert set(body["latest_draw"]) == LATEST_KEYS
    assert body["latest_draw"]["issue"] == "2026002"
    assert body["latest_draw"]["special"] == ["16"]
    assert body["latest_draw"]["special_mean_value"] == 16
    assert [item["mean_value"] for item in body["distribution"]] == [7.71]
    assert all(set(item) == BUCKET_KEYS for item in body["distribution"])
    assert _bucket(body["distribution"], 7.71) == {"mean_value": 7.71, "count": 1, "rate": 1.0}
    assert body["common"] == [{"mean_value": 7.71, "count": 1, "rate": 1.0}]
    assert 16 not in [int(item) for item in body["latest_draw"]["main"]]
    assert 33 in [int(item) for item in body["latest_draw"]["main"]]
    special = body["special"]
    assert set(special) == SPECIAL_KEYS
    assert special["label"] == "蓝球"
    assert [item["mean_value"] for item in special["distribution"]] == [16]


def test_junzhi_is_not_sum_hewei_span_zone_or_daxiao(db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "07"], ["16"])
    body = junzhi_summary(db, "ssq")
    assert body["latest_draw"]["mean_value"] == 3.67
    assert body["latest_draw"]["special_mean_value"] == 16
    assert "sum" not in body["latest_draw"]
    assert "hewei" not in body
    assert "span" not in body
    assert "big_count" not in body
    assert "zone_bias" not in body
    summed = sum_summary(db, "ssq")
    hewei = hewei_summary(db, "ssq")
    span = span_summary(db, "ssq")
    zone = zone_summary(db, "ssq")
    daxiao = daxiao_summary(db, "ssq")
    assert summed["latest_draw"]["sum"] == 22
    assert hewei["latest_draw"]["hewei"] == 2
    assert span["latest_draw"]["span"] == 6
    assert summed["latest_draw"]["sum"] != body["latest_draw"]["mean_value"]
    assert hewei["latest_draw"]["hewei"] != body["latest_draw"]["mean_value"]
    assert span["latest_draw"]["span"] != body["latest_draw"]["mean_value"]
    assert "mean_value" not in summed["latest_draw"]
    assert "mean_value" not in hewei["latest_draw"]
    assert "mean_value" not in span["latest_draw"]
    assert "mean_value" not in zone["latest_draw"]
    assert "mean_value" not in daxiao["latest_draw"]


def test_digit_distribution_uses_exact_keys_and_lotto_fills_fine_buckets(db):
    _draw(db, "fc3d", "2026001", ["0", "0", "0"])
    _draw(db, "fc3d", "2026002", ["0", "0", "3"])
    digit = junzhi_summary(db, "fc3d")
    assert [item["mean_value"] for item in digit["distribution"]] == [0, 1]
    assert all(item["count"] == 1 for item in digit["distribution"])
    assert len(digit["distribution"]) == 2

    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["08"])
    _draw(db, "ssq", "2026002", ["01", "02", "03", "04", "05", "07"], ["09"])
    body = junzhi_summary(db, "ssq")
    keys = [item["mean_value"] for item in body["distribution"]]
    assert keys[0] == 3.5
    assert keys[-1] == 3.67
    assert len(keys) == 18
    assert keys == [round(3.5 + index * 0.01, 2) for index in range(18)]
    assert _bucket(body["distribution"], 3.5)["count"] == 1
    assert _bucket(body["distribution"], 3.67)["count"] == 1
    assert _bucket(body["distribution"], 3.51)["count"] == 0
    assert _bucket(body["distribution"], 3.5)["rate"] == 0.5


def test_wide_lotto_means_list_only_observed_keys(db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["08"])
    _draw(db, "ssq", "2026002", ["07", "08", "09", "10", "11", "12"], ["08"])
    body = junzhi_summary(db, "ssq")
    assert [item["mean_value"] for item in body["distribution"]] == [3.5, 9.5]
    assert _bucket(body["distribution"], 3.5)["count"] == 1
    assert _bucket(body["distribution"], 9.5)["count"] == 1
    assert body["latest_draw"]["mean_value"] == 9.5
    assert body["special"]["distribution"] == [{"mean_value": 8, "count": 2, "rate": 1.0}]


def test_pulse_rises_when_recent_means_are_higher(db):
    low = ["01", "02", "03", "04", "05", "06"]
    high = ["04", "05", "06", "07", "08", "09"]
    series = [low] * 5 + [high] * 6
    for index, balls in enumerate(series, start=1):
        _draw(db, "ssq", f"2026{index:03d}", balls, ["08"])

    body = junzhi_summary(db, "ssq", short=5, long=10)
    assert body["sample_size"] == 11
    assert body["short_avg"] == 6.5
    assert body["long_avg"] == pytest.approx(5.1364)
    assert body["pulse"] == pytest.approx(1.3636)
    assert body["drift"] == "rising"
    assert body["mean"] == pytest.approx(5.1364)
    assert body["median"] == 6.5
    assert [item["mean_value"] for item in body["distribution"]] == [3.5, 6.5]
    assert _bucket(body["distribution"], 3.5)["count"] == 5
    assert _bucket(body["distribution"], 6.5)["count"] == 6
    assert body["common"][0]["mean_value"] == 6.5
    assert body["common"][1]["mean_value"] == 3.5
    assert body["latest_draw"]["mean_value"] == 6.5
    assert body["special"]["drift"] == "flat"
    assert body["special"]["pulse"] == 0.0
    assert body["special"]["mean"] == 8


def test_pulse_threshold_edges_keep_half_point_for_digits(db):
    flat_low = ["01", "02", "03", "04", "05", "06"]
    flat_high = ["03", "04", "05", "06", "07", "08"]
    for index, balls in enumerate([flat_low] + [flat_high] * 5, start=1):
        _draw(db, "ssq", f"2026{index:03d}", balls, ["08"])
    flat = junzhi_summary(db, "ssq", short=5, long=20)
    assert flat["sample_size"] == 6
    assert flat["short_avg"] == 5.5
    assert flat["long_avg"] == pytest.approx(5.1667)
    assert flat["pulse"] == pytest.approx(0.3333)
    assert flat["drift"] == "flat"

    edge_low = ["01", "02", "03", "04", "05", "06"]
    edge_high = ["04", "05", "06", "07", "08", "09"]
    for index, balls in enumerate([edge_low] + [edge_high] * 5, start=1):
        _draw(db, "dlt", f"2026{index:03d}", balls[:5], ["01", "02"])
    rising = junzhi_summary(db, "dlt", short=5, long=20)
    assert rising["basis"] == "main"
    assert rising["short_avg"] == 6.0
    assert rising["long_avg"] == 5.5
    assert rising["pulse"] == 0.5
    assert rising["drift"] == "rising"
    assert rising["special"]["drift"] == "flat"
    assert rising["special"]["mean"] == 1.5

    for index, balls in enumerate([["3", "3", "3"]] + [["0", "0", "0"]] * 5, start=1):
        _draw(db, "fc3d", f"2026{index:03d}", balls)
    falling = junzhi_summary(db, "fc3d", short=5, long=20)
    assert falling["basis"] == "digits"
    assert falling["short_avg"] == 0.0
    assert falling["long_avg"] == 0.5
    assert falling["pulse"] == -0.5
    assert falling["drift"] == "falling"
    assert falling["special"] is None
    assert falling["threshold"] == 0.5

    for index, balls in enumerate([["0", "0", "0"]] + [["2", "2", "2"]] * 5, start=1):
        _draw(db, "pl3", f"2026{index:03d}", balls)
    digit_flat = junzhi_summary(db, "pl3", short=5, long=20)
    assert digit_flat["pulse"] == pytest.approx(0.3333)
    assert digit_flat["drift"] == "flat"

    for index, balls in enumerate([["0", "0", "0"]] + [["3", "3", "3"]] * 5, start=1):
        _draw(db, "pl5", f"2026{index:03d}", balls + ["0", "0"])
    digit_rise = junzhi_summary(db, "pl5", short=5, long=20)
    assert digit_rise["short_avg"] == 1.8
    assert digit_rise["long_avg"] == 1.5
    assert digit_rise["pulse"] == 0.3
    assert digit_rise["drift"] == "flat"
    assert digit_rise["special"] is None


def test_dlt_special_mean_and_qlc_single_ball(db):
    _draw(db, "dlt", "2026001", ["01", "02", "03", "04", "05"], ["07", "01"])
    _draw(db, "dlt", "2026002", ["01", "02", "03", "04", "05"], ["11", "11", "12"], draw_date="2026-02-02")
    body = junzhi_summary(db, "dlt", short=5, long=20)
    assert body["latest_draw"]["mean_value"] == 3
    assert body["latest_draw"]["special"] == ["11", "12"]
    assert body["latest_draw"]["special_mean_value"] == 11.5
    assert 11 not in [int(item) for item in body["latest_draw"]["main"]]
    assert body["special"]["label"] == "后区"
    assert [item["mean_value"] for item in body["special"]["distribution"]] == [4, 11.5]
    assert body["special"]["common"][0]["mean_value"] == 4

    _draw(db, "qlc", "2026001", ["01", "02", "03", "04", "05", "06", "07"], ["09"])
    _draw(db, "qlc", "2026002", ["02", "03", "04", "05", "06", "07", "08"], ["04"])
    single = junzhi_summary(db, "qlc")
    assert single["latest_draw"]["mean_value"] == 5
    assert single["special"]["label"] == "特别号"
    assert single["latest_draw"]["special_mean_value"] == 4
    assert single["special"]["sample_size"] == 2
    assert [item["mean_value"] for item in single["special"]["distribution"]] == [4, 9]


def test_digit_qxc_special_is_positional_mean(db):
    _draw(db, "qxc", "2026001", ["1", "2", "3", "4", "5", "6"], ["3"])
    _draw(db, "qxc", "2026002", ["1", "1", "1", "1", "1", "9"], ["5"])
    qxc = junzhi_summary(db, "qxc")
    assert qxc["basis"] == "digits"
    assert qxc["latest_draw"]["main"] == ["1", "1", "1", "1", "1", "9"]
    assert qxc["latest_draw"]["mean_value"] == 2.33
    assert qxc["latest_draw"]["special"] == ["5"]
    assert qxc["latest_draw"]["special_mean_value"] == 5
    assert qxc["special"]["sample_size"] == 2
    assert qxc["special"]["label"] == "特别号"
    assert [item["mean_value"] for item in qxc["distribution"]] == [2.33, 3.5]
    assert [item["mean_value"] for item in qxc["special"]["distribution"]] == [3, 5]


def test_blank_main_does_not_consume_the_analysis_window(db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"])
    _draw(db, "ssq", "2026002", ["02", "03", "04", "05", "06", "07"])
    _draw(db, "ssq", "2026003", ["03", "04", "05", "06", "07", "08"])
    _draw(db, "ssq", "2026004", ["04", "05", "06", "07", "08", "09"])
    _draw(db, "ssq", "2026005", [])
    _draw(db, "ssq", "2026006", ["06", "07", "08", "09", "10", "11"])

    body = junzhi_summary(db, "ssq", limit=5, short=5, long=20)
    assert body["sample_size"] == 4
    assert body["latest_draw"]["issue"] == "2026006"
    assert body["latest_draw"]["mean_value"] == 8.5
    assert 3.5 not in [item["mean_value"] for item in body["distribution"]]
    assert body["special"] is None


def test_missing_special_does_not_enter_the_special_block(db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], [])
    _draw(db, "ssq", "2026002", ["02", "03", "04", "05", "06", "07"], ["09"])
    body = junzhi_summary(db, "ssq")
    assert body["sample_size"] == 2
    assert body["latest_draw"]["special_mean_value"] == 9
    assert body["special"]["sample_size"] == 1
    assert body["special"]["distribution"] == [{"mean_value": 9, "count": 1, "rate": 1.0}]


def test_score_aligns_with_pulse_and_marks_rarity(db):
    low = ["01", "02", "03", "04", "05", "06"]
    high = ["07", "08", "09", "10", "11", "12"]
    for index, balls in enumerate([low] * 5 + [high] * 6, start=1):
        _draw(db, "ssq", f"2026{index:03d}", balls, ["08"])

    wide = score_junzhi(
        db,
        "ssq",
        ["07", "08", "09", "10", "11", "12"],
        ["09"],
        short=5,
        long=10,
    )
    assert set(wide) == POST_KEYS
    assert wide["query"] == {
        "main": ["07", "08", "09", "10", "11", "12"],
        "special": ["09"],
    }
    assert set(wide["ticket"]) == TICKET_KEYS
    assert wide["ticket"]["mean_value"] == 9.5
    assert wide["ticket"]["percentile"] == 1.0
    assert wide["ticket"]["typicality"] == pytest.approx(0.5455)
    assert wide["ticket"]["rarity"] == "common"
    assert wide["ticket"]["alignment"] == "aligned"
    assert wide["ticket"]["note"] == (
        "均值 9.5，历史分位 100%，出现率 54.55%，常见，"
        "短窗 9.5 比长窗 6.7727 走高，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert wide["special_ticket"]["mean_value"] == 9
    assert wide["special_ticket"]["percentile"] == 1.0
    assert wide["special_ticket"]["typicality"] == 0.0
    assert wide["special_ticket"]["rarity"] == "rare"
    assert wide["special_ticket"]["alignment"] == "neutral"
    assert wide["special_ticket"]["note"] == (
        "均值 9，历史分位 100%，出现率 0%，少见，"
        "短窗 8 和长窗 8 差不多，没有明显顺逆。仅供娱乐，不构成投注建议。"
    )
    assert wide["drift"] == "rising"
    assert "仅供娱乐" in wide["disclaimer"]

    same = score_junzhi(db, "ssq", "01 02 03 04 05 06", special="08", short=5, long=10)
    assert same["ticket"]["mean_value"] == 3.5
    assert same["ticket"]["percentile"] == pytest.approx(0.4545)
    assert same["ticket"]["typicality"] == pytest.approx(0.4545)
    assert same["ticket"]["rarity"] == "typical"
    assert same["ticket"]["alignment"] == "against"
    assert same["ticket"]["note"] == (
        "均值 3.5，历史分位 45.45%，出现率 45.45%，居中，"
        "短窗 9.5 比长窗 6.7727 走高，和短窗脉动反向。仅供娱乐，不构成投注建议。"
    )
    assert same["special_ticket"]["mean_value"] == 8
    assert same["special_ticket"]["rarity"] == "common"
    assert same["special_ticket"]["alignment"] == "neutral"

    rare = score_junzhi(
        db,
        "ssq",
        ["01", "02", "03", "04", "05", "33"],
        ["08"],
        short=5,
        long=10,
    )
    assert rare["ticket"]["mean_value"] == 8
    assert rare["ticket"]["percentile"] == pytest.approx(0.4545)
    assert rare["ticket"]["typicality"] == 0.0
    assert rare["ticket"]["rarity"] == "rare"
    assert rare["ticket"]["alignment"] == "against"
    assert "少见" in rare["ticket"]["note"]

    high = score_junzhi(
        db,
        "ssq",
        ["28", "29", "30", "31", "32", "33"],
        ["08"],
        short=5,
        long=10,
    )
    assert high["ticket"]["mean_value"] == 30.5
    assert high["ticket"]["alignment"] == "aligned"
    assert high["ticket"]["rarity"] == "rare"

    dlt_low = ["01", "02", "03", "04", "05"]
    dlt_high = ["21", "22", "23", "24", "25"]
    for index, balls in enumerate([dlt_high] * 5 + [dlt_low] * 6, start=1):
        special = ["09", "12"] if index <= 5 else ["01", "02"]
        _draw(db, "dlt", f"2027{index:03d}", balls, special)

    tight = score_junzhi(db, "dlt", ["01", "02", "03", "04", "05"], ["01", "02"], short=5, long=10)
    assert tight["drift"] == "falling"
    assert tight["short_avg"] == 3.0
    assert tight["long_avg"] == pytest.approx(12.0909)
    assert tight["ticket"]["mean_value"] == 3
    assert tight["ticket"]["alignment"] == "aligned"
    assert tight["ticket"]["note"] == (
        "均值 3，历史分位 54.55%，出现率 54.55%，常见，"
        "短窗 3 比长窗 12.0909 走低，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert tight["special"]["drift"] == "falling"
    assert tight["special_ticket"]["mean_value"] == 1.5
    assert tight["special_ticket"]["alignment"] == "aligned"
    assert "不构成投注建议" in tight["special_ticket"]["note"]
    assert 9 not in [int(item) for item in tight["query"]["main"]]

    far = score_junzhi(db, "dlt", ["31", "32", "33", "34", "35"], ["11", "12"], short=5, long=10)
    assert far["ticket"]["mean_value"] == 33
    assert far["ticket"]["alignment"] == "against"
    assert far["ticket"]["rarity"] == "rare"
    assert far["special_ticket"]["mean_value"] == 11.5
    assert far["special_ticket"]["alignment"] == "against"


def test_digit_score_keeps_duplicates_and_empty_history(db):
    _draw(db, "fc3d", "2026001", ["1", "3", "2"])
    _draw(db, "fc3d", "2026002", ["1", "1", "9"])
    body = score_junzhi(db, "fc3d", ["1", "1", "9"])
    assert body["basis"] == "digits"
    assert body["ticket"]["mean_value"] == 3.67
    assert body["ticket"]["percentile"] == 1.0
    assert body["ticket"]["typicality"] == 0.5
    assert body["ticket"]["rarity"] == "common"
    assert body["ticket"]["alignment"] == "neutral"
    assert body["ticket"]["note"] == (
        "均值 3.67，历史分位 100%，出现率 50%，常见，"
        "短窗 2.8333 和长窗 2.8333 差不多，没有明显顺逆。仅供娱乐，不构成投注建议。"
    )
    assert body["special_ticket"] == _empty_ticket()

    same_mean = score_junzhi(db, "fc3d", ["9", "1", "1"])
    assert same_mean["ticket"]["mean_value"] == 3.67
    assert same_mean["query"]["main"] == ["9", "1", "1"]

    low = score_junzhi(db, "fc3d", ["1", "1", "1"])
    assert low["ticket"]["mean_value"] == 1
    assert low["ticket"]["percentile"] == 0.0
    assert low["ticket"]["typicality"] == 0.0
    assert low["ticket"]["rarity"] == "rare"

    _draw(db, "pl3", "2026101", ["1", "1", "1"])
    alone = score_junzhi(db, "pl3", [2, 2, 2])
    assert alone["sample_size"] == 1
    assert alone["ticket"]["mean_value"] == 2
    assert alone["ticket"]["percentile"] == 1.0
    assert alone["ticket"]["typicality"] == 0.0
    assert alone["ticket"]["rarity"] == "rare"
    assert alone["ticket"]["alignment"] == "neutral"
    assert alone["ticket"]["note"] == (
        "均值 2，历史分位 100%，出现率 0%，少见，"
        "短窗 1 和长窗 1 差不多，没有明显顺逆。仅供娱乐，不构成投注建议。"
    )
    assert alone["special_ticket"] == _empty_ticket()

    _draw(db, "qxc", "2026101", ["1", "2", "3", "4", "5", "6"], [])
    missing = score_junzhi(db, "qxc", ["1", "2", "3", "4", "5", "7"], ["3"])
    assert missing["ticket"]["mean_value"] == pytest.approx(3.67)
    assert missing["special"] is None
    assert missing["special_ticket"]["mean_value"] == 3
    assert missing["special_ticket"]["percentile"] is None
    assert missing["special_ticket"]["note"] == "均值 3，还没有历史可对照。仅供娱乐，不构成投注建议。"

    empty = score_junzhi(db, "kl8", ["01"])
    assert empty["sample_size"] == 0
    assert empty["latest_draw"] is None
    assert empty["ticket"]["mean_value"] == 1
    assert empty["ticket"]["percentile"] is None
    assert empty["ticket"]["rarity"] is None
    assert empty["ticket"]["alignment"] is None
    assert empty["ticket"]["note"] == "均值 1，还没有历史可对照。仅供娱乐，不构成投注建议。"
    assert empty["special_ticket"] == _empty_ticket()


def test_empty_history_parameter_clamp_and_common_cap(db):
    empty = junzhi_summary(db, "kl8", limit="no", short=None, long="bad")
    assert empty["lottery_type"] == "kl8"
    assert empty["sample_size"] == 0
    assert empty["short"] == 10
    assert empty["long"] == 50
    assert empty["distribution"] == []
    assert empty["common"] == []
    assert empty["mean"] is None
    assert empty["pulse"] is None
    assert empty["drift"] is None
    assert empty["latest_draw"] is None
    assert empty["special"] is None
    assert empty["data_status"] == "seed"
    assert empty["basis"] == "main"
    assert "去重" in empty["note"]

    clamped = junzhi_summary(db, "kl8", limit=1, short=1, long=1)
    assert clamped["short"] == 5
    assert clamped["long"] == 20

    opened = junzhi_summary(db, "kl8", short=30, long=20)
    assert opened["short"] == 30
    assert opened["long"] == 31

    states = [
        ["0", "0", "0"],
        ["1", "0", "0"],
        ["2", "0", "0"],
        ["3", "0", "0"],
        ["4", "0", "0"],
        ["5", "0", "0"],
        ["6", "0", "0"],
        ["7", "0", "0"],
        ["8", "0", "0"],
    ]
    for index, balls in enumerate(states, start=1):
        _draw(db, "fc3d", f"2028{index:03d}", balls)
    capped = junzhi_summary(db, "fc3d")
    assert capped["sample_size"] == 9
    assert len(capped["common"]) == 8
    assert [item["mean_value"] for item in capped["common"]] == [0, 0.33, 0.67, 1, 1.33, 1.67, 2, 2.33]
    assert all(item["count"] == 1 and item["rate"] == pytest.approx(0.1111) for item in capped["common"])
    assert 2.67 not in [item["mean_value"] for item in capped["common"]]
    assert [item["mean_value"] for item in capped["distribution"]] == [0, 0.33, 0.67, 1, 1.33, 1.67, 2, 2.33, 2.67]

    with pytest.raises(ValueError, match="未知彩种"):
        junzhi_summary(db, "nope")
    with pytest.raises(ValueError, match="未知彩种"):
        score_junzhi(db, "nope", ["01"])
    with pytest.raises(ValueError):
        score_junzhi(db, "ssq", ["01", "01", "03", "04", "05", "06"], ["01"])
    with pytest.raises(ValueError):
        score_junzhi(db, "fc3d", ["1", "2"])
    with pytest.raises(ValueError):
        score_junzhi(db, "kl8", ["01", "02"], ["03"])


def test_ensemble_includes_junzhi_at_equal_weight(db):
    _draw(db, "ssq", "2026001", ["01", "08", "18", "19", "20", "33"], ["09"])
    _draw(db, "ssq", "2026002", ["02", "09", "18", "19", "21", "32"], ["10"])
    scored = score_ticket(db, "ssq", ["03", "08", "14", "19", "25", "31"], ["09"])
    assert [item["module"] for item in scored["breakdown"]][-2] == "junzhi"
    row = next(item for item in scored["breakdown"] if item["module"] == "junzhi")
    assert row["label"] == "均值"
    assert row["weight"] == 1.0
    assert row["score"] is not None
    assert "均值" in row["note"]
    assert {item["weight"] for item in scored["breakdown"]} == {1.0}


def test_junzhi_endpoints_bounds_and_old_contracts(client, db):
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

    res = client.get("/api/analysis/ssq/junzhi")
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
    assert body["latest_draw"]["mean_value"] == 4.5
    assert body["latest_draw"]["special_mean_value"] == 9
    assert body["mean"] == 4
    assert body["pulse"] == 0.0
    assert body["drift"] == "flat"
    assert body["special"]["sample_size"] == 2
    assert "sum" not in body["latest_draw"]
    assert "hewei" not in body
    assert body["distribution"][0] == {"mean_value": 3.5, "count": 1, "rate": 0.5}
    assert body["distribution"][-1]["mean_value"] == 4.5
    assert body["distribution"][-1]["count"] == 1
    assert len(body["distribution"]) == 101
    assert body["distribution"][1]["count"] == 0

    custom = client.get("/api/analysis/ssq/junzhi", params={"limit": 80, "short": 5, "long": 20})
    assert custom.status_code == 200
    assert custom.json()["short"] == 5
    assert custom.json()["long"] == 20

    widened = client.get("/api/analysis/ssq/junzhi", params={"short": 30, "long": 20})
    assert widened.status_code == 200
    assert widened.json()["short"] == 30
    assert widened.json()["long"] == 31

    assert client.get("/api/analysis/ssq/junzhi", params={"limit": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/junzhi", params={"limit": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/junzhi", params={"short": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/junzhi", params={"short": 31}).status_code == 422
    assert client.get("/api/analysis/ssq/junzhi", params={"long": 19}).status_code == 422
    assert client.get("/api/analysis/ssq/junzhi", params={"long": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/junzhi", params={"limit": 5, "short": 5, "long": 20}).status_code == 200
    assert client.get("/api/analysis/ssq/junzhi", params={"limit": 200, "short": 30, "long": 200}).status_code == 200

    unknown = client.get("/api/analysis/nope/junzhi")
    assert unknown.status_code == 400
    assert "未知彩种" in unknown.json()["detail"]

    empty = client.get("/api/analysis/kl8/junzhi")
    assert empty.status_code == 200
    assert empty.json()["sample_size"] == 0
    assert empty.json()["latest_draw"] is None
    assert empty.json()["distribution"] == []
    assert empty.json()["drift"] is None

    alias = client.get("/api/analysis/3d/junzhi")
    assert alias.status_code == 200
    assert alias.json()["lottery_type"] == "fc3d"
    assert alias.json()["mode"] == "digit"
    assert alias.json()["basis"] == "digits"

    posted = client.post(
        "/api/analysis/ssq/junzhi/score",
        json={"main": "02 03 04 05 06 07", "special": "09", "limit": 80, "short": 10, "long": 50},
    )
    assert posted.status_code == 200, posted.text
    scored = posted.json()
    assert set(scored) == POST_KEYS
    assert scored["query"] == {"main": ["02", "03", "04", "05", "06", "07"], "special": ["09"]}
    assert scored["ticket"]["mean_value"] == 4.5
    assert scored["ticket"]["rarity"] == "common"
    assert scored["ticket"]["alignment"] == "neutral"
    assert scored["special_ticket"]["mean_value"] == 9
    assert "仅供娱乐" in scored["ticket"]["note"]
    assert "均值 4.5" in scored["ticket"]["note"]

    spaced = client.post("/api/analysis/3d/junzhi/score", json={"main": ["1", "1", "9"], "short": 5, "long": 20})
    assert spaced.status_code == 200
    assert spaced.json()["lottery_type"] == "fc3d"
    assert spaced.json()["mode"] == "digit"
    assert spaced.json()["ticket"]["mean_value"] == 3.67

    bad = client.post("/api/analysis/ssq/junzhi/score", json={"main": ["99"], "special": ["01"]})
    assert bad.status_code == 400
    duplicate = client.post(
        "/api/analysis/ssq/junzhi/score",
        json={"main": ["01", "01", "03", "04", "05", "06"], "special": ["01"]},
    )
    assert duplicate.status_code == 400
    short = client.post("/api/analysis/fc3d/junzhi/score", json={"main": ["1", "2"]})
    assert short.status_code == 400
    extra = client.post("/api/analysis/kl8/junzhi/score", json={"main": ["01", "02"], "special": ["03"]})
    assert extra.status_code == 400
    unknown_post = client.post("/api/analysis/nope/junzhi/score", json={"main": ["01"]})
    assert unknown_post.status_code == 400
    assert client.post("/api/analysis/ssq/junzhi/score", json={"main": ["01"], "limit": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/junzhi/score", json={"main": ["01"], "short": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/junzhi/score", json={"main": ["01"], "long": 201}).status_code == 422

    analysis = client.get("/api/analysis/ssq")
    assert analysis.status_code == 200
    assert "junzhi" not in analysis.json()
    assert "mean_value" not in analysis.json()

    pulse = client.post("/api/predict", json={"lottery_type": "ssq", "strategy": "pulse", "count": 1})
    assert pulse.status_code == 200
    modules = pulse.json()["modules"]
    assert "junzhi" in modules
    assert modules[-2] == "junzhi"
    assert "zhenfu" in modules
    breakdown = pulse.json()["recommendations"][0]["breakdown"]
    assert any(item["module"] == "junzhi" and item["weight"] == 1.0 for item in breakdown)

    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    weights = spec.json()["components"]["schemas"]["PredictIn"]["properties"]["weights"]["description"]
    assert "junzhi" in weights
    assert "zhenfu" in weights
    paths = spec.json()["paths"]
    assert "/api/analysis/{lottery_type}/junzhi" in paths
    assert "/api/analysis/{lottery_type}/junzhi/score" in paths
    assert "JunzhiOut" in spec.json()["components"]["schemas"]
    assert "JunzhiScoreOut" in spec.json()["components"]["schemas"]
