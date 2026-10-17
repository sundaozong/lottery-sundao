"""邻号牵引：主号开出后，±1 在随后 horizon 期里出现得有多勤。

同期共现不算牵引，下一期原号重开也不算邻号。
乐透按集合，特别号单独计；数字彩按位，0 与 9 不环绕。
只统计后面刚好够 horizon 期的出现，分母是完整窗口。
"""
from __future__ import annotations

import json

from app.models import Draw
from app.services.neighbor import DISCLAIMER, neighbor_summary, score_neighbor

GET_KEYS = {
    "lottery_type",
    "mode",
    "sample_size",
    "horizon",
    "edge",
    "numbers",
    "pulled",
    "positions",
    "special",
    "latest_draw",
    "data_status",
    "disclaimer",
}

POST_KEYS = GET_KEYS | {"query", "ticket", "special_ticket"}

NUMBER_KEYS = {"number", "appearances", "triggers", "neighbors", "pull_rate", "baseline", "lift"}
NEIGHBOR_KEYS = {"number", "side", "hits", "rate", "baseline", "lift"}
PULLED_KEYS = {"source", "number", "side", "hits", "triggers", "opportunities", "rate", "baseline", "lift"}
TICKET_KEYS = {"items", "pulled", "idle", "pulled_count", "idle_count", "strength", "score"}
ITEM_KEYS = {"number", "pulled", "sources", "hits", "lift"}


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


def _edge(rows, source, number):
    found = [item for item in rows if item["source"] == source and item["number"] == number]
    assert len(found) == 1
    return found[0]


def _empty_ticket():
    return {
        "items": [],
        "pulled": [],
        "idle": [],
        "pulled_count": 0,
        "idle_count": 0,
        "strength": 0.0,
        "score": 0,
    }


def test_set_pull_uses_following_draws_not_same_draw(db):
    _draw(db, "ssq", "2026001", ["01", "05"], ["16"], draw_date="2026-01-01")
    _draw(db, "ssq", "2026002", ["02", "10"], ["03"], draw_date="2026-01-03")
    _draw(db, "ssq", "2026003", ["03", "06"], ["01"], draw_date="2026-01-05")
    _draw(db, "ssq", "2026004", ["07"], ["02"], source="crawl", draw_date="2026-01-08")

    body = neighbor_summary(db, "ssq", limit=80, horizon=2)
    assert set(body) == GET_KEYS
    assert body["lottery_type"] == "ssq"
    assert body["mode"] == "set"
    assert body["sample_size"] == 4
    assert body["horizon"] == 2
    assert body["edge"] == "clamp"
    assert body["positions"] == []
    assert body["data_status"] == "mixed"
    assert body["disclaimer"] == DISCLAIMER
    assert "仅供娱乐" in body["disclaimer"]
    assert "不构成投注建议" in body["disclaimer"]
    assert body["latest_draw"] == {
        "issue": "2026004",
        "draw_date": "2026-01-08",
        "main": ["07"],
        "special": ["02"],
    }

    stats = _by_number(body["numbers"])
    assert list(stats) == ["01", "02", "03", "05", "06", "07", "10"]
    assert set(stats["01"]) == NUMBER_KEYS
    assert set(stats["01"]["neighbors"][0]) == NEIGHBOR_KEYS
    assert stats["01"] == {
        "number": "01",
        "appearances": 1,
        "triggers": 1,
        "neighbors": [
            {"number": "02", "side": "high", "hits": 1, "rate": 0.5, "baseline": 0.25, "lift": 0.25},
        ],
        "pull_rate": 0.5,
        "baseline": 0.25,
        "lift": 0.25,
    }
    assert stats["05"] == {
        "number": "05",
        "appearances": 1,
        "triggers": 1,
        "neighbors": [
            {"number": "04", "side": "low", "hits": 0, "rate": 0.0, "baseline": 0.0, "lift": 0.0},
            {"number": "06", "side": "high", "hits": 1, "rate": 0.5, "baseline": 0.25, "lift": 0.25},
        ],
        "pull_rate": 0.25,
        "baseline": 0.125,
        "lift": 0.125,
    }
    assert stats["02"]["triggers"] == 1
    assert stats["02"]["pull_rate"] == 0.25
    assert stats["02"]["baseline"] == 0.25
    assert stats["02"]["lift"] == 0.0
    assert stats["02"]["neighbors"][0]["lift"] == -0.25
    assert stats["02"]["neighbors"][1] == {
        "number": "03",
        "side": "high",
        "hits": 1,
        "rate": 0.5,
        "baseline": 0.25,
        "lift": 0.25,
    }
    assert stats["10"]["lift"] == 0.0
    assert stats["03"]["triggers"] == 0
    assert stats["03"]["pull_rate"] is None
    assert stats["03"]["lift"] is None
    assert stats["03"]["baseline"] == 0.125
    assert stats["03"]["neighbors"][0]["rate"] is None
    assert stats["06"]["triggers"] == 0
    assert stats["07"]["appearances"] == 1
    assert stats["07"]["triggers"] == 0

    assert [item["number"] for item in body["pulled"]] == ["02", "03", "06", "04", "09", "11", "01"]
    assert set(body["pulled"][0]) == PULLED_KEYS
    assert _edge(body["pulled"], "01", "02")["side"] == "high"
    assert _edge(body["pulled"], "01", "02")["opportunities"] == 2
    assert _edge(body["pulled"], "05", "06")["lift"] == 0.25
    assert _edge(body["pulled"], "02", "01")["lift"] == -0.25
    assert all(item["triggers"] > 0 for item in body["pulled"])

    special = body["special"]
    assert special["label"] == "蓝球"
    spec = _by_number(special["numbers"])
    assert list(spec) == ["01", "02", "03", "16"]
    assert spec["16"]["neighbors"] == [
        {"number": "15", "side": "low", "hits": 0, "rate": 0.0, "baseline": 0.0, "lift": 0.0},
    ]
    assert spec["16"]["pull_rate"] == 0.0
    assert spec["03"]["pull_rate"] == 0.25
    assert spec["03"]["lift"] == 0.125
    assert spec["03"]["neighbors"][0]["number"] == "02"
    assert spec["01"]["triggers"] == 0
    assert [item["number"] for item in special["pulled"]] == ["02", "04", "15"]
    assert _edge(special["pulled"], "03", "02")["lift"] == 0.25
    assert "02" not in {item["number"] for item in body["pulled"] if item["source"] == "03"}
    assert all(item["source"] != "16" for item in body["pulled"])


