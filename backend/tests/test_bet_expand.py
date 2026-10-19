"""复式 / 胆拖展开：按彩种规则计数、分页、常见带过滤。

不改奖金估算，也不进入脉动综合。注数用组合数，金额按 2 元/注。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models import Draw
from app.services.pulse_ensemble import PULSE_MODULES


def expand(**kwargs):
    from app.services.bet_expand import expand_bets

    return expand_bets(**kwargs)


def _nums(start: int, count: int, width: int = 2) -> list[str]:
    return [str(start + offset).zfill(width) for offset in range(count)]


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


def test_module_is_not_a_pulse():
    source = (Path(__file__).resolve().parents[1] / "app" / "services" / "bet_expand.py").read_text(encoding="utf-8")
    assert "pulse" not in source.lower()
    assert all(module.key != "bet_expand" for module in PULSE_MODULES)


def test_rules_cover_every_game():
    from app.services.bet_expand import LIST_CAP, expand_rules

    rules = expand_rules()
    assert rules["stake"] == 2
    assert rules["list_cap"] == LIST_CAP
    assert set(rules["games"]) == {"ssq", "dlt", "fc3d", "pl3", "pl5", "qxc", "qlc", "kl8"}
    ssq = rules["games"]["ssq"]
    assert ssq["zones"][0]["pick"] == 6
    assert ssq["zones"][0]["max"] == 20
    assert ssq["zones"][1]["banker"] is False
    assert rules["games"]["kl8"]["pick_min"] == 1
    assert rules["games"]["kl8"]["pick_max"] == 10
    assert rules["games"]["qxc"]["positions"][-1]["hi"] == 14
    assert "仅供娱乐" in rules["disclaimer"]


def test_ssq_compound_count_order_cost_and_page():
    result = expand(
        lottery_type="ssq",
        mode="compound",
        main={"numbers": _nums(1, 7)},
        special={"numbers": ["01", "02"]},
        limit=3,
    )
    assert result["valid"] is True
    assert result["bet_count"] == 14
    assert result["cost"] == 28
    assert result["stake"] == 2
    assert result["returned"] == 3
    assert result["has_more"] is True
    assert result["tickets"][0] == {"main": ["01", "02", "03", "04", "05", "06"], "special": ["01"]}
    assert result["tickets"][1]["main"] == ["01", "02", "03", "04", "05", "07"]
    assert result["tickets"][2]["main"] == ["01", "02", "03", "04", "06", "07"]

    page = expand(
        lottery_type="ssq",
        mode="compound",
        main={"numbers": _nums(1, 7)},
        special={"numbers": ["01", "02"]},
        offset=7,
        limit=1,
    )
    assert page["tickets"] == [{"main": ["01", "02", "03", "04", "05", "06"], "special": ["02"]}]
    assert page["has_more"] is True

    tail = expand(
        lottery_type="ssq",
        mode="compound",
        main={"numbers": _nums(1, 7)},
        special={"numbers": ["01", "02"]},
        offset=14,
        limit=60,
    )
    assert tail["tickets"] == []
    assert tail["returned"] == 0
    assert tail["has_more"] is False
    assert tail["expanded"] is True


def test_ssq_compound_single_is_one_bet():
    result = expand(
        lottery_type="ssq",
        mode="复式",
        main={"numbers": "01 02 03 04 05 06"},
        special={"numbers": "9"},
    )
    assert result["valid"] is True
    assert result["bet_count"] == 1
    assert result["cost"] == 2
    assert result["tickets"] == [{"main": ["01", "02", "03", "04", "05", "06"], "special": ["09"]}]
    assert any("单式" in note for note in result["notes"])


def test_ssq_compound_rejects_range_dup_and_count():
    short = expand(lottery_type="ssq", mode="compound", main={"numbers": ["01"]}, special={"numbers": ["01"]})
    assert short["valid"] is False
    assert short["bet_count"] == 0
    assert "复式红球需要 6–20 个" in short["messages"]

    too_many = expand(
        lottery_type="ssq",
        mode="compound",
        main={"numbers": _nums(1, 21)},
        special={"numbers": ["01"]},
    )
    assert "复式红球需要 6–20 个" in too_many["messages"]

    dup = expand(
        lottery_type="ssq",
        mode="compound",
        main={"numbers": ["01", "01", "03", "04", "05", "06"]},
        special={"numbers": ["01"]},
    )
    assert any("重复" in message for message in dup["messages"])

    high = expand(
        lottery_type="ssq",
        mode="compound",
        main={"numbers": ["01", "02", "03", "04", "05", "34"]},
        special={"numbers": ["17"]},
    )
    assert any("红球超出" in message for message in high["messages"])
    assert any("蓝球超出" in message for message in high["messages"])

    text = expand(
        lottery_type="ssq",
        mode="compound",
        main={"numbers": ["01", "02", "03", "04", "05", "ab"]},
        special={"numbers": ["01"]},
    )
    assert any("无效" in message for message in text["messages"])


def test_ssq_banker_count_and_constraints():
    result = expand(
        lottery_type="ssq",
        mode="banker",
        main={"bankers": ["01", "02"], "drags": _nums(3, 6)},
        special={"numbers": ["09"]},
    )
    assert result["valid"] is True
    assert result["bet_count"] == 15
    assert result["cost"] == 30
    assert result["tickets"][0] == {"main": ["01", "02", "03", "04", "05", "06"], "special": ["09"]}
    assert result["tickets"][-1]["main"] == ["01", "02", "05", "06", "07", "08"]

    minimum = expand(
        lottery_type="ssq",
        mode="胆拖",
        main={"bankers": _nums(1, 5), "drags": ["06", "07"]},
        special={"numbers": ["01"]},
    )
    assert minimum["bet_count"] == 2
    assert minimum["tickets"][0]["main"] == ["01", "02", "03", "04", "05", "06"]
    assert minimum["tickets"][1]["main"] == ["01", "02", "03", "04", "05", "07"]

    overlap = expand(
        lottery_type="ssq",
        mode="banker",
        main={"bankers": ["01"], "drags": ["01", "02", "03", "04", "05", "06"]},
        special={"numbers": ["01"]},
    )
    assert overlap["valid"] is False
    assert any("重复" in message for message in overlap["messages"])

    blue = expand(
        lottery_type="ssq",
        mode="banker",
        main={"bankers": ["01"], "drags": _nums(2, 6)},
        special={"bankers": ["01"], "drags": ["02"]},
    )
    assert any("蓝球不能设胆码" in message for message in blue["messages"])

    bare = expand(
        lottery_type="ssq",
        mode="banker",
        main={"drags": _nums(1, 7)},
        special={"numbers": ["01"]},
    )
    assert "胆拖至少要有一组胆码" in bare["messages"]

    short_drag = expand(
        lottery_type="ssq",
        mode="banker",
        main={"bankers": ["01"], "drags": _nums(2, 5)},
        special={"numbers": ["01"]},
    )
    assert "红球胆码加拖码至少 7 个" in short_drag["messages"]

    one_drag = expand(
        lottery_type="ssq",
        mode="banker",
        main={"bankers": ["01"], "drags": ["02"]},
        special={"numbers": ["01"]},
    )
    assert "红球拖码至少 2 个" in one_drag["messages"]
    assert "红球胆码加拖码至少 7 个" in one_drag["messages"]

    too_many_bankers = expand(
        lottery_type="ssq",
        mode="banker",
        main={"bankers": _nums(1, 6), "drags": ["07", "08"]},
        special={"numbers": ["01"]},
    )
    assert "红球胆码需要 1–5 个" in too_many_bankers["messages"]


def test_ssq_over_list_cap_keeps_count_without_tickets():
    result = expand(
        lottery_type="ssq",
        mode="compound",
        main={"numbers": _nums(1, 15)},
        special={"numbers": ["01"]},
        limit=60,
    )
    assert result["valid"] is True
    assert result["bet_count"] == 5005
    assert result["cost"] == 10010
    assert result["tickets"] == []
    assert result["expanded"] is False
    assert result["truncated"] is True
    assert result["has_more"] is False
    assert any("5000" in message for message in result["warnings"])


def test_dlt_compound_and_banker():
    compound = expand(
        lottery_type="dlt",
        mode="compound",
        main={"numbers": _nums(1, 6)},
        special={"numbers": ["01", "02", "03"]},
    )
    assert compound["bet_count"] == 18
    assert compound["cost"] == 36
    assert compound["tickets"][0] == {"main": ["01", "02", "03", "04", "05"], "special": ["01", "02"]}

    banker = expand(
        lottery_type="dlt",
        mode="banker",
        main={"bankers": ["01", "02"], "drags": ["03", "04", "05", "06"]},
        special={"bankers": ["01"], "drags": ["02", "03"]},
    )
    assert banker["bet_count"] == 8
    assert banker["tickets"][0] == {"main": ["01", "02", "03", "04", "05"], "special": ["01", "02"]}
    assert banker["tickets"][1]["main"] == ["01", "02", "03", "04", "06"]
    assert banker["tickets"][1]["special"] == ["01", "02"]
    assert banker["tickets"][4]["special"] == ["01", "03"]

    back_plain = expand(
        lottery_type="dlt",
        mode="banker",
        main={"bankers": ["01"], "drags": _nums(2, 5)},
        special={"numbers": ["01", "02"]},
    )
    assert back_plain["valid"] is True
    assert back_plain["bet_count"] == 5

    two_back = expand(
        lottery_type="dlt",
        mode="banker",
        main={"bankers": ["01"], "drags": _nums(2, 5)},
        special={"bankers": ["01", "02"], "drags": ["03", "04"]},
    )
    assert "后区胆码只能有 1 个" in two_back["messages"]


def test_qlc_compound_and_banker():
    compound = expand(lottery_type="qlc", mode="compound", main={"numbers": _nums(1, 8)})
    assert compound["bet_count"] == 8
    assert compound["tickets"][0]["special"] == []
    assert compound["tickets"][0]["main"] == _nums(1, 7)

    banker = expand(
        lottery_type="qlc",
        mode="banker",
        main={"bankers": ["01", "02"], "drags": _nums(3, 7)},
    )
    assert banker["bet_count"] == 21
    assert banker["tickets"][0]["main"] == ["01", "02", "03", "04", "05", "06", "07"]

    huge = expand(lottery_type="qlc", mode="compound", main={"numbers": _nums(1, 17)})
    assert "复式基本号需要 7–16 个" in huge["messages"]


def test_kl8_pick_compound_and_banker():
    compound = expand(lottery_type="kl8", mode="compound", pick=5, main={"numbers": _nums(1, 6)})
    assert compound["bet_count"] == 6
    assert compound["pick"] == 5
    assert compound["tickets"][0]["main"] == _nums(1, 5)

    missing = expand(lottery_type="kl8", mode="compound", main={"numbers": _nums(1, 6)})
    assert "请选择选几" in missing["messages"][0]

    bad_pick = expand(lottery_type="kl8", mode="compound", pick=11, main={"numbers": _nums(1, 11)})
    assert "选一到选十" in bad_pick["messages"][0]

    select_one = expand(lottery_type="kl8", mode="banker", pick=1, main={"bankers": ["01"], "drags": ["02", "03"]})
    assert "选一没有胆拖" in select_one["messages"]

    banker = expand(
        lottery_type="kl8",
        mode="banker",
        pick=3,
        main={"bankers": ["01"], "drags": ["02", "03", "04"]},
    )
    assert banker["bet_count"] == 3
    assert [ticket["main"] for ticket in banker["tickets"]] == [
        ["01", "02", "03"],
        ["01", "02", "04"],
        ["01", "03", "04"],
    ]

    over = expand(lottery_type="kl8", mode="compound", pick=10, main={"numbers": _nums(1, 21)})
    assert "复式号码需要 10–20 个" in over["messages"]


def test_digit_compound_and_banker():
    fc3d = expand(
        lottery_type="fc3d",
        mode="compound",
        positions=[{"numbers": ["1", "2"]}, {"numbers": ["3"]}, {"numbers": ["4"]}],
    )
    assert fc3d["bet_count"] == 2
    assert fc3d["cost"] == 4
    assert fc3d["tickets"] == [
        {"main": ["1", "3", "4"], "special": []},
        {"main": ["2", "3", "4"], "special": []},
    ]

    alias = expand(
        lottery_type="3d",
        mode="compound",
        positions=[{"numbers": ["0"]}, {"numbers": ["1"]}, {"numbers": "2"}],
    )
    assert alias["lottery_type"] == "fc3d"
    assert alias["bet_count"] == 1

    missing = expand(lottery_type="pl3", mode="compound", positions=[{"numbers": ["1"]}, {"numbers": []}, {"numbers": ["3"]}])
    assert "十位至少选 1 个号码" in missing["messages"]

    dup = expand(
        lottery_type="pl3",
        mode="compound",
        positions=[{"numbers": ["1", "1"]}, {"numbers": ["2"]}, {"numbers": ["3"]}],
    )
    assert any("重复" in message for message in dup["messages"])

    high = expand(
        lottery_type="pl5",
        mode="compound",
        positions=[{"numbers": ["1"]}, {"numbers": ["2"]}, {"numbers": ["3"]}, {"numbers": ["4"]}, {"numbers": ["15"]}],
    )
    assert any("个位超出" in message for message in high["messages"])

    pl5 = expand(
        lottery_type="pl5",
        mode="compound",
        positions=[{"numbers": ["1", "2"]}, {"numbers": ["0"]}, {"numbers": ["0"]}, {"numbers": ["0"]}, {"numbers": ["1", "2"]}],
    )
    assert pl5["bet_count"] == 4
    assert pl5["tickets"][0]["main"] == ["1", "0", "0", "0", "1"]
    assert pl5["tickets"][1]["main"] == ["2", "0", "0", "0", "1"]

    locked = expand(
        lottery_type="fc3d",
        mode="banker",
        positions=[
            {"bankers": ["8"], "drags": []},
            {"drags": ["1", "2"]},
            {"drags": ["3"]},
        ],
    )
    assert locked["bet_count"] == 2
    assert locked["tickets"][0]["main"] == ["8", "1", "3"]
    assert locked["tickets"][1]["main"] == ["8", "2", "3"]

    mixed = expand(
        lottery_type="fc3d",
        mode="banker",
        positions=[
            {"bankers": ["8"], "drags": ["1"]},
            {"drags": ["1"]},
            {"drags": ["2"]},
        ],
    )
    assert "百位已锁胆码，不能再加拖码" in mixed["messages"]

    no_lock = expand(
        lottery_type="pl3",
        mode="banker",
        positions=[{"drags": ["1", "2"]}, {"drags": ["3"]}, {"drags": ["4"]}],
    )
    assert "胆拖至少要有一组胆码" in no_lock["messages"]

    short = expand(lottery_type="qxc", mode="compound")
    assert "请按位选择号码" in short["messages"]


def test_qxc_splits_special_and_rejects_huge_product():
    result = expand(
        lottery_type="qxc",
        mode="compound",
        positions=[
            {"numbers": ["0", "1"]},
            {"numbers": ["2"]},
            {"numbers": ["3"]},
            {"numbers": ["4"]},
            {"numbers": ["5"]},
            {"numbers": ["6"]},
            {"numbers": ["7", "14"]},
        ],
    )
    assert result["bet_count"] == 4
    assert result["tickets"][0] == {"main": ["0", "2", "3", "4", "5", "6"], "special": ["7"]}
    assert result["tickets"][2] == {"main": ["0", "2", "3", "4", "5", "6"], "special": ["14"]}

    full = [{"numbers": [str(n) for n in range(10)]} for _ in range(6)]
    full.append({"numbers": [str(n) for n in range(15)]})
    huge = expand(lottery_type="qxc", mode="compound", positions=full)
    assert huge["valid"] is False
    assert huge["bet_count"] == 15_000_000
    assert any("2000000" in message for message in huge["messages"])


def test_unknown_mode_and_limit_only_count():
    unknown = expand(lottery_type="nope", mode="compound", main={"numbers": ["01"]})
    assert unknown["valid"] is False
    assert unknown["messages"] == ["未知彩种"]

    bad_mode = expand(lottery_type="ssq", mode="pulse", main={"numbers": _nums(1, 6)}, special={"numbers": ["01"]})
    assert "复式或胆拖" in bad_mode["messages"][0]

    counted = expand(
        lottery_type="ssq",
        mode="compound",
        main={"numbers": _nums(1, 7)},
        special={"numbers": ["01"]},
        limit=0,
    )
    assert counted["valid"] is True
    assert counted["bet_count"] == 7
    assert counted["tickets"] == []
    assert counted["expanded"] is False
    assert counted["truncated"] is False


def test_center_band_filters_and_pages_matches():
    band = {
        "sum": {"low": 21, "high": 22},
        "span": {"low": 0, "high": 99},
        "odd": {"low": 0, "high": 6},
    }
    result = expand(
        lottery_type="ssq",
        mode="compound",
        main={"numbers": _nums(1, 7)},
        special={"numbers": ["01"]},
        band=band,
        limit=1,
    )
    assert result["valid"] is True
    assert result["bet_count"] == 7
    assert result["matched"] == 2
    assert result["returned"] == 1
    assert result["has_more"] is True
    assert result["tickets"] == [{"main": ["01", "02", "03", "04", "05", "06"], "special": ["01"]}]

    second = expand(
        lottery_type="ssq",
        mode="compound",
        main={"numbers": _nums(1, 7)},
        special={"numbers": ["01"]},
        band=band,
        offset=1,
        limit=10,
    )
    assert second["tickets"] == [{"main": ["01", "02", "03", "04", "05", "07"], "special": ["01"]}]
    assert second["has_more"] is False

    none = expand(
        lottery_type="ssq",
        mode="compound",
        main={"numbers": _nums(1, 6)},
        special={"numbers": ["01"]},
        band={"sum": {"low": 0, "high": 1}, "span": {"low": 0, "high": 99}, "odd": {"low": 0, "high": 6}},
    )
    assert none["matched"] == 0
    assert none["tickets"] == []
    assert any("常见带" in note for note in none["notes"])


def test_center_band_scans_above_list_cap_and_refuses_huge_scan():
    band = {
        "sum": {"low": 0, "high": 0},
        "span": {"low": 0, "high": 99},
        "odd": {"low": 0, "high": 20},
    }
    scanned = expand(
        lottery_type="ssq",
        mode="compound",
        main={"numbers": _nums(1, 15)},
        special={"numbers": ["01"]},
        band=band,
        limit=5,
    )
    assert scanned["valid"] is True
    assert scanned["bet_count"] == 5005
    assert scanned["matched"] == 0
    assert scanned["truncated"] is False
    assert scanned["expanded"] is True

    huge = expand(
        lottery_type="ssq",
        mode="compound",
        main={"numbers": _nums(1, 20)},
        special={"numbers": _nums(1, 16)},
        band=band,
    )
    assert huge["bet_count"] == 38760 * 16
    assert huge["truncated"] is True
    assert huge["tickets"] == []
    assert huge["matched"] is None
    assert any("扫描" in message for message in huge["warnings"])


def test_api_expand_rules_and_bands(client, db):
    rules = client.get("/api/bet-expand/rules")
    assert rules.status_code == 200
    assert "qlc" in rules.json()["games"]

    empty = client.get("/api/bet-expand/bands", params={"lottery_type": "ssq"})
    assert empty.status_code == 200
    assert empty.json()["ready"] is False

    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["07"])
    ready = client.get("/api/bet-expand/bands", params={"lottery_type": "ssq"})
    assert ready.status_code == 200
    body = ready.json()
    assert body["ready"] is True
    assert body["bands"]["sum"]["low"] == body["bands"]["sum"]["high"] == 21

    posted = client.post(
        "/api/bet-expand",
        json={
            "lottery_type": "ssq",
            "mode": "compound",
            "main": {"numbers": ["01", "02", "03", "04", "05", "06", "07"]},
            "special": {"numbers": ["01"]},
            "only_center": True,
            "limit": 10,
        },
    )
    assert posted.status_code == 200
    payload = posted.json()
    assert payload["bet_count"] == 7
    assert payload["matched"] == 1
    assert payload["filter"]["applied"] is True
    assert payload["tickets"][0]["main"] == ["01", "02", "03", "04", "05", "06"]
    assert "pulse" not in payload

    skipped = client.post(
        "/api/bet-expand",
        json={
            "lottery_type": "ssq",
            "mode": "compound",
            "main": {"numbers": ["01", "02", "03", "04", "05", "06"]},
            "special": {"numbers": ["08"]},
            "only_center": True,
        },
    )
    # 历史带已存在，这注和值 21、跨度 5、奇数 3，应命中。
    assert skipped.json()["matched"] == 1

    no_history = client.post(
        "/api/bet-expand",
        json={
            "lottery_type": "dlt",
            "mode": "compound",
            "main": {"numbers": ["01", "02", "03", "04", "05"]},
            "special": {"numbers": ["01", "02"]},
            "only_center": True,
        },
    )
    quiet = no_history.json()
    assert quiet["valid"] is True
    assert quiet["filter"]["applied"] is False
    assert quiet["bet_count"] == 1
    assert any("未做常见带过滤" in note for note in quiet["notes"])

    bad_limit = client.post("/api/bet-expand", json={"lottery_type": "ssq", "mode": "compound", "limit": 201})
    assert bad_limit.status_code == 422

    unknown = client.post("/api/bet-expand", json={"lottery_type": "nope", "mode": "compound"})
    assert unknown.status_code == 200
    assert unknown.json()["valid"] is False

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True


def test_center_bands_follow_form_check_quantile(db):
    from app.services.form_check import center_bands, place_value

    _draw(db, "ssq", "2026002", ["02", "03", "04", "05", "06", "16"], ["09"])
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["08"])
    bands = center_bands(db, "ssq", limit=80)
    sums = [21, 36]
    placed_low = place_value(21, sums)
    assert bands["bands"]["sum"]["low"] == placed_low["band_low"]
    assert bands["bands"]["sum"]["high"] == placed_low["band_high"]
    with pytest.raises(ValueError, match="未知彩种"):
        center_bands(db, "nope")
