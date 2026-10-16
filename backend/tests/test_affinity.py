"""号码结伴：主号共现。不改冷热 / 形态 / 回声的返回形状。"""
from __future__ import annotations

import json

from app.models import Draw
from app.services.affinity import summarize


def _draw(db, lottery_type, issue, main, special=None):
    row = Draw(
        lottery_type=lottery_type,
        issue=issue,
        numbers=json.dumps({"main": main, "special": special or []}, ensure_ascii=False),
        draw_date="",
        source="seed",
    )
    db.add(row)
    db.commit()
    return row


SET_DRAWS = [
    [1, 2, 3],
    [1, 2, 4],
    [1, 5, 6],
    [7, 8, 9],
]

DIGIT_DRAWS = [
    [1, 2, 3],
    [1, 2, 9],
    [1, 8, 3],
    [4, 5, 6],
]


def test_set_mode_counts_companions_and_pair_rate():
    body = summarize(SET_DRAWS, "ssq")
    assert body["lottery_type"] == "ssq"
    assert body["mode"] == "set"
    assert body["sample_size"] == 4
    assert body["seed"] is None
    assert "娱乐" in body["disclaimer"]

    pairs = {(item["a"], item["b"]): item for item in body["top_pairs"]}
    assert pairs[("01", "02")]["count"] == 2
    assert pairs[("01", "02")]["rate"] == 0.5
    assert body["top_pairs"][0]["a"] == "01"
    assert body["top_pairs"][0]["b"] == "02"

    groups = {item["n"]: item for item in body["companions"]}
    anchor = groups["01"]
    assert anchor["appearances"] == 3
    companions = {item["n"]: item for item in anchor["companions"]}
    assert companions["02"]["count"] == 2
    assert companions["02"]["rate"] == round(2 / 3, 4)
    assert companions["03"]["count"] == 1
    assert companions["03"]["rate"] == round(1 / 3, 4)
    assert [item["n"] for item in anchor["companions"]][0] == "02"
    assert [item["n"] for item in body["companions"]][0] == "01"


def test_set_seed_ranks_one_number_and_keeps_overall_pairs():
    body = summarize(SET_DRAWS, "dlt", seed="1")
    assert body["mode"] == "set"
    assert body["seed"] == "01"
    assert [item["n"] for item in body["companions"]] == ["01"]
    ranked = [item["n"] for item in body["companions"][0]["companions"]]
    assert ranked == ["02", "03", "04", "05", "06"]
    assert body["top_pairs"][0] == {"a": "01", "b": "02", "count": 2, "rate": 0.5}


def test_set_duplicates_do_not_double_count_and_special_stays_separate():
    body = summarize([[1, 1, 2, 3]], "ssq", seed="02", specials=[[16, 16]])
    companions = {item["n"]: item["count"] for item in body["companions"][0]["companions"]}
    assert companions == {"01": 1, "03": 1}
    assert body["special"]["label"] == "蓝球"
    pairs = {(item["main"], item["special"]): item["count"] for item in body["special"]["top_pairs"]}
    assert pairs == {("01", "16"): 1, ("02", "16"): 1, ("03", "16"): 1}


def test_set_missing_seed_and_invalid_input():
    missing = summarize([[1, 2, 3]], "qlc", seed="30")
    assert missing["seed"] == "30"
    assert missing["companions"] == [{"n": "30", "appearances": 0, "companions": []}]
    assert missing["top_pairs"][0]["count"] == 1

    empty = summarize([], "kl8")
    assert empty["mode"] == "set"
    assert empty["sample_size"] == 0
    assert empty["companions"] == []
    assert empty["top_pairs"] == []
    assert empty["special"] is None

    try:
        summarize([[1]], "nope")
    except ValueError as exc:
        assert "未知彩种" in str(exc)
    else:
        raise AssertionError("unknown type should fail")

    try:
        summarize([[1, 2]], "ssq", seed="99")
    except ValueError as exc:
        assert "超出" in str(exc)
    else:
        raise AssertionError("out of range seed should fail")

    try:
        summarize([[1, 2]], "ssq", seed="蓝")
    except ValueError as exc:
        assert "无效" in str(exc)
    else:
        raise AssertionError("non-numeric seed should fail")


def test_digit_mode_counts_cross_position_pairs_only():
    body = summarize(DIGIT_DRAWS, "fc3d")
    assert body["mode"] == "digit"
    assert body["lottery_type"] == "fc3d"
    assert body["sample_size"] == 4
    assert body["special"] is None
    assert all(item["pos_a"] != item["pos_b"] for item in body["top_pairs"])

    pairs = {(item["pos_a"], item["a"], item["pos_b"], item["b"]): item for item in body["top_pairs"]}
    assert pairs[(0, "1", 1, "2")]["count"] == 2
    assert pairs[(0, "1", 1, "2")]["rate"] == 0.5
    assert pairs[(0, "1", 1, "2")]["label_a"] == "百"
    assert pairs[(0, "1", 1, "2")]["label_b"] == "十"
    assert pairs[(0, "1", 2, "3")]["count"] == 2
    assert pairs[(0, "1", 2, "3")]["label_b"] == "个"
    assert (0, "1", 0, "1") not in pairs
    assert body["top_pairs"][0]["pos_b"] == 1
    assert body["top_pairs"][1]["pos_b"] == 2

    assert summarize([[1, 2, 3, 4, 5]], "pl5")["mode"] == "digit"
    assert summarize([[1, 2, 3, 4, 5, 6]], "qxc")["mode"] == "digit"