def test_boundaries_clamp_and_dlt_specials_stay_out_of_main(db):
    _draw(db, "ssq", "2026101", ["01", "33"], ["01"])
    _draw(db, "ssq", "2026102", ["32"], ["16"])
    _draw(db, "ssq", "2026103", ["02"], ["15"])
    body = neighbor_summary(db, "ssq", horizon=1)
    stats = _by_number(body["numbers"])
    assert stats["01"]["neighbors"] == [
        {"number": "02", "side": "high", "hits": 0, "rate": 0.0, "baseline": 0.3333, "lift": -0.3333},
    ]
    assert stats["01"]["lift"] == -0.3333
    assert stats["33"]["neighbors"] == [
        {"number": "32", "side": "low", "hits": 1, "rate": 1.0, "baseline": 0.3333, "lift": 0.6667},
    ]
    assert stats["33"]["pull_rate"] == 1.0
    assert stats["33"]["lift"] == 0.6667
    assert "00" not in {item["number"] for item in stats["01"]["neighbors"]}
    assert "34" not in {item["number"] for item in stats["33"]["neighbors"]}
    assert _edge(body["pulled"], "01", "02")["hits"] == 0
    assert _edge(body["pulled"], "33", "32")["hits"] == 1
    assert stats["32"]["pull_rate"] == 0.0
    assert stats["32"]["baseline"] == 0.1667
    assert stats["32"]["lift"] == -0.1667
    assert stats["02"]["triggers"] == 0
    assert stats["02"]["baseline"] == 0.1667

    spec = _by_number(body["special"]["numbers"])
    assert spec["16"]["neighbors"] == [
        {"number": "15", "side": "low", "hits": 1, "rate": 1.0, "baseline": 0.3333, "lift": 0.6667},
    ]
    assert spec["01"]["neighbors"][0]["number"] == "02"
    assert spec["01"]["neighbors"][0]["hits"] == 0

    _draw(db, "dlt", "2026111", ["02", "03", "04", "05", "06"], ["01", "02"])
    _draw(db, "dlt", "2026112", ["10", "11", "12", "13", "14"], ["02", "03"])
    dlt = neighbor_summary(db, "dlt", horizon=1)
    main = _by_number(dlt["numbers"])
    assert dlt["special"]["label"] == "后区"
    assert main["02"]["neighbors"][0]["hits"] == 0
    assert main["02"]["neighbors"][1]["hits"] == 0
    assert "01" not in main
    back = _by_number(dlt["special"]["numbers"])
    assert back["01"]["neighbors"] == [
        {"number": "02", "side": "high", "hits": 1, "rate": 1.0, "baseline": 1.0, "lift": 0.0},
    ]
    assert all(item["source"] != "01" or item["number"] != "02" for item in dlt["pulled"])


