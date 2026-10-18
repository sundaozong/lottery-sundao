"""机选条件：在热号/冷号/混合/随机抽样之后做有限次拒绝采样。

不改脉动综合的打分。未传 constraints 时，响应字段与原来一致。
"""
from __future__ import annotations

import json
import random

import pytest

from app.models import Draw
from app.services.predict import generate


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


def _seed_ssq(db, count=8):
    for index in range(count):
        main = [f"{(index + offset) % 33 + 1:02d}" for offset in (1, 4, 8, 13, 19, 26)]
        _draw(db, "ssq", f"2026{index + 1:03d}", main, [f"{index % 16 + 1:02d}"])


def _ints(numbers):
    return [int(number) for number in numbers]


def _odd(numbers):
    return sum(number % 2 for number in _ints(numbers))


def _sum(numbers):
    return sum(_ints(numbers))


def _span(numbers):
    values = _ints(numbers)
    return max(values) - min(values)


def _max_run(numbers):
    ordered = sorted(set(_ints(numbers)))
    best = run = 1
    for previous, current in zip(ordered, ordered[1:]):
        if current == previous + 1:
            run += 1
            best = max(best, run)
        else:
            run = 1
    return best


def _zones(numbers):
    counts = [0, 0, 0]
    for number in _ints(numbers):
        if number <= 11:
            counts[0] += 1
        elif number <= 22:
            counts[1] += 1
        else:
            counts[2] += 1
    return counts


def _big(numbers, mid=17):
    return sum(number > mid for number in _ints(numbers))


def test_unconstrained_response_keeps_legacy_contract(db):
    _seed_ssq(db)
    random.seed(11)
    body = generate(db, "ssq", "hot", count=2)
    assert set(body) == {
        "lottery_type",
        "strategy",
        "recommendations",
        "disclaimer",
        "entertainment_only",
        "data_status",
    }
    assert body["strategy"] == "hot"
    assert body["entertainment_only"] is True
    assert "仅供娱乐" in body["disclaimer"]
    assert len(body["recommendations"]) == 2
    for rec in body["recommendations"]:
        assert set(rec) == {"main", "special"}
        assert len(rec["main"]) == 6
        assert len(rec["special"]) == 1


def test_empty_constraints_do_not_change_sampling(db):
    _seed_ssq(db)
    random.seed(23)
    plain = generate(db, "dlt", "cold", count=2)
    random.seed(23)
    empty = generate(db, "dlt", "cold", count=2, constraints={})
    random.seed(23)
    nulls = generate(
        db,
        "dlt",
        "cold",
        count=2,
        constraints={"include_main": [], "odd_count": None, "sum_min": None},
    )
    assert empty == plain
    assert nulls == plain
    assert "constraints" not in plain


def test_include_and_exclude_enforced_for_lotto(db):
    _seed_ssq(db)
    body = generate(
        db,
        "ssq",
        "random",
        count=4,
        constraints={
            "include_main": ["3", "07"],
            "exclude_main": ["01", "02", "33"],
            "include_special": ["8"],
            "exclude_special": ["01", "16"],
        },
    )
    assert body["constraints"]["include_main"] == ["03", "07"]
    assert body["constraints"]["exclude_main"] == ["01", "02", "33"]
    assert body["constraints"]["include_special"] == ["08"]
    assert len(body["recommendations"]) == 4
    for rec in body["recommendations"]:
        assert {"03", "07"} <= set(rec["main"])
        assert not ({"01", "02", "33"} & set(rec["main"]))
        assert rec["special"] == ["08"]
        assert len(rec["main"]) == 6
        assert "含胆 03" in rec["constraint_summary"]
        assert "07" in rec["constraint_summary"]


def test_odd_sum_and_span_filters(db):
    body = generate(
        db,
        "ssq",
        "hybrid",
        count=3,
        constraints={
            "odd_count": 3,
            "sum_min": 80,
            "sum_max": 140,
            "span_min": 15,
            "span_max": 32,
        },
    )
    for rec in body["recommendations"]:
        assert _odd(rec["main"]) == 3
        assert 80 <= _sum(rec["main"]) <= 140
        assert 15 <= _span(rec["main"]) <= 32
        assert "奇3偶3" in rec["constraint_summary"]
        assert "和值" in rec["constraint_summary"]
        assert "跨度" in rec["constraint_summary"]


