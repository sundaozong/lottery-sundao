"""重号脉搏：相邻两期主号重叠。不改冷热 / 形态 / 回声 / 结伴 / 撞车的返回形状。"""
from __future__ import annotations

import json

from app.models import Draw
from app.services.repeat import DISCLAIMER, repeat_pulse, score_repeat

GET_KEYS = {
    "lottery_type",
    "mode",
    "sample_size",
    "pair_count",
    "order",
    "latest_draw",
    "distribution",
    "mean",
    "median",
    "max",
    "recent_pairs",
    "data_status",
    "disclaimer",
}

POST_KEYS = GET_KEYS | {
    "query",
    "overlap",
    "special_overlap",
    "repeat_main",
    "fresh_main",
    "repeat_special",
    "fresh_special",
    "positions",
    "percentile",
    "rank",
    "message",
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


def _seed_ssq(db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["01"], draw_date="2026-01-01")
    _draw(db, "ssq", "2026002", ["01", "02", "03", "07", "08", "09"], ["16"], draw_date="2026-01-03")
    _draw(db, "ssq", "2026003", ["11", "12", "13", "14", "15", "16"], ["16"], draw_date="2026-01-05")
    _draw(db, "ssq", "2026004", ["11", "12", "13", "14", "15", "16"], ["09"], draw_date="2026-01-08")


def test_set_pairs_keep_specials_out_of_main_score(db):
    _seed_ssq(db)
    body = repeat_pulse(db, "ssq", limit=80)
    assert set(body) == GET_KEYS
    assert body["lottery_type"] == "ssq"
    assert body["mode"] == "set"
    assert body["order"] == "older_to_newer"
    assert body["sample_size"] == 4
    assert body["pair_count"] == 3
    assert body["data_status"] == "seed"
    assert body["disclaimer"] == DISCLAIMER
    assert "仅供娱乐" in body["disclaimer"]
    assert "不构成投注建议" in body["disclaimer"]
    assert body["latest_draw"] == {
        "issue": "2026004",
        "draw_date": "2026-01-08",
        "main": ["11", "12", "13", "14", "15", "16"],
        "special": ["09"],
    }

    pairs = body["recent_pairs"]
    assert [item["issue_to"] for item in pairs] == ["2026004", "2026003", "2026002"]
    assert [(item["issue_from"], item["issue_to"]) for item in pairs] == [
        ("2026003", "2026004"),
        ("2026002", "2026003"),
        ("2026001", "2026002"),
    ]
    full = pairs[0]
    assert full["overlap"] == 6
    assert full["special_overlap"] == 0
    assert full["shared_main"] == ["11", "12", "13", "14", "15", "16"]
    assert full["shared_special"] == []
    assert full["positions"] == []
    assert full["main"] == full["shared_main"]
    none = pairs[1]
    assert none["overlap"] == 0
    assert none["special_overlap"] == 1
    assert none["shared_main"] == []
    assert none["shared_special"] == ["16"]
    partial = pairs[2]
    assert partial["overlap"] == 3
    assert partial["special_overlap"] == 0
    assert partial["shared_main"] == ["01", "02", "03"]

    buckets = {item["overlap"]: item for item in body["distribution"]}
    assert list(buckets) == [0, 1, 2, 3, 4, 5, 6]
    assert buckets[0]["count"] == 1
    assert buckets[3]["count"] == 1
    assert buckets[6]["count"] == 1
    assert buckets[1]["count"] == 0
    assert buckets[0]["rate"] == round(1 / 3, 4)
    assert buckets[1]["rate"] == 0
    assert body["mean"] == round(9 / 3, 4)
    assert body["median"] == 3
    assert body["max"] == 6


def test_set_duplicates_count_once_and_dlt_specials_stay_separate(db):
    _draw(db, "dlt", "2026101", [1, 1, 2, 3, 4], [2, 10])
    _draw(db, "dlt", "2026102", ["02", "03", "05", "06", "07"], ["02", "11"])
    body = repeat_pulse(db, "dlt")
    assert body["mode"] == "set"
    pair = body["recent_pairs"][0]
    assert pair["overlap"] == 2
    assert pair["shared_main"] == ["02", "03"]
    assert pair["special_overlap"] == 1
    assert pair["shared_special"] == ["02"]
    assert body["max"] == 2
    assert body["mean"] == 2

    qlc = repeat_pulse(db, "qlc")
    assert qlc["mode"] == "set"
    assert qlc["sample_size"] == 0
    assert qlc["latest_draw"] is None


def test_digit_overlap_is_positional_and_qxc_special_is_separate(db):
    _draw(db, "fc3d", "2026201", ["1", "8", "3"])
    _draw(db, "fc3d", "2026202", ["1", "2", "3"])
    _draw(db, "fc3d", "2026203", ["9", "2", "8"])
    _draw(db, "fc3d", "2026204", ["4", "8", "6"])
    body = repeat_pulse(db, "fc3d")
    assert body["mode"] == "digit"
    assert body["pair_count"] == 3
    pairs = body["recent_pairs"]
    assert pairs[0]["overlap"] == 0
    assert pairs[0]["shared_main"] == []
    assert [item["repeat"] for item in pairs[0]["positions"]] == [False, False, False]
    assert pairs[0]["positions"][0]["label"] == "百"
    assert pairs[0]["positions"][1] == {"index": 1, "label": "十", "repeat": False, "from": "2", "to": "8"}
    swapped = pairs[1]
    assert swapped["overlap"] == 1
    assert swapped["shared_main"] == ["2"]
    assert [item["repeat"] for item in swapped["positions"]] == [False, True, False]
    assert swapped["positions"][1]["from"] == "2"
    assert swapped["positions"][1]["to"] == "2"
    kept = pairs[2]
    assert kept["overlap"] == 2
    assert kept["shared_main"] == ["1", "3"]
    assert kept["positions"][0]["repeat"] is True
    assert kept["positions"][2]["label"] == "个"
    assert body["distribution"][-1]["overlap"] == 2
    assert body["max"] == 2
    assert body["mean"] == 1
    assert body["median"] == 1

    _draw(db, "pl5", "2026301", ["1", "2", "3", "4", "5"])
    _draw(db, "pl5", "2026302", ["1", "0", "3", "0", "5"])
    pl5 = repeat_pulse(db, "pl5")
    assert pl5["mode"] == "digit"
    assert pl5["recent_pairs"][0]["overlap"] == 3
    assert [item["label"] for item in pl5["recent_pairs"][0]["positions"]] == ["万", "千", "百", "十", "个"]

    _draw(db, "qxc", "2026401", ["1", "2", "3", "4", "5", "6"], ["7"])
    _draw(db, "qxc", "2026402", ["1", "9", "3", "4", "5", "0"], ["7"])
    qxc = repeat_pulse(db, "qxc")
    pair = qxc["recent_pairs"][0]
    assert qxc["mode"] == "digit"
    assert pair["overlap"] == 4
    assert pair["special_overlap"] == 1
    assert pair["shared_special"] == ["7"]
    assert pair["shared_main"] == ["1", "3", "4", "5"]
    assert len(pair["positions"]) == 6
    assert pair["positions"][1]["repeat"] is False
    assert qxc["max"] == 4


def test_empty_single_and_blank_rows(db):
    empty = repeat_pulse(db, "kl8")
    assert empty["sample_size"] == 0
    assert empty["pair_count"] == 0
    assert empty["latest_draw"] is None
    assert empty["distribution"] == []
    assert empty["recent_pairs"] == []
    assert empty["mean"] is None
    assert empty["median"] is None
    assert empty["max"] is None
    assert empty["mode"] == "set"
    assert empty["data_status"] == "seed"

    _draw(db, "kl8", "2026501", ["01", "02"])
    single = repeat_pulse(db, "kl8")
    assert single["sample_size"] == 1
    assert single["pair_count"] == 0
    assert single["latest_draw"]["issue"] == "2026501"
    assert single["mean"] is None
    assert single["recent_pairs"] == []

    _draw(db, "ssq", "2026601", ["01", "02", "03"], ["04"])
    _draw(db, "ssq", "2026602", [], ["04"])
    _draw(db, "ssq", "2026603", ["01", "05", "06"], ["04"], source="crawl")
    skipped = repeat_pulse(db, "ssq")
    assert skipped["sample_size"] == 2
    assert skipped["pair_count"] == 1
    assert skipped["data_status"] == "mixed"
    pair = skipped["recent_pairs"][0]
    assert pair["issue_from"] == "2026601"
    assert pair["issue_to"] == "2026603"
    assert pair["overlap"] == 1
    assert pair["shared_main"] == ["01"]
    assert pair["special_overlap"] == 1

    try:
        repeat_pulse(db, "nope")
    except ValueError as exc:
        assert "未知彩种" in str(exc)
    else:
        raise AssertionError("unknown type should fail")


def test_even_median_and_limit_window(db):
    overlaps_issues = [
        ("2026701", ["01"]),
        ("2026702", ["02"]),
        ("2026703", ["02", "03"]),
        ("2026704", ["02", "03", "04"]),
        ("2026705", ["09", "10", "11", "12"]),
        ("2026706", ["09", "10", "11", "12"]),
    ]
    for issue, main in overlaps_issues:
        _draw(db, "qlc", issue, main)
    body = repeat_pulse(db, "qlc", limit=5)
    assert body["sample_size"] == 5
    assert body["pair_count"] == 4
    assert body["latest_draw"]["issue"] == "2026706"
    assert [item["overlap"] for item in body["recent_pairs"]] == [4, 0, 2, 1]
    assert body["recent_pairs"][-1]["issue_from"] == "2026702"
    assert all(item["issue_from"] != "2026701" and item["issue_to"] != "2026701" for item in body["recent_pairs"])
    assert body["mean"] == round((4 + 0 + 2 + 1) / 4, 4)
    assert body["median"] == 1.5
    assert body["max"] == 4
    assert body["distribution"][0]["count"] == 1
    assert body["distribution"][3]["count"] == 0


def test_score_ranks_against_history_without_mixing_specials(db):
    _seed_ssq(db)
    zero = score_repeat(db, "ssq", ["21", "22", "23", "24", "25", "26"], ["16"])
    assert set(zero) == POST_KEYS
    assert zero["query"] == {"main": ["21", "22", "23", "24", "25", "26"], "special": ["16"]}
    assert zero["overlap"] == 0
    assert zero["special_overlap"] == 0
    assert zero["repeat_main"] == []
    assert zero["fresh_main"] == ["21", "22", "23", "24", "25", "26"]
    assert zero["repeat_special"] == []
    assert zero["fresh_special"] == ["16"]
    assert zero["positions"] == []
    assert zero["percentile"] == round(1 / 3, 4)
    assert zero["rank"] == 3
    assert zero["max"] == 6
    assert zero["message"] == ""
    assert zero["distribution"] == repeat_pulse(db, "ssq")["distribution"]
    assert "仅供娱乐" in zero["disclaimer"] and "不构成投注建议" in zero["disclaimer"]

    full = score_repeat(db, "ssq", "16 15 14 13 12 11", "09")
    assert full["overlap"] == 6
    assert full["repeat_main"] == ["11", "12", "13", "14", "15", "16"]
    assert full["fresh_main"] == []
    assert full["special_overlap"] == 1
    assert full["repeat_special"] == ["09"]
    assert full["percentile"] == 1
    assert full["rank"] == 1

    mid = score_repeat(db, "ssq", ["11", "12", "13", "20", "21", "22"], [])
    assert mid["overlap"] == 3
    assert mid["repeat_main"] == ["11", "12", "13"]
    assert mid["fresh_main"] == ["20", "21", "22"]
    assert mid["percentile"] == round(2 / 3, 4)
    assert mid["rank"] == 2

    special_only = score_repeat(db, "ssq", ["21", "22", "23", "24", "25", "26"], ["09"])
    assert special_only["overlap"] == 0
    assert special_only["special_overlap"] == 1
    assert special_only["percentile"] == zero["percentile"]
    assert special_only["rank"] == zero["rank"]


def test_score_digit_extremes_and_short_history(db):
    _draw(db, "fc3d", "2026801", ["1", "2", "3"])
    alone = score_repeat(db, "fc3d", ["1", "9", "3"], None)
    assert alone["mode"] == "digit"
    assert alone["overlap"] == 2
    assert alone["repeat_main"] == ["1", "3"]
    assert alone["fresh_main"] == ["9"]
    assert alone["percentile"] is None
    assert alone["rank"] is None
    assert alone["pair_count"] == 0
    assert alone["message"] == ""
    assert [item["repeat"] for item in alone["positions"]] == [True, False, True]
    assert alone["positions"][0]["label"] == "百"
    assert alone["positions"][1] == {"index": 1, "label": "十", "ticket": "9", "latest": "2", "repeat": False}

    _draw(db, "fc3d", "2026802", ["1", "2", "3"])
    _draw(db, "fc3d", "2026803", ["1", "2", "3"])
    same = score_repeat(db, "fc3d", ["1", "2", "3"])
    assert same["overlap"] == 3
    assert same["fresh_main"] == []
    assert same["percentile"] == 1
    assert same["rank"] == 1
    assert same["max"] == 3
    fresh = score_repeat(db, "pl3", [4, 5, 6])
    assert fresh["lottery_type"] == "pl3"
    assert fresh["overlap"] is None
    assert fresh["message"] == "暂无开奖可对照"
    assert fresh["repeat_main"] == []
    assert fresh["fresh_main"] == []
    assert fresh["percentile"] is None
    assert fresh["rank"] is None

    _draw(db, "pl3", "2026901", ["1", "2", "3"])
    _draw(db, "pl3", "2026902", ["1", "2", "3"])
    low = score_repeat(db, "pl3", ["4", "5", "6"])
    assert low["overlap"] == 0
    assert low["fresh_main"] == ["4", "5", "6"]
    assert low["percentile"] == 0
    assert low["rank"] == 2
    assert low["max"] == 3
    tied = score_repeat(db, "pl3", ["1", "2", "3"])
    assert tied["overlap"] == 3
    assert tied["percentile"] == 1
    assert tied["rank"] == 1


def test_repeat_endpoints_bounds_and_old_contracts(client, db):
    _seed_ssq(db)
    for index in range(90):
        _draw(db, "pl3", f"{index:04d}", [index % 10, (index + 1) % 10, (index + 2) % 10])

    res = client.get("/api/analysis/ssq/repeat")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == GET_KEYS
    assert body["sample_size"] == 4
    assert body["disclaimer"] == DISCLAIMER

    window = client.get("/api/analysis/pl3/repeat")
    assert window.status_code == 200
    assert window.json()["sample_size"] == 80
    assert window.json()["pair_count"] == 79
    assert window.json()["latest_draw"]["issue"] == "0089"
    assert window.json()["recent_pairs"][-1]["issue_from"] == "0010"

    tight = client.get("/api/analysis/pl3/repeat", params={"limit": 5})
    assert tight.status_code == 200
    assert tight.json()["sample_size"] == 5
    assert tight.json()["recent_pairs"][0]["issue_to"] == "0089"
    assert tight.json()["recent_pairs"][-1]["issue_from"] == "0085"

    assert client.get("/api/analysis/ssq/repeat", params={"limit": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/repeat", params={"limit": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/repeat", params={"limit": 200}).status_code == 200

    unknown = client.get("/api/analysis/nope/repeat")
    assert unknown.status_code == 400
    assert "未知彩种" in unknown.json()["detail"]

    empty = client.get("/api/analysis/kl8/repeat")
    assert empty.status_code == 200
    assert empty.json()["sample_size"] == 0
    assert empty.json()["latest_draw"] is None
    assert "仅供娱乐" in empty.json()["disclaimer"]

    posted = client.post(
        "/api/analysis/ssq/repeat",
        json={"main": "11 12 13 14 15 16", "special": "09", "limit": 80},
    )
    assert posted.status_code == 200, posted.text
    scored = posted.json()
    assert set(scored) == POST_KEYS
    assert scored["overlap"] == 6
    assert scored["percentile"] == 1
    assert scored["rank"] == 1
    assert scored["query"]["special"] == ["09"]

    spaced = client.post("/api/analysis/3d/repeat", json={"main": ["0", "0", "1"], "limit": 5})
    assert spaced.status_code == 200
    assert spaced.json()["lottery_type"] == "fc3d"
    assert spaced.json()["mode"] == "digit"

    bad = client.post("/api/analysis/ssq/repeat", json={"main": ["99"], "special": ["01"]})
    assert bad.status_code == 400
    duplicate = client.post(
        "/api/analysis/ssq/repeat",
        json={"main": ["01", "01", "03", "04", "05", "06"], "special": ["01"]},
    )
    assert duplicate.status_code == 400
    short = client.post("/api/analysis/fc3d/repeat", json={"main": ["1", "2"]})
    assert short.status_code == 400
    extra = client.post("/api/analysis/kl8/repeat", json={"main": ["01", "02"], "special": ["03"]})
    assert extra.status_code == 400
    unknown_post = client.post("/api/analysis/nope/repeat", json={"main": ["01"]})
    assert unknown_post.status_code == 400
    assert client.post("/api/analysis/ssq/repeat", json={"main": ["01"], "limit": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/repeat", json={"main": ["01"], "limit": 201}).status_code == 422

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
    shape = client.get("/api/analysis/ssq/shape")
    assert shape.status_code == 200
    assert "odd_even" in shape.json()
    assert "recent_pairs" not in shape.json()
    echo = client.post("/api/analysis/ssq/echo", json={"main": ["01", "02", "03", "04", "05", "06"], "special": ["16"]})
    assert echo.status_code == 200
    assert "echoes" in echo.json()
    assert "recent_pairs" not in echo.json()
    affinity = client.get("/api/analysis/ssq/affinity")
    assert affinity.status_code == 200
    assert "companions" in affinity.json()
    assert "percentile" not in affinity.json()
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
    assert "percentile" not in collision.json()