def test_same_draw_pair_and_exact_repeat_are_not_neighbor_hits(db):
    _draw(db, "ssq", "2026301", ["08", "08", "09"], ["01"])
    _draw(db, "ssq", "2026302", ["08"], ["01"])
    body = neighbor_summary(db, "ssq", horizon=1)
    stats = _by_number(body["numbers"])
    assert stats["08"]["appearances"] == 2
    assert stats["08"]["triggers"] == 1
    assert stats["08"]["neighbors"][1] == {
        "number": "09",
        "side": "high",
        "hits": 0,
        "rate": 0.0,
        "baseline": 0.5,
        "lift": -0.5,
    }
    assert stats["08"]["neighbors"][0]["number"] == "07"
    assert stats["08"]["neighbors"][0]["hits"] == 0
    low = _edge(body["pulled"], "09", "08")
    assert low["hits"] == 1
    assert low["side"] == "low"
    assert _edge(body["pulled"], "08", "09")["hits"] == 0


def test_digit_pull_is_per_position_and_clamps_ends(db):
    _draw(db, "fc3d", "2026201", ["0", "5", "9"])
    _draw(db, "fc3d", "2026202", ["1", "5", "8"])
    _draw(db, "fc3d", "2026203", ["1", "6", "9"])
    body = neighbor_summary(db, "fc3d", horizon=1)
    assert body["mode"] == "digit"
    assert body["edge"] == "clamp"
    assert body["numbers"] == []
    assert body["pulled"] == []
    assert body["special"] is None
    assert [item["label"] for item in body["positions"]] == ["百", "十", "个"]
    assert [item["index"] for item in body["positions"]] == [0, 1, 2]

    hundred, ten, unit = body["positions"]
    h = _by_number(hundred["numbers"])
    t = _by_number(ten["numbers"])
    u = _by_number(unit["numbers"])
    assert h["0"] == {
        "number": "0",
        "appearances": 1,
        "triggers": 1,
        "neighbors": [
            {"number": "1", "side": "high", "hits": 1, "rate": 1.0, "baseline": 0.6667, "lift": 0.3333},
        ],
        "pull_rate": 1.0,
        "baseline": 0.6667,
        "lift": 0.3333,
    }
    assert all(item["number"] != "9" for item in h["0"]["neighbors"])
    assert h["1"]["appearances"] == 2
    assert h["1"]["triggers"] == 1
    assert h["1"]["pull_rate"] == 0.0
    assert h["1"]["baseline"] == 0.1667
    assert h["1"]["lift"] == -0.1667
    assert h["1"]["neighbors"][0]["lift"] == -0.3333
    assert t["5"]["appearances"] == 2
    assert t["5"]["triggers"] == 2
    assert t["5"]["neighbors"][1] == {
        "number": "6",
        "side": "high",
        "hits": 1,
        "rate": 0.5,
        "baseline": 0.3333,
        "lift": 0.1667,
    }
    assert t["5"]["pull_rate"] == 0.25
    assert t["5"]["baseline"] == 0.1667
    assert t["5"]["lift"] == 0.0833
    assert u["9"]["neighbors"] == [
        {"number": "8", "side": "low", "hits": 1, "rate": 1.0, "baseline": 0.3333, "lift": 0.6667},
    ]
    assert all(item["number"] != "0" for item in u["9"]["neighbors"])
    assert u["8"]["pull_rate"] == 0.5
    assert u["8"]["baseline"] == 0.3333
    assert u["8"]["lift"] == 0.1667
    assert _edge(hundred["pulled"], "0", "1")["lift"] == 0.3333
    assert _edge(unit["pulled"], "9", "8")["index"] == 2
    assert _edge(unit["pulled"], "9", "8")["label"] == "个"
    assert hundred["pulled"][0]["index"] == 0
    assert "8" not in {item["number"] for item in hundred["pulled"]}

    _draw(db, "pl5", "2026401", ["1", "2", "3", "4", "5"])
    pl5 = neighbor_summary(db, "pl5", horizon=1)
    assert [item["label"] for item in pl5["positions"]] == ["万", "千", "百", "十", "个"]
    assert pl5["numbers"] == []
    assert pl5["positions"][0]["numbers"][0]["number"] == "1"
    assert pl5["positions"][0]["numbers"][0]["triggers"] == 0


