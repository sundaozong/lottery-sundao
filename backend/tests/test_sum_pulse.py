"""和值脉动：主号算术和的历史分布，以及短窗相对长窗的升降。

乐透按主号集合相加，特别号不计入；至少两个特别号才另计 special 和值。
数字彩按整注各位数字相加，0 与 9 不绕圈。短窗、长窗用实际有的期数求平均，
缺口不当成和值 0。只读本地开奖，不改其他分析接口的返回形状。
"""
from __future__ import annotations

import json

import pytest

from app.models import Draw
from app.services.shape import shape_stats
from app.services.sum_pulse import (
    COMMON_LIMIT,
    DIGIT_NOTE,
    DISCLAIMER,
    SET_NOTE,
    THRESHOLD,
    score_sum,
    sum_summary,
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
    "note",
    "latest_draw",
    "special",
    "data_status",
    "disclaimer",
}

POST_KEYS = GET_KEYS | {"query", "ticket", "special_ticket"}

BUCKET_KEYS = {"sum", "count", "rate"}
TICKET_KEYS = {"sum", "percentile", "typicality", "rarity", "alignment", "note"}
LATEST_KEYS = {"issue", "draw_date", "main", "special", "sum", "special_sum"}
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


def _bucket(rows, total):
    found = [item for item in rows if item["sum"] == total]
    assert len(found) == 1
    return found[0]


def _empty_ticket():
    return {
        "sum": None,
        "percentile": None,
        "typicality": None,
        "rarity": None,
        "alignment": None,
        "note": "",
    }


def test_threshold_and_common_limit():
    assert THRESHOLD == 0.5
    assert COMMON_LIMIT == 8


def test_set_sum_ignores_special_and_fills_gaps(db):
    _draw(db, "ssq", "2026005", ["01", "08", "09"], ["16"], source="crawl", draw_date="2026-01-09")
    _draw(db, "ssq", "2026004", ["02", "04"], ["03"])
    _draw(db, "ssq", "2026003", [], ["01"])
    _draw(db, "ssq", "2026002", ["05", "05", "07"], ["02"])
    _draw(db, "ssq", "2026001", ["x", "03", "06"], ["04"])

    body = sum_summary(db, "ssq", limit=80, short=10, long=50)
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
    assert body["special"] is None
    assert body["mean"] == 11.25
    assert body["median"] == 10.5
    assert body["short_avg"] == 11.25
    assert body["long_avg"] == 11.25
    assert body["pulse"] == 0.0
    assert body["drift"] == "flat"
    assert body["latest_draw"] == {
        "issue": "2026005",
        "draw_date": "2026-01-09",
        "main": ["01", "08", "09"],
        "special": ["16"],
        "sum": 18,
        "special_sum": None,
    }
    assert set(body["latest_draw"]) == LATEST_KEYS

    distribution = body["distribution"]
    assert [item["sum"] for item in distribution] == list(range(6, 19))
    assert all(set(item) == BUCKET_KEYS for item in distribution)
    assert _bucket(distribution, 6) == {"sum": 6, "count": 1, "rate": 0.25}
    assert _bucket(distribution, 9) == {"sum": 9, "count": 1, "rate": 0.25}
    assert _bucket(distribution, 12) == {"sum": 12, "count": 1, "rate": 0.25}
    assert _bucket(distribution, 16)["count"] == 0
    assert _bucket(distribution, 18) == {"sum": 18, "count": 1, "rate": 0.25}
    assert body["common"] == [
        {"sum": 6, "count": 1, "rate": 0.25},
        {"sum": 9, "count": 1, "rate": 0.25},
        {"sum": 12, "count": 1, "rate": 0.25},
        {"sum": 18, "count": 1, "rate": 0.25},
    ]


def test_pulse_rises_when_recent_sums_are_higher(db):
    for index, balls in enumerate([["10", "20"]] * 5 + [["01", "09"]] * 5):
        _draw(db, "ssq", f"{2026010 - index:07d}", balls, ["08"])

    body = sum_summary(db, "ssq", short=5, long=10)
    assert body["sample_size"] == 10
    assert body["short_avg"] == 30.0
    assert body["long_avg"] == 20.0
    assert body["pulse"] == 10.0
    assert body["drift"] == "rising"
    assert body["mean"] == 20.0
    assert body["median"] == 20.0
    assert body["special"] is None
    assert _bucket(body["distribution"], 10)["count"] == 5
    assert _bucket(body["distribution"], 30)["count"] == 5
    assert _bucket(body["distribution"], 20)["count"] == 0
    assert body["common"][0]["sum"] == 10
    assert body["common"][1]["sum"] == 30