def test_consecutive_zone_and_big_filters(db):
    body = generate(
        db,
        "ssq",
        "random",
        count=3,
        constraints={
            "max_consecutive": 3,
            "zone_counts": [2, 2, 2],
            "big_min": 2,
            "big_max": 4,
        },
    )
    assert body["constraints"]["zone_counts"] == [2, 2, 2]
    for rec in body["recommendations"]:
        assert _max_run(rec["main"]) <= 3
        assert _zones(rec["main"]) == [2, 2, 2]
        assert 2 <= _big(rec["main"]) <= 4
        assert "区位 2:2:2" in rec["constraint_summary"]
        assert "大" in rec["constraint_summary"]


def test_digit_lottery_keeps_duplicates_and_filters(db, monkeypatch):
    sequence = iter(["7", "7", "1"])

    def fake_choice(_pool):
        return next(sequence)

    monkeypatch.setattr("app.services.predict.random.choice", fake_choice)
    body = generate(
        db,
        "pl3",
        "random",
        count=1,
        constraints={
            "include_main": ["7"],
            "exclude_main": ["0"],
            "odd_count": 3,
            "sum_min": 15,
            "sum_max": 15,
            "span_min": 6,
            "span_max": 6,
            "big_count": 2,
        },
    )
    rec = body["recommendations"][0]
    assert rec["main"] == ["7", "7", "1"]
    assert rec["special"] == []
    assert "奇3偶0" in rec["constraint_summary"]
    assert "和值 15" in rec["constraint_summary"]
    assert "跨度 6" in rec["constraint_summary"]
    assert "含胆 7" in rec["constraint_summary"]
    assert "2大1小" in rec["constraint_summary"]

    varied = generate(
        db,
        "fc3d",
        "hot",
        count=3,
        constraints={
            "include_main": ["7"],
            "exclude_main": ["0"],
            "odd_min": 1,
            "odd_max": 3,
            "sum_min": 8,
            "sum_max": 24,
            "span_min": 1,
            "span_max": 9,
        },
    )
    assert varied["lottery_type"] == "fc3d"
    for rec in varied["recommendations"]:
        nums = _ints(rec["main"])
        assert len(nums) == 3
        assert 7 in nums
        assert 0 not in nums
        assert 1 <= _odd(nums) <= 3
        assert 8 <= _sum(nums) <= 24
        assert 1 <= _span(nums) <= 9


def test_qxc_special_constraints(db):
    body = generate(
        db,
        "qxc",
        "random",
        count=2,
        constraints={"include_special": ["14"], "exclude_special": ["0"], "exclude_main": ["9"]},
    )
    for rec in body["recommendations"]:
        assert rec["special"] == ["14"]
        assert "9" not in rec["main"]
        assert len(rec["main"]) == 6


def test_weighted_strategy_retries_until_match(db, monkeypatch):
    queued = [
        ["01", "02", "03", "04", "05", "06"],
        ["08"],
        ["02", "09", "16", "23", "30", "33"],
        ["09"],
    ]

    def fake_pick(_pool, _weights, _k):
        return queued.pop(0)

    monkeypatch.setattr("app.services.predict._pick", fake_pick)
    body = generate(
        db,
        "ssq",
        "hot",
        count=1,
        constraints={"sum_min": 100, "exclude_main": ["01"]},
    )
    rec = body["recommendations"][0]
    assert rec["main"] == ["02", "09", "16", "23", "30", "33"]
    assert rec["special"] == ["09"]
    assert queued == []
    assert "杀号 01" in rec["constraint_summary"]
    assert "和值 113" in rec["constraint_summary"]