def test_qxc_special_clamps_without_entering_positions(db):
    _draw(db, "qxc", "2026501", ["0", "9", "1", "2", "3", "4"], ["0"])
    _draw(db, "qxc", "2026502", ["1", "8", "1", "2", "3", "4"], ["1"])
    _draw(db, "qxc", "2026503", ["0", "9", "5", "5", "5", "5"], ["14"])
    body = neighbor_summary(db, "qxc", horizon=1)
    assert body["mode"] == "digit"
    assert len(body["positions"]) == 6
    assert body["positions"][0]["label"] == "1"
    assert body["positions"][1]["label"] == "2"
    head = _by_number(body["positions"][0]["numbers"])
    second = _by_number(body["positions"][1]["numbers"])
    assert head["0"]["neighbors"] == [
        {"number": "1", "side": "high", "hits": 1, "rate": 1.0, "baseline": 0.3333, "lift": 0.6667},
    ]
    assert second["9"]["neighbors"] == [
        {"number": "8", "side": "low", "hits": 1, "rate": 1.0, "baseline": 0.3333, "lift": 0.6667},
    ]
    assert all(item["number"] != "0" for item in second["9"]["neighbors"])
    spec = _by_number(body["special"]["numbers"])
    assert body["special"]["label"] == "特别号"
    assert spec["0"]["neighbors"] == [
        {"number": "1", "side": "high", "hits": 1, "rate": 1.0, "baseline": 0.3333, "lift": 0.6667},
    ]
    assert spec["14"]["triggers"] == 0
    assert spec["14"]["neighbors"] == [
        {"number": "13", "side": "low", "hits": 0, "rate": None, "baseline": 0.0, "lift": None},
    ]
    assert all(item["number"] != "0" for item in spec["14"]["neighbors"])
    assert _edge(body["special"]["pulled"], "0", "1")["lift"] == 0.6667
    assert all(item.get("label") != "特别号" for item in body["positions"][0]["pulled"])


def test_empty_history_blank_rows_and_unknown(db):
    empty = neighbor_summary(db, "kl8")
    assert empty["sample_size"] == 0
    assert empty["horizon"] == 3
    assert empty["edge"] == "clamp"
    assert empty["latest_draw"] is None
    assert empty["mode"] == "set"
    assert empty["data_status"] == "seed"
    assert empty["numbers"] == []
    assert empty["pulled"] == []
    assert empty["positions"] == []
    assert empty["special"] is None
    assert "仅供娱乐" in empty["disclaimer"]

    fc3d = neighbor_summary(db, "fc3d")
    assert fc3d["numbers"] == []
    assert fc3d["pulled"] == []
    assert [item["label"] for item in fc3d["positions"]] == ["百", "十", "个"]
    assert all(item["numbers"] == [] and item["pulled"] == [] for item in fc3d["positions"])

    pl5 = neighbor_summary(db, "pl5")
    assert [item["label"] for item in pl5["positions"]] == ["万", "千", "百", "十", "个"]

    ssq = neighbor_summary(db, "ssq")
    assert ssq["special"] == {"label": "蓝球", "numbers": [], "pulled": []}

    _draw(db, "ssq", "2026601", ["01"], ["04"])
    _draw(db, "ssq", "2026602", [], ["04"])
    _draw(db, "ssq", "2026603", ["02"], ["05"], source="crawl")
    skipped = neighbor_summary(db, "ssq", horizon=1)
    assert skipped["sample_size"] == 2
    assert skipped["data_status"] == "mixed"
    assert skipped["latest_draw"]["issue"] == "2026603"
    stats = _by_number(skipped["numbers"])
    assert stats["01"]["triggers"] == 1
    assert stats["01"]["neighbors"][0]["hits"] == 1
    assert stats["01"]["lift"] == 0.5
    assert "2026602" not in (skipped["latest_draw"]["issue"])

    try:
        neighbor_summary(db, "nope")
    except ValueError as exc:
        assert "未知彩种" in str(exc)
    else:
        raise AssertionError("unknown type should fail")


