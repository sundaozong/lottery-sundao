"""主号形态统计：奇偶、大小、和值、连号、区间、三位形态。

只读已有开奖，不改分析接口的返回。蓝球 / 特别号不计入。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..lotteries import LOTTERIES, normalize_type, parse_numbers
from ..models import Draw

DISCLAIMER = "形态统计只看本地开奖的主号，仅供娱乐，不构成投注建议。"

# split：小于等于该值算小。区间含两端。
PROFILES = {
    "ssq": {
        "mode": "set",
        "split": 16,
        "zones": [(1, 11, "一区"), (12, 22, "二区"), (23, 33, "三区")],
        "width": 2,
    },
    "dlt": {
        "mode": "set",
        "split": 17,
        "zones": [(1, 12, "一区"), (13, 24, "二区"), (25, 35, "三区")],
        "width": 2,
    },
    "qlc": {
        "mode": "set",
        "split": 15,
        "zones": [(1, 10, "一区"), (11, 20, "二区"), (21, 30, "三区")],
        "width": 2,
    },
    "kl8": {
        "mode": "set",
        "split": 40,
        "zones": [(1, 27, "一区"), (28, 54, "二区"), (55, 80, "三区")],
        "width": 2,
    },
    "fc3d": {"mode": "digit3", "split": 4, "zones": [], "width": 1},
    "pl3": {"mode": "digit3", "split": 4, "zones": [], "width": 1},
    "pl5": {"mode": "digit", "split": 4, "zones": [], "width": 1},
    "qxc": {"mode": "digit", "split": 4, "zones": [], "width": 1},
}


def _zone_label(name: str, lo: int, hi: int, width: int) -> str:
    if width > 1:
        return f"{name} {lo:02d}–{hi:02d}"
    return f"{name} {lo}–{hi}"


def _ratio_rows(counter: dict[str, dict]) -> list[dict]:
    rows = list(counter.values())
    rows.sort(key=lambda item: (-item["count"], item["label"]))
    return rows


def _sum_buckets(values: list[int], parts: int = 5) -> list[dict]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if lo == hi:
        return [{"label": str(lo), "count": len(values)}]
    parts = max(1, min(parts, hi - lo + 1))
    step = (hi - lo) / parts
    counts = [0] * parts
    for value in values:
        index = min(parts - 1, int((value - lo) / step))
        counts[index] += 1
    buckets = []
    for index, count in enumerate(counts):
        start = lo if index == 0 else round(lo + step * index)
        end = hi if index == parts - 1 else round(lo + step * (index + 1))
        label = str(start) if start == end else f"{start}–{end}"
        buckets.append({"label": label, "count": count})
    return buckets


def _pattern(nums: list[int]) -> str:
    if len(nums) != 3:
        return "其他"
    distinct = len(set(nums))
    if distinct == 1:
        return "豹子"
    if distinct == 2:
        return "组三"
    return "组六"


def summarize(draws: list[list[int]], lottery_type: str) -> dict:
    """draws 已是每期主号整数列表。"""
    t = normalize_type(lottery_type)
    profile = PROFILES.get(t)
    if profile is None:
        raise ValueError("未知彩种")
    split = profile["split"]
    width = profile["width"]
    odd_even: dict[str, dict] = {}
    big_small: dict[str, dict] = {}
    sums: list[int] = []
    spans: list[int] = []
    pair_counts: list[int] = []
    zone_totals = [0 for _ in profile["zones"]]
    pattern_counts = {"豹子": 0, "组三": 0, "组六": 0, "其他": 0}

    for nums in draws:
        odd = sum(1 for n in nums if n % 2)
        even = len(nums) - odd
        oe_label = f"{odd}奇{even}偶"
        odd_even.setdefault(oe_label, {"label": oe_label, "odd": odd, "even": even, "count": 0})
        odd_even[oe_label]["count"] += 1

        big = sum(1 for n in nums if n > split)
        small = len(nums) - big
        bs_label = f"{big}大{small}小"
        big_small.setdefault(bs_label, {"label": bs_label, "big": big, "small": small, "count": 0})
        big_small[bs_label]["count"] += 1

        sums.append(sum(nums))
        spans.append(max(nums) - min(nums))
        ordered = sorted(set(nums))
        pairs = sum(1 for a, b in zip(ordered, ordered[1:]) if b - a == 1)
        pair_counts.append(pairs)
        for index, (lo, hi, _name) in enumerate(profile["zones"]):
            zone_totals[index] += sum(1 for n in nums if lo <= n <= hi)
        if profile["mode"] == "digit3":
            pattern_counts[_pattern(nums)] += 1

    sample = len(draws)
    zones = [
        {
            "label": _zone_label(name, lo, hi, width),
            "avg": round(zone_totals[index] / sample, 2) if sample else 0,
        }
        for index, (lo, hi, name) in enumerate(profile["zones"])
    ]
    patterns = []
    if profile["mode"] == "digit3":
        patterns = [{"label": label, "count": pattern_counts[label]} for label in ("豹子", "组三", "组六")]
        if pattern_counts["其他"]:
            patterns.append({"label": "其他", "count": pattern_counts["其他"]})

    return {
        "lottery_type": t,
        "sample_size": sample,
        "mode": profile["mode"],
        "number_scope": "主号",
        "odd_even": _ratio_rows(odd_even),
        "big_small": _ratio_rows(big_small),
        "sum": {
            "min": min(sums) if sums else None,
            "max": max(sums) if sums else None,
            "avg": round(sum(sums) / sample, 2) if sample else None,
            "buckets": _sum_buckets(sums),
        },
        "span": {
            "min": min(spans) if spans else None,
            "max": max(spans) if spans else None,
            "avg": round(sum(spans) / sample, 2) if sample else None,
        },
        "consecutive": {
            "draws_with": sum(1 for n in pair_counts if n),
            "draws_without": sum(1 for n in pair_counts if not n),
            "avg_pairs": round(sum(pair_counts) / sample, 2) if sample else 0,
        },
        "zones": zones,
        "patterns": patterns,
        "disclaimer": DISCLAIMER,
    }


def shape_stats(db: Session, lottery_type: str, limit: int = 50) -> dict:
    t = normalize_type(lottery_type)
    if t not in LOTTERIES:
        raise ValueError("未知彩种")
    rows = (
        db.query(Draw)
        .filter(Draw.lottery_type == t)
        .order_by(Draw.issue.desc())
        .limit(limit)
        .all()
    )
    draws: list[list[int]] = []
    for row in rows:
        nums = []
        for raw in parse_numbers(row.numbers)["main"]:
            text = str(raw).strip()
            if text.isdigit():
                nums.append(int(text))
        if nums:
            draws.append(nums)
    return summarize(draws, t)
