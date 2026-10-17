"""冷热动量：短窗口出现率减去长窗口出现率。

特别号单独统计，不进入主号 numbers / rising / falling / flat。
数字彩按位置（百/十/个等）计算，顶层号码列表留空。
阈值 0.02：delta >= 阈值升温，delta <= -阈值降温，其余持平。
出现率的分母是请求的窗口长度，历史更短时也不改分母。
"""
from __future__ import annotations

import json

from app.models import Draw
from app.services.momentum import DISCLAIMER, THRESHOLD, momentum_summary, score_momentum

GET_KEYS = {
    "lottery_type",
    "mode",
    "sample_size",
    "short",
    "long",
    "threshold",
    "numbers",
    "rising",
    "falling",
    "flat",
    "positions",
    "special",
    "latest_draw",
    "data_status",
    "disclaimer",
}

POST_KEYS = GET_KEYS | {"query", "ticket", "special_ticket"}

STAT_KEYS = {"number", "hits_short", "hits_long", "rate_short", "rate_long", "delta", "trend"}
TICKET_KEYS = {"rising", "falling", "flat", "rising_count", "falling_count", "flat_count", "score"}


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


def _by_number(rows):
    return {item["number"]: item for item in rows}


def _seed_ssq(db):
    """50 期双色球。下标 0 是最新一期。窗口 short=10、long=50。"""
    for index in range(50):
        main = ["20", "21", "22"]
        if index < 10:
            main.append("01")
        if index in (0, 1) or 10 <= index <= 17:
            main.append("03")
        if index == 3:
            main.extend(["04", "04"])
        if index == 0 or 10 <= index <= 12:
            main.append("07")
        if index == 10:
            main.append("08")
        if index == 1 or 13 <= index <= 16:
            main.append("09")
        if index == 2 or 17 <= index <= 21:
            main.append("10")
        if 10 <= index <= 29:
            main.append("02")
        special = ["16"]
        if index < 10:
            special.append("05")
        if 10 <= index <= 29:
            special.append("06")
        _draw(
            db,
            "ssq",
            f"{2026001 + 49 - index}",
            main,
            special,
            source="crawl" if index == 0 else "seed",
            draw_date="2026-06-01" if index == 0 else "",
        )


def test_threshold_is_two_percent():
    assert THRESHOLD == 0.02


