"""质合脉动：主号质数个数的历史分布，以及短窗相对长窗的升降。

乐透按主号集合数质数，特别号不计入；至少两个特别号才另计 special 质数个数。
数字彩按整注各位数字数质数，1 是质数，0 是合数，不绕圈。短窗、长窗用实际有的期数求平均，
缺口不当成质数个数 0。只读本地开奖，不改形态统计、奇偶脉动和其他分析接口的返回形状。
"""
from __future__ import annotations

import json

import pytest

from app.models import Draw
from app.services.prime import (
    COMMON_LIMIT,
    DIGIT_NOTE,
    DISCLAIMER,
    SET_NOTE,
    THRESHOLD,
    is_prime,
    prime_summary,
    score_prime,
)
from app.services.shape import shape_stats

GET_KEYS = {
    "lottery_type",
    "mode",
    "basis",
    "sample_size",
    "short",
    "long",
    "threshold",
    "distribution",
    "common",
    "mean",
    "median",
    "short_avg",
    "long_avg",
    "pulse",
    "drift",
    "note",
    "latest_draw",
    "special",
    "data_status",
    "disclaimer",
}

POST_KEYS = GET_KEYS | {"query", "ticket", "special_ticket"}

BUCKET_KEYS = {"prime_count", "count", "rate"}
RATIO_KEYS = {"prime_count", "composite_count", "ratio", "count", "rate"}
TICKET_KEYS = {
    "prime_count",
    "composite_count",
    "imbalance",
    "percentile",
    "typicality",
    "rarity",
    "alignment",
    "note",
}
LATEST_KEYS = {
    "issue",
    "draw_date",
    "main",
    "special",
    "prime_count",
    "composite_count",
    "special_prime_count",
    "special_composite_count",
}
SPECIAL_KEYS = {
    "label",
    "sample_size",
    "distribution",
    "common",
    "mean",
    "median",
    "short_avg",
    "long_avg",
    "pulse",
    "drift",
}

SSQ_PRIMES = {1, 2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}
QLC_PRIMES = {1, 2, 3, 5, 7, 11, 13, 17, 19, 23, 29}
KL8_EXTRA = {37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79}


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


def _bucket(rows, prime_count):
    found = [item for item in rows if item["prime_count"] == prime_count]
    assert len(found) == 1
    return found[0]


def _empty_ticket():
    return {
        "prime_count": None,
        "composite_count": None,
        "imbalance": None,
        "percentile": None,
        "typicality": None,
        "rarity": None,
        "alignment": None,
        "note": "",
    }


def test_one_is_prime_and_zero_is_composite():
    assert THRESHOLD == 0.5
    assert COMMON_LIMIT == 8
    assert DISCLAIMER == "质合脉动看主号质数个数的历史分布与短窗升降，仅供娱乐，不构成投注建议。"
    assert is_prime(1) is True
    assert is_prime(0) is False
    assert is_prime(2) is True
    assert is_prime(4) is False
    assert is_prime(9) is False
    assert is_prime(25) is False
    assert is_prime(35) is False
    assert is_prime(49) is False
    assert is_prime(77) is False
    assert is_prime(79) is True
    assert is_prime(80) is False
    assert {n for n in range(1, 34) if is_prime(n)} == SSQ_PRIMES
    assert {n for n in range(1, 36) if is_prime(n)} == SSQ_PRIMES
    assert {n for n in range(1, 31) if is_prime(n)} == QLC_PRIMES
    assert {n for n in range(1, 81) if is_prime(n)} == SSQ_PRIMES | KL8_EXTRA
    assert {n for n in range(10) if is_prime(n)} == {1, 2, 3, 5, 7}