def test_pulse_threshold_edges(db):
    for index, total in enumerate([4, 4, 4, 4, 4, 2]):
        _draw(db, "ssq", f"{2026106 - index}", [f"{total:02d}"])
    flat = sum_summary(db, "ssq", short=5, long=20)
    assert flat["sample_size"] == 6
    assert flat["short_avg"] == 4.0
    assert flat["long_avg"] == 3.6667
    assert flat["pulse"] == 0.3333
    assert flat["drift"] == "flat"

    for index, total in enumerate([4, 4, 4, 4, 4, 1]):
        _draw(db, "fc3d", f"{2026206 - index}", [0, total, 0])
    rising = sum_summary(db, "fc3d", short=5, long=20)
    assert rising["basis"] == "digits"
    assert rising["short_avg"] == 4.0
    assert rising["long_avg"] == 3.5
    assert rising["pulse"] == 0.5
    assert rising["drift"] == "rising"

    for index, total in enumerate([2, 2, 2, 2, 2, 5]):
        _draw(db, "pl3", f"{2026306 - index}", [0, total, 0])
    falling = sum_summary(db, "pl3", short=5, long=20)
    assert falling["short_avg"] == 2.0
    assert falling["long_avg"] == 2.5
    assert falling["pulse"] == -0.5
    assert falling["drift"] == "falling"


def test_dlt_special_sum_stays_out_of_main(db):
    _draw(db, "dlt", "2026003", ["01", "05", "20"], ["01", "12"], draw_date="2026-02-03")
    _draw(db, "dlt", "2026002", ["03", "04"], ["02", "03"])
    _draw(db, "dlt", "2026001", ["08", "10"], ["05"])
    _draw(db, "dlt", "2026000", ["01", "02"], ["03", "03"])

    body = sum_summary(db, "dlt", short=5, long=20)
    assert body["basis"] == "main"
    assert body["sample_size"] == 4
    assert body["mean"] == 13.5
    assert body["median"] == 12.5
    assert body["short_avg"] == 13.5
    assert body["latest_draw"]["sum"] == 26
    assert body["latest_draw"]["special_sum"] == 13
    assert body["latest_draw"]["special"] == ["01", "12"]
    assert _bucket(body["distribution"], 26)["count"] == 1
    assert _bucket(body["distribution"], 7)["count"] == 1
    assert _bucket(body["distribution"], 13)["count"] == 0

    special = body["special"]
    assert set(special) == SPECIAL_KEYS
    assert special["label"] == "后区"
    assert special["sample_size"] == 2
    assert special["mean"] == 9.0
    assert special["median"] == 9.0
    assert special["short_avg"] == 9.0
    assert special["long_avg"] == 9.0
    assert special["pulse"] == 0.0
    assert special["drift"] == "flat"
    assert [item["sum"] for item in special["distribution"]] == list(range(5, 14))
    assert _bucket(special["distribution"], 5) == {"sum": 5, "count": 1, "rate": 0.5}
    assert _bucket(special["distribution"], 13) == {"sum": 13, "count": 1, "rate": 0.5}
    assert _bucket(special["distribution"], 6)["count"] == 0
    assert special["common"] == [
        {"sum": 5, "count": 1, "rate": 0.5},
        {"sum": 13, "count": 1, "rate": 0.5},
    ]

    _draw(db, "qlc", "2026001", ["01", "03", "09"], ["04"])
    single = sum_summary(db, "qlc")
    assert single["special"] is None
    assert single["latest_draw"]["sum"] == 13
    assert single["latest_draw"]["special_sum"] is None


