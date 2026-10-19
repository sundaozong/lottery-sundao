"""历史回放：一注对照开奖，以及机选条件的逐期前推。

不改奖金页原有回测的返回形状，也不走脉动综合。
"""
from __future__ import annotations

import json

import pytest

from app.models import Draw
from app.services.analyze import analyze
from app.services.predict import generate
from app.services.replay import MAX_STRATEGY_PERIODS, MAX_TICKET_PERIODS, replay_strategy, replay_ticket


def _draw(db, lottery_type, issue, main, special=None, draw_date=""):
    row = Draw(
        lottery_type=lottery_type,
        issue=issue,
        numbers=json.dumps({"main": main, "special": special or []}, ensure_ascii=False),
        draw_date=draw_date,
        source="seed",
    )
    db.add(row)
    db.commit()
    return row


def _ssq(main, special):
    return {"main": main, "special": special}


SSQ_BET = _ssq(["01", "02", "03", "04", "05", "06"], ["07"])


def test_analyze_cutoff_drops_current_and_later_draws(db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["01"])
    _draw(db, "ssq", "2026002", ["07", "08", "09", "10", "11", "12"], ["02"])
    _draw(db, "ssq", "2026003", ["13", "14", "15", "16", "17", "18"], ["03"])

    full = analyze(db, "ssq", limit=50)
    assert full["sample_size"] == 3

    cut = analyze(db, "ssq", limit=50, before_issue="2026002")
    assert cut["sample_size"] == 1
    assert {item["issue"] for item in cut["history"]} == {"2026001"}


def test_ticket_replay_levels_best_stake_rate_and_miss_streak(client, db):
    _draw(db, "ssq", "2026001", ["11", "12", "13", "14", "15", "16"], ["08"], "2026-01-01")
    _draw(db, "ssq", "2026002", ["01", "02", "03", "04", "05", "06"], ["07"], "2026-01-03")
    _draw(db, "ssq", "2026003", ["21", "22", "23", "24", "25", "26"], ["09"], "2026-01-05")
    _draw(db, "ssq", "2026004", ["27", "28", "29", "30", "31", "32"], ["10"], "2026-01-07")
    _draw(db, "ssq", "2026005", ["31", "32", "33", "18", "19", "20"], ["07"], "2026-01-09")

    report = client.post("/api/replay/ticket", json={"lottery_type": "ssq", "bet_numbers": SSQ_BET, "window": "all"})
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["sample_size"] == 5
    assert body["history_size"] == 5
    assert body["capped"] is False
    assert body["win_draws"] == 2
    assert body["spent"] == 10
    assert body["prize"] == 5_000_005
    assert body["prize_is_reference"] is True
    assert body["return_rate"] == 500_000.5
    assert body["longest_miss"] == 2
    assert body["best"]["issue"] == "2026002"
    assert body["best"]["level"] == "一等奖"
    assert body["best"]["amount"] == 5_000_000
    assert body["best"]["floating"] is True
    assert "参考" in body["best"]["amount_label"]
    assert body["best"]["numbers"]["main"] == SSQ_BET["main"]
    levels = {row["level"]: row for row in body["levels"]}
    assert levels["一等奖"]["count"] == 1
    assert levels["六等奖"]["count"] == 1
    assert levels["二等奖"]["count"] == 0
    assert levels["六等奖"]["amount"] == 5
    assert levels["六等奖"]["floating"] is False
    assert [hit["issue"] for hit in body["hits"]] == ["2026005", "2026002"]
    assert "独立" in body["note"]
    assert "不代表" in body["disclaimer"]

    latest = client.post("/api/replay/ticket", json={"lottery_type": "ssq", "bet_numbers": SSQ_BET, "window": 2})
    assert latest.status_code == 200
    narrowed = latest.json()
    assert narrowed["sample_size"] == 2
    assert narrowed["history_size"] == 5
    assert narrowed["win_draws"] == 1
    assert narrowed["prize"] == 5
    assert narrowed["spent"] == 4
    assert narrowed["return_rate"] == 1.25
    assert narrowed["prize_is_reference"] is False
    assert narrowed["longest_miss"] == 1
    assert narrowed["best"]["issue"] == "2026005"
    assert narrowed["best"]["level"] == "六等奖"
    assert "参考" not in narrowed["best"]["amount_label"]


