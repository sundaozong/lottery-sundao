"""连号簇脉动：主号连号簇最长长度的历史分布，以及短窗相对长窗的升降。

乐透按主号集合，相邻差为 1 且长度至少为 2 算一簇；没有连号时最长簇记为 1。
多个特别号才另计 special，不并进主号。数字彩按位从左到右，0 与 9 不绕圈。
短窗、长窗用实际有的期数求平均，缺口不当成最长簇 0。主打分看最长簇。
只读本地开奖，不改其他分析接口的返回形状。
"""
from __future__ import annotations

import json

import pytest

from app.models import Draw
from app.services.cluster import (
    COMMON_LIMIT,
    DIGIT_NOTE,
    DISCLAIMER,
    SET_NOTE,
    THRESHOLD,
    cluster_summary,
    score_cluster,
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
    "cluster_counts",
    "note",
    "latest_draw",
    "special",
    "data_status",
    "disclaimer",
}

POST_KEYS = GET_KEYS | {"query", "ticket", "special_ticket"}

BUCKET_KEYS = {"max_len", "count", "rate"}
COUNT_BUCKET_KEYS = {"clusters", "count", "rate"}
COUNT_KEYS = {
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
TICKET_KEYS = {"max_len", "clusters", "percentile", "typicality", "rarity", "alignment", "note"}
LATEST_KEYS = {
    "issue",
    "draw_date",
    "main",
    "special",
    "max_len",
    "clusters",
    "special_max_len",
    "special_clusters",
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
    "cluster_counts",
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


def _bucket(rows, max_len, key="max_len"):
    found = [item for item in rows if item[key] == max_len]
    assert len(found) == 1
    return found[0]


def _nums(length: int) -> list[str]:
    if length <= 1:
        return ["01", "03"]
    return [f"{number:02d}" for number in range(1, length + 1)]


def _empty_ticket():
    return {
        "max_len": None,
        "clusters": None,
        "percentile": None,
        "typicality": None,
        "rarity": None,
        "alignment": None,
        "note": "",
    }


def test_threshold_and_common_limit():
    assert THRESHOLD == 0.5
    assert COMMON_LIMIT == 8


def test_set_cluster_skips_blank_and_ignores_single_special(db):
    _draw(db, "ssq", "2026005", ["01", "08", "09"], ["16"], source="crawl", draw_date="2026-01-09")
    _draw(db, "ssq", "2026004", ["02", "04"], ["03"])
    _draw(db, "ssq", "2026003", [], ["01"])
    _draw(db, "ssq", "2026002", ["05", "05", "07"], ["02"])
    _draw(db, "ssq", "2026001", ["x", "03", "06"], ["04"])

    body = cluster_summary(db, "ssq", limit=80, short=10, long=50)
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
    assert body["median"] == 1
    assert body["short_avg"] == 1.25
    assert body["long_avg"] == 1.25
    assert body["pulse"] == 0.0
    assert body["drift"] == "flat"
    assert body["latest_draw"] == {
        "issue": "2026005",
        "draw_date": "2026-01-09",
        "main": ["01", "08", "09"],
        "special": ["16"],
        "max_len": 2,
        "clusters": 1,
        "special_max_len": None,
        "special_clusters": None,
    }
    assert set(body["latest_draw"]) == LATEST_KEYS

    distribution = body["distribution"]
    assert [item["max_len"] for item in distribution] == [1, 2]
    assert all(set(item) == BUCKET_KEYS for item in distribution)
    assert _bucket(distribution, 1) == {"max_len": 1, "count": 3, "rate": 0.75}
    assert _bucket(distribution, 2) == {"max_len": 2, "count": 1, "rate": 0.25}
    assert body["common"] == [
        {"max_len": 1, "count": 3, "rate": 0.75},
        {"max_len": 2, "count": 1, "rate": 0.25},
    ]

    counts = body["cluster_counts"]
    assert set(counts) == COUNT_KEYS
    assert counts["sample_size"] == 4
    assert counts["mean"] == 0.25
    assert counts["median"] == 0
    assert counts["short_avg"] == 0.25
    assert counts["long_avg"] == 0.25
    assert counts["pulse"] == 0.0
    assert counts["drift"] == "flat"
    assert all(set(item) == COUNT_BUCKET_KEYS for item in counts["distribution"])
    assert _bucket(counts["distribution"], 0, "clusters") == {"clusters": 0, "count": 3, "rate": 0.75}
    assert _bucket(counts["distribution"], 1, "clusters") == {"clusters": 1, "count": 1, "rate": 0.25}


def test_multi_cluster_is_not_pair_count(db):
    _draw(db, "ssq", "2026012", ["01", "02", "04", "05", "06", "08"])
    _draw(db, "ssq", "2026011", ["01", "03", "05", "07", "09", "11"])

    body = cluster_summary(db, "ssq")
    assert body["latest_draw"]["max_len"] == 3
    assert body["latest_draw"]["clusters"] == 2
    assert body["mean"] == 2.0
    assert body["median"] == 2.0
    assert [item["max_len"] for item in body["distribution"]] == [1, 2, 3]
    assert _bucket(body["distribution"], 2)["count"] == 0
    assert body["cluster_counts"]["mean"] == 1.0
    assert _bucket(body["cluster_counts"]["distribution"], 0, "clusters")["count"] == 1
    assert _bucket(body["cluster_counts"]["distribution"], 2, "clusters")["count"] == 1

    shape = shape_stats(db, "ssq")
    assert set(shape["consecutive"]) == {"draws_with", "draws_without", "avg_pairs"}
    assert shape["consecutive"]["avg_pairs"] == 1.5
    assert "max_len" not in shape
    assert "pulse" not in shape


def test_pulse_rises_when_recent_clusters_are_longer(db):
    for index, length in enumerate([4, 4, 4, 4, 4, 1, 1, 1, 1, 1]):
        _draw(db, "ssq", f"{2026010 - index:07d}", _nums(length), ["08"])

    body = cluster_summary(db, "ssq", short=5, long=10)
    assert body["sample_size"] == 10
    assert body["short_avg"] == 4.0
    assert body["long_avg"] == 2.5
    assert body["pulse"] == 1.5
    assert body["drift"] == "rising"
    assert body["mean"] == 2.5
    assert body["median"] == 2.5
    assert body["special"] is None
    assert _bucket(body["distribution"], 1)["count"] == 5
    assert _bucket(body["distribution"], 4)["count"] == 5
    assert _bucket(body["distribution"], 2)["count"] == 0
    assert _bucket(body["distribution"], 3)["count"] == 0
    assert body["common"][0]["max_len"] == 1
    assert body["common"][1]["max_len"] == 4
    assert body["cluster_counts"]["short_avg"] == 1.0
    assert body["cluster_counts"]["long_avg"] == 0.5
    assert body["cluster_counts"]["pulse"] == 0.5
    assert body["cluster_counts"]["drift"] == "rising"


def test_pulse_threshold_edges(db):
    for index, length in enumerate([4, 4, 4, 4, 4, 2]):
        _draw(db, "ssq", f"{2026106 - index}", _nums(length))
    flat = cluster_summary(db, "ssq", short=5, long=20)
    assert flat["sample_size"] == 6
    assert flat["short_avg"] == 4.0
    assert flat["long_avg"] == 3.6667
    assert flat["pulse"] == 0.3333
    assert flat["drift"] == "flat"

    for index, length in enumerate([4, 4, 4, 4, 4, 1]):
        _draw(db, "pl5", f"{2026206 - index}", [str(number) for number in ([1, 2, 3, 4, 6] if length == 4 else [0, 2, 4, 6, 8])])
    rising = cluster_summary(db, "pl5", short=5, long=20)
    assert rising["basis"] == "digits"
    assert rising["mode"] == "digit"
    assert rising["short_avg"] == 4.0
    assert rising["long_avg"] == 3.5
    assert rising["pulse"] == 0.5
    assert rising["drift"] == "rising"
    assert rising["latest_draw"]["max_len"] == 4
    assert rising["latest_draw"]["clusters"] == 1

    for index, length in enumerate([2, 2, 2, 2, 2, 5]):
        nums = ["01", "02"] if length == 2 else ["01", "02", "03", "04", "05"]
        _draw(db, "dlt", f"{2026306 - index}", nums, ["01", "02"])
    falling = cluster_summary(db, "dlt", short=5, long=20)
    assert falling["short_avg"] == 2.0
    assert falling["long_avg"] == 2.5
    assert falling["pulse"] == -0.5
    assert falling["drift"] == "falling"


def test_dlt_special_cluster_stays_out_of_main(db):
    _draw(db, "dlt", "2026003", ["01", "03", "20"], ["01", "02", "03", "04"], draw_date="2026-02-03")
    _draw(db, "dlt", "2026002", ["03", "04", "05", "10", "11"], ["02", "03"])
    _draw(db, "dlt", "2026001", ["08", "10"], ["05"])

    body = cluster_summary(db, "dlt", short=5, long=20)
    assert body["basis"] == "main"
    assert body["sample_size"] == 3
    assert body["mean"] == 1.6667
    assert body["median"] == 1
    assert body["short_avg"] == 1.6667
    assert body["latest_draw"]["max_len"] == 1
    assert body["latest_draw"]["clusters"] == 0
    assert body["latest_draw"]["special_max_len"] == 4
    assert body["latest_draw"]["special_clusters"] == 1
    assert body["latest_draw"]["special"] == ["01", "02", "03", "04"]
    assert _bucket(body["distribution"], 1)["count"] == 2
    assert _bucket(body["distribution"], 2)["count"] == 0
    assert _bucket(body["distribution"], 3)["count"] == 1
    assert 4 not in {item["max_len"] for item in body["distribution"]}

    special = body["special"]
    assert set(special) == SPECIAL_KEYS
    assert special["label"] == "后区"
    assert special["sample_size"] == 2
    assert special["mean"] == 3.0
    assert special["median"] == 3.0
    assert special["short_avg"] == 3.0
    assert special["long_avg"] == 3.0
    assert special["pulse"] == 0.0
    assert special["drift"] == "flat"
    assert [item["max_len"] for item in special["distribution"]] == [2, 3, 4]
    assert _bucket(special["distribution"], 2) == {"max_len": 2, "count": 1, "rate": 0.5}
    assert _bucket(special["distribution"], 3)["count"] == 0
    assert _bucket(special["distribution"], 4) == {"max_len": 4, "count": 1, "rate": 0.5}
    assert special["common"] == [
        {"max_len": 2, "count": 1, "rate": 0.5},
        {"max_len": 4, "count": 1, "rate": 0.5},
    ]
    assert special["cluster_counts"]["mean"] == 1.0
    assert special["cluster_counts"]["pulse"] == 0.0
    assert special["cluster_counts"]["drift"] == "flat"
    assert special["cluster_counts"]["distribution"] == [{"clusters": 1, "count": 2, "rate": 1.0}]

    _draw(db, "qlc", "2026001", ["01", "03", "09"], ["04"])
    single = cluster_summary(db, "qlc")
    assert single["special"] is None
    assert single["latest_draw"]["max_len"] == 1
    assert single["latest_draw"]["clusters"] == 0
    assert single["latest_draw"]["special_max_len"] is None
    assert single["latest_draw"]["special_clusters"] is None


def test_digit_cluster_does_not_wrap_zero_and_nine(db):
    _draw(db, "fc3d", "2026004", ["0", "9", "1"], draw_date="2026-03-04")
    _draw(db, "fc3d", "2026003", ["1", "2", "3"])
    _draw(db, "fc3d", "2026002", ["5", "5", "5"])
    _draw(db, "fc3d", "2026001", ["9", "0", "1"])
    _draw(db, "fc3d", "2026000", [], ["1"])
    _draw(db, "pl5", "2026008", ["1", "2", "4", "5", "7"])
    _draw(db, "pl5", "2026007", ["3", "2", "1", "5", "9"])
    _draw(db, "qxc", "2026008", ["1", "2", "3", "4", "5", "9"], ["14"])

    body = cluster_summary(db, "fc3d")
    assert body["lottery_type"] == "fc3d"
    assert body["mode"] == "digit"
    assert body["basis"] == "digits"
    assert body["note"] == DIGIT_NOTE
    assert "0" in body["note"] and "9" in body["note"]
    assert body["sample_size"] == 4
    assert body["special"] is None
    assert body["mean"] == 1.75
    assert body["median"] == 1.5
    assert body["short_avg"] == 1.75
    assert body["drift"] == "flat"
    assert body["latest_draw"]["max_len"] == 1
    assert body["latest_draw"]["clusters"] == 0
    assert body["latest_draw"]["main"] == ["0", "9", "1"]
    assert body["latest_draw"]["special_max_len"] is None
    assert _bucket(body["distribution"], 1) == {"max_len": 1, "count": 2, "rate": 0.5}
    assert _bucket(body["distribution"], 2) == {"max_len": 2, "count": 1, "rate": 0.25}
    assert _bucket(body["distribution"], 3) == {"max_len": 3, "count": 1, "rate": 0.25}
    assert body["cluster_counts"]["mean"] == 0.5

    broken = cluster_summary(db, "pl5")
    assert broken["sample_size"] == 2
    assert broken["latest_draw"]["max_len"] == 2
    assert broken["latest_draw"]["clusters"] == 2
    assert broken["distribution"] == [
        {"max_len": 2, "count": 1, "rate": 0.5},
        {"max_len": 3, "count": 1, "rate": 0.5},
    ]
    assert broken["cluster_counts"]["distribution"] == [
        {"clusters": 1, "count": 1, "rate": 0.5},
        {"clusters": 2, "count": 1, "rate": 0.5},
    ]

    qxc = cluster_summary(db, "qxc")
    assert qxc["basis"] == "digits"
    assert qxc["special"] is None
    assert qxc["latest_draw"]["max_len"] == 5
    assert qxc["latest_draw"]["clusters"] == 1
    assert qxc["latest_draw"]["special"] == ["14"]
    assert qxc["latest_draw"]["special_max_len"] is None
    assert qxc["distribution"] == [{"max_len": 5, "count": 1, "rate": 1.0}]


def test_score_aligns_with_pulse_and_marks_rarity(db):
    for index, length in enumerate([4, 4, 4, 4, 4, 1, 1, 1, 1, 1]):
        _draw(db, "ssq", f"{2026010 - index:07d}", _nums(length), ["08"])

    wide = score_cluster(db, "ssq", ["01", "02", "03", "04"], ["08"], short=5, long=10)
    assert set(wide) == POST_KEYS
    assert wide["query"] == {"main": ["01", "02", "03", "04"], "special": ["08"]}
    assert set(wide["ticket"]) == TICKET_KEYS
    assert wide["ticket"]["max_len"] == 4
    assert wide["ticket"]["clusters"] == 1
    assert wide["ticket"]["percentile"] == 1.0
    assert wide["ticket"]["typicality"] == 0.5
    assert wide["ticket"]["rarity"] == "common"
    assert wide["ticket"]["alignment"] == "aligned"
    assert wide["ticket"]["note"] == (
        "最长簇 4，1 个簇，历史分位 100%，出现率 50%，常见，短窗 4 比长窗 2.5 变长，和短窗脉动同向。仅供娱乐，不构成投注建议。"
    )
    assert wide["special_ticket"] == _empty_ticket()
    assert wide["drift"] == "rising"

    narrow = score_cluster(db, "ssq", "01 03", special="08", short=5, long=10)
    assert narrow["ticket"]["max_len"] == 1
    assert narrow["ticket"]["clusters"] == 0
    assert narrow["ticket"]["percentile"] == 0.5
    assert narrow["ticket"]["typicality"] == 0.5
    assert narrow["ticket"]["rarity"] == "common"
    assert narrow["ticket"]["alignment"] == "against"
    assert "变长" in narrow["ticket"]["note"]
    assert "反向" in narrow["ticket"]["note"]
    assert "仅供娱乐" in narrow["ticket"]["note"]

    rare = score_cluster(db, "ssq", ["01", "02", "03", "04", "05", "06"], ["08"], short=5, long=10)
    assert rare["ticket"]["max_len"] == 6
    assert rare["ticket"]["clusters"] == 1
    assert rare["ticket"]["percentile"] == 1.0
    assert rare["ticket"]["typicality"] == 0.0
    assert rare["ticket"]["rarity"] == "rare"
    assert rare["ticket"]["alignment"] == "aligned"
    assert "少见" in rare["ticket"]["note"]

    unseen_history = score_cluster(db, "ssq", ["01", "02", "03"], ["01", "02", "04"], short=5, long=10)
    assert unseen_history["ticket"]["max_len"] == 3
    assert unseen_history["special_ticket"]["max_len"] == 2
    assert unseen_history["special_ticket"]["clusters"] == 1
    assert unseen_history["special_ticket"]["percentile"] is None
    assert unseen_history["special_ticket"]["alignment"] is None
    assert unseen_history["special_ticket"]["note"] == (
        "最长簇 2，1 个簇，还没有历史可对照。仅供娱乐，不构成投注建议。"
    )

    for index, pair in enumerate([(1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (4, 4), (4, 4), (4, 4), (4, 4), (4, 4)]):
        main_len, special_len = pair
        _draw(
            db,
            "dlt",
            f"{2027010 - index:07d}",
            _nums(main_len),
            _nums(special_len),
        )

    tight = score_cluster(db, "dlt", ["01", "03"], ["01", "03"], short=5, long=10)
    assert tight["drift"] == "falling"
    assert tight["short_avg"] == 1.0
    assert tight["long_avg"] == 2.5
    assert tight["pulse"] == -1.5
    assert tight["ticket"]["max_len"] == 1
    assert tight["ticket"]["clusters"] == 0
    assert tight["ticket"]["alignment"] == "aligned"
    assert "变短" in tight["ticket"]["note"]
    assert "同向" in tight["ticket"]["note"]
    assert tight["special"]["drift"] == "falling"
    assert tight["special"]["short_avg"] == 1.0
    assert tight["special"]["long_avg"] == 2.5
    assert tight["special_ticket"]["max_len"] == 1
    assert tight["special_ticket"]["clusters"] == 0
    assert tight["special_ticket"]["alignment"] == "aligned"
    assert tight["special_ticket"]["rarity"] == "common"
    assert "不构成投注建议" in tight["special_ticket"]["note"]

    wide_back = score_cluster(db, "dlt", ["01", "02", "03", "04", "05"], ["01", "02", "03", "04", "05"], short=5, long=10)
    assert wide_back["ticket"]["max_len"] == 5
    assert wide_back["ticket"]["alignment"] == "against"
    assert wide_back["ticket"]["rarity"] == "rare"
    assert wide_back["special_ticket"]["max_len"] == 5
    assert wide_back["special_ticket"]["alignment"] == "against"
    assert wide_back["special_ticket"]["percentile"] == 1.0
    assert wide_back["special_ticket"]["typicality"] == 0.0

    one_back = score_cluster(db, "dlt", ["01", "02"], ["03"], short=5, long=10)
    assert one_back["special_ticket"] == _empty_ticket()
    assert one_back["ticket"]["max_len"] == 2
    assert one_back["ticket"]["alignment"] == "against"


def test_digit_score_uses_position_order_not_wrap(db):
    _draw(db, "fc3d", "2026004", ["0", "9", "1"])
    _draw(db, "fc3d", "2026003", ["1", "2", "3"])
    _draw(db, "fc3d", "2026002", ["5", "5", "5"])
    _draw(db, "fc3d", "2026001", ["9", "0", "1"])

    body = score_cluster(db, "fc3d", ["0", "9", "1"])
    assert body["basis"] == "digits"
    assert body["ticket"]["max_len"] == 1
    assert body["ticket"]["clusters"] == 0
    assert body["ticket"]["percentile"] == 0.5
    assert body["ticket"]["typicality"] == 0.5
    assert body["ticket"]["rarity"] == "common"
    assert body["ticket"]["alignment"] == "neutral"
    assert body["ticket"]["note"] == (
        "最长簇 1，0 个簇，历史分位 50%，出现率 50%，常见，短窗 1.75 和长窗 1.75 差不多，没有明显顺逆。仅供娱乐，不构成投注建议。"
    )
    assert body["special_ticket"] == _empty_ticket()

    low = score_cluster(db, "pl3", [5, 5, 5])
    assert low["sample_size"] == 0
    assert low["ticket"]["max_len"] == 1
    assert low["ticket"]["clusters"] == 0
    assert low["ticket"]["percentile"] is None
    assert low["ticket"]["rarity"] is None
    assert low["ticket"]["alignment"] is None
    assert low["ticket"]["note"] == "最长簇 1，0 个簇，还没有历史可对照。仅供娱乐，不构成投注建议。"

    middle = score_cluster(db, "fc3d", "1 2 4")
    assert middle["ticket"]["max_len"] == 2
    assert middle["ticket"]["clusters"] == 1
    assert middle["ticket"]["percentile"] == 0.75
    assert middle["ticket"]["typicality"] == 0.25
    assert middle["ticket"]["rarity"] == "typical"
    assert middle["ticket"]["alignment"] == "neutral"
    assert "居中" in middle["ticket"]["note"]

    descending = score_cluster(db, "pl3", ["3", "2", "1"])
    assert descending["ticket"]["max_len"] == 3
    assert descending["ticket"]["clusters"] == 1
    assert descending["ticket"]["note"].startswith("最长簇 3，1 个簇，还没有历史可对照")


def test_empty_history_parameter_clamp_and_common_cap(db):
    empty = cluster_summary(db, "kl8", limit="no", short=None, long="bad")
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
    assert empty["cluster_counts"]["distribution"] == []
    assert empty["cluster_counts"]["pulse"] is None
    assert empty["cluster_counts"]["drift"] is None
    assert empty["latest_draw"] is None
    assert empty["special"] is None
    assert empty["data_status"] == "seed"
    assert empty["basis"] == "main"

    scored = score_cluster(db, "kl8", ["01", "02"])
    assert scored["ticket"]["max_len"] == 2
    assert scored["ticket"]["clusters"] == 1
    assert scored["ticket"]["percentile"] is None
    assert scored["ticket"]["note"] == "最长簇 2，1 个簇，还没有历史可对照。仅供娱乐，不构成投注建议。"
    assert scored["special_ticket"] == _empty_ticket()

    quiet = score_cluster(db, "kl8", ["01", "03", "05", "08"])
    assert quiet["ticket"]["max_len"] == 1
    assert quiet["ticket"]["clusters"] == 0

    several = score_cluster(db, "kl8", ["01", "02", "03", "10", "11"])
    assert several["ticket"]["max_len"] == 3
    assert several["ticket"]["clusters"] == 2

    for length in range(1, 7):
        _draw(db, "kl8", f"202600{length}", _nums(length))
    clamped = cluster_summary(db, "kl8", limit=1, short=1, long=1)
    assert clamped["short"] == 5
    assert clamped["long"] == 20
    assert clamped["sample_size"] == 5
    assert clamped["latest_draw"]["max_len"] == 6
    assert clamped["latest_draw"]["clusters"] == 1
    assert clamped["mean"] == 4.0
    assert 1 not in {item["max_len"] for item in clamped["distribution"]}

    opened = cluster_summary(db, "kl8", short=30, long=20)
    assert opened["short"] == 30
    assert opened["long"] == 31
    assert opened["sample_size"] == 6
    assert opened["mean"] == 3.5

    for length in range(1, 10):
        _draw(db, "ssq", f"202610{length}", _nums(length))
    capped = cluster_summary(db, "ssq")
    assert capped["sample_size"] == 9
    assert len(capped["common"]) == 8
    assert [item["max_len"] for item in capped["common"]] == list(range(1, 9))
    assert all(item["count"] == 1 and item["rate"] == 0.1111 for item in capped["common"])
    assert capped["mean"] == 5.0
    assert capped["median"] == 5

    with pytest.raises(ValueError, match="未知彩种"):
        cluster_summary(db, "nope")
    with pytest.raises(ValueError, match="未知彩种"):
        score_cluster(db, "nope", ["01"])
    with pytest.raises(ValueError):
        score_cluster(db, "ssq", ["01", "01", "03", "04", "05", "06"], ["01"])
    with pytest.raises(ValueError):
        score_cluster(db, "fc3d", ["1", "2"])
    with pytest.raises(ValueError):
        score_cluster(db, "kl8", ["01", "02"], ["03"])


def test_cluster_endpoints_bounds_and_old_contracts(client, db):
    _draw(db, "ssq", "2026001", ["01", "02", "03", "10", "20", "30"], ["16"], draw_date="2026-04-01")
    _draw(db, "ssq", "2026002", ["05", "07", "09", "11", "13", "15"], ["02"], source="crawl", draw_date="2026-04-03")

    res = client.get("/api/analysis/ssq/cluster")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == GET_KEYS
    assert body["sample_size"] == 2
    assert body["short"] == 10
    assert body["long"] == 50
    assert body["basis"] == "main"
    assert body["disclaimer"] == DISCLAIMER
    assert body["data_status"] == "mixed"
    assert body["latest_draw"]["issue"] == "2026002"
    assert body["latest_draw"]["max_len"] == 1
    assert body["latest_draw"]["clusters"] == 0
    assert body["mean"] == 2.0
    assert body["pulse"] == 0.0
    assert body["drift"] == "flat"
    assert body["special"] is None
    assert body["distribution"][0]["max_len"] == 1
    assert "span" not in body["distribution"][0]

    custom = client.get("/api/analysis/ssq/cluster", params={"limit": 80, "short": 5, "long": 20})
    assert custom.status_code == 200
    assert custom.json()["short"] == 5
    assert custom.json()["long"] == 20

    widened = client.get("/api/analysis/ssq/cluster", params={"short": 30, "long": 20})
    assert widened.status_code == 200
    assert widened.json()["short"] == 30
    assert widened.json()["long"] == 31

    assert client.get("/api/analysis/ssq/cluster", params={"limit": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/cluster", params={"limit": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/cluster", params={"short": 4}).status_code == 422
    assert client.get("/api/analysis/ssq/cluster", params={"short": 31}).status_code == 422
    assert client.get("/api/analysis/ssq/cluster", params={"long": 19}).status_code == 422
    assert client.get("/api/analysis/ssq/cluster", params={"long": 201}).status_code == 422
    assert client.get("/api/analysis/ssq/cluster", params={"limit": 5, "short": 5, "long": 20}).status_code == 200
    assert client.get("/api/analysis/ssq/cluster", params={"limit": 200, "short": 30, "long": 200}).status_code == 200

    unknown = client.get("/api/analysis/nope/cluster")
    assert unknown.status_code == 400
    assert "未知彩种" in unknown.json()["detail"]

    empty = client.get("/api/analysis/kl8/cluster")
    assert empty.status_code == 200
    assert empty.json()["sample_size"] == 0
    assert empty.json()["latest_draw"] is None
    assert empty.json()["distribution"] == []
    assert empty.json()["drift"] is None

    alias = client.get("/api/analysis/3d/cluster")
    assert alias.status_code == 200
    assert alias.json()["lottery_type"] == "fc3d"
    assert alias.json()["mode"] == "digit"
    assert alias.json()["basis"] == "digits"

    posted = client.post(
        "/api/analysis/ssq/cluster",
        json={"main": "01 02 03 10 20 30", "special": "16", "limit": 80, "short": 10, "long": 50},
    )
    assert posted.status_code == 200, posted.text
    scored = posted.json()
    assert set(scored) == POST_KEYS
    assert scored["query"] == {"main": ["01", "02", "03", "10", "20", "30"], "special": ["16"]}
    assert scored["ticket"]["max_len"] == 3
    assert scored["ticket"]["clusters"] == 1
    assert scored["ticket"]["rarity"] == "common"
    assert scored["ticket"]["alignment"] == "neutral"
    assert scored["special_ticket"]["max_len"] is None
    assert "仅供娱乐" in scored["ticket"]["note"]

    spaced = client.post("/api/analysis/3d/cluster", json={"main": ["0", "9", "1"], "short": 5, "long": 20})
    assert spaced.status_code == 200
    assert spaced.json()["lottery_type"] == "fc3d"
    assert spaced.json()["ticket"]["max_len"] == 1
    assert spaced.json()["ticket"]["clusters"] == 0
    assert spaced.json()["mode"] == "digit"

    bad = client.post("/api/analysis/ssq/cluster", json={"main": ["99"], "special": ["01"]})
    assert bad.status_code == 400
    duplicate = client.post(
        "/api/analysis/ssq/cluster",
        json={"main": ["01", "01", "03", "04", "05", "06"], "special": ["01"]},
    )
    assert duplicate.status_code == 400
    short = client.post("/api/analysis/fc3d/cluster", json={"main": ["1", "2"]})
    assert short.status_code == 400
    extra = client.post("/api/analysis/kl8/cluster", json={"main": ["01", "02"], "special": ["03"]})
    assert extra.status_code == 400
    unknown_post = client.post("/api/analysis/nope/cluster", json={"main": ["01"]})
    assert unknown_post.status_code == 400
    assert client.post("/api/analysis/ssq/cluster", json={"main": ["01"], "limit": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/cluster", json={"main": ["01"], "short": 4}).status_code == 422
    assert client.post("/api/analysis/ssq/cluster", json={"main": ["01"], "long": 201}).status_code == 422

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
    assert "max_len" not in analysis.json()

    shape = client.get("/api/analysis/ssq/shape")
    assert shape.status_code == 200
    shape_body = shape.json()
    assert set(shape_body["consecutive"]) == {"draws_with", "draws_without", "avg_pairs"}
    assert shape_body["consecutive"]["avg_pairs"] == 1.0
    assert set(shape_body["span"]) == {"min", "max", "avg"}
    assert "pulse" not in shape_body
    assert "distribution" not in shape_body
    assert "max_len" not in shape_body
    direct = shape_stats(db, "ssq", limit=50)
    assert direct["consecutive"]["avg_pairs"] == 1.0

    span = client.get("/api/analysis/ssq/span")
    assert span.status_code == 200
    span_body = span.json()
    assert "pulse" in span_body
    assert span_body["distribution"][0]["span"] in (10, 29)
    assert "max_len" not in span_body
    assert "cluster_counts" not in span_body

    neighbor = client.get("/api/analysis/ssq/neighbor")
    assert neighbor.status_code == 200
    assert "pulled" in neighbor.json()
    assert "max_len" not in neighbor.json()
    assert "cluster_counts" not in neighbor.json()