def test_set_classifies_acceleration_and_keeps_specials_separate(db):
    _seed_ssq(db)
    body = momentum_summary(db, "ssq", limit=80, short=10, long=50)
    assert set(body) == GET_KEYS
    assert body["lottery_type"] == "ssq"
    assert body["mode"] == "set"
    assert body["sample_size"] == 50
    assert body["short"] == 10
    assert body["long"] == 50
    assert body["threshold"] == 0.02
    assert body["positions"] == []
    assert body["data_status"] == "mixed"
    assert body["disclaimer"] == DISCLAIMER
    assert "仅供娱乐" in body["disclaimer"]
    assert "不构成投注建议" in body["disclaimer"]
    assert body["latest_draw"]["issue"] == "2026050"
    assert body["latest_draw"]["draw_date"] == "2026-06-01"
    assert body["latest_draw"]["main"] == ["20", "21", "22", "01", "03", "07"]
    assert body["latest_draw"]["special"] == ["16", "05"]

    stats = _by_number(body["numbers"])
    assert set(stats) == {f"{n:02d}" for n in range(1, 34)}
    assert set(stats["01"]) == STAT_KEYS
    assert stats["01"] == {
        "number": "01",
        "hits_short": 10,
        "hits_long": 10,
        "rate_short": 1.0,
        "rate_long": 0.2,
        "delta": 0.8,
        "trend": "rising",
    }
    assert stats["04"]["hits_short"] == 1
    assert stats["04"]["hits_long"] == 1
    assert stats["04"]["delta"] == 0.08
    assert stats["04"]["trend"] == "rising"
    assert stats["07"] == {
        "number": "07",
        "hits_short": 1,
        "hits_long": 4,
        "rate_short": 0.1,
        "rate_long": 0.08,
        "delta": 0.02,
        "trend": "rising",
    }
    assert stats["02"]["hits_short"] == 0
    assert stats["02"]["hits_long"] == 20
    assert stats["02"]["delta"] == -0.4
    assert stats["02"]["trend"] == "falling"
    assert stats["08"]["delta"] == -0.02
    assert stats["08"]["trend"] == "falling"
    assert stats["10"]["hits_short"] == 1
    assert stats["10"]["hits_long"] == 6
    assert stats["10"]["delta"] == -0.02
    assert stats["10"]["trend"] == "falling"
    assert stats["03"]["hits_short"] == 2
    assert stats["03"]["hits_long"] == 10
    assert stats["03"]["delta"] == 0.0
    assert stats["03"]["trend"] == "flat"
    assert stats["09"]["delta"] == 0.0
    assert stats["20"]["hits_short"] == 10
    assert stats["20"]["hits_long"] == 50
    assert stats["20"]["trend"] == "flat"
    assert stats["05"]["trend"] == "flat"
    assert stats["06"]["trend"] == "flat"

    assert body["rising"] == ["01", "04", "07"]
    assert body["falling"] == ["02", "08", "10"]
    assert set(body["rising"]) | set(body["falling"]) | set(body["flat"]) == set(stats)
    assert "05" in body["flat"]
    assert "06" in body["flat"]
    assert body["numbers"][0]["number"] == "01"
    assert body["numbers"][-1]["number"] == "33"

    special = body["special"]
    assert special["label"] == "蓝球"
    spec = _by_number(special["numbers"])
    assert set(spec) == {f"{n:02d}" for n in range(1, 17)}
    assert spec["05"]["trend"] == "rising"
    assert spec["05"]["delta"] == 0.8
    assert spec["06"]["trend"] == "falling"
    assert spec["06"]["delta"] == -0.4
    assert spec["16"]["trend"] == "flat"
    assert special["rising"] == ["05"]
    assert special["falling"] == ["06"]
    assert "05" not in body["rising"]
    assert "06" not in body["falling"]


def test_inside_threshold_stays_flat(db):
    for index in range(100):
        main = ["20"]
        if index == 0 or 10 <= index <= 17:
            main.append("01")
        if index == 10:
            main.append("02")
        if index == 1 or 18 <= index <= 24:
            main.append("03")
        if index in (11, 12):
            main.append("04")
        _draw(db, "ssq", f"{2026100 + 99 - index}", main, ["01"])
    body = momentum_summary(db, "ssq", limit=100, short=10, long=100)
    stats = _by_number(body["numbers"])
    assert stats["01"]["delta"] == 0.01
    assert stats["01"]["trend"] == "flat"
    assert stats["02"]["delta"] == -0.01
    assert stats["02"]["trend"] == "flat"
    assert stats["03"]["delta"] == 0.02
    assert stats["03"]["trend"] == "rising"
    assert stats["04"]["delta"] == -0.02
    assert stats["04"]["trend"] == "falling"
    assert "01" in body["flat"]
    assert body["special"]["numbers"]
    assert _by_number(body["special"]["numbers"])["01"]["trend"] == "flat"


def test_dlt_specials_do_not_leak_into_main(db):
    _draw(db, "dlt", "2026201", ["02", "03", "04", "05", "06"], ["01", "02"])
    body = momentum_summary(db, "dlt", short=5, long=20)
    assert body["mode"] == "set"
    assert body["sample_size"] == 1
    stats = _by_number(body["numbers"])
    assert stats["01"]["hits_short"] == 0
    assert stats["01"]["trend"] == "flat"
    assert stats["02"]["hits_short"] == 1
    assert stats["02"]["hits_long"] == 1
    assert stats["02"]["rate_short"] == 0.2
    assert stats["02"]["rate_long"] == 0.05
    assert stats["02"]["trend"] == "rising"
    spec = _by_number(body["special"]["numbers"])
    assert body["special"]["label"] == "后区"
    assert spec["01"]["trend"] == "rising"
    assert spec["01"]["hits_short"] == 1
    assert "01" not in body["rising"]


