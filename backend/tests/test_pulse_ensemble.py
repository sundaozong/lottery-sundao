"""脉动综合推荐：多个已有 score_* 模块给候选票打分后排序。

只新增 pulse 策略。hot / cold / hybrid / random 仍只按频次出号，
推荐项里没有综合分和分项。分数是近期形态对照，不是中奖预测。
"""
from __future__ import annotations

import json
import random

import pytest

from app.models import Draw
from app.services.predict import DISCLAIMER, generate
from app.services.pulse_ensemble import (
    PULSE_MODULES,
    SKIPPED_MODULES,
    PulseModule,
    combine_scores,
    contribution,
    generate_pulse,
    score_ticket,
)

INCLUDED = {"repeat", "momentum", "neighbor", "span", "cluster", "road", "sum", "parity", "prime"}


def _draw(db, lottery_type, issue, main, special=None):
    row = Draw(
        lottery_type=lottery_type,
        issue=issue,
        numbers=json.dumps({"main": main, "special": special or []}, ensure_ascii=False),
        draw_date="2026-01-01",
        source="seed",
    )
    db.add(row)
    db.commit()
    return row


def _seed_ssq(db, count=12):
    for index in range(count):
        main = [f"{(index + offset) % 33 + 1:02d}" for offset in (1, 4, 8, 13, 19, 26)]
        blue = f"{index % 16 + 1:02d}"
        _draw(db, "ssq", f"2026{index + 1:03d}", main, [blue])


def _seed_dlt(db, count=10):
    for index in range(count):
        main = [f"{(index + offset) % 35 + 1:02d}" for offset in (1, 6, 11, 18, 27)]
        special = [f"{index % 12 + 1:02d}", f"{(index + 5) % 12 + 1:02d}"]
        if special[0] == special[1]:
            special[1] = f"{(int(special[1]) % 12) + 1:02d}"
        _draw(db, "dlt", f"2026{index + 1:03d}", main, special)


def test_registry_uses_existing_ticket_scorers_and_skips_modules_without_one():
    keys = [item.key for item in PULSE_MODULES]
    assert keys == ["repeat", "momentum", "neighbor", "span", "cluster", "road", "sum", "parity", "prime"]
    assert len(keys) == len(set(keys))
    skipped = {item["module"]: item["reason"] for item in SKIPPED_MODULES}
    assert {"collision", "echo", "affinity"} <= set(skipped)
    for reason in skipped.values():
        assert reason


def test_shape_contribution_rewards_typical_aligned_common():
    high, note = contribution(
        {
            "ticket": {
                "typicality": 1.0,
                "alignment": "aligned",
                "rarity": "common",
                "note": "和值 100，和短窗脉动同向。",
            }
        }
    )
    low, _ = contribution(
        {
            "ticket": {
                "typicality": 0.0,
                "alignment": "against",
                "rarity": "rare",
                "note": "少见",
            }
        }
    )
    assert high == 1.0
    assert low < high
    assert "和值" in note


def test_empty_shape_ticket_is_omitted():
    score, note = contribution(
        {
            "ticket": {
                "sum": None,
                "percentile": None,
                "typicality": None,
                "rarity": None,
                "alignment": None,
                "note": "",
            },
            "special_ticket": {
                "sum": None,
                "percentile": None,
                "typicality": None,
                "rarity": None,
                "alignment": None,
                "note": "",
            },
        }
    )
    assert score is None
    assert note == ""


def test_momentum_and_neighbor_contributions_stay_in_unit_interval():
    rising, note = contribution(
        {"ticket": {"rising_count": 6, "falling_count": 0, "flat_count": 0, "score": 6}}
    )
    mixed, _ = contribution(
        {"ticket": {"rising_count": 1, "falling_count": 1, "flat_count": 0, "score": 0}}
    )
    pulled, _ = contribution(
        {"ticket": {"pulled_count": 4, "idle_count": 0, "strength": 2.4, "score": 4}}
    )
    idle, _ = contribution(
        {"ticket": {"pulled_count": 0, "idle_count": 4, "strength": 0, "score": 0}}
    )
    assert rising == 1.0
    assert mixed == 0.5
    assert "上升" in note
    assert pulled == 1.0
    assert idle == 0.0


def test_repeat_contribution_uses_overlap_distribution():
    score, note = contribution(
        {
            "overlap": 2,
            "percentile": 0.5,
            "mean": 2,
            "max": 4,
            "distribution": [{"overlap": 2, "count": 5, "rate": 0.5}],
        }
    )
    assert score == pytest.approx(0.7)
    assert "重号" in note


def test_combine_scores_uses_equal_weights_and_skips_missing():
    total = combine_scores(
        [
            {"score": 1.0, "weight": 1},
            {"score": 0.0, "weight": 1},
            {"score": None, "weight": 1},
        ]
    )
    assert total == 0.5


def test_combine_scores_respects_weights():
    total = combine_scores(
        [
            {"score": 1.0, "weight": 3},
            {"score": 0.0, "weight": 1},
        ]
    )
    assert total == 0.75