def test_strategies_without_constraints_stay_field_compatible(db):
    _seed_ssq(db)
    for strategy in ("hot", "cold", "hybrid", "random"):
        body = generate(db, "ssq", strategy, count=1)
        assert body["strategy"] == strategy
        assert "constraints" not in body
        assert set(body["recommendations"][0]) == {"main", "special"}


@pytest.mark.parametrize(
    "constraints",
    [
        {"include_main": ["01"], "exclude_main": ["1"]},
        {"odd_count": 7},
        {"sum_min": 500},
        {"span_max": 2},
        {"include_main": ["01", "02", "03", "04", "05", "06", "07"]},
        {"odd_min": 5, "odd_max": 2},
        {"max_consecutive": 1, "include_main": ["01", "02", "03"]},
        {"zone_counts": [6, 0, 1]},
        {"big_count": 9},
    ],
)
def test_impossible_constraints_return_400(client, constraints):
    response = client.post(
        "/api/predict",
        json={"lottery_type": "ssq", "strategy": "random", "count": 1, "constraints": constraints},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert isinstance(detail, str)
    assert any("\u4e00" <= char <= "\u9fff" for char in detail)


def test_digit_rules_reject_positional_overflow_and_consecutive(client):
    odd = client.post(
        "/api/predict",
        json={"lottery_type": "fc3d", "strategy": "hot", "count": 1, "constraints": {"odd_count": 4}},
    )
    assert odd.status_code == 400
    assert "奇" in odd.json()["detail"]

    run = client.post(
        "/api/predict",
        json={"lottery_type": "pl5", "strategy": "random", "count": 1, "constraints": {"max_consecutive": 2}},
    )
    assert run.status_code == 400
    assert "连号" in run.json()["detail"]


def test_attempt_cap_does_not_infinite_loop(db, monkeypatch):
    calls = {"n": 0}

    def fake_choice(_pool):
        calls["n"] += 1
        return "0"

    monkeypatch.setattr("app.services.predict.random.choice", fake_choice)
    with pytest.raises(ValueError, match="限定次数"):
        generate(
            db,
            "fc3d",
            "random",
            count=1,
            constraints={"sum_min": 20, "sum_max": 27},
            max_attempts=5,
        )
    assert calls["n"] == 15

    def refuse(*_args, **_kwargs):
        raise AssertionError("达到次数上限前不应再抽样")

    monkeypatch.setattr("app.services.predict.random.sample", refuse)
    with pytest.raises(ValueError, match="限定次数"):
        generate(
            db,
            "ssq",
            "random",
            count=1,
            constraints={"sum_min": 90, "sum_max": 110},
            max_attempts=0,
        )


def test_pulse_rejects_constraints_and_stays_unchanged_without_them(client, db):
    _seed_ssq(db)
    blocked = client.post(
        "/api/predict",
        json={"lottery_type": "ssq", "strategy": "pulse", "count": 1, "constraints": {"odd_count": 3}},
    )
    assert blocked.status_code == 400
    assert "脉动" in blocked.json()["detail"]

    plain = client.post("/api/predict", json={"lottery_type": "ssq", "strategy": "pulse", "count": 1})
    assert plain.status_code == 200
    body = plain.json()
    assert body["strategy"] == "pulse"
    assert "constraints" not in body
    assert "constraint_summary" not in body["recommendations"][0]
    assert "score" in body["recommendations"][0]


def test_openapi_documents_constraints(client):
    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    schemas = spec.json()["components"]["schemas"]
    predict_in = schemas["PredictIn"]["properties"]
    assert "constraints" in predict_in
    ref = predict_in["constraints"]["anyOf"][0]["$ref"]
    name = ref.rsplit("/", 1)[-1]
    fields = schemas[name]["properties"]
    for key in (
        "include_main",
        "exclude_main",
        "include_special",
        "exclude_special",
        "odd_count",
        "odd_min",
        "odd_max",
        "sum_min",
        "sum_max",
        "span_min",
        "span_max",
        "max_consecutive",
        "zone_counts",
        "big_count",
        "big_min",
        "big_max",
    ):
        assert key in fields
    description = schemas[name].get("description", "")
    assert "数字彩" in description
    assert "乐透" in description or "集合" in description