def test_digit_momentum_is_per_position(db):
    for index in range(50):
        hundred = "1" if index < 10 else "0"
        ten = "5" if 10 <= index <= 29 else "0"
        unit = "3" if index in (0, 1) or 10 <= index <= 17 else "0"
        _draw(db, "fc3d", f"{2026301 + 49 - index}", [hundred, ten, unit])
    body = momentum_summary(db, "fc3d", limit=80, short=10, long=50)
    assert body["mode"] == "digit"
    assert body["numbers"] == []
    assert body["rising"] == []
    assert body["falling"] == []
    assert body["flat"] == []
    assert body["special"] is None
    assert [item["label"] for item in body["positions"]] == ["百", "十", "个"]
    assert [item["index"] for item in body["positions"]] == [0, 1, 2]

    hundred, ten, unit = body["positions"]
    h = _by_number(hundred["numbers"])
    t = _by_number(ten["numbers"])
    u = _by_number(unit["numbers"])
    assert set(h) == {str(n) for n in range(10)}
    assert h["1"]["hits_short"] == 10
    assert h["1"]["hits_long"] == 10
    assert h["1"]["delta"] == 0.8
    assert h["1"]["trend"] == "rising"
    assert h["0"]["hits_short"] == 0
    assert h["0"]["hits_long"] == 40
    assert h["0"]["trend"] == "falling"
    assert hundred["rising"] == ["1"]
    assert hundred["falling"] == ["0"]
    assert t["5"]["trend"] == "falling"
    assert t["5"]["delta"] == -0.4
    assert t["0"]["trend"] == "rising"
    assert t["0"]["delta"] == 0.4
    assert ten["rising"] == ["0"]
    assert ten["falling"] == ["5"]
    assert u["3"]["hits_short"] == 2
    assert u["3"]["hits_long"] == 10
    assert u["3"]["trend"] == "flat"
    assert u["0"]["trend"] == "flat"
    assert unit["rising"] == []
    assert unit["falling"] == []
    assert h["0"]["trend"] != t["0"]["trend"]
    assert t["0"]["trend"] != u["0"]["trend"]

    _draw(db, "pl5", "2026401", ["1", "2", "3", "4", "5"])
    pl5 = momentum_summary(db, "pl5", short=5, long=20)
    assert [item["label"] for item in pl5["positions"]] == ["万", "千", "百", "十", "个"]
    assert pl5["positions"][0]["rising"] == ["1"]
    assert pl5["numbers"] == []


def test_qxc_special_momentum_stays_out_of_positions(db):
    for index in range(20):
        special = ["7"] if index < 10 else ["3"]
        _draw(db, "qxc", f"{2026501 + 19 - index}", ["0", "0", "0", "0", "0", "0"], special)
    body = momentum_summary(db, "qxc", limit=20, short=10, long=20)
    assert body["mode"] == "digit"
    assert len(body["positions"]) == 6
    assert body["positions"][0]["label"] == "1"
    assert body["positions"][0]["rising"] == []
    assert body["positions"][0]["falling"] == []
    assert "7" in body["positions"][0]["flat"]
    spec = _by_number(body["special"]["numbers"])
    assert body["special"]["label"] == "特别号"
    assert spec["7"]["trend"] == "rising"
    assert spec["7"]["delta"] == 0.5
    assert spec["3"]["trend"] == "falling"
    assert spec["3"]["delta"] == -0.5
    assert body["special"]["rising"] == ["7"]
    assert body["special"]["falling"] == ["3"]
    assert all("7" not in pos["rising"] for pos in body["positions"])