def test_digit_seed_is_per_position_and_allows_repeated_digits():
    seeded = summarize(DIGIT_DRAWS, "pl3", seed="01")
    assert seeded["seed"] == "1"
    groups = {item["position"]: item for item in seeded["companions"]}
    assert set(groups) == {0}
    anchor = groups[0]
    assert anchor["position_label"] == "百"
    assert anchor["appearances"] == 3
    hot = {(item["position"], item["n"]): item for item in anchor["companions"] if item["count"] == 2}
    assert set(hot) == {(1, "2"), (2, "3")}
    assert hot[(1, "2")]["position_label"] == "十"
    assert hot[(1, "2")]["rate"] == round(2 / 3, 4)

    repeated = summarize([[1, 1, 2]], "fc3d", seed="1")
    by_pos = {item["position"]: item for item in repeated["companions"]}
    left = {(item["position"], item["n"]): item["count"] for item in by_pos[0]["companions"]}
    assert left == {(1, "1"): 1, (2, "2"): 1}
    right = {(item["position"], item["n"]): item["count"] for item in by_pos[1]["companions"]}
    assert right[(0, "1")] == 1

    absent = summarize([[4, 5, 6]], "fc3d", seed="1")
    assert absent["companions"] == [
        {"n": "1", "position": None, "position_label": "", "appearances": 0, "companions": []}
    ]

    try:
        summarize([[1, 2, 3]], "fc3d", seed="10")
    except ValueError as exc:
        assert "0–9" in str(exc) or "0-9" in str(exc)
    else:
        raise AssertionError("digit seed above 9 should fail")


def test_qxc_special_pairs_stay_out_of_main_positions():
    body = summarize([[1, 2, 3, 4, 5, 6]], "qxc", specials=[[7]])
    assert body["mode"] == "digit"
    assert all(item["pos_b"] <= 5 for item in body["top_pairs"])
    assert body["special"]["label"] == "特别号"
    first = body["special"]["top_pairs"][0]
    assert first["n"] == "1"
    assert first["position"] == 0
    assert first["special"] == "7"
    assert first["count"] == 1
    assert len(body["special"]["top_pairs"]) == 6


def test_affinity_endpoint_disclaimer_and_old_contracts(client, db):
    _draw(db, "ssq", "2026001", ["01", "02", "03"], ["16"])
    _draw(db, "ssq", "2026002", ["01", "02", "04"], ["16"])
    _draw(db, "ssq", "2026003", ["01", "05", "06"], ["02"])
    _draw(db, "ssq", "2026004", ["07", "08", "09"], ["09"])
    _draw(db, "fc3d", "2026101", ["1", "2", "3"])
    _draw(db, "fc3d", "2026102", ["1", "2", "9"])
    _draw(db, "fc3d", "2026103", ["1", "8", "3"])
    _draw(db, "fc3d", "2026104", ["4", "5", "6"])

    res = client.get("/api/analysis/ssq/affinity")
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "set"
    assert body["sample_size"] == 4
    assert "娱乐" in body["disclaimer"]
    assert body["top_pairs"][0]["count"] == 2
    assert {item["n"] for item in body["companions"]} >= {"01"}

    seeded = client.get("/api/analysis/ssq/affinity", params={"seed": "7", "limit": 50})
    assert seeded.status_code == 200
    seeded_body = seeded.json()
    assert seeded_body["seed"] == "07"
    assert seeded_body["companions"][0]["appearances"] == 1
    assert seeded_body["special"]["top_pairs"]

    blank = client.get("/api/analysis/ssq/affinity", params={"seed": "  "})
    assert blank.status_code == 200
    assert blank.json()["seed"] is None

    digit = client.get("/api/analysis/fc3d/affinity", params={"seed": "1"})
    assert digit.status_code == 200
    digit_body = digit.json()
    assert digit_body["mode"] == "digit"
    assert digit_body["companions"][0]["position_label"] == "百"
    assert digit_body["companions"][0]["appearances"] == 3

    bad_seed = client.get("/api/analysis/ssq/affinity", params={"seed": "99"})
    assert bad_seed.status_code == 400

    unknown = client.get("/api/analysis/nope/affinity")
    assert unknown.status_code == 400
    assert client.get("/api/analysis/ssq/affinity?limit=1").status_code == 422
    assert client.get("/api/analysis/ssq/affinity?limit=201").status_code == 422

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
    assert "companions" not in shape.json()
    echo = client.post("/api/analysis/ssq/echo", json={"main": ["01", "02", "03", "04", "05", "06"], "special": ["16"]})
    assert echo.status_code == 200
    assert "echoes" in echo.json()
    assert "companions" not in echo.json()
