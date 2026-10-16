"""号码撞车：多注重叠与覆盖空洞。不改冷热 / 形态 / 结伴 / 回声的返回形状。"""
from __future__ import annotations

import json

from app.models import Draw, PurchaseRecord
from app.services.collision import collide, collide_records

DISCLAIMER = "预测/分析仅供娱乐，不构成投注建议。"


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


def _record(db, lottery_type, main, special=None, issue="", prize=0.0, positions=None):
    payload = {"main": main, "special": special or []}
    if positions is not None:
        payload["positions"] = positions
    row = PurchaseRecord(
        lottery_type=lottery_type,
        issue=issue,
        numbers=json.dumps(payload, ensure_ascii=False),
        cost=2.0,
        prize=prize,
        note="",
        purchased_at="2026-10-01",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _ssq(main, special):
    return {"main": main, "special": special}


def test_set_overlap_coverage_holes_and_separate_specials():
    body = collide(
        "ssq",
        [
            _ssq(["6", "5", "4", "03", "02", 1], ["16"]),
            _ssq(["01", "02", "03", "07", "08", "09"], ["16"]),
            _ssq(["01", "10", "11", "12", "13", "14"], ["01"]),
        ],
    )
    assert body["lottery_type"] == "ssq"
    assert body["mode"] == "set"
    assert body["source"] == "tickets"
    assert body["record_scope"] == ""
    assert body["ticket_count"] == 3
    assert body["message"] == ""
    assert body["disclaimer"] == DISCLAIMER
    assert body["tickets"][0]["main"] == ["06", "05", "04", "03", "02", "01"]
    assert body["tickets"][0]["special"] == ["16"]
    assert body["tickets"][0]["index"] == 1
    assert body["tickets"][0]["record_id"] is None

    pairs = {(item["left"], item["right"]): item for item in body["pairs"]}
    assert set(pairs) == {(1, 2), (1, 3), (2, 3)}
    heavy = pairs[(1, 2)]
    assert heavy["overlap_count"] == 3
    assert heavy["special_overlap_count"] == 1
    assert heavy["unordered_overlap_count"] == 3
    assert heavy["overlapping"] == {
        "main": ["01", "02", "03"],
        "special": ["16"],
        "positions": [],
    }
    assert heavy["waste_hint"] == "浪费偏多：主号撞了 3 个，蓝球撞了 1 个"
    assert pairs[(1, 3)]["overlap_count"] == 1
    assert pairs[(1, 3)]["special_overlap_count"] == 0
    assert pairs[(1, 3)]["overlapping"]["main"] == ["01"]
    assert pairs[(1, 3)]["waste_hint"] == "主号撞了 1 个"
    assert pairs[(2, 3)]["waste_hint"] == "主号撞了 1 个"

    hits = {(item["kind"], item["n"], item["position"]): item for item in body["number_hits"]}
    assert hits[("main", "01", None)]["count"] == 3
    assert hits[("main", "01", None)]["collision"] is True
    assert hits[("main", "02", None)]["count"] == 2
    assert hits[("main", "14", None)]["collision"] is False
    assert hits[("special", "16", None)]["count"] == 2
    assert hits[("special", "16", None)]["collision"] is True
    assert hits[("special", "01", None)]["count"] == 1
    assert hits[("special", "01", None)]["kind"] == "special"
    assert body["number_hits"][0]["n"] == "01"
    assert body["number_hits"][0]["kind"] == "main"

    assert body["unique_coverage"] == {"covered": 14, "pool": 33, "ratio": round(14 / 33, 4)}
    assert body["holes"] == [f"{n:02d}" for n in range(15, 34)]
    assert len(body["holes"]) <= 24
    assert body["summary"] == "共 3 注，3 个号码被重复选中，另有 1 个特别号被重复选中"


def test_set_no_overlap_and_dlt_specials_stay_out_of_mains():
    none = collide(
        "qlc",
        [
            {"main": ["01", "02", "03", "04", "05", "06", "07"], "special": ["08"]},
            {"main": ["09", "10", "11", "12", "13", "14", "15"], "special": ["16"]},
        ],
    )
    assert none["pairs"][0]["overlap_count"] == 0
    assert none["pairs"][0]["special_overlap_count"] == 0
    assert none["pairs"][0]["waste_hint"] == "没有撞号，覆盖是拉开的"
    assert none["summary"] == "共 2 注，0 个号码被重复选中"
    assert none["holes"][:2] == ["08", "16"]
    assert len(none["holes"]) == 16

    dlt = collide(
        "dlt",
        [
            {"main": ["01", "02", "03", "04", "05"], "special": ["01", "02"]},
            {"main": ["01", "02", "03", "06", "07"], "special": ["01", "03"]},
        ],
    )
    pair = dlt["pairs"][0]
    assert pair["overlap_count"] == 3
    assert pair["special_overlap_count"] == 1
    assert pair["overlapping"]["main"] == ["01", "02", "03"]
    assert pair["overlapping"]["special"] == ["01"]
    assert pair["waste_hint"] == "浪费偏多：主号撞了 3 个，后区撞了 1 个"
    hits = {(item["kind"], item["n"]): item["count"] for item in dlt["number_hits"]}
    assert hits[("main", "01")] == 2
    assert hits[("special", "01")] == 2
    assert dlt["unique_coverage"]["pool"] == 35


def test_kl8_holes_are_capped_and_pool_is_eighty():
    body = collide("kl8", [{"main": ["1"]}, {"main": ["2"]}])
    assert body["mode"] == "set"
    assert body["unique_coverage"] == {"covered": 2, "pool": 80, "ratio": 0.025}
    assert body["holes"][0] == "03"
    assert len(body["holes"]) == 24
    assert "01" not in body["holes"]
    assert "02" not in body["holes"]
    assert body["pairs"][0]["waste_hint"] == "没有撞号，覆盖是拉开的"


def test_digit_position_overlap_and_unordered_multiset():
    body = collide(
        "fc3d",
        [
            {"main": ["01", "02", "03"]},
            {"main": ["1", "2", "9"]},
            {"main": ["3", "2", "1"]},
        ],
    )
    assert body["mode"] == "digit"
    assert body["tickets"][0]["main"] == ["1", "2", "3"]
    pairs = {(item["left"], item["right"]): item for item in body["pairs"]}
    assert pairs[(1, 2)]["overlap_count"] == 2
    assert pairs[(1, 2)]["unordered_overlap_count"] == 2
    assert pairs[(1, 2)]["overlapping"] == {"main": ["1", "2"], "special": [], "positions": [0, 1]}
    assert pairs[(1, 2)]["waste_hint"] == "浪费偏多：同位撞了 2 个"
    swapped = pairs[(1, 3)]
    assert swapped["overlap_count"] == 1
    assert swapped["unordered_overlap_count"] == 3
    assert swapped["overlapping"]["main"] == ["2"]
    assert swapped["overlapping"]["positions"] == [1]
    assert swapped["waste_hint"] == "同位撞了 1 个，不计位置还有 2 个数字重复"
    assert pairs[(2, 3)]["waste_hint"] == "同位撞了 1 个，不计位置还有 1 个数字重复"

    hits = {(item["position"], item["n"]): item for item in body["number_hits"]}
    assert hits[(1, "2")]["count"] == 3
    assert hits[(1, "2")]["collision"] is True
    assert hits[(1, "2")]["position_label"] == "十"
    assert hits[(0, "1")]["count"] == 2
    assert hits[(0, "1")]["position_label"] == "百"
    assert hits[(2, "3")]["collision"] is False
    assert body["unique_coverage"] == {"covered": 6, "pool": 30, "ratio": 0.2}
    assert body["holes"] == []
    assert body["summary"] == "共 3 注，2 个号码被重复选中"


def test_qxc_special_is_scored_apart_from_positions():
    body = collide(
        "qxc",
        [
            {"main": ["1", "2", "3", "4", "5", "6"], "special": ["7"]},
            {"main": ["1", "2", "3", "4", "5", "9"], "special": ["7"]},
        ],
    )
    pair = body["pairs"][0]
    assert pair["overlap_count"] == 5
    assert pair["special_overlap_count"] == 1
    assert pair["unordered_overlap_count"] == 5
    assert pair["overlapping"]["positions"] == [0, 1, 2, 3, 4]
    assert pair["overlapping"]["special"] == ["7"]
    assert pair["waste_hint"] == "浪费偏多：同位撞了 5 个，特别号撞了 1 个"
    assert body["unique_coverage"]["pool"] == 60
    assert body["unique_coverage"]["covered"] == 7
    specials = [item for item in body["number_hits"] if item["kind"] == "special"]
    assert specials == [
        {"n": "7", "count": 2, "collision": True, "kind": "special", "position": None, "position_label": "特别号"}
    ]
    assert body["summary"] == "共 2 注，5 个号码被重复选中，另有 1 个特别号被重复选中"


def test_repeated_digits_count_once_per_position():
    body = collide("pl3", [{"main": ["1", "1", "2"]}, {"main": ["1", "1", "3"]}])
    pair = body["pairs"][0]
    assert pair["overlap_count"] == 2
    assert pair["unordered_overlap_count"] == 2
    assert pair["overlapping"]["positions"] == [0, 1]
    hits = {(item["position"], item["n"]): item["count"] for item in body["number_hits"]}
    assert hits[(0, "1")] == 2
    assert hits[(1, "1")] == 2
    assert hits[(2, "2")] == 1
    assert body["summary"] == "共 2 注，2 个号码被重复选中"


def test_validation_errors_name_the_ticket():
    try:
        collide("ssq", [_ssq(["01", "02", "03", "04", "05", "06"], ["01"])])
    except ValueError as exc:
        assert "至少" in str(exc)
    else:
        raise AssertionError("one ticket should fail")

    try:
        collide("ssq", [_ssq(["01"], ["01"]) for _ in range(21)])
    except ValueError as exc:
        assert "20" in str(exc)
    else:
        raise AssertionError("21 tickets should fail")

    try:
        collide(
            "ssq",
            [
                _ssq(["01", "02", "03", "04", "05", "06"], ["01"]),
                _ssq(["99", "02", "03", "04", "05", "06"], ["01"]),
            ],
        )
    except ValueError as exc:
        assert str(exc).startswith("第 2 注")
        assert "超出" in str(exc)
    else:
        raise AssertionError("out of range should fail")

    try:
        collide(
            "dlt",
            [
                {"main": ["01", "01", "03", "04", "05"], "special": ["01", "02"]},
                {"main": ["06", "07", "08", "09", "10"], "special": ["03", "04"]},
            ],
        )
    except ValueError as exc:
        assert "第 1 注" in str(exc)
        assert "重复" in str(exc)
    else:
        raise AssertionError("duplicate mains should fail")

    try:
        collide("fc3d", [{"main": ["1", "2"]}, {"main": ["1", "2", "3"]}])
    except ValueError as exc:
        assert "第 1 注" in str(exc)
    else:
        raise AssertionError("short digit ticket should fail")

    try:
        collide("pl5", [{"main": ["1", "2", "3"], "special": ["4"]}, {"main": ["1", "2", "3", "4", "5"]}])
    except ValueError as exc:
        assert "特别号" in str(exc)
    else:
        raise AssertionError("unexpected special should fail")

    try:
        collide("nope", [{"main": ["01"]}, {"main": ["02"]}])
    except ValueError as exc:
        assert "未知彩种" in str(exc)
    else:
        raise AssertionError("unknown type should fail")


def test_from_records_prefers_open_then_falls_back(db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["07"])
    settled_paid = _record(
        db,
        "ssq",
        ["11", "12", "13", "14", "15", "16"],
        ["01"],
        issue="2026001",
        prize=10,
    )
    settled_drawn = _record(
        db,
        "ssq",
        ["21", "22", "23", "24", "25", "26"],
        ["02"],
        issue="2026001",
        prize=0,
    )
    open_a = _record(db, "ssq", ["01", "02", "03", "04", "05", "06"], ["09"], issue="")
    open_b = _record(db, "ssq", ["01", "02", "03", "07", "08", "09"], ["09"], issue="2026999")
    _record(db, "dlt", ["01", "02", "03", "04", "05"], ["01", "02"])

    body = collide_records(db, "ssq")
    assert body["source"] == "records"
    assert body["record_scope"] == "open"
    assert body["ticket_count"] == 2
    assert [item["record_id"] for item in body["tickets"]] == [open_a.id, open_b.id]
    assert settled_paid.id not in [item["record_id"] for item in body["tickets"]]
    assert settled_drawn.id not in [item["record_id"] for item in body["tickets"]]
    assert body["pairs"][0]["overlap_count"] == 3
    assert body["pairs"][0]["overlapping"]["special"] == ["09"]
    assert body["tickets"][0]["issue"] == ""
    assert body["tickets"][1]["issue"] == "2026999"

    only_open = collide_records(db, "dlt")
    assert only_open["ticket_count"] == 0
    assert only_open["pairs"] == []
    assert only_open["message"] == "购彩记录不足 2 注，先记下至少两注再看撞号。"
    assert only_open["summary"] == only_open["message"]
    assert only_open["disclaimer"] == DISCLAIMER
    assert "娱乐" in only_open["disclaimer"]


def test_from_records_uses_latest_when_open_is_scarce_and_skips_bad_rows(db):
    _draw(db, "fc3d", "2026101", ["1", "2", "3"])
    first = _record(db, "fc3d", ["4", "5", "6"], issue="2026101", prize=0)
    second = _record(db, "fc3d", [], positions=[["1"], ["2"], ["3"]], issue="2026101", prize=0)
    _record(db, "fc3d", ["9"], issue="", prize=0)
    third = _record(db, "fc3d", ["1", "9", "3"], issue="", prize=0)

    body = collide_records(db, "fc3d")
    assert body["record_scope"] == "latest"
    assert [item["record_id"] for item in body["tickets"]] == [first.id, second.id, third.id]
    assert body["tickets"][1]["main"] == ["1", "2", "3"]
    assert body["mode"] == "digit"
    pairs = {(item["left"], item["right"]): item["overlap_count"] for item in body["pairs"]}
    assert pairs[(2, 3)] == 2

    for index in range(22):
        _record(db, "pl5", [str(index % 10), "1", "2", "3", "4"])
    capped = collide_records(db, "pl5")
    assert capped["ticket_count"] == 20
    assert capped["tickets"][0]["record_id"] == capped["tickets"][-1]["record_id"] - 19


def test_collision_endpoint_and_existing_contracts(client, db):
    res = client.post(
        "/api/analysis/ssq/collision",
        json={
            "tickets": [
                {"main": [1, 2, 3, 4, 5, 6], "special": [9]},
                {"main": "01 02 03 10 11 12", "special": "09"},
            ],
            "from_records": False,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == {
        "lottery_type",
        "mode",
        "source",
        "record_scope",
        "ticket_count",
        "tickets",
        "pairs",
        "number_hits",
        "unique_coverage",
        "holes",
        "summary",
        "message",
        "disclaimer",
    }
    assert body["source"] == "tickets"
    assert body["pairs"][0]["overlap_count"] == 3
    assert body["pairs"][0]["overlapping"]["special"] == ["09"]
    assert body["disclaimer"] == DISCLAIMER

    _record(db, "ssq", ["21", "22", "23", "24", "25", "26"], ["08"])
    _record(db, "ssq", ["21", "22", "23", "27", "28", "29"], ["08"])
    from_rows = client.post(
        "/api/analysis/ssq/collision",
        json={"tickets": [{"main": ["99"]}], "from_records": True},
    )
    assert from_rows.status_code == 200, from_rows.text
    recorded = from_rows.json()
    assert recorded["source"] == "records"
    assert recorded["ticket_count"] == 2
    assert recorded["pairs"][0]["overlap_count"] == 3
    assert recorded["tickets"][0]["main"][0] == "21"

    short = client.post("/api/analysis/ssq/collision", json={"tickets": [{"main": ["01", "02", "03", "04", "05", "06"], "special": ["01"]}]})
    assert short.status_code == 400
    assert "至少" in short.json()["detail"]
    bad = client.post(
        "/api/analysis/fc3d/collision",
        json={"tickets": [{"main": ["1", "2", "3"]}, {"main": ["1", "2"]}]},
    )
    assert bad.status_code == 400
    assert "第 2 注" in bad.json()["detail"]
    unknown = client.post("/api/analysis/nope/collision", json={"tickets": [{"main": ["1"]}, {"main": ["2"]}]})
    assert unknown.status_code == 400

    lonely = client.post("/api/analysis/pl3/collision", json={"from_records": True})
    assert lonely.status_code == 200
    assert "不足 2" in lonely.json()["message"]
    assert lonely.json()["pairs"] == []

    analysis = client.get("/api/analysis/ssq")
    assert analysis.status_code == 200
    assert "main_freq" in analysis.json()
    assert "pairs" not in analysis.json()
    echo = client.post(
        "/api/analysis/ssq/echo",
        json={"main": ["01", "02", "03", "04", "05", "06"], "special": ["09"]},
    )
    assert echo.status_code == 200
    assert "echoes" in echo.json()
    assert "pairs" not in echo.json()
    affinity = client.get("/api/analysis/ssq/affinity")
    assert affinity.status_code == 200
    assert "companions" in affinity.json()
    assert "pairs" not in affinity.json()