def test_empty_history_and_blank_rows(db):
    empty = momentum_summary(db, "kl8")
    assert empty["sample_size"] == 0
    assert empty["latest_draw"] is None
    assert empty["mode"] == "set"
    assert empty["data_status"] == "seed"
    assert empty["short"] == 10
    assert empty["long"] == 50
    assert empty["rising"] == []
    assert empty["falling"] == []
    assert len(empty["numbers"]) == 80
    assert len(empty["flat"]) == 80
    assert all(item["trend"] == "flat" and item["delta"] == 0.0 for item in empty["numbers"])
    assert empty["special"] is None
    assert empty["positions"] == []
    assert "仅供娱乐" in empty["disclaimer"]

    fc3d = momentum_summary(db, "fc3d")
    assert fc3d["numbers"] == []
    assert [item["label"] for item in fc3d["positions"]] == ["百", "十", "个"]
    assert all(len(item["flat"]) == 10 and item["rising"] == [] for item in fc3d["positions"])

    pl5 = momentum_summary(db, "pl5")
    assert [item["label"] for item in pl5["positions"]] == ["万", "千", "百", "十", "个"]

    _draw(db, "kl8", "2026606", ["01"])
    _draw(db, "kl8", "2026605", [])
    _draw(db, "kl8", "2026604", ["02"])
    _draw(db, "kl8", "2026603", ["03"])
    _draw(db, "kl8", "2026602", ["04"])
    _draw(db, "kl8", "2026601", ["05"])
    window = momentum_summary(db, "kl8", limit=5, short=5, long=20)
    assert window["sample_size"] == 4
    assert window["latest_draw"]["issue"] == "2026606"
    stats = _by_number(window["numbers"])
    assert stats["01"]["hits_short"] == 1
    assert stats["01"]["hits_long"] == 1
    assert stats["05"]["hits_long"] == 0
    assert stats["02"]["hits_long"] == 1

    try:
        momentum_summary(db, "nope")
    except ValueError as exc:
        assert "未知彩种" in str(exc)
    else:
        raise AssertionError("unknown type should fail")


def test_clamp_windows_and_limit(db):
    for index in range(30):
        _draw(db, "kl8", f"{index:04d}", ["01", "02"])
    low = momentum_summary(db, "kl8", limit=1, short=1, long=1)
    assert low["short"] == 5
    assert low["long"] == 20
    assert low["sample_size"] == 5

    swapped = momentum_summary(db, "kl8", limit=999, short=40, long=25)
    assert swapped["short"] == 30
    assert swapped["long"] == 31
    assert swapped["sample_size"] == 30

    wide = momentum_summary(db, "kl8", short="nope", long=None, limit="nope")
    assert wide["short"] == 10
    assert wide["long"] == 50
    assert wide["sample_size"] == 30

    capped = momentum_summary(db, "kl8", limit=10, short=5, long=20)
    stats = _by_number(capped["numbers"])
    assert capped["sample_size"] == 10
    assert capped["latest_draw"]["issue"] == "0029"
    assert stats["01"]["hits_short"] == 5
    assert stats["01"]["hits_long"] == 10
    assert stats["01"]["rate_short"] == 1.0
    assert stats["01"]["rate_long"] == 0.5
    assert stats["01"]["delta"] == 0.5
    assert stats["01"]["trend"] == "rising"