def test_window_past_history_and_empty_history(client, db):
    empty = client.post("/api/replay/ticket", json={"lottery_type": "ssq", "bet_numbers": SSQ_BET, "window": 300})
    assert empty.status_code == 200, empty.text
    blank = empty.json()
    assert blank["sample_size"] == 0
    assert blank["history_size"] == 0
    assert blank["spent"] == 0
    assert blank["prize"] == 0
    assert blank["return_rate"] is None
    assert blank["longest_miss"] == 0
    assert blank["best"] is None
    assert blank["win_draws"] == 0
    assert blank["capped"] is False

    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["07"])
    _draw(db, "ssq", "2026002", ["11", "12", "13", "14", "15", "16"], ["08"])
    wide = client.post("/api/replay/ticket", json={"lottery_type": "ssq", "bet_numbers": SSQ_BET, "window": "300"})
    assert wide.status_code == 200
    body = wide.json()
    assert body["history_size"] == 2
    assert body["sample_size"] == 2
    assert body["capped"] is False
    assert body["win_draws"] == 1
    assert body["prize"] == 5_000_000


def test_invalid_ticket_and_unknown_lottery(client):
    bad = client.post(
        "/api/replay/ticket",
        json={"lottery_type": "ssq", "bet_numbers": {"main": ["99"], "special": ["1"]}},
    )
    assert bad.status_code == 400
    unknown = client.post("/api/replay/ticket", json={"lottery_type": "nope", "bet_numbers": {}})
    assert unknown.status_code == 400
    window = client.post(
        "/api/replay/ticket",
        json={"lottery_type": "ssq", "bet_numbers": SSQ_BET, "window": "soon"},
    )
    assert window.status_code == 400


def test_incomplete_draw_is_skipped(client, db):
    _draw(db, "ssq", "2026001", ["01"], ["01"])
    _draw(db, "ssq", "2026002", ["01", "02", "03", "04", "05", "06"], ["07"])
    report = client.post("/api/replay/ticket", json={"lottery_type": "ssq", "bet_numbers": SSQ_BET, "window": "all"})
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["sample_size"] == 1
    assert body["skipped_draws"] == 1
    assert body["prize"] == 5_000_000
    assert body["spent"] == 2


def test_multiple_scales_stake_and_prize(client, db):
    _draw(db, "ssq", "2026001", ["31", "32", "33", "18", "19", "20"], ["07"])
    report = client.post(
        "/api/replay/ticket",
        json={"lottery_type": "ssq", "bet_numbers": SSQ_BET, "window": 30, "multiple": 2},
    )
    assert report.status_code == 200
    body = report.json()
    assert body["spent"] == 4
    assert body["prize"] == 10
    assert body["levels"]
    sixth = next(row for row in body["levels"] if row["level"] == "六等奖")
    assert sixth["count"] == 1
    assert sixth["amount"] == 10