def test_new_scorer_registers_with_one_list_entry(db):
    def score_extra(db, lottery_type, main, special=None):
        hit = "01" in (main or [])
        return {
            "ticket": {
                "typicality": 1.0 if hit else 0.0,
                "alignment": "aligned" if hit else "against",
                "rarity": "common" if hit else "rare",
                "note": "附加较多" if hit else "附加较少",
            }
        }

    modules = list(PULSE_MODULES) + [PulseModule("extra", "附加", score_extra)]
    _seed_ssq(db)
    body = generate_pulse(
        db,
        "ssq",
        count=1,
        modules=modules,
        candidate_count=24,
        rng=random.Random(3),
    )
    names = [item["module"] for item in body["recommendations"][0]["breakdown"]]
    assert names[-1] == "extra"
    assert "附加" in {item["label"] for item in body["recommendations"][0]["breakdown"]}
    assert "parity" in names


def test_generate_pulse_ranks_ssq_and_states_entertainment_only(db):
    _seed_ssq(db)
    body = generate_pulse(db, "ssq", count=3, candidate_count=40, rng=random.Random(7))
    assert body["lottery_type"] == "ssq"
    assert body["strategy"] == "pulse"
    assert body["entertainment_only"] is True
    assert body["disclaimer"] == DISCLAIMER
    assert "仅供娱乐" in body["disclaimer"]
    assert "不保证" in body["disclaimer"]
    assert len(body["recommendations"]) == 3
    assert body["candidate_count"] >= 40
    scores = [item["score"] for item in body["recommendations"]]
    assert scores == sorted(scores, reverse=True)
    modules = [item.key for item in PULSE_MODULES]
    assert body["modules"] == modules
    seen = set()
    for rec in body["recommendations"]:
        assert len(rec["main"]) == 6
        assert len(set(rec["main"])) == 6
        assert rec["main"] == sorted(rec["main"], key=int)
        assert all(1 <= int(n) <= 33 for n in rec["main"])
        assert len(rec["special"]) == 1
        assert 1 <= int(rec["special"][0]) <= 16
        assert 0 <= rec["score"] <= 1
        assert "仅供娱乐" in rec["rationale"]
        assert "预测" not in rec["rationale"]
        assert [item["module"] for item in rec["breakdown"]] == modules
        for item in rec["breakdown"]:
            assert item["score"] is None or 0 <= item["score"] <= 1
            assert item["label"]
        seen.add((tuple(rec["main"]), tuple(rec["special"])))
    assert len(seen) == 3
    assert {item["module"] for item in body["skipped_modules"]} >= {"collision", "echo", "affinity"}


def test_generate_pulse_dlt_ticket_shape(db):
    _seed_dlt(db)
    body = generate_pulse(db, "dlt", count=2, candidate_count=30, rng=random.Random(11))
    assert body["lottery_type"] == "dlt"
    assert len(body["recommendations"]) == 2
    for rec in body["recommendations"]:
        assert len(rec["main"]) == 5
        assert len(set(rec["main"])) == 5
        assert all(1 <= int(n) <= 35 for n in rec["main"])
        assert len(rec["special"]) == 2
        assert len(set(rec["special"])) == 2
        assert all(1 <= int(n) <= 12 for n in rec["special"])


def test_digit_lottery_keeps_position_order(db):
    for index in range(8):
        _draw(db, "fc3d", f"2026{index + 1:03d}", [str(index % 10), str((index + 3) % 10), str((index + 7) % 10)])
    body = generate_pulse(db, "fc3d", count=2, candidate_count=20, rng=random.Random(1))
    for rec in body["recommendations"]:
        assert len(rec["main"]) == 3
        assert rec["special"] == []
        assert all(n.isdigit() and 0 <= int(n) <= 9 for n in rec["main"])


def test_other_supported_lotteries_reuse_the_pipeline(db):
    samples = {
        "qlc": (["01", "02", "03", "04", "05", "06", "07"], []),
        "kl8": ([f"{n:02d}" for n in range(1, 21)], []),
        "pl5": (["1", "2", "3", "4", "5"], []),
        "qxc": (["1", "2", "3", "4", "5", "6"], ["7"]),
    }
    for index in range(6):
        for lottery, (main, special) in samples.items():
            _draw(db, lottery, f"2026{index + 1:03d}", main, special)
    for lottery, (main, special) in samples.items():
        body = generate_pulse(db, lottery, count=1, candidate_count=12, rng=random.Random(2))
        rec = body["recommendations"][0]
        assert len(rec["main"]) == len(main)
        assert len(rec["special"]) == len(special)
        assert body["entertainment_only"] is True


def test_empty_history_still_returns_entertainment_tickets(db):
    body = generate_pulse(db, "ssq", count=1, candidate_count=12, rng=random.Random(1))
    rec = body["recommendations"][0]
    assert len(rec["main"]) == 6
    assert len(rec["special"]) == 1
    assert body["entertainment_only"] is True
    assert "仅供娱乐" in rec["rationale"]


def test_unknown_lottery_is_rejected(db):
    with pytest.raises(ValueError, match="彩种"):
        generate_pulse(db, "nope", count=1)