def test_score_ticket_splits_trends_without_mixing_specials(db):
    _seed_ssq(db)
    body = score_momentum(db, "ssq", ["07", "01", "02", "20", "21", "03"], ["05", "16"])
    assert set(body) == POST_KEYS
    assert body["query"] == {
        "main": ["07", "01", "02", "20", "21", "03"],
        "special": ["05", "16"],
    }
    assert set(body["ticket"]) == TICKET_KEYS
    assert body["ticket"]["rising"] == ["07", "01"]
    assert body["ticket"]["falling"] == ["02"]
    assert body["ticket"]["flat"] == ["20", "21", "03"]
    assert body["ticket"]["rising_count"] == 2
    assert body["ticket"]["falling_count"] == 1
    assert body["ticket"]["flat_count"] == 3
    assert body["ticket"]["score"] == 1
    assert body["special_ticket"]["rising"] == ["05"]
    assert body["special_ticket"]["falling"] == []
    assert body["special_ticket"]["flat"] == ["16"]
    assert body["special_ticket"]["score"] == 1
    assert body["ticket"]["score"] == 1
    assert body["rising"] == ["01", "04", "07"]
    assert "仅供娱乐" in body["disclaimer"]

    hot = score_momentum(db, "ssq", "01 04 07", None, short=10, long=50)
    assert hot["ticket"]["rising"] == ["01", "04", "07"]
    assert hot["ticket"]["falling"] == []
    assert hot["ticket"]["score"] == 3
    assert hot["special_ticket"]["score"] == 0
    assert hot["special_ticket"]["flat"] == []


def test_score_digit_positions_and_empty_pool(db):
    for index in range(50):
        hundred = "1" if index < 10 else "0"
        ten = "5" if 10 <= index <= 29 else "0"
        unit = "3" if index in (0, 1) or 10 <= index <= 17 else "0"
        _draw(db, "fc3d", f"{2026701 + 49 - index}", [hundred, ten, unit])
    body = score_momentum(db, "fc3d", ["1", "5", "3"])
    assert body["mode"] == "digit"
    assert body["ticket"]["rising"] == [{"index": 0, "label": "百", "number": "1"}]
    assert body["ticket"]["falling"] == [{"index": 1, "label": "十", "number": "5"}]
    assert body["ticket"]["flat"] == [{"index": 2, "label": "个", "number": "3"}]
    assert body["ticket"]["rising_count"] == 1
    assert body["ticket"]["falling_count"] == 1
    assert body["ticket"]["flat_count"] == 1
    assert body["ticket"]["score"] == 0
    assert body["special_ticket"]["score"] == 0

    zeros = score_momentum(db, "fc3d", ["0", "0", "0"])
    assert [item["label"] for item in zeros["ticket"]["falling"]] == ["百"]
    assert [item["label"] for item in zeros["ticket"]["rising"]] == ["十"]
    assert [item["label"] for item in zeros["ticket"]["flat"]] == ["个"]
    assert zeros["ticket"]["score"] == 0

    fresh = score_momentum(db, "pl3", [4, 5, 6])
    assert fresh["lottery_type"] == "pl3"
    assert fresh["sample_size"] == 0
    assert fresh["ticket"]["flat"] == [
        {"index": 0, "label": "百", "number": "4"},
        {"index": 1, "label": "十", "number": "5"},
        {"index": 2, "label": "个", "number": "6"},
    ]
    assert fresh["ticket"]["rising"] == []
    assert fresh["ticket"]["score"] == 0
    assert fresh["positions"][0]["label"] == "百"