def test_digit_sum_does_not_wrap_zero_and_nine(db):
    _draw(db, "fc3d", "2026004", ["0", "9", "1"], draw_date="2026-03-04")
    _draw(db, "fc3d", "2026003", ["1", "2", "3"])
    _draw(db, "fc3d", "2026002", ["5", "5", "5"])
    _draw(db, "fc3d", "2026001", ["9", "0", "0"])
    _draw(db, "fc3d", "2026000", [], ["1"])
    _draw(db, "qxc", "2026008", ["1", "2", "3", "4", "5", "9"], ["14"])

    body = sum_summary(db, "fc3d")
    assert body["lottery_type"] == "fc3d"
    assert body["mode"] == "digit"
    assert body["basis"] == "digits"
    assert body["note"] == DIGIT_NOTE
    assert "0" in body["note"] and "9" in body["note"]
    assert body["sample_size"] == 4
    assert body["special"] is None
    assert body["mean"] == 10.0
    assert body["median"] == 9.5
    assert body["short_avg"] == 10.0
    assert body["drift"] == "flat"
    assert body["latest_draw"]["sum"] == 10
    assert body["latest_draw"]["main"] == ["0", "9", "1"]
    assert body["latest_draw"]["special_sum"] is None
    assert _bucket(body["distribution"], 6) == {"sum": 6, "count": 1, "rate": 0.25}
    assert _bucket(body["distribution"], 7)["count"] == 0
    assert _bucket(body["distribution"], 9) == {"sum": 9, "count": 1, "rate": 0.25}
    assert _bucket(body["distribution"], 10) == {"sum": 10, "count": 1, "rate": 0.25}
    assert _bucket(body["distribution"], 15) == {"sum": 15, "count": 1, "rate": 0.25}
    assert body["common"][0] == {"sum": 6, "count": 1, "rate": 0.25}

    qxc = sum_summary(db, "qxc")
    assert qxc["basis"] == "digits"
    assert qxc["special"] is None
    assert qxc["latest_draw"]["sum"] == 24
    assert qxc["latest_draw"]["special"] == ["14"]
    assert qxc["latest_draw"]["special_sum"] is None
    assert qxc["distribution"] == [{"sum": 24, "count": 1, "rate": 1.0}]