def test_bad_weights_are_rejected(db):
    _seed_ssq(db, count=6)
    with pytest.raises(ValueError, match="权重"):
        generate_pulse(db, "ssq", count=1, weights={"not-a-module": 1}, candidate_count=8)
    with pytest.raises(ValueError, match="权重"):
        generate_pulse(db, "ssq", count=1, weights={"span": -0.2}, candidate_count=8)


def test_weights_change_which_ticket_ranks_first(db):
    def score_front(db, lottery_type, main, special=None):
        hit = "01" in (main or [])
        return {
            "ticket": {
                "typicality": 1.0 if hit else 0.0,
                "alignment": "aligned" if hit else "against",
                "rarity": "common" if hit else "rare",
                "note": "偏前" if hit else "不偏前",
            }
        }

    def score_back(db, lottery_type, main, special=None):
        hit = "01" not in (main or [])
        return {
            "ticket": {
                "typicality": 1.0 if hit else 0.0,
                "alignment": "aligned" if hit else "against",
                "rarity": "common" if hit else "rare",
                "note": "避开" if hit else "含有",
            }
        }

    modules = [
        PulseModule("front", "偏前", score_front),
        PulseModule("back", "避开", score_back),
    ]
    shared = dict(count=1, modules=modules, candidate_count=80, rng=random.Random(5))
    prefer_front = generate_pulse(db, "ssq", weights={"front": 5, "back": 0.1}, **shared)
    prefer_back = generate_pulse(db, "ssq", weights={"front": 0.1, "back": 5}, **shared)
    assert "01" in prefer_front["recommendations"][0]["main"]
    assert "01" not in prefer_back["recommendations"][0]["main"]


def test_score_ticket_calls_registered_modules(db):
    _seed_ssq(db)
    scored = score_ticket(db, "ssq", ["03", "08", "14", "19", "25", "31"], ["09"])
    assert [item["module"] for item in scored["breakdown"]] == [item.key for item in PULSE_MODULES]
    assert scored["score"] is not None
    notes = " ".join(item["note"] for item in scored["breakdown"])
    assert "和值" in notes
    parity = next(item for item in scored["breakdown"] if item["module"] == "parity")
    assert parity["label"] == "奇偶"
    assert parity["score"] is not None
    assert "奇数" in parity["note"]
    prime = next(item for item in scored["breakdown"] if item["module"] == "prime")
    assert prime["label"] == "质合"
    assert prime["score"] is not None
    assert "质数" in prime["note"]


def test_existing_strategies_do_not_gain_pulse_fields(db):
    _seed_ssq(db)
    for strategy in ("hot", "cold", "hybrid", "random"):
        body = generate(db, "ssq", strategy, count=2)
        assert body["strategy"] == strategy
        assert body["entertainment_only"] is True
        assert "modules" not in body
        assert "breakdown" not in body
        for rec in body["recommendations"]:
            assert set(rec) == {"main", "special"}


def test_generate_delegates_pulse_without_changing_unknown_fallback(db):
    _seed_ssq(db)
    pulse = generate(db, "ssq", "pulse", count=1)
    assert pulse["strategy"] == "pulse"
    assert "breakdown" in pulse["recommendations"][0]
    unknown = generate(db, "ssq", "mystery", count=1)
    assert unknown["strategy"] == "random"
    assert set(unknown["recommendations"][0]) == {"main", "special"}


def test_api_pulse_and_legacy_strategies(client, db):
    _seed_ssq(db)
    _seed_dlt(db)
    pulse = client.post("/api/predict", json={"lottery_type": "ssq", "strategy": "pulse", "count": 2})
    assert pulse.status_code == 200
    body = pulse.json()
    assert body["strategy"] == "pulse"
    assert body["entertainment_only"] is True
    assert "仅供娱乐" in body["disclaimer"]
    assert len(body["recommendations"]) == 2
    assert body["recommendations"][0]["score"] >= body["recommendations"][1]["score"]
    assert INCLUDED <= {item["module"] for item in body["recommendations"][0]["breakdown"]}

    hot = client.post(
        "/api/predict",
        json={"lottery_type": "ssq", "strategy": "hot", "count": 1, "weights": {"span": 3}},
    )
    assert hot.status_code == 200
    hot_body = hot.json()
    assert hot_body["strategy"] == "hot"
    assert "score" not in hot_body["recommendations"][0]
    assert "modules" not in hot_body

    rejected = client.post("/api/predict", json={"lottery_type": "nope", "strategy": "pulse", "count": 1})
    assert rejected.status_code == 400
    assert "彩种" in rejected.json()["detail"]

    bounded = client.post("/api/predict", json={"lottery_type": "ssq", "strategy": "pulse", "count": 11})
    assert bounded.status_code == 422


def test_openapi_documents_pulse_strategy(client):
    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    schema = spec.json()["components"]["schemas"]["PredictIn"]
    description = schema["properties"]["strategy"]["description"]
    assert "pulse" in description
    assert "脉动综合" in description
    post = spec.json()["paths"]["/api/predict"]["post"]
    text = f"{post.get('summary', '')} {post.get('description', '')}"
    assert "pulse" in text or "脉动" in text
