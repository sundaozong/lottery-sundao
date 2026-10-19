"""遗漏看板：窗口内当前/平均/最大遗漏，不进入脉动综合。

平均遗漏 =（样本期数 − 出现次数）/ 出现次数。
从未出现时，当前、平均、最大遗漏都等于样本期数，比值记 1。
平均为 0（每期都出现）时比值记 0。
偏冷：出现次数为 0，或当前/平均 ≥ 1.5，或当前 ≥ 平均 + 3。
数字彩同一期出现多次只计 1 次。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models import Draw
from app.services.analyze import analyze
from app.services.pulse_ensemble import PULSE_MODULES


def _draw(db, lottery_type, issue, main, special=None):
    row = Draw(
        lottery_type=lottery_type,
        issue=issue,
        numbers=json.dumps({"main": main, "special": special or []}, ensure_ascii=False),
        source="seed",
    )
    db.add(row)
    db.commit()
    return row


def _by_n(rows):
    return {item["n"]: item for item in rows}


def test_module_is_not_a_pulse():
    source = (Path(__file__).resolve().parents[1] / "app" / "services" / "omit_board.py").read_text(encoding="utf-8")
    assert "pulse_ensemble" not in source
    assert "def score_" not in source
    assert all(module.key != "omit" and "omit" not in module.key for module in PULSE_MODULES)


def test_hand_gaps_average_max_and_cold_rules():
    from app.services.omit_board import board_from_history

    # 最旧 → 最新。01 在第 2、5 期开出；02 从未开出；03 每期都在；04 只在最旧两期。
    draws = []
    for index in range(1, 7):
        main = ["03"]
        if index in (2, 5):
            main.append("01")
        if index in (1, 2):
            main.append("04")
        draws.append({"issue": f"202600{index}", "main": main, "special": ["01"] if index == 6 else ["02"]})

    board = board_from_history("ssq", draws, limit=20, sort="n")
    assert board["lottery_type"] == "ssq"
    assert board["sample_size"] == 6
    assert board["limit"] == 20
    assert "仅供娱乐" in board["disclaimer"]
    assert "不构成投注建议" in board["disclaimer"]
    assert "1.5" in board["cold_rule"]
    assert "+ 3" in board["cold_rule"]

    rows = _by_n(board["main"])
    one = rows["01"]
    # 遗漏段：1（开出前）、2（两次之间）、1（最新一期）。最大 2，当前 1，出现 2 次。
    assert one["current"] == 1
    assert one["count"] == 2
    assert one["max"] == 2
    assert one["avg"] == 2
    assert one["rate"] == round(2 / 6, 4)
    assert one["ratio"] == 0.5
    assert one["last_issue"] == "2026005"
    assert one["cold"] is False

    never = rows["02"]
    assert never["current"] == 6
    assert never["avg"] == 6
    assert never["max"] == 6
    assert never["count"] == 0
    assert never["rate"] == 0
    assert never["ratio"] == 1
    assert never["last_issue"] is None
    assert never["cold"] is True

    always = rows["03"]
    assert always["current"] == 0
    assert always["count"] == 6
    assert always["max"] == 0
    assert always["avg"] == 0
    assert always["ratio"] == 0
    assert always["rate"] == 1
    assert always["cold"] is False

    early = rows["04"]
    assert early["current"] == 4
    assert early["count"] == 2
    assert early["max"] == 4
    assert early["avg"] == 2
    assert early["ratio"] == 2
    assert early["last_issue"] == "2026002"
    assert early["cold"] is True

    blue = _by_n(board["special"])
    assert blue["01"]["current"] == 0
    assert blue["01"]["count"] == 1
    assert blue["01"]["max"] == 5
    assert blue["01"]["last_issue"] == "2026006"
    assert blue["02"]["current"] == 1
    assert set(blue) == {f"{i:02d}" for i in range(1, 17)}


def test_ratio_boundary_and_extra_gap_are_cold():
    from app.services.omit_board import board_from_history

    # 10 期、出现 2 次、当前 6：平均 (10-2)/2 = 4，比值正好 1.5。
    exact = []
    for index in range(10):
        main = ["01"] if index in (0, 3) else ["09"]
        exact.append({"issue": f"{index:02d}", "main": main, "special": []})
    exact_rows = _by_n(board_from_history("ssq", exact, limit=20)["main"])
    assert exact_rows["01"]["current"] == 6
    assert exact_rows["01"]["avg"] == 4
    assert exact_rows["01"]["ratio"] == 1.5
    assert exact_rows["01"]["cold"] is True

    # 同样平均 4、当前 5：比值 1.25，也没到平均 + 3。
    below = []
    for index in range(10):
        main = ["01"] if index in (0, 4) else ["09"]
        below.append({"issue": f"{index:02d}", "main": main, "special": []})
    below_rows = _by_n(board_from_history("ssq", below, limit=20)["main"])
    assert below_rows["01"]["current"] == 5
    assert below_rows["01"]["avg"] == 4
    assert below_rows["01"]["ratio"] == 1.25
    assert below_rows["01"]["cold"] is False

    # 22 期、出现 2 次、当前 13：平均 10，比值 1.3，但当前 = 平均 + 3。
    wide = []
    for index in range(22):
        main = ["01"] if index in (0, 8) else ["09"]
        wide.append({"issue": f"{index:02d}", "main": main, "special": []})
    wide_rows = _by_n(board_from_history("ssq", wide, limit=30)["main"])
    hit = wide_rows["01"]
    assert hit["current"] == 13
    assert hit["count"] == 2
    assert hit["max"] == 13
    assert hit["avg"] == 10
    assert hit["ratio"] == 1.3
    assert hit["cold"] is True


def test_interior_gap_sets_max_and_window_drops_older_draws():
    from app.services.omit_board import board_from_history

    draws = []
    for index in range(1, 9):
        main = ["02"]
        if index in (1, 7):
            main.append("01")
        draws.append({"issue": f"202610{index}", "main": main, "special": []})
    rows = _by_n(board_from_history("ssq", draws, limit=20)["main"])
    assert rows["01"]["current"] == 1
    assert rows["01"]["count"] == 2
    assert rows["01"]["max"] == 5
    assert rows["01"]["avg"] == 3
    assert rows["01"]["ratio"] == round(1 / 3, 4)

    longer = [
        {"issue": "2026001", "main": ["01", "02", "03", "04", "05", "06"], "special": ["01"]},
        {"issue": "2026002", "main": ["07", "08", "09", "10", "11", "12"], "special": ["02"]},
        {"issue": "2026003", "main": ["13", "14", "15", "16", "17", "18"], "special": ["03"]},
        {"issue": "2026004", "main": ["19", "20", "21", "22", "23", "24"], "special": ["04"]},
        {"issue": "2026005", "main": ["01", "25", "26", "27", "28", "29"], "special": ["05"]},
    ]
    cut = _by_n(board_from_history("ssq", longer, limit=3)["main"])
    assert cut["01"]["count"] == 1
    assert cut["01"]["current"] == 0
    assert cut["01"]["max"] == 2
    assert cut["01"]["last_issue"] == "2026005"
    assert cut["07"]["count"] == 0
    assert cut["07"]["current"] == 3


def test_digit_hit_counts_once_per_issue_and_sorts():
    from app.services.omit_board import board_from_history

    draws = [
        {"issue": "2026001", "main": ["1", "2", "3"], "special": []},
        {"issue": "2026002", "main": ["7", "7", "1"], "special": []},
        {"issue": "2026003", "main": ["4", "5", "6"], "special": []},
        {"issue": "2026004", "main": ["7", "0", "0"], "special": []},
        {"issue": "2026005", "main": ["8", "8", "8"], "special": []},
        {"issue": "2026006", "main": ["9", "9", "2"], "special": []},
    ]
    board = board_from_history("fc3d", draws, limit=20, sort="current")
    assert board["special"] == []
    rows = _by_n(board["main"])
    assert set(rows) == {str(i) for i in range(10)}
    seven = rows["7"]
    assert seven["count"] == 2
    assert seven["current"] == 2
    assert seven["max"] == 2
    assert seven["avg"] == 2
    assert seven["ratio"] == 1
    assert seven["last_issue"] == "2026004"
    assert seven["cold"] is False
    one = rows["1"]
    assert one["count"] == 2
    assert one["current"] == 4
    assert one["max"] == 4
    assert one["ratio"] == 2
    assert one["cold"] is True

    # 当前遗漏：3 为 5，1 为 4。同值时号码从小到大。
    ordered = [item["n"] for item in board["main"]]
    assert ordered[0] == "3"
    assert ordered[1] == "1"
    assert ordered.index("7") > ordered.index("1")

    by_count = board_from_history("fc3d", draws, limit=20, sort="count")
    assert by_count["main"][0]["n"] == "1"
    assert [item["count"] for item in by_count["main"]] == sorted((item["count"] for item in by_count["main"]), reverse=True)


def test_dlt_zones_and_invalid_sort():
    from app.services.omit_board import board_from_history

    draws = [
        {"issue": "2026001", "main": ["01", "02", "03", "04", "05"], "special": ["01", "02"]},
        {"issue": "2026002", "main": ["06", "07", "08", "09", "10"], "special": ["03", "04"]},
        {"issue": "2026003", "main": ["01", "11", "12", "13", "14"], "special": ["01", "05"]},
    ]
    board = board_from_history("dlt", draws, limit=20, sort="max")
    assert len(board["main"]) == 35
    assert len(board["special"]) == 12
    front = _by_n(board["main"])["01"]
    assert front["count"] == 2
    assert front["current"] == 0
    assert front["max"] == 1
    assert front["last_issue"] == "2026003"
    back = _by_n(board["special"])["01"]
    assert back["count"] == 2
    assert back["current"] == 0
    assert [item["max"] for item in board["main"]] == sorted((item["max"] for item in board["main"]), reverse=True)

    with pytest.raises(ValueError):
        board_from_history("dlt", draws, sort="hot")
    with pytest.raises(ValueError):
        board_from_history("unknown", draws)


def test_api_matches_hand_calc_for_ssq_dlt_and_fc3d(client, db):
    for index in range(1, 21):
        main = ["03", "04", "05", "06", "07", "08"]
        if index in (2, 10, 18):
            main[0] = "01"
        if index <= 2:
            main[1] = "02"
        _draw(db, "ssq", f"2026{index:03d}", main, ["16"] if index == 20 else ["01"])
    for index in range(1, 21):
        _draw(
            db,
            "dlt",
            f"2026{index:03d}",
            ["01", "02", "03", "04", "05"] if index == 20 else ["06", "07", "08", "09", "10"],
            ["01", "02"] if index > 18 else ["03", "04"],
        )
    _draw(db, "fc3d", "2026001", ["1", "2", "3"])
    _draw(db, "fc3d", "2026002", ["7", "7", "1"])
    _draw(db, "fc3d", "2026003", ["4", "5", "6"])
    _draw(db, "fc3d", "2026004", ["7", "0", "0"])
    for index in range(5, 21):
        _draw(db, "fc3d", f"2026{index:03d}", ["8", "8", "8"])

    ssq = client.get("/api/analysis/ssq/omit-board?limit=80")
    assert ssq.status_code == 200, ssq.text
    body = ssq.json()
    assert body["sample_size"] == 20
    assert body["limit"] == 80
    assert len(body["main"]) == 33
    assert len(body["special"]) == 16
    rows = _by_n(body["main"])
    # 20 期里 01 开在第 2、10、18 期：当前 2，出现 3，最大间隔 7，平均 17/3。
    assert rows["01"]["current"] == 2
    assert rows["01"]["count"] == 3
    assert rows["01"]["max"] == 7
    assert rows["01"]["avg"] == round(17 / 3, 4)
    assert rows["01"]["rate"] == 0.15
    assert rows["01"]["ratio"] == round(2 / (17 / 3), 4)
    assert rows["01"]["last_issue"] == "2026018"
    assert rows["01"]["cold"] is False
    assert rows["02"]["current"] == 18
    assert rows["02"]["count"] == 2
    assert rows["02"]["ratio"] == 2
    assert rows["02"]["cold"] is True
    assert rows["33"]["current"] == 20
    assert rows["33"]["count"] == 0
    assert rows["33"]["cold"] is True
    assert _by_n(body["special"])["16"]["current"] == 0
    assert _by_n(body["special"])["16"]["last_issue"] == "2026020"
    assert "仅供娱乐" in body["disclaimer"]
    assert "不构成投注建议" in body["disclaimer"]

    analysis = analyze(db, "ssq", limit=80)
    omit = {item["n"]: item["omit"] for item in analysis["main_omit"]}
    spec = {item["n"]: item["omit"] for item in analysis["special_omit"]}
    for item in body["main"]:
        assert item["current"] == omit[item["n"]]
    for item in body["special"]:
        assert item["current"] == spec[item["n"]]

    ranked = client.get("/api/analysis/ssq/omit-board?limit=20&sort=current")
    assert ranked.status_code == 200
    currents = [item["current"] for item in ranked.json()["main"]]
    assert currents == sorted(currents, reverse=True)

    dlt = client.get("/api/analysis/dlt/omit-board?limit=20&sort=ratio")
    assert dlt.status_code == 200, dlt.text
    dlt_body = dlt.json()
    assert dlt_body["sample_size"] == 20
    assert len(dlt_body["main"]) == 35
    assert len(dlt_body["special"]) == 12
    front = _by_n(dlt_body["main"])["01"]
    assert front["current"] == 0
    assert front["count"] == 1
    assert front["max"] == 19
    assert front["last_issue"] == "2026020"
    ratios = [item["ratio"] for item in dlt_body["main"]]
    assert ratios == sorted(ratios, reverse=True)

    fc3d = client.get("/api/analysis/fc3d/omit-board?limit=20")
    assert fc3d.status_code == 200, fc3d.text
    digit = _by_n(fc3d.json()["main"])
    assert fc3d.json()["special"] == []
    assert digit["7"]["count"] == 2
    assert digit["7"]["current"] == 16
    assert digit["7"]["last_issue"] == "2026004"
    assert digit["1"]["count"] == 2
    assert digit["8"]["count"] == 16

    assert client.get("/api/analysis/ssq/omit-board?limit=19").status_code == 422
    assert client.get("/api/analysis/ssq/omit-board?limit=201").status_code == 422
    bad = client.get("/api/analysis/nope/omit-board?limit=20")
    assert bad.status_code == 400
    unsorted = client.get("/api/analysis/ssq/omit-board?limit=20&sort=pulse")
    assert unsorted.status_code == 400