def test_momentum_endpoints_bounds_and_old_contracts(client, db):
    _seed_ssq(db)
    res = client.get("/api/analysis/ssq/momentum")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == GET_KEYS
    assert body["sample_size"] == 50
    assert body["short"] == 10
    assert body["long"] == 50
    assert body["threshold"] == 0.02
    assert body["rising"] == ["01", "04", "07"]
    assert body["disclaimer"] == DISCLAIMER

    custom = client.get("/api/analysis/ssq/momentum", params={"limit": 50, "short": 10, "long": 50})
    assert custom.status_code == 200
    assert custom.json()["falling"] == ["02", "08", "10"]

    clamped = client.get("/api/analysis/ssq/momentum", params={"short": 30, "long": 20})
    assert clamped.status_code == 200
    assert clamped.json()["short"] == 30
    assert clamped.json()["long"] == 31

    assert client.get("/api/analysis/ssq/momentum", params={"limit": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/momentum", params={"limit": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/momentum", params={"short": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/momentum", params={"short": 31}).status_code == 422
    assert client.get("/api/analysis/ssq/momentum", params={"long": 19}).status_code == 422
    assert client.get("/api/analysis/ssq/momentum", params={"long": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/momentum", params={"limit": 200, "short": 5, "long": 200}).status_code == 200

    unknown = client.get("/api/analysis/nope/momentum")
    assert unknown.status_code == 400
    assert "未知彩种" in unknown.json()["detail"]

    empty = client.get("/api/analysis/kl8/momentum")
    assert empty.status_code == 200
    assert empty.json()["sample_size"] == 0
    assert empty.json()["latest_draw"] is None
    assert len(empty.json()["flat"]) == 80

    alias = client.get("/api/analysis/3d/momentum")
    assert alias.status_code == 200
    assert alias.json()["lottery_type"] == "fc3d"
    assert alias.json()["mode"] == "digit"
    assert [item["label"] for item in alias.json()["positions"]] == ["百", "十", "个"]

    posted = client.post(
        "/api/analysis/ssq/momentum",
        json={"main": "07 01 02 20 21 03", "special": "05 16", "limit": 80, "short": 10, "long": 50},
    )
    assert posted.status_code == 200, posted.text
    scored = posted.json()
    assert set(scored) == POST_KEYS
    assert scored["ticket"]["rising"] == ["07", "01"]
    assert scored["ticket"]["score"] == 1
    assert scored["special_ticket"]["rising"] == ["05"]
    assert scored["special_ticket"]["score"] == 1

    spaced = client.post("/api/analysis/3d/momentum", json={"main": ["1", "5", "0"], "short": 5, "long": 20})
    assert spaced.status_code == 200
    assert spaced.json()["lottery_type"] == "fc3d"
    assert spaced.json()["mode"] == "digit"

    bad = client.post("/api/analysis/ssq/momentum", json={"main": ["99"], "special": ["01"]})
    assert bad.status_code == 400
    duplicate = client.post(
        "/api/analysis/ssq/momentum",
        json={"main": ["01", "01", "03", "04", "05", "06"], "special": ["01"]},
    )
    assert duplicate.status_code == 400
    short = client.post("/api/analysis/fc3d/momentum", json={"main": ["1", "2"]})
    assert short.status_code == 400
    extra = client.post("/api/analysis/kl8/momentum", json={"main": ["01", "02"], "special": ["03"]})
    assert extra.status_code == 400
    unknown_post = client.post("/api/analysis/nope/momentum", json={"main": ["01"]})
    assert unknown_post.status_code == 400
    assert client.post("/api/analysis/ssq/momentum", json={"main": ["01"], "limit": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/momentum", json={"main": ["01"], "short": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/momentum", json={"main": ["01"], "long": 201}).status_code == 422

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
    assert "rising" not in analysis.json()
    shape = client.get("/api/analysis/ssq/shape")
    assert shape.status_code == 200
    assert "odd_even" in shape.json()
    assert "rising" not in shape.json()
    echo = client.post("/api/analysis/ssq/echo", json={"main": ["01", "02", "03", "04", "05", "06"], "special": ["16"]})
    assert echo.status_code == 200
    assert "echoes" in echo.json()
    assert "ticket" not in echo.json()
    affinity = client.get("/api/analysis/ssq/affinity")
    assert affinity.status_code == 200
    assert "companions" in affinity.json()
    assert "threshold" not in affinity.json()
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
    assert "threshold" not in collision.json()
    repeat = client.get("/api/analysis/ssq/repeat")
    assert repeat.status_code == 200
    assert "recent_pairs" in repeat.json()
    assert "threshold" not in repeat.json()
    assert "rising" not in repeat.json()
