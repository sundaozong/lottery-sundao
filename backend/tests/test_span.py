"""跨度脉动：主号 max−min 的历史分布，以及短窗相对长窗的升降。

乐透按主号集合，特别号不计入；多个特别号才另计 special 跨度。
数字彩按整注各位数字，0 与 9 不绕圈。短窗、长窗用实际有的期数求平均，
缺口不当成跨度 0。只读本地开奖，不改其他分析接口的返回形状。
"""
from __future__ import annotations

import json

import pytest

from app.models import Draw
from app.services.shape import shape_stats
from app.services.span import (
    COMMON_LIMIT,
    DIGIT_NOTE,
    DISCLAIMER,
    SET_NOTE,
    THRESHOLD,
    score_span,
    span_summary,
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

BUCKET_KEYS = {"span", "count", "rate"}
TICKET_KEYS = {"span", "percentile", "typicality", "rarity", "alignment", "note"}
LATEST_KEYS = {"issue", "draw_date", "main", "special", "span", "special_span"}
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


def _bucket(rows, span):
    found = [item for item in rows if item["span"] == span]
    assert len(found) == 1
    return found[0]


def _empty_ticket():
    return {
        "span": None,
        "percentile": None,
        "typicality": None,
        "rarity": None,
        "alignment": None,
        "note": "",
    }


def test_threshold_and_common_limit():
    assert THRESHOLD == 0.5
    assert COMMON_LIMIT == 8


def test_set_span_ignores_special_and_fills_gaps(db):
    _draw(db, "ssq", "2026005", ["01", "08", "09"], ["16"], source="crawl", draw_date="2026-01-09")
    _draw(db, "ssq", "2026004", ["02", "04"], ["03"])
    _draw(db, "ssq", "2026003", [], ["01"])
    _draw(db, "ssq", "2026002", ["05", "05", "07"], ["02"])
    _draw(db, "ssq", "2026001", ["x", "03", "06"], ["04"])

    body = span_summary(db, "ssq", limit=80, short=10, long=50)
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
    assert body["mean"] == 3.75
    assert body["median"] == 2.5
    assert body["short_avg"] == 3.75
    assert body["long_avg"] == 3.75
    assert body["pulse"] == 0.0
    assert body["drift"] == "flat"
    assert body["latest_draw"] == {
        "issue": "2026005",
        "draw_date": "2026-01-09",
        "main": ["01", "08", "09"],
        "special": ["16"],
        "span": 8,
        "special_span": None,
    }
    assert set(body["latest_draw"]) == LATEST_KEYS

    distribution = body["distribution"]
    assert [item["span"] for item in distribution] == [2, 3, 4, 5, 6, 7, 8]
    assert all(set(item) == BUCKET_KEYS for item in distribution)
    assert _bucket(distribution, 2) == {"span": 2, "count": 2, "rate": 0.5}
    assert _bucket(distribution, 3) == {"span": 3, "count": 1, "rate": 0.25}
    assert _bucket(distribution, 4)["count"] == 0
    assert _bucket(distribution, 8) == {"span": 8, "count": 1, "rate": 0.25}
    assert body["common"] == [
        {"span": 2, "count": 2, "rate": 0.5},
        {"span": 3, "count": 1, "rate": 0.25},
        {"span": 8, "count": 1, "rate": 0.25},
    ]
    assert 16 not in {item["span"] for item in distribution}


def test_pulse_rises_when_recent_spans_are_wider(db):
    for index, span in enumerate([9, 9, 9, 9, 9, 1, 1, 1, 1, 1]):
        hi = span + 1
        _draw(db, "ssq", f"{2026010 - index:07d}", ["01", f"{hi:02d}"], ["08"])

    body = span_summary(db, "ssq", short=5, long=10)
    assert body["sample_size"] == 10
    assert body["short_avg"] == 9.0
    assert body["long_avg"] == 5.0
    assert body["pulse"] == 4.0
    assert body["drift"] == "rising"
    assert body["mean"] == 5.0
    assert body["median"] == 5.0
    assert body["special"] is None
    assert _bucket(body["distribution"], 1)["count"] == 5
    assert _bucket(body["distribution"], 9)["count"] == 5
    assert _bucket(body["distribution"], 5)["count"] == 0
    assert body["common"][0]["span"] == 1
    assert body["common"][1]["span"] == 9


def test_pulse_threshold_edges(db):
    for index, span in enumerate([4, 4, 4, 4, 4, 2]):
        _draw(db, "ssq", f"{2026106 - index}", [1, 1 + span])
    flat = span_summary(db, "ssq", short=5, long=20)
    assert flat["sample_size"] == 6
    assert flat["short_avg"] == 4.0
    assert flat["long_avg"] == 3.6667
    assert flat["pulse"] == 0.3333
    assert flat["drift"] == "flat"

    for index, span in enumerate([4, 4, 4, 4, 4, 1]):
        _draw(db, "fc3d", f"{2026206 - index}", [0, span, 0])
    rising = span_summary(db, "fc3d", short=5, long=20)
    assert rising["basis"] == "digits"
    assert rising["short_avg"] == 4.0
    assert rising["long_avg"] == 3.5
    assert rising["pulse"] == 0.5
    assert rising["drift"] == "rising"

    for index, span in enumerate([2, 2, 2, 2, 2, 5]):
        _draw(db, "pl3", f"{2026306 - index}", [0, span, 1])
    falling = span_summary(db, "pl3", short=5, long=20)
    assert falling["short_avg"] == 2.0
    assert falling["long_avg"] == 2.5
    assert falling["pulse"] == -0.5
    assert falling["drift"] == "falling"


def test_dlt_special_span_stays_out_of_main(db):
    _draw(db, "dlt", "2026003", ["01", "05", "20"], ["01", "12"], draw_date="2026-02-03")
    _draw(db, "dlt", "2026002", ["03", "04"], ["02", "03"])
    _draw(db, "dlt", "2026001", ["08", "10"], ["05"])

    body = span_summary(db, "dlt", short=5, long=20)
    assert body["basis"] == "main"
    assert body["sample_size"] == 3
    assert body["mean"] == 7.3333
    assert body["median"] == 2
    assert body["short_avg"] == 7.3333
    assert body["latest_draw"]["span"] == 19
    assert body["latest_draw"]["special_span"] == 11
    assert body["latest_draw"]["special"] == ["01", "12"]
    assert _bucket(body["distribution"], 19)["count"] == 1
    assert _bucket(body["distribution"], 1)["count"] == 1
    assert _bucket(body["distribution"], 11)["count"] == 0

    special = body["special"]
    assert set(special) == SPECIAL_KEYS
    assert special["label"] == "后区"
    assert special["sample_size"] == 2
    assert special["mean"] == 6.0
    assert special["median"] == 6.0
    assert special["short_avg"] == 6.0
    assert special["long_avg"] == 6.0
    assert special["pulse"] == 0.0
    assert special["drift"] == "flat"
    assert [item["span"] for item in special["distribution"]] == list(range(1, 12))
    assert _bucket(special["distribution"], 1) == {"span": 1, "count": 1, "rate": 0.5}
    assert _bucket(special["distribution"], 11) == {"span": 11, "count": 1, "rate": 0.5}
    assert _bucket(special["distribution"], 6)["count"] == 0
    assert special["common"] == [
        {"span": 1, "count": 1, "rate": 0.5},
        {"span": 11, "count": 1, "rate": 0.5},
    ]

    _draw(db, "qlc", "2026001", ["01", "03", "09"], ["04"])
    single = span_summary(db, "qlc")
    assert single["special"] is None
    assert single["latest_draw"]["span"] == 8
    assert single["latest_draw"]["special_span"] is None


def test_digit_span_does_not_wrap_zero_and_nine(db):
    _draw(db, "fc3d", "2026004", ["0", "9", "1"], draw_date="2026-03-04")
    _draw(db, "fc3d", "2026003", ["1", "2", "3"])
    _draw(db, "fc3d", "2026002", ["5", "5", "5"])
    _draw(db, "fc3d", "2026001", ["9", "0", "0"])
    _draw(db, "fc3d", "2026000", [], ["1"])
    _draw(db, "qxc", "2026008", ["1", "2", "3", "4", "5", "9"], ["14"])

    body = span_summary(db, "fc3d")
    assert body["lottery_type"] == "fc3d"
    assert body["mode"] == "digit"
    assert body["basis"] == "digits"
    assert body["note"] == DIGIT_NOTE
    assert "0" in body["note"] and "9" in body["note"]
    assert body["sample_size"] == 4
    assert body["special"] is None
    assert body["mean"] == 5.0
    assert body["median"] == 5.5
    assert body["short_avg"] == 5.0
    assert body["drift"] == "flat"
    assert body["latest_draw"]["span"] == 9
    assert body["latest_draw"]["main"] == ["0", "9", "1"]
    assert body["latest_draw"]["special_span"] is None
    assert _bucket(body["distribution"], 0) == {"span": 0, "count": 1, "rate": 0.25}
    assert _bucket(body["distribution"], 1)["count"] == 0
    assert _bucket(body["distribution"], 2) == {"span": 2, "count": 1, "rate": 0.25}
    assert _bucket(body["distribution"], 9) == {"span": 9, "count": 2, "rate": 0.5}
    assert body["common"][0] == {"span": 9, "count": 2, "rate": 0.5}

    qxc = span_summary(db, "qxc")
    assert qxc["basis"] == "digits"
    assert qxc["special"] is None
    assert qxc["latest_draw"]["span"] == 8
    assert qxc["latest_draw"]["special"] == ["14"]
    assert qxc["latest_draw"]["special_span"] is None
    assert qxc["distribution"] == [{"span": 8, "count": 1, "rate": 1.0}]


def test_score_aligns_with_pulse_and_marks_rarity(db):
    for index, span in enumerate([9, 9, 9, 9, 9, 1, 1, 1, 1, 1]):
        hi = span + 1
        _draw(db, "ssq", f"{2026010 - index:07d}", ["01", f"{hi:02d}"], ["08"])

    wide = score_span(db, "ssq", ["01", "10"], ["08"], short=5, long=10)
    assert set(wide) == POST_KEYS
    assert wide["query"] == {"main": ["01", "10"], "special": ["08"]}
    assert set(wide["ticket"]) == TICKET_KEYS
    assert wide["ticket"]["span"] == 9
    assert wide["ticket"]["percentile"] == 1.0
    assert wide["ticket"]["typicality"] == 0.5
    assert wide["ticket"]["rarity"] == "common"
    assert wide["ticket"]["alignment"] == "aligned"
    assert wide["ticket"]["note"] == (
        "跨度 9，历史分位 100%，出现率 50%，常见，短窗 9 比长窗 5 变宽，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert wide["special_ticket"] == _empty_ticket()
    assert wide["drift"] == "rising"

    narrow = score_span(db, "ssq", "01 02", special="08", short=5, long=10)
    assert narrow["ticket"]["span"] == 1
    assert narrow["ticket"]["percentile"] == 0.5
    assert narrow["ticket"]["typicality"] == 0.5
    assert narrow["ticket"]["rarity"] == "common"
    assert narrow["ticket"]["alignment"] == "against"
    assert "变宽" in narrow["ticket"]["note"]
    assert "反向" in narrow["ticket"]["note"]
    assert "仅供娱乐" in narrow["ticket"]["note"]

    rare = score_span(db, "ssq", ["01", "20"], ["08"], short=5, long=10)
    assert rare["ticket"]["span"] == 19
    assert rare["ticket"]["percentile"] == 1.0
    assert rare["ticket"]["typicality"] == 0.0
    assert rare["ticket"]["rarity"] == "rare"
    assert rare["ticket"]["alignment"] == "aligned"
    assert "少见" in rare["ticket"]["note"]

    unseen_history = score_span(db, "ssq", ["03", "07"], ["01", "05"], short=5, long=10)
    assert unseen_history["ticket"]["span"] == 4
    assert unseen_history["special_ticket"]["span"] == 4
    assert unseen_history["special_ticket"]["percentile"] is None
    assert unseen_history["special_ticket"]["alignment"] is None
    assert unseen_history["special_ticket"]["note"] == (
        "跨度 4，还没有历史可对照。仅供娱乐，不构成投注建议。"
    )

    for index, pair in enumerate([(1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (9, 8), (9, 8), (9, 8), (9, 8), (9, 8)]):
        main_span, special_span = pair
        _draw(
            db,
            "dlt",
            f"{2027010 - index:07d}",
            ["01", f"{main_span + 1:02d}"],
            ["01", f"{special_span + 1:02d}"],
        )

    tight = score_span(db, "dlt", ["01", "02"], ["01", "02"], short=5, long=10)
    assert tight["drift"] == "falling"
    assert tight["ticket"]["span"] == 1
    assert tight["ticket"]["alignment"] == "aligned"
    assert "变窄" in tight["ticket"]["note"]
    assert "同向" in tight["ticket"]["note"]
    assert tight["special"]["drift"] == "falling"
    assert tight["special"]["short_avg"] == 1.0
    assert tight["special"]["long_avg"] == 4.5
    assert tight["special_ticket"]["span"] == 1
    assert tight["special_ticket"]["alignment"] == "aligned"
    assert tight["special_ticket"]["rarity"] == "common"
    assert "不构成投注建议" in tight["special_ticket"]["note"]

    wide_back = score_span(db, "dlt", ["01", "10"], ["01", "09"], short=5, long=10)
    assert wide_back["ticket"]["span"] == 9
    assert wide_back["ticket"]["alignment"] == "against"
    assert wide_back["special_ticket"]["span"] == 8
    assert wide_back["special_ticket"]["alignment"] == "against"
    assert wide_back["special_ticket"]["percentile"] == 1.0
    assert wide_back["special_ticket"]["typicality"] == 0.5

    one_back = score_span(db, "dlt", ["01", "02"], ["03"], short=5, long=10)
    assert one_back["special_ticket"] == _empty_ticket()


def test_digit_score_uses_whole_ticket_not_wrap(db):
    _draw(db, "fc3d", "2026004", ["0", "9", "1"])
    _draw(db, "fc3d", "2026003", ["1", "2", "3"])
    _draw(db, "fc3d", "2026002", ["5", "5", "5"])
    _draw(db, "fc3d", "2026001", ["9", "0", "0"])

    body = score_span(db, "fc3d", ["0", "9", "1"])
    assert body["basis"] == "digits"
    assert body["ticket"]["span"] == 9
    assert body["ticket"]["percentile"] == 1.0
    assert body["ticket"]["typicality"] == 0.5
    assert body["ticket"]["rarity"] == "common"
    assert body["ticket"]["alignment"] == "neutral"
    assert body["ticket"]["note"] == (
        "跨度 9，历史分位 100%，出现率 50%，常见，短窗 5 和长窗 5 差不多，没有明显顺逆。仅供娱乐，不构成投注建议。"
    )
    assert body["special_ticket"] == _empty_ticket()

    low = score_span(db, "pl3", [5, 5, 5])
    assert low["sample_size"] == 0
    assert low["ticket"]["span"] == 0
    assert low["ticket"]["percentile"] is None
    assert low["ticket"]["rarity"] is None
    assert low["ticket"]["alignment"] is None
    assert low["ticket"]["note"] == "跨度 0，还没有历史可对照。仅供娱乐，不构成投注建议。"

    same = score_span(db, "fc3d", "5 5 5")
    assert same["ticket"]["span"] == 0
    assert same["ticket"]["percentile"] == 0.25
    assert same["ticket"]["typicality"] == 0.25
    assert same["ticket"]["rarity"] == "typical"
    assert same["ticket"]["alignment"] == "neutral"
    assert "居中" in same["ticket"]["note"]


def test_empty_history_parameter_clamp_and_common_cap(db):
    empty = span_summary(db, "kl8", limit="no", short=None, long="bad")
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

    scored = score_span(db, "kl8", ["01", "05"])
    assert scored["ticket"]["span"] == 4
    assert scored["ticket"]["percentile"] is None
    assert scored["ticket"]["note"] == "跨度 4，还没有历史可对照。仅供娱乐，不构成投注建议。"
    assert scored["special_ticket"] == _empty_ticket()

    for span in range(1, 7):
        _draw(db, "kl8", f"202600{span}", ["01", f"{span + 1:02d}"])
    clamped = span_summary(db, "kl8", limit=1, short=1, long=1)
    assert clamped["short"] == 5
    assert clamped["long"] == 20
    assert clamped["sample_size"] == 5
    assert clamped["latest_draw"]["span"] == 6
    assert clamped["mean"] == 4.0
    assert 1 not in {item["span"] for item in clamped["distribution"]}

    opened = span_summary(db, "kl8", short=30, long=20)
    assert opened["short"] == 30
    assert opened["long"] == 31
    assert opened["sample_size"] == 6
    assert opened["mean"] == 3.5

    for span in range(1, 10):
        _draw(db, "ssq", f"202610{span}", ["01", f"{span + 1:02d}"])
    capped = span_summary(db, "ssq")
    assert capped["sample_size"] == 9
    assert len(capped["common"]) == 8
    assert [item["span"] for item in capped["common"]] == list(range(1, 9))
    assert all(item["count"] == 1 and item["rate"] == 0.1111 for item in capped["common"])
    assert capped["mean"] == 5.0
    assert capped["median"] == 5

    with pytest.raises(ValueError, match="未知彩种"):
        span_summary(db, "nope")
    with pytest.raises(ValueError, match="未知彩种"):
        score_span(db, "nope", ["01"])
    with pytest.raises(ValueError):
        score_span(db, "ssq", ["01", "01", "03", "04", "05", "06"], ["01"])
    with pytest.raises(ValueError):
        score_span(db, "fc3d", ["1", "2"])
    with pytest.raises(ValueError):
        score_span(db, "kl8", ["01", "02"], ["03"])


def test_span_endpoints_bounds_and_old_contracts(client, db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "10", "20", "30"], ["16"], draw_date="2026-04-01")
    _draw(db, "ssq", "2026002", ["05", "07", "09", "11", "13", "15"], ["02"], source="crawl", draw_date="2026-04-03")

    res = client.get("/api/analysis/ssq/span")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == GET_KEYS
    assert body["sample_size"] == 2
    assert body["short"] == 10
    assert body["long"] == 50
    assert body["basis"] == "main"
    assert body["disclaimer"] == DISCLAIMER
    assert body["data_status"] == "mixed"
    assert body["latest_draw"]["span"] == 10
    assert body["mean"] == 19.5
    assert body["special"] is None

    custom = client.get("/api/analysis/ssq/span", params={"limit": 80, "short": 5, "long": 20})
    assert custom.status_code == 200
    assert custom.json()["short"] == 5
    assert custom.json()["long"] == 20

    widened = client.get("/api/analysis/ssq/span", params={"short": 30, "long": 20})
    assert widened.status_code == 200
    assert widened.json()["short"] == 30
    assert widened.json()["long"] == 31

    assert client.get("/api/analysis/ssq/span", params={"limit": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/span", params={"limit": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/span", params={"short": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/span", params={"short": 31}).status_code == 422
    assert client.get("/api/analysis/ssq/span", params={"long": 19}).status_code == 422
    assert client.get("/api/analysis/ssq/span", params={"long": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/span", params={"limit": 5, "short": 5, "long": 20}).status_code == 200
    assert client.get("/api/analysis/ssq/span", params={"limit": 200, "short": 30, "long": 200}).status_code == 200

    unknown = client.get("/api/analysis/nope/span")
    assert unknown.status_code == 400
    assert "未知彩种" in unknown.json()["detail"]

    empty = client.get("/api/analysis/kl8/span")
    assert empty.status_code == 200
    assert empty.json()["sample_size"] == 0
    assert empty.json()["latest_draw"] is None
    assert empty.json()["distribution"] == []
    assert empty.json()["drift"] is None

    alias = client.get("/api/analysis/3d/span")
    assert alias.status_code == 200
    assert alias.json()["lottery_type"] == "fc3d"
    assert alias.json()["mode"] == "digit"
    assert alias.json()["basis"] == "digits"

    posted = client.post(
        "/api/analysis/ssq/span",
        json={"main": "01 02 03 10 20 30", "special": "16", "limit": 80, "short": 10, "long": 50},
    )
    assert posted.status_code == 200, posted.text
    scored = posted.json()
    assert set(scored) == POST_KEYS
    assert scored["query"] == {"main": ["01", "02", "03", "10", "20", "30"], "special": ["16"]}
    assert scored["ticket"]["span"] == 29
    assert scored["ticket"]["rarity"] == "common"
    assert scored["ticket"]["alignment"] == "neutral"
    assert scored["special_ticket"]["span"] is None
    assert "仅供娱乐" in scored["ticket"]["note"]

    spaced = client.post("/api/analysis/3d/span", json={"main": ["0", "9", "1"], "short": 5, "long": 20})
    assert spaced.status_code == 200
    assert spaced.json()["lottery_type"] == "fc3d"
    assert spaced.json()["ticket"]["span"] == 9
    assert spaced.json()["mode"] == "digit"

    bad = client.post("/api/analysis/ssq/span", json={"main": ["99"], "special": ["01"]})
    assert bad.status_code == 400
    duplicate = client.post(
        "/api/analysis/ssq/span",
        json={"main": ["01", "01", "03", "04", "05", "06"], "special": ["01"]},
    )
    assert duplicate.status_code == 400
    short = client.post("/api/analysis/fc3d/span", json={"main": ["1", "2"]})
    assert short.status_code == 400
    extra = client.post("/api/analysis/kl8/span", json={"main": ["01", "02"], "special": ["03"]})
    assert extra.status_code == 400
    unknown_post = client.post("/api/analysis/nope/span", json={"main": ["01"]})
    assert unknown_post.status_code == 400
    assert client.post("/api/analysis/ssq/span", json={"main": ["01"], "limit": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/span", json={"main": ["01"], "short": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/span", json={"main": ["01"], "long": 201}).status_code == 422

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
    assert set(shape_body["span"]) == {"min", "max", "avg"}
    assert shape_body["span"] == {"min": 10, "max": 29, "avg": 19.5}
    assert "pulse" not in shape_body
    assert "distribution" not in shape_body
    assert "drift" not in shape_body
    direct = shape_stats(db, "ssq", limit=50)
    assert set(direct["span"]) == {"min", "max", "avg"}
    assert direct["span"] == {"min": 10, "max": 29, "avg": 19.5}

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