@pytest.mark.parametrize(
    ("lottery", "bet", "draw_main", "draw_special", "play", "pick", "level", "amount", "floating"),
    [
        ("ssq", ["01", "02", "03", "04", "05", "06"], ["01", "02", "03", "04", "05", "06"], ["07"], None, None, "一等奖", 5_000_000, True),
        ("dlt", ["01", "02", "03", "04", "05"], ["01", "02", "03", "04", "05"], ["01", "02"], None, None, "一等奖", 10_000_000, True),
        ("dlt", ["01", "02", "03", "04", "05"], ["11", "12", "13", "14", "15"], ["01", "02"], None, None, "九等奖", 5, False),
        ("fc3d", ["1", "2", "3"], ["1", "2", "3"], [], None, None, "直选", 1040, False),
        ("fc3d", ["1", "1", "2"], ["2", "1", "1"], [], "group3", None, "组三", 346, False),
        ("fc3d", ["1", "2", "3"], ["3", "1", "2"], [], "group6", None, "组六", 173, False),
        ("pl3", ["4", "5", "6"], ["4", "5", "6"], [], None, None, "直选", 1040, False),
        ("pl3", ["7", "7", "8"], ["8", "7", "7"], [], "group3", None, "组三", 346, False),
        ("pl5", ["1", "2", "3", "4", "5"], ["1", "2", "3", "4", "5"], [], None, None, "直选", 100_000, False),
        ("qxc", ["1", "2", "3", "4", "5", "6"], ["1", "2", "3", "4", "5", "6"], ["7"], None, None, "一等奖", 5_000_000, True),
        ("qxc", ["1", "2", "3", "4", "5", "6"], ["9", "8", "7", "6", "5", "4"], ["7"], None, None, "六等奖", 5, False),
        ("qlc", ["01", "02", "03", "04", "05", "06", "07"], ["01", "02", "03", "04", "05", "06", "07"], ["08"], None, None, "一等奖", 500_000, True),
        ("qlc", ["01", "02", "03", "04", "05", "06", "07"], ["01", "02", "03", "04", "18", "19", "20"], ["09"], None, None, "七等奖", 5, False),
        ("kl8", [f"{i:02d}" for i in range(1, 11)], [f"{i:02d}" for i in range(1, 21)], [], None, 10, "一等奖", 5_000_000, True),
        ("kl8", ["01", "02"], ["01", "02"] + [f"{i:02d}" for i in range(3, 21)], [], None, 2, "一等奖", 19, False),
    ],
)
def test_each_lottery_prize_level(client, db, lottery, bet, draw_main, draw_special, play, pick, level, amount, floating):
    _draw(db, lottery, "2026015", draw_main, draw_special)
    special_bet = []
    if lottery == "ssq":
        special_bet = ["07"]
    elif lottery == "dlt":
        special_bet = ["01", "02"]
    elif lottery == "qxc":
        special_bet = ["7"]
    payload = {"lottery_type": lottery, "bet_numbers": {"main": bet, "special": special_bet}, "window": 30}
    if play:
        payload["play"] = play
    if pick:
        payload["pick"] = pick
    report = client.post("/api/replay/ticket", json=payload)
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["best"]["level"] == level
    assert body["best"]["amount"] == amount
    assert body["best"]["floating"] is floating
    assert body["prize"] == amount
    matched = next(row for row in body["levels"] if row["level"] == level)
    assert matched["count"] == 1
    assert matched["floating"] is floating
    if floating:
        assert "参考" in matched["amount_label"]
    else:
        assert "参考" not in matched["amount_label"]


def test_ticket_cap_keeps_the_newest_draws(client, db, monkeypatch):
    monkeypatch.setattr("app.services.replay.MAX_TICKET_PERIODS", 2)
    _draw(db, "ssq", "2026001", ["01", "02", "03", "04", "05", "06"], ["07"])
    _draw(db, "ssq", "2026002", ["11", "12", "13", "14", "15", "16"], ["08"])
    _draw(db, "ssq", "2026003", ["21", "22", "23", "24", "25", "26"], ["09"])
    report = client.post("/api/replay/ticket", json={"lottery_type": "ssq", "bet_numbers": SSQ_BET, "window": "all"})
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["history_size"] == 3
    assert body["sample_size"] == 2
    assert body["capped"] is True
    assert body["win_draws"] == 0
    assert MAX_TICKET_PERIODS >= 2


def _flat(recs):
    return [{"main": list(item["main"]), "special": list(item["special"])} for item in recs]


def test_walk_forward_matches_prior_only_generator(db):
    draws = [
        (["01", "02", "03", "04", "05", "06"], ["01"]),
        (["02", "03", "04", "05", "06", "07"], ["02"]),
        (["08", "09", "10", "11", "12", "13"], ["03"]),
        (["14", "15", "16", "17", "18", "19"], ["04"]),
    ]
    for index, (main, special) in enumerate(draws, start=1):
        _draw(db, "ssq", f"202600{index}", main, special, f"2026-02-0{index}")

    report = replay_strategy(db, "ssq", strategy="hot", tickets=2, window=2, seed=5)
    assert report["sample_size"] == 2
    assert [period["issue"] for period in report["strategy"]["periods"]] == ["2026003", "2026004"]
    assert [period["prior_draws"] for period in report["strategy"]["periods"]] == [2, 3]

    import random

    random.seed(5)
    first = generate(db, "ssq", "hot", count=2, before_issue="2026003")
    second = generate(db, "ssq", "hot", count=2, before_issue="2026004")
    assert report["strategy"]["periods"][0]["tickets"] == _flat(first["recommendations"])
    assert report["strategy"]["periods"][1]["tickets"] == _flat(second["recommendations"])
    assert report["strategy"]["latest_tickets"] == _flat(second["recommendations"])

    target = db.query(Draw).filter(Draw.issue == "2026004").one()
    target.numbers = json.dumps(
        {"main": report["strategy"]["periods"][1]["tickets"][0]["main"], "special": report["strategy"]["periods"][1]["tickets"][0]["special"]},
        ensure_ascii=False,
    )
    db.commit()
    again = replay_strategy(db, "ssq", strategy="hot", tickets=2, window=2, seed=5)
    assert again["strategy"]["periods"][0]["tickets"] == report["strategy"]["periods"][0]["tickets"]
    assert again["strategy"]["periods"][1]["tickets"] == report["strategy"]["periods"][1]["tickets"]
    assert report["strategy"]["periods"][1]["prize"] < 5_000_000
    assert again["strategy"]["periods"][1]["prize"] >= 5_000_000
    assert again["strategy"]["periods"][1]["prize"] > report["strategy"]["periods"][1]["prize"]

    _draw(db, "ssq", "2026009", ["20", "21", "22", "23", "24", "25"], ["16"])
    with_future = replay_strategy(db, "ssq", strategy="hot", tickets=2, window=3, seed=5)
    older = [period for period in with_future["strategy"]["periods"] if period["issue"] == "2026003"][0]
    assert older["tickets"] == report["strategy"]["periods"][0]["tickets"]
    assert older["prior_draws"] == 2