def test_set_prime_count_ignores_special_and_fills_gaps(db):
    _draw(db, "ssq", "2026005", ["01", "08", "09"], ["16"], source="crawl", draw_date="2026-01-09")
    _draw(db, "ssq", "2026004", ["02", "04"], ["03"])
    _draw(db, "ssq", "2026003", [], ["01"])
    _draw(db, "ssq", "2026002", ["05", "05", "07"], ["02"])
    _draw(db, "ssq", "2026001", ["x", "03", "06"], ["04"])

    body = prime_summary(db, "ssq", limit=80, short=10, long=50)
    assert set(body) == GET_KEYS
    assert body["lottery_type"] == "ssq"
    assert body["mode"] == "set"
    assert body["basis"] == "main"
    assert body["sample_size"] == 4
    assert body["short"] == 10
    assert body["long"] == 50
    assert body["threshold"] == 0.5
    assert body["data_status"] == "mixed"
    assert body["disclaimer"] == DISCLAIMER
    assert "仅供娱乐" in body["disclaimer"]
    assert "不构成投注建议" in body["disclaimer"]
    assert body["note"] == SET_NOTE
    assert body["special"] is None
    assert body["mean"] == 1.25
    assert body["median"] == 1.0
    assert body["short_avg"] == 1.25
    assert body["long_avg"] == 1.25
    assert body["pulse"] == 0.0
    assert body["drift"] == "flat"
    assert body["latest_draw"] == {
        "issue": "2026005",
        "draw_date": "2026-01-09",
        "main": ["01", "08", "09"],
        "special": ["16"],
        "prime_count": 1,
        "composite_count": 2,
        "special_prime_count": None,
        "special_composite_count": None,
    }
    assert set(body["latest_draw"]) == LATEST_KEYS

    distribution = body["distribution"]
    assert [item["prime_count"] for item in distribution] == [1, 2]
    assert all(set(item) == BUCKET_KEYS for item in distribution)
    assert _bucket(distribution, 1) == {"prime_count": 1, "count": 3, "rate": 0.75}
    assert _bucket(distribution, 2) == {"prime_count": 2, "count": 1, "rate": 0.25}
    assert body["common"] == [
        {"prime_count": 1, "composite_count": 1, "ratio": "1质1合", "count": 2, "rate": 0.5},
        {"prime_count": 1, "composite_count": 2, "ratio": "1质2合", "count": 1, "rate": 0.25},
        {"prime_count": 2, "composite_count": 0, "ratio": "2质0合", "count": 1, "rate": 0.25},
    ]
    assert all(set(item) == RATIO_KEYS for item in body["common"])


def test_pulse_rises_when_recent_prime_counts_are_higher(db):
    for index, balls in enumerate([["01", "02", "03"]] * 5 + [["04", "06", "08"]] * 5):
        _draw(db, "ssq", f"{2026010 - index:07d}", balls, ["08"])

    body = prime_summary(db, "ssq", short=5, long=10)
    assert body["sample_size"] == 10
    assert body["short_avg"] == 3.0
    assert body["long_avg"] == 1.5
    assert body["pulse"] == 1.5
    assert body["drift"] == "rising"
    assert body["mean"] == 1.5
    assert body["median"] == 1.5
    assert body["special"] is None
    assert _bucket(body["distribution"], 0)["count"] == 5
    assert _bucket(body["distribution"], 3)["count"] == 5
    assert _bucket(body["distribution"], 1)["count"] == 0
    assert _bucket(body["distribution"], 2)["count"] == 0
    assert body["common"][0]["ratio"] == "0质3合"
    assert body["common"][1]["ratio"] == "3质0合"


def test_pulse_threshold_edges(db):
    for index, prime_count in enumerate([4, 4, 4, 4, 4, 2]):
        primes = ["01", "02", "03", "05"][:prime_count]
        composites = ["04", "06", "08", "09"]
        balls = primes + composites[: 2 if prime_count == 4 else 2]
        _draw(db, "ssq", f"{2026106 - index}", balls)
    flat = prime_summary(db, "ssq", short=5, long=20)
    assert flat["sample_size"] == 6
    assert flat["short_avg"] == 4.0
    assert flat["long_avg"] == 3.6667
    assert flat["pulse"] == 0.3333
    assert flat["drift"] == "flat"

    for index, prime_count in enumerate([3, 3, 3, 3, 3, 0]):
        balls = ["1", "2", "3"] if prime_count else ["0", "4", "6"]
        _draw(db, "fc3d", f"{2026206 - index}", balls)
    rising = prime_summary(db, "fc3d", short=5, long=20)
    assert rising["basis"] == "digits"
    assert rising["short_avg"] == 3.0
    assert rising["long_avg"] == 2.5
    assert rising["pulse"] == 0.5
    assert rising["drift"] == "rising"

    for index, prime_count in enumerate([0, 0, 0, 0, 0, 3]):
        balls = ["0", "4", "6"] if prime_count == 0 else ["1", "2", "3"]
        _draw(db, "pl3", f"{2026306 - index}", balls)
    falling = prime_summary(db, "pl3", short=5, long=20)
    assert falling["short_avg"] == 0.0
    assert falling["long_avg"] == 0.5
    assert falling["pulse"] == -0.5
    assert falling["drift"] == "falling"