def test_score_aligns_with_pulse_and_marks_rarity(db):
    for index, balls in enumerate([["10", "20"]] * 5 + [["01", "09"]] * 5):
        _draw(db, "ssq", f"{2026010 - index:07d}", balls, ["08"])

    wide = score_sum(db, "ssq", ["10", "20"], ["08"], short=5, long=10)
    assert set(wide) == POST_KEYS
    assert wide["query"] == {"main": ["10", "20"], "special": ["08"]}
    assert set(wide["ticket"]) == TICKET_KEYS
    assert wide["ticket"]["sum"] == 30
    assert wide["ticket"]["percentile"] == 1.0
    assert wide["ticket"]["typicality"] == 0.5
    assert wide["ticket"]["rarity"] == "common"
    assert wide["ticket"]["alignment"] == "aligned"
    assert wide["ticket"]["note"] == (
        "和值 30，历史分位 100%，出现率 50%，常见，短窗 30 比长窗 20 走高，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert wide["special_ticket"] == _empty_ticket()
    assert wide["drift"] == "rising"

    narrow = score_sum(db, "ssq", "01 09", special="08", short=5, long=10)
    assert narrow["ticket"]["sum"] == 10
    assert narrow["ticket"]["percentile"] == 0.5
    assert narrow["ticket"]["typicality"] == 0.5
    assert narrow["ticket"]["rarity"] == "common"
    assert narrow["ticket"]["alignment"] == "against"
    assert "走高" in narrow["ticket"]["note"]
    assert "反向" in narrow["ticket"]["note"]
    assert "仅供娱乐" in narrow["ticket"]["note"]

    rare = score_sum(db, "ssq", ["01", "33"], ["08"], short=5, long=10)
    assert rare["ticket"]["sum"] == 34
    assert rare["ticket"]["percentile"] == 1.0
    assert rare["ticket"]["typicality"] == 0.0
    assert rare["ticket"]["rarity"] == "rare"
    assert rare["ticket"]["alignment"] == "aligned"
    assert "少见" in rare["ticket"]["note"]

    unseen_history = score_sum(db, "ssq", ["03", "07"], ["01", "05"], short=5, long=10)
    assert unseen_history["ticket"]["sum"] == 10
    assert unseen_history["special_ticket"]["sum"] == 6
    assert unseen_history["special_ticket"]["percentile"] is None
    assert unseen_history["special_ticket"]["alignment"] is None
    assert unseen_history["special_ticket"]["note"] == (
        "和值 6，还没有历史可对照。仅供娱乐，不构成投注建议。"
    )

    for index, pair in enumerate([(["01", "05"], ["01", "02"])] * 5 + [(["10", "20"], ["02", "10"])] * 5):
        main, special = pair
        _draw(db, "dlt", f"{2027010 - index:07d}", main, special)

    tight = score_sum(db, "dlt", ["01", "05"], ["01", "02"], short=5, long=10)
    assert tight["drift"] == "falling"
    assert tight["ticket"]["sum"] == 6
    assert tight["ticket"]["alignment"] == "aligned"
    assert "走低" in tight["ticket"]["note"]
    assert "同向" in tight["ticket"]["note"]
    assert tight["special"]["drift"] == "falling"
    assert tight["special"]["short_avg"] == 3.0
    assert tight["special"]["long_avg"] == 7.5
    assert tight["special_ticket"]["sum"] == 3
    assert tight["special_ticket"]["alignment"] == "aligned"
    assert tight["special_ticket"]["rarity"] == "common"
    assert "不构成投注建议" in tight["special_ticket"]["note"]

    wide_back = score_sum(db, "dlt", ["10", "20"], ["02", "10"], short=5, long=10)
    assert wide_back["ticket"]["sum"] == 30
    assert wide_back["ticket"]["alignment"] == "against"
    assert wide_back["special_ticket"]["sum"] == 12
    assert wide_back["special_ticket"]["alignment"] == "against"
    assert wide_back["special_ticket"]["percentile"] == 1.0
    assert wide_back["special_ticket"]["typicality"] == 0.5

    one_back = score_sum(db, "dlt", ["01", "05"], ["03"], short=5, long=10)
    assert one_back["special_ticket"] == _empty_ticket()


def test_digit_score_uses_whole_ticket_not_wrap(db):
    _draw(db, "fc3d", "2026004", ["0", "9", "1"])
    _draw(db, "fc3d", "2026003", ["1", "2", "3"])
    _draw(db, "fc3d", "2026002", ["5", "5", "5"])
    _draw(db, "fc3d", "2026001", ["9", "0", "0"])

    body = score_sum(db, "fc3d", ["0", "9", "1"])
    assert body["basis"] == "digits"
    assert body["ticket"]["sum"] == 10
    assert body["ticket"]["percentile"] == 0.75
    assert body["ticket"]["typicality"] == 0.25
    assert body["ticket"]["rarity"] == "common"
    assert body["ticket"]["alignment"] == "neutral"
    assert body["ticket"]["note"] == (
        "和值 10，历史分位 75%，出现率 25%，常见，短窗 10 和长窗 10 差不多，没有明显顺逆。仅供娱乐，不构成投注建议。"
    )
    assert body["special_ticket"] == _empty_ticket()

    low = score_sum(db, "pl3", [5, 5, 5])
    assert low["sample_size"] == 0
    assert low["ticket"]["sum"] == 15
    assert low["ticket"]["percentile"] is None
    assert low["ticket"]["rarity"] is None
    assert low["ticket"]["alignment"] is None
    assert low["ticket"]["note"] == "和值 15，还没有历史可对照。仅供娱乐，不构成投注建议。"

    for index in range(3):
        _draw(db, "fc3d", f"202600{7 - index}", ["9", "9", "2"])
    mid = score_sum(db, "fc3d", ["0", "6", "0"])
    assert mid["ticket"]["sum"] == 6
    assert mid["ticket"]["percentile"] == 0.1429
    assert mid["ticket"]["typicality"] == 0.1429
    assert mid["ticket"]["rarity"] == "typical"
    assert mid["ticket"]["alignment"] == "neutral"
    assert "居中" in mid["ticket"]["note"]


def test_empty_history_parameter_clamp_and_common_cap(db):
    empty = sum_summary(db, "kl8", limit="no", short=None, long="bad")
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

    scored = score_sum(db, "kl8", ["01", "05"])
    assert scored["ticket"]["sum"] == 6
    assert scored["ticket"]["percentile"] is None
    assert scored["ticket"]["note"] == "和值 6，还没有历史可对照。仅供娱乐，不构成投注建议。"
    assert scored["special_ticket"] == _empty_ticket()

    for total in range(1, 7):
        _draw(db, "kl8", f"202600{total}", ["01", f"{total + 1:02d}"])
    clamped = sum_summary(db, "kl8", limit=1, short=1, long=1)
    assert clamped["short"] == 5
    assert clamped["long"] == 20
    assert clamped["sample_size"] == 5
    assert clamped["latest_draw"]["sum"] == 8
    assert clamped["mean"] == 6.0
    assert 3 not in {item["sum"] for item in clamped["distribution"]}

    opened = sum_summary(db, "kl8", short=30, long=20)
    assert opened["short"] == 30
    assert opened["long"] == 31
    assert opened["sample_size"] == 6
    assert opened["mean"] == 5.5

    for total in range(1, 10):
        _draw(db, "ssq", f"202610{total}", ["01", f"{total + 1:02d}"])
    capped = sum_summary(db, "ssq")
    assert capped["sample_size"] == 9
    assert len(capped["common"]) == 8
    assert [item["sum"] for item in capped["common"]] == list(range(3, 11))
    assert all(item["count"] == 1 and item["rate"] == 0.1111 for item in capped["common"])
    assert capped["mean"] == 7.0
    assert capped["median"] == 7

    with pytest.raises(ValueError, match="未知彩种"):
        sum_summary(db, "nope")
    with pytest.raises(ValueError, match="未知彩种"):
        score_sum(db, "nope", ["01"])
    with pytest.raises(ValueError):
        score_sum(db, "ssq", ["01", "01", "03", "04", "05", "06"], ["01"])
    with pytest.raises(ValueError):
        score_sum(db, "fc3d", ["1", "2"])
    with pytest.raises(ValueError):
        score_sum(db, "kl8", ["01", "02"], ["03"])


def test_sum_endpoints_bounds_and_old_contracts(client, db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "10", "20", "30"], ["16"], draw_date="2026-04-01")
    _draw(db, "ssq", "2026002", ["05", "07", "09", "11", "13", "15"], ["02"], source="crawl", draw_date="2026-04-03")

    res = client.get("/api/analysis/ssq/sum")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == GET_KEYS
    assert body["sample_size"] == 2
    assert body["short"] == 10
    assert body["long"] == 50
    assert body["basis"] == "main"
    assert body["disclaimer"] == DISCLAIMER
    assert body["data_status"] == "mixed"
    assert body["latest_draw"]["sum"] == 60
    assert body["mean"] == 63.0
    assert body["special"] is None
    assert "span" not in body

    custom = client.get("/api/analysis/ssq/sum", params={"limit": 80, "short": 5, "long": 20})
    assert custom.status_code == 200
    assert custom.json()["short"] == 5
    assert custom.json()["long"] == 20

    widened = client.get("/api/analysis/ssq/sum", params={"short": 30, "long": 20})
    assert widened.status_code == 200
    assert widened.json()["short"] == 30
    assert widened.json()["long"] == 31

    assert client.get("/api/analysis/ssq/sum", params={"limit": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/sum", params={"limit": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/sum", params={"short": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/sum", params={"short": 31}).status_code == 422
    assert client.get("/api/analysis/ssq/sum", params={"long": 19}).status_code == 422
    assert client.get("/api/analysis/ssq/sum", params={"long": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/sum", params={"limit": 5, "short": 5, "long": 20}).status_code == 200
    assert client.get("/api/analysis/ssq/sum", params={"limit": 200, "short": 30, "long": 200}).status_code == 200

    unknown = client.get("/api/analysis/nope/sum")
    assert unknown.status_code == 400
    assert "未知彩种" in unknown.json()["detail"]

    empty = client.get("/api/analysis/kl8/sum")
    assert empty.status_code == 200
    assert empty.json()["sample_size"] == 0
    assert empty.json()["latest_draw"] is None
    assert empty.json()["distribution"] == []
    assert empty.json()["drift"] is None

    alias = client.get("/api/analysis/3d/sum")
    assert alias.status_code == 200
    assert alias.json()["lottery_type"] == "fc3d"
    assert alias.json()["mode"] == "digit"
    assert alias.json()["basis"] == "digits"

    posted = client.post(
        "/api/analysis/ssq/sum/score",
        json={"main": "01 02 03 10 20 30", "special": "16", "limit": 80, "short": 10, "long": 50},
    )
    assert posted.status_code == 200, posted.text
    scored = posted.json()
    assert set(scored) == POST_KEYS
    assert scored["query"] == {"main": ["01", "02", "03", "10", "20", "30"], "special": ["16"]}
    assert scored["ticket"]["sum"] == 66
    assert scored["ticket"]["rarity"] == "common"
    assert scored["ticket"]["alignment"] == "neutral"
    assert scored["special_ticket"]["sum"] is None
    assert "仅供娱乐" in scored["ticket"]["note"]

    spaced = client.post("/api/analysis/3d/sum/score", json={"main": ["0", "9", "1"], "short": 5, "long": 20})
    assert spaced.status_code == 200
    assert spaced.json()["lottery_type"] == "fc3d"
    assert spaced.json()["ticket"]["sum"] == 10
    assert spaced.json()["mode"] == "digit"

    bad = client.post("/api/analysis/ssq/sum/score", json={"main": ["99"], "special": ["01"]})
    assert bad.status_code == 400
    duplicate = client.post(
        "/api/analysis/ssq/sum/score",
        json={"main": ["01", "01", "03", "04", "05", "06"], "special": ["01"]},
    )
    assert duplicate.status_code == 400
    short = client.post("/api/analysis/fc3d/sum/score", json={"main": ["1", "2"]})
    assert short.status_code == 400
    extra = client.post("/api/analysis/kl8/sum/score", json={"main": ["01", "02"], "special": ["03"]})
    assert extra.status_code == 400
    unknown_post = client.post("/api/analysis/nope/sum/score", json={"main": ["01"]})
    assert unknown_post.status_code == 400
    assert client.post("/api/analysis/ssq/sum/score", json={"main": ["01"], "limit": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/sum/score", json={"main": ["01"], "short": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/sum/score", json={"main": ["01"], "long": 201}).status_code == 422

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
    assert "basis" not in analysis.json()

    shape = client.get("/api/analysis/ssq/shape")
    assert shape.status_code == 200
    shape_body = shape.json()
    assert set(shape_body["sum"]) == {"min", "max", "avg", "buckets"}
    assert shape_body["sum"]["min"] == 60
    assert shape_body["sum"]["max"] == 66
    assert shape_body["sum"]["avg"] == 63.0
    assert "pulse" not in shape_body
    assert "distribution" not in shape_body
    assert "drift" not in shape_body
    assert set(shape_body["span"]) == {"min", "max", "avg"}
    direct = shape_stats(db, "ssq", limit=50)
    assert set(direct["sum"]) == {"min", "max", "avg", "buckets"}
    assert direct["sum"]["min"] == 60
    assert direct["sum"]["max"] == 66

    span = client.get("/api/analysis/ssq/span")
    assert span.status_code == 200
    assert "pulse" in span.json()
    assert span.json()["latest_draw"]["span"] == 10
    assert "special_sum" not in span.json()["latest_draw"]

    echo = client.post("/api/analysis/ssq/echo", json={"main": ["01", "02", "03", "04", "05", "06"], "special": ["16"]})
    assert echo.status_code == 200
    assert "echoes" in echo.json()
    assert "ticket" not in echo.json()
    affinity = client.get("/api/analysis/ssq/affinity")
    assert affinity.status_code == 200
    assert "companions" in affinity.json()
    assert "pulse" not in affinity.json()
    collision = client.post(
        "/api/analysis/ssq/collision",
        json={
            "tickets": [
                {"main": ["01", "02", "03", "04", "05", "06"], "special": ["16"]},
                {"main": ["01", "02", "03", "07", "08", "09"], "special": ["01"]},
            ]
        },
    )
    assert collision.status_code == 200
    assert "pairs" in collision.json()
    assert "pulse" not in collision.json()
    repeat = client.get("/api/analysis/ssq/repeat")
    assert repeat.status_code == 200
    assert "recent_pairs" in repeat.json()
    assert "pulse" not in repeat.json()
    momentum = client.get("/api/analysis/ssq/momentum")
    assert momentum.status_code == 200
    assert "rising" in momentum.json()
    assert "pulse" not in momentum.json()
    assert "basis" not in momentum.json()
    neighbor = client.get("/api/analysis/ssq/neighbor")
    assert neighbor.status_code == 200
    assert "pulled" in neighbor.json()
    assert "pulse" not in neighbor.json()
    assert "basis" not in neighbor.json()
    road = client.get("/api/analysis/ssq/road")
    assert road.status_code == 200
    assert "imbalance" not in road.json() or "avg_road_counts" in road.json()
    cluster = client.get("/api/analysis/ssq/cluster")
    assert cluster.status_code == 200
    assert "max_len" in cluster.json()["latest_draw"]