def test_clamp_limit_and_horizon(db):
    for index in range(30):
        _draw(db, "kl8", f"{index:04d}", ["01", "02"])

    low = neighbor_summary(db, "kl8", limit=1, horizon=0)
    assert low["horizon"] == 1
    assert low["sample_size"] == 5
    assert low["latest_draw"]["issue"] == "0029"
    stats = _by_number(low["numbers"])
    assert stats["01"]["appearances"] == 5
    assert stats["01"]["triggers"] == 4
    assert stats["01"]["neighbors"][0]["number"] == "02"
    assert stats["01"]["neighbors"][0]["hits"] == 4
    assert stats["01"]["lift"] == 0.0

    wide = neighbor_summary(db, "kl8", limit=999, horizon=99)
    assert wide["horizon"] == 10
    assert wide["sample_size"] == 30
    assert _by_number(wide["numbers"])["01"]["triggers"] == 20

    defaulted = neighbor_summary(db, "kl8", limit="nope", horizon=None)
    assert defaulted["horizon"] == 3
    assert defaulted["sample_size"] == 30
    assert _by_number(defaulted["numbers"])["01"]["triggers"] == 27

    capped = neighbor_summary(db, "kl8", limit=10, horizon=1)
    assert capped["sample_size"] == 10
    assert capped["latest_draw"]["issue"] == "0029"
    assert _by_number(capped["numbers"])["01"]["triggers"] == 9
    assert _by_number(capped["numbers"])["02"]["triggers"] == 9


def test_score_ticket_against_recent_window(db):
    _draw(db, "ssq", "2026201", ["05", "21", "22", "23", "24", "25"], ["05"])
    _draw(db, "ssq", "2026202", ["06", "21", "22", "23", "24", "25"], ["06"])
    _draw(db, "ssq", "2026203", ["06", "30", "31", "32", "33", "01"], ["06"])
    body = score_neighbor(
        db,
        "ssq",
        ["05", "07", "04", "16", "18", "32"],
        ["05", "07"],
        horizon=1,
    )
    assert set(body) == POST_KEYS
    assert body["horizon"] == 1
    assert body["query"] == {
        "main": ["05", "07", "04", "16", "18", "32"],
        "special": ["05", "07"],
    }
    assert set(body["ticket"]) == TICKET_KEYS
    assert set(body["ticket"]["items"][0]) == ITEM_KEYS
    by_item = {item["number"]: item for item in body["ticket"]["items"]}
    assert by_item["05"] == {
        "number": "05",
        "pulled": True,
        "sources": ["06"],
        "hits": 1,
        "lift": -0.3333,
    }
    assert by_item["07"]["pulled"] is True
    assert by_item["07"]["sources"] == ["06"]
    assert by_item["07"]["lift"] == 0.0
    assert by_item["32"] == {
        "number": "32",
        "pulled": True,
        "sources": ["31", "33"],
        "hits": 1,
        "lift": 0.0,
    }
    assert by_item["04"]["pulled"] is False
    assert by_item["04"]["sources"] == []
    assert by_item["04"]["lift"] == 0.0
    assert body["ticket"]["pulled"] == ["05", "07", "32"]
    assert body["ticket"]["idle"] == ["04", "16", "18"]
    assert body["ticket"]["pulled_count"] == 3
    assert body["ticket"]["idle_count"] == 3
    assert body["ticket"]["score"] == 3
    assert body["ticket"]["strength"] == -0.3333
    assert body["special_ticket"]["pulled"] == ["05", "07"]
    assert body["special_ticket"]["score"] == 2
    assert body["special_ticket"]["items"][0]["lift"] == -0.3333
    assert body["special_ticket"]["strength"] == -0.3333
    assert body["ticket"]["score"] == 3
    assert "仅供娱乐" in body["disclaimer"]

    repeat = score_neighbor(db, "ssq", ["06", "30", "31", "32", "33", "01"], None, horizon=1)
    flags = {item["number"]: item["pulled"] for item in repeat["ticket"]["items"]}
    assert flags["06"] is False
    assert flags["01"] is False
    assert flags["30"] is True
    assert flags["31"] is True
    assert repeat["special_ticket"] == _empty_ticket()