def test_dlt_special_prime_count_stays_out_of_main(db):
    _draw(db, "dlt", "2026003", ["01", "05", "20"], ["01", "12"], draw_date="2026-02-03")
    _draw(db, "dlt", "2026002", ["03", "04"], ["02", "03"])
    _draw(db, "dlt", "2026001", ["08", "10"], ["05"])
    _draw(db, "dlt", "2026000", ["01", "02"], ["03", "03"])

    body = prime_summary(db, "dlt", short=5, long=20)
    assert body["basis"] == "main"
    assert body["sample_size"] == 4
    assert body["mean"] == 1.25
    assert body["median"] == 1.5
    assert body["short_avg"] == 1.25
    assert body["latest_draw"]["prime_count"] == 2
    assert body["latest_draw"]["composite_count"] == 1
    assert body["latest_draw"]["special_prime_count"] == 1
    assert body["latest_draw"]["special_composite_count"] == 1
    assert body["latest_draw"]["special"] == ["01", "12"]
    assert _bucket(body["distribution"], 2)["count"] == 2
    assert _bucket(body["distribution"], 1)["count"] == 1
    assert _bucket(body["distribution"], 0)["count"] == 1

    special = body["special"]
    assert set(special) == SPECIAL_KEYS
    assert special["label"] == "后区"
    assert special["sample_size"] == 2
    assert special["mean"] == 1.5
    assert special["median"] == 1.5
    assert special["short_avg"] == 1.5
    assert special["long_avg"] == 1.5
    assert special["pulse"] == 0.0
    assert special["drift"] == "flat"
    assert special["distribution"] == [
        {"prime_count": 1, "count": 1, "rate": 0.5},
        {"prime_count": 2, "count": 1, "rate": 0.5},
    ]
    assert special["common"] == [
        {"prime_count": 1, "composite_count": 1, "ratio": "1质1合", "count": 1, "rate": 0.5},
        {"prime_count": 2, "composite_count": 0, "ratio": "2质0合", "count": 1, "rate": 0.5},
    ]

    _draw(db, "qlc", "2026001", ["01", "03", "09"], ["04"])
    single = prime_summary(db, "qlc")
    assert single["special"] is None
    assert single["latest_draw"]["prime_count"] == 2
    assert single["latest_draw"]["composite_count"] == 1
    assert single["latest_draw"]["special_prime_count"] is None
    assert single["latest_draw"]["special_composite_count"] is None


def test_digit_prime_count_treats_zero_composite_and_one_prime(db):
    _draw(db, "fc3d", "2026004", ["0", "9", "1"], draw_date="2026-03-04")
    _draw(db, "fc3d", "2026003", ["1", "2", "3"])
    _draw(db, "fc3d", "2026002", ["5", "5", "5"])
    _draw(db, "fc3d", "2026001", ["9", "0", "0"])
    _draw(db, "fc3d", "2026000", [], ["1"])
    _draw(db, "qxc", "2026008", ["1", "2", "3", "4", "5", "9"], ["14"])
    _draw(db, "pl5", "2026008", ["0", "1", "2", "3", "4"])

    body = prime_summary(db, "fc3d")
    assert body["lottery_type"] == "fc3d"
    assert body["mode"] == "digit"
    assert body["basis"] == "digits"
    assert body["note"] == DIGIT_NOTE
    assert "0" in body["note"] and "1" in body["note"]
    assert body["sample_size"] == 4
    assert body["special"] is None
    assert body["mean"] == 1.75
    assert body["median"] == 2.0
    assert body["short_avg"] == 1.75
    assert body["drift"] == "flat"
    assert body["latest_draw"]["prime_count"] == 1
    assert body["latest_draw"]["composite_count"] == 2
    assert body["latest_draw"]["main"] == ["0", "9", "1"]
    assert body["latest_draw"]["special_prime_count"] is None
    assert _bucket(body["distribution"], 0) == {"prime_count": 0, "count": 1, "rate": 0.25}
    assert _bucket(body["distribution"], 1) == {"prime_count": 1, "count": 1, "rate": 0.25}
    assert _bucket(body["distribution"], 2) == {"prime_count": 2, "count": 0, "rate": 0.0}
    assert _bucket(body["distribution"], 3) == {"prime_count": 3, "count": 2, "rate": 0.5}
    assert body["common"][0] == {
        "prime_count": 3,
        "composite_count": 0,
        "ratio": "3质0合",
        "count": 2,
        "rate": 0.5,
    }

    qxc = prime_summary(db, "qxc")
    assert qxc["basis"] == "digits"
    assert qxc["special"] is None
    assert qxc["latest_draw"]["prime_count"] == 4
    assert qxc["latest_draw"]["composite_count"] == 2
    assert qxc["latest_draw"]["special"] == ["14"]
    assert qxc["latest_draw"]["special_prime_count"] is None
    assert qxc["distribution"] == [{"prime_count": 4, "count": 1, "rate": 1.0}]

    pl5 = prime_summary(db, "pl5")
    assert pl5["basis"] == "digits"
    assert pl5["latest_draw"]["prime_count"] == 3
    assert pl5["latest_draw"]["composite_count"] == 2
    assert pl5["latest_draw"]["main"] == ["0", "1", "2", "3", "4"]