def test_strategy_constraints_baseline_and_guards(client, db):
    for index in range(6):
        main = [f"{(index + offset) % 33 + 1:02d}" for offset in (1, 4, 8, 13, 19, 26)]
        _draw(db, "ssq", f"202610{index}", main, [f"{index % 16 + 1:02d}"])

    report = client.post(
        "/api/replay/strategy",
        json={
            "lottery_type": "ssq",
            "strategy": "cold",
            "tickets": 2,
            "window": "all",
            "seed": 9,
            "constraints": {"include_main": ["3", "07"], "exclude_main": ["01"]},
        },
    )
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["sample_size"] == 6
    assert body["strategy"]["name"] == "cold"
    assert body["strategy"]["constraints_applied"] is True
    assert body["baseline"]["name"] == "random"
    assert body["baseline"]["constraints_applied"] is False
    assert body["baseline"]["sample_size"] == body["strategy"]["sample_size"]
    assert body["strategy"]["spent"] == 2 * 2 * 6
    assert body["baseline"]["spent"] == body["strategy"]["spent"]
    assert "随机" in body["note"] or "独立" in body["note"]
    for period in body["strategy"]["periods"]:
        assert period["prior_draws"] == int(period["issue"][-1])
        for ticket in period["tickets"]:
            assert {"03", "07"} <= set(ticket["main"])
            assert "01" not in ticket["main"]
    plain = [ticket for period in body["baseline"]["periods"] for ticket in period["tickets"]]
    assert any("03" not in ticket["main"] or "07" not in ticket["main"] for ticket in plain)

    blocked = client.post("/api/replay/strategy", json={"lottery_type": "ssq", "strategy": "pulse", "window": 30})
    assert blocked.status_code == 400
    weird = client.post("/api/replay/strategy", json={"lottery_type": "ssq", "strategy": "martingale", "window": 30})
    assert weird.status_code == 400
    tight = client.post(
        "/api/replay/strategy",
        json={
            "lottery_type": "ssq",
            "strategy": "hot",
            "constraints": {"include_main": ["01", "02", "03", "04", "05", "06", "07"]},
            "window": 30,
        },
    )
    assert tight.status_code == 400
    missing = client.post("/api/replay/strategy", json={"lottery_type": "nope", "strategy": "hot"})
    assert missing.status_code == 400


def test_strategy_empty_history(client):
    report = client.post("/api/replay/strategy", json={"lottery_type": "dlt", "strategy": "hybrid", "window": "100", "tickets": 1})
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["sample_size"] == 0
    assert body["strategy"]["spent"] == 0
    assert body["strategy"]["return_rate"] is None
    assert body["strategy"]["longest_miss"] == 0
    assert body["strategy"]["best"] is None
    assert body["baseline"]["prize"] == 0


def test_strategy_cap(monkeypatch, db):
    monkeypatch.setattr("app.services.replay.MAX_STRATEGY_PERIODS", 2)
    for index in range(4):
        _draw(db, "ssq", f"202620{index}", ["01", "02", "03", "04", "05", "06"], ["01"])
    report = replay_strategy(db, "ssq", strategy="random", tickets=1, window="all", seed=1)
    assert report["history_size"] == 4
    assert report["sample_size"] == 2
    assert report["capped"] is True
    assert [period["issue"] for period in report["strategy"]["periods"]] == ["2026202", "2026203"]
    assert MAX_STRATEGY_PERIODS >= 2