def test_score_digit_positions_do_not_wrap_or_cross(db):
    _draw(db, "fc3d", "2026701", ["0", "5", "9"])
    _draw(db, "fc3d", "2026702", ["1", "5", "8"])
    _draw(db, "fc3d", "2026703", ["1", "6", "9"])
    same = score_neighbor(db, "fc3d", ["1", "5", "8"], horizon=1)
    assert same["mode"] == "digit"
    assert [item["pulled"] for item in same["ticket"]["items"]] == [False, True, True]
    assert same["ticket"]["items"][1] == {
        "index": 1,
        "label": "十",
        "number": "5",
        "pulled": True,
        "sources": ["6"],
        "hits": 1,
        "lift": 0.0,
    }
    assert same["ticket"]["items"][2]["sources"] == ["9"]
    assert same["ticket"]["items"][2]["lift"] == 0.6667
    assert same["ticket"]["pulled"] == [
        {"index": 1, "label": "十", "number": "5"},
        {"index": 2, "label": "个", "number": "8"},
    ]
    assert same["ticket"]["idle"] == [{"index": 0, "label": "百", "number": "1"}]
    assert same["ticket"]["score"] == 2
    assert same["ticket"]["strength"] == 0.6667
    assert same["special_ticket"]["score"] == 0

    clamped = score_neighbor(db, "fc3d", ["0", "4", "0"], horizon=1)
    assert clamped["ticket"]["items"][0]["pulled"] is True
    assert clamped["ticket"]["items"][0]["sources"] == ["1"]
    assert clamped["ticket"]["items"][0]["lift"] == -0.3333
    assert clamped["ticket"]["items"][1]["pulled"] is False
    assert clamped["ticket"]["items"][2]["pulled"] is False
    assert clamped["ticket"]["score"] == 1
    assert clamped["ticket"]["strength"] == -0.3333

    fresh = score_neighbor(db, "pl3", [4, 5, 6])
    assert fresh["lottery_type"] == "pl3"
    assert fresh["sample_size"] == 0
    assert fresh["ticket"]["score"] == 0
    assert fresh["ticket"]["strength"] == 0.0
    assert fresh["ticket"]["idle"] == [
        {"index": 0, "label": "百", "number": "4"},
        {"index": 1, "label": "十", "number": "5"},
        {"index": 2, "label": "个", "number": "6"},
    ]
    assert fresh["ticket"]["pulled"] == []
    assert fresh["positions"][0]["label"] == "百"