def test_score_aligns_with_pulse_and_marks_rarity(db):
    for index, balls in enumerate([["01", "02", "03"]] * 5 + [["04", "06", "08"]] * 5):
        _draw(db, "ssq", f"{2026010 - index:07d}", balls, ["08"])

    wide = score_prime(db, "ssq", ["01", "02", "03"], ["08"], short=5, long=10)
    assert set(wide) == POST_KEYS
    assert wide["query"] == {"main": ["01", "02", "03"], "special": ["08"]}
    assert set(wide["ticket"]) == TICKET_KEYS
    assert wide["ticket"]["prime_count"] == 3
    assert wide["ticket"]["composite_count"] == 0
    assert wide["ticket"]["imbalance"] == 3
    assert wide["ticket"]["percentile"] == 1.0
    assert wide["ticket"]["typicality"] == 0.5
    assert wide["ticket"]["rarity"] == "common"
    assert wide["ticket"]["alignment"] == "aligned"
    assert wide["ticket"]["note"] == (
        "质数个数 3（3质0合），历史分位 100%，出现率 50%，常见，短窗 3 比长窗 1.5 走高，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert wide["special_ticket"] == _empty_ticket()
    assert wide["drift"] == "rising"

    narrow = score_prime(db, "ssq", "04 06 08", special="08", short=5, long=10)
    assert narrow["ticket"]["prime_count"] == 0
    assert narrow["ticket"]["composite_count"] == 3
    assert narrow["ticket"]["imbalance"] == 3
    assert narrow["ticket"]["percentile"] == 0.5
    assert narrow["ticket"]["typicality"] == 0.5
    assert narrow["ticket"]["rarity"] == "common"
    assert narrow["ticket"]["alignment"] == "against"
    assert "走高" in narrow["ticket"]["note"]
    assert "反向" in narrow["ticket"]["note"]
    assert "仅供娱乐" in narrow["ticket"]["note"]

    rare = score_prime(db, "ssq", ["01", "02", "03", "05", "07", "11"], ["08"], short=5, long=10)
    assert rare["ticket"]["prime_count"] == 6
    assert rare["ticket"]["composite_count"] == 0
    assert rare["ticket"]["imbalance"] == 6
    assert rare["ticket"]["percentile"] == 1.0
    assert rare["ticket"]["typicality"] == 0.0
    assert rare["ticket"]["rarity"] == "rare"
    assert rare["ticket"]["alignment"] == "aligned"
    assert "少见" in rare["ticket"]["note"]

    unseen_history = score_prime(db, "ssq", ["04", "06", "08"], ["01", "05"], short=5, long=10)
    assert unseen_history["ticket"]["prime_count"] == 0
    assert unseen_history["special_ticket"]["prime_count"] == 2
    assert unseen_history["special_ticket"]["composite_count"] == 0
    assert unseen_history["special_ticket"]["imbalance"] == 2
    assert unseen_history["special_ticket"]["percentile"] is None
    assert unseen_history["special_ticket"]["alignment"] is None
    assert unseen_history["special_ticket"]["note"] == (
        "质数个数 2（2质0合），还没有历史可对照。仅供娱乐，不构成投注建议。"
    )

    for index, pair in enumerate([(["04", "06"], ["04", "06"])] * 5 + [(["01", "02", "03"], ["01", "02"])] * 5):
        main, special = pair
        _draw(db, "dlt", f"{2027010 - index:07d}", main, special)

    tight = score_prime(db, "dlt", ["04", "06"], ["04", "06"], short=5, long=10)
    assert tight["drift"] == "falling"
    assert tight["ticket"]["prime_count"] == 0
    assert tight["ticket"]["composite_count"] == 2
    assert tight["ticket"]["alignment"] == "aligned"
    assert "走低" in tight["ticket"]["note"]
    assert "同向" in tight["ticket"]["note"]
    assert tight["special"]["drift"] == "falling"
    assert tight["special"]["short_avg"] == 0.0
    assert tight["special"]["long_avg"] == 1.0
    assert tight["special_ticket"]["prime_count"] == 0
    assert tight["special_ticket"]["composite_count"] == 2
    assert tight["special_ticket"]["imbalance"] == 2
    assert tight["special_ticket"]["alignment"] == "aligned"
    assert tight["special_ticket"]["rarity"] == "common"
    assert "不构成投注建议" in tight["special_ticket"]["note"]

    wide_back = score_prime(db, "dlt", ["01", "02", "03"], ["01", "02"], short=5, long=10)
    assert wide_back["ticket"]["prime_count"] == 3
    assert wide_back["ticket"]["alignment"] == "against"
    assert wide_back["special_ticket"]["prime_count"] == 2
    assert wide_back["special_ticket"]["alignment"] == "against"
    assert wide_back["special_ticket"]["percentile"] == 1.0
    assert wide_back["special_ticket"]["typicality"] == 0.5

    one_back = score_prime(db, "dlt", ["04", "06"], ["03"], short=5, long=10)
    assert one_back["special_ticket"] == _empty_ticket()


def test_digit_score_uses_whole_ticket_not_wrap(db):
    _draw(db, "fc3d", "2026004", ["0", "9", "1"])
    _draw(db, "fc3d", "2026003", ["1", "2", "3"])
    _draw(db, "fc3d", "2026002", ["5", "5", "5"])
    _draw(db, "fc3d", "2026001", ["9", "0", "0"])

    body = score_prime(db, "fc3d", ["0", "9", "1"])
    assert body["basis"] == "digits"
    assert body["ticket"]["prime_count"] == 1
    assert body["ticket"]["composite_count"] == 2
    assert body["ticket"]["imbalance"] == 1
    assert body["ticket"]["percentile"] == 0.5
    assert body["ticket"]["typicality"] == 0.25
    assert body["ticket"]["rarity"] == "typical"
    assert body["ticket"]["alignment"] == "neutral"
    assert body["ticket"]["note"] == (
        "质数个数 1（1质2合），历史分位 50%，出现率 25%，居中，短窗 1.75 和长窗 1.75 差不多，没有明显顺逆。仅供娱乐，不构成投注建议。"
    )
    assert body["special_ticket"] == _empty_ticket()

    low = score_prime(db, "pl3", [1, 3, 5])
    assert low["sample_size"] == 0
    assert low["ticket"]["prime_count"] == 3
    assert low["ticket"]["composite_count"] == 0
    assert low["ticket"]["imbalance"] == 3
    assert low["ticket"]["percentile"] is None
    assert low["ticket"]["rarity"] is None
    assert low["ticket"]["alignment"] is None
    assert low["ticket"]["note"] == "质数个数 3（3质0合），还没有历史可对照。仅供娱乐，不构成投注建议。"

    for index in range(3):
        _draw(db, "fc3d", f"202600{7 - index}", ["1", "1", "1"])
    mid = score_prime(db, "fc3d", ["0", "9", "1"])
    assert mid["ticket"]["prime_count"] == 1
    assert mid["ticket"]["percentile"] == 0.2857
    assert mid["ticket"]["typicality"] == 0.1429
    assert mid["ticket"]["rarity"] == "typical"
    assert mid["ticket"]["alignment"] == "neutral"
    assert "居中" in mid["ticket"]["note"]


def test_empty_history_parameter_clamp_and_common_cap(db):
    empty = prime_summary(db, "kl8", limit="no", short=None, long="bad")
    assert empty["lottery_type"] == "kl8"
    assert empty["sample_size"] == 0
    assert empty["short"] == 10
    assert empty["long"] == 50
    assert empty["distribution"] == []
    assert empty["common"] == []
    assert empty["mean"] is None
    assert empty["median"] is None
    assert empty["short_avg"] is None
    assert empty["long_avg"] is None
    assert empty["pulse"] is None
    assert empty["drift"] is None
    assert empty["latest_draw"] is None
    assert empty["special"] is None
    assert empty["data_status"] == "seed"
    assert empty["basis"] == "main"

    scored = score_prime(db, "kl8", ["01", "05"])
    assert scored["ticket"]["prime_count"] == 2
    assert scored["ticket"]["composite_count"] == 0
    assert scored["ticket"]["imbalance"] == 2
    assert scored["ticket"]["percentile"] is None
    assert scored["ticket"]["note"] == "质数个数 2（2质0合），还没有历史可对照。仅供娱乐，不构成投注建议。"
    assert scored["special_ticket"] == _empty_ticket()

    for total in range(1, 7):
        _draw(db, "kl8", f"202600{total}", [f"{n:02d}" for n in range(1, total + 1)])
    clamped = prime_summary(db, "kl8", limit=1, short=1, long=1)
    assert clamped["short"] == 5
    assert clamped["long"] == 20
    assert clamped["sample_size"] == 5
    assert clamped["latest_draw"]["prime_count"] == 4
    assert clamped["latest_draw"]["composite_count"] == 2
    assert clamped["mean"] == 3.2

    opened = prime_summary(db, "kl8", short=30, long=20)
    assert opened["short"] == 30
    assert opened["long"] == 31
    assert opened["sample_size"] == 6
    assert opened["mean"] == 2.8333

    primes = [1, 2, 3, 5, 7, 11, 13, 17, 19]
    for total in range(1, 10):
        _draw(db, "ssq", f"202610{total}", [f"{n:02d}" for n in primes[:total]])
    capped = prime_summary(db, "ssq")
    assert capped["sample_size"] == 9
    assert len(capped["common"]) == 8
    assert [item["ratio"] for item in capped["common"]] == [f"{n}质0合" for n in range(1, 9)]
    assert all(item["count"] == 1 and item["rate"] == 0.1111 for item in capped["common"])
    assert capped["mean"] == 5.0
    assert capped["median"] == 5

    with pytest.raises(ValueError, match="未知彩种"):
        prime_summary(db, "nope")
    with pytest.raises(ValueError, match="未知彩种"):
        score_prime(db, "nope", ["01"])
    with pytest.raises(ValueError):
        score_prime(db, "ssq", ["01", "01", "03", "04", "05", "06"], ["01"])
    with pytest.raises(ValueError):
        score_prime(db, "fc3d", ["1", "2"])
    with pytest.raises(ValueError):
        score_prime(db, "kl8", ["01", "02"], ["03"])


def test_prime_endpoints_bounds_and_old_contracts(client, db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "10", "20", "30"], ["16"], draw_date="2026-04-01")
    _draw(db, "ssq", "2026002", ["05", "07", "09", "11", "13", "15"], ["02"], source="crawl", draw_date="2026-04-03")

    res = client.get("/api/analysis/ssq/prime")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == GET_KEYS
    assert body["sample_size"] == 2
    assert body["short"] == 10
    assert body["long"] == 50
    assert body["basis"] == "main"
    assert body["disclaimer"] == DISCLAIMER
    assert body["data_status"] == "mixed"
    assert body["latest_draw"]["prime_count"] == 4
    assert body["latest_draw"]["composite_count"] == 2
    assert body["mean"] == 3.5
    assert body["special"] is None
    assert "sum" not in body
    assert "odd_count" not in body
    assert body["common"][0]["ratio"] == "3质3合"

    custom = client.get("/api/analysis/ssq/prime", params={"limit": 80, "short": 5, "long": 20})
    assert custom.status_code == 200
    assert custom.json()["short"] == 5
    assert custom.json()["long"] == 20

    widened = client.get("/api/analysis/ssq/prime", params={"short": 30, "long": 20})
    assert widened.status_code == 200
    assert widened.json()["short"] == 30
    assert widened.json()["long"] == 31

    assert client.get("/api/analysis/ssq/prime", params={"limit": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/prime", params={"limit": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/prime", params={"short": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/prime", params={"short": 31}).status_code == 422
    assert client.get("/api/analysis/ssq/prime", params={"long": 19}).status_code == 422
    assert client.get("/api/analysis/ssq/prime", params={"long": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/prime", params={"limit": 5, "short": 5, "long": 20}).status_code == 200
    assert client.get("/api/analysis/ssq/prime", params={"limit": 200, "short": 30, "long": 200}).status_code == 200

    unknown = client.get("/api/analysis/nope/prime")
    assert unknown.status_code == 400
    assert "未知彩种" in unknown.json()["detail"]

    empty = client.get("/api/analysis/kl8/prime")
    assert empty.status_code == 200
    assert empty.json()["sample_size"] == 0
    assert empty.json()["latest_draw"] is None
    assert empty.json()["distribution"] == []
    assert empty.json()["drift"] is None

    alias = client.get("/api/analysis/3d/prime")
    assert alias.status_code == 200
    assert alias.json()["lottery_type"] == "fc3d"
    assert alias.json()["mode"] == "digit"
    assert alias.json()["basis"] == "digits"

    posted = client.post(
        "/api/analysis/ssq/prime/score",
        json={"main": "01 02 03 10 20 30", "special": "16", "limit": 80, "short": 10, "long": 50},
    )
    assert posted.status_code == 200, posted.text
    scored = posted.json()
    assert set(scored) == POST_KEYS
    assert scored["query"] == {"main": ["01", "02", "03", "10", "20", "30"], "special": ["16"]}
    assert scored["ticket"]["prime_count"] == 3
    assert scored["ticket"]["composite_count"] == 3
    assert scored["ticket"]["imbalance"] == 0
    assert scored["ticket"]["rarity"] == "common"
    assert scored["ticket"]["alignment"] == "neutral"
    assert scored["special_ticket"]["prime_count"] is None
    assert "仅供娱乐" in scored["ticket"]["note"]

    spaced = client.post("/api/analysis/3d/prime/score", json={"main": ["0", "9", "1"], "short": 5, "long": 20})
    assert spaced.status_code == 200
    assert spaced.json()["lottery_type"] == "fc3d"
    assert spaced.json()["ticket"]["prime_count"] == 1
    assert spaced.json()["ticket"]["composite_count"] == 2
    assert spaced.json()["mode"] == "digit"

    bad = client.post("/api/analysis/ssq/prime/score", json={"main": ["99"], "special": ["01"]})
    assert bad.status_code == 400
    duplicate = client.post(
        "/api/analysis/ssq/prime/score",
        json={"main": ["01", "01", "03", "04", "05", "06"], "special": ["01"]},
    )
    assert duplicate.status_code == 400
    short = client.post("/api/analysis/fc3d/prime/score", json={"main": ["1", "2"]})
    assert short.status_code == 400
    extra = client.post("/api/analysis/kl8/prime/score", json={"main": ["01", "02"], "special": ["03"]})
    assert extra.status_code == 400
    unknown_post = client.post("/api/analysis/nope/prime/score", json={"main": ["01"]})
    assert unknown_post.status_code == 400
    assert client.post("/api/analysis/ssq/prime/score", json={"main": ["01"], "limit": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/prime/score", json={"main": ["01"], "short": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/prime/score", json={"main": ["01"], "long": 201}).status_code == 422

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
    assert "pulse" not in analysis.json()
    assert "prime_count" not in analysis.json()
    assert "odd_count" not in analysis.json()

    shape = client.get("/api/analysis/ssq/shape")
    assert shape.status_code == 200
    shape_body = shape.json()
    assert "pulse" not in shape_body
    assert "distribution" not in shape_body
    assert "drift" not in shape_body
    assert "prime_count" not in shape_body
    assert "odd_count" not in shape_body
    direct = shape_stats(db, "ssq", limit=50)
    assert "prime_count" not in direct

    parity = client.get("/api/analysis/ssq/parity")
    assert parity.status_code == 200
    assert parity.json()["latest_draw"]["odd_count"] == 6
    assert "prime_count" not in parity.json()
    assert "prime_count" not in parity.json()["latest_draw"]

    summed = client.get("/api/analysis/ssq/sum")
    assert summed.status_code == 200
    assert "prime_count" not in summed.json()
    assert "prime_count" not in summed.json()["latest_draw"]