def test_neighbor_endpoints_bounds_and_old_contracts(client, db):
    _draw(db, "ssq", "2026001", ["01", "05"], ["16"], draw_date="2026-01-01")
    _draw(db, "ssq", "2026002", ["02", "10"], ["03"], draw_date="2026-01-03")
    _draw(db, "ssq", "2026003", ["03", "06"], ["01"], draw_date="2026-01-05")
    _draw(db, "ssq", "2026004", ["07"], ["02"], source="crawl", draw_date="2026-01-08")

    res = client.get("/api/analysis/ssq/neighbor")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == GET_KEYS
    assert body["sample_size"] == 4
    assert body["horizon"] == 3
    assert body["edge"] == "clamp"
    assert body["disclaimer"] == DISCLAIMER
    assert _by_number(body["numbers"])["01"]["triggers"] == 1
    assert _by_number(body["numbers"])["07"]["triggers"] == 0

    custom = client.get("/api/analysis/ssq/neighbor", params={"limit": 80, "horizon": 2})
    assert custom.status_code == 200
    assert custom.json()["horizon"] == 2
    assert _by_number(custom.json()["numbers"])["01"]["lift"] == 0.25

    assert client.get("/api/analysis/ssq/neighbor", params={"limit": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/neighbor", params={"limit": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/neighbor", params={"horizon": 0}).status_code == 422
    assert client.get("/api/analysis/ssq/neighbor", params={"horizon": 11}).status_code == 422
    assert client.get("/api/analysis/ssq/neighbor", params={"limit": 5, "horizon": 1}).status_code == 200
    assert client.get("/api/analysis/ssq/neighbor", params={"limit": 200, "horizon": 10}).status_code == 200

    unknown = client.get("/api/analysis/nope/neighbor")
    assert unknown.status_code == 400
    assert "未知彩种" in unknown.json()["detail"]

    empty = client.get("/api/analysis/kl8/neighbor")
    assert empty.status_code == 200
    assert empty.json()["sample_size"] == 0
    assert empty.json()["latest_draw"] is None
    assert empty.json()["numbers"] == []

    alias = client.get("/api/analysis/3d/neighbor")
    assert alias.status_code == 200
    assert alias.json()["lottery_type"] == "fc3d"
    assert alias.json()["mode"] == "digit"
    assert [item["label"] for item in alias.json()["positions"]] == ["百", "十", "个"]

    posted = client.post(
        "/api/analysis/ssq/neighbor",
        json={"main": "06 08 01 02 03 04", "special": "01", "limit": 80, "horizon": 1},
    )
    assert posted.status_code == 200, posted.text
    scored = posted.json()
    assert set(scored) == POST_KEYS
    assert scored["ticket"]["pulled"] == ["06", "08"]
    assert scored["ticket"]["score"] == 2
    assert scored["ticket"]["strength"] == 0.0
    assert scored["special_ticket"]["pulled"] == ["01"]
    assert scored["special_ticket"]["score"] == 1
    assert scored["query"]["special"] == ["01"]

    spaced = client.post("/api/analysis/3d/neighbor", json={"main": ["1", "5", "8"], "horizon": 1})
    assert spaced.status_code == 200
    assert spaced.json()["lottery_type"] == "fc3d"
    assert spaced.json()["mode"] == "digit"

    bad = client.post("/api/analysis/ssq/neighbor", json={"main": ["99"], "special": ["01"]})
    assert bad.status_code == 400
    duplicate = client.post(
        "/api/analysis/ssq/neighbor",
        json={"main": ["01", "01", "03", "04", "05", "06"], "special": ["01"]},
    )
    assert duplicate.status_code == 400
    short = client.post("/api/analysis/fc3d/neighbor", json={"main": ["1", "2"]})
    assert short.status_code == 400
    extra = client.post("/api/analysis/kl8/neighbor", json={"main": ["01", "02"], "special": ["03"]})
    assert extra.status_code == 400
    unknown_post = client.post("/api/analysis/nope/neighbor", json={"main": ["01"]})
    assert unknown_post.status_code == 400
    assert client.post("/api/analysis/ssq/neighbor", json={"main": ["01"], "limit": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/neighbor", json={"main": ["01"], "horizon": 0}).status_code == 422
    assert client.post("/api/analysis/ssq/neighbor", json={"main": ["01"], "horizon": 11}).status_code == 422

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
    assert "horizon" not in analysis.json()
    assert "pulled" not in analysis.json()
    shape = client.get("/api/analysis/ssq/shape")
    assert shape.status_code == 200
    assert "odd_even" in shape.json()
    assert "horizon" not in shape.json()
    echo = client.post("/api/analysis/ssq/echo", json={"main": ["01", "02", "03", "04", "05", "06"], "special": ["16"]})
    assert echo.status_code == 200
    assert "echoes" in echo.json()
    assert "ticket" not in echo.json()
    affinity = client.get("/api/analysis/ssq/affinity")
    assert affinity.status_code == 200
    assert "companions" in affinity.json()
    assert "horizon" not in affinity.json()
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
    assert "horizon" not in collision.json()
    repeat = client.get("/api/analysis/ssq/repeat")
    assert repeat.status_code == 200
    assert "recent_pairs" in repeat.json()
    assert "horizon" not in repeat.json()
    momentum = client.get("/api/analysis/ssq/momentum")
    assert momentum.status_code == 200
    assert "rising" in momentum.json()
    assert "horizon" not in momentum.json()
    assert "pulled" not in momentum.json()
