"""重号脉搏：相邻两期里，主号有多少被留下来。

开奖按期号从新到旧取最近 limit 期（5–200，默认 80）。空白主号的行会跳过。
每一对按「较早一期 → 较晚一期」比较，recent_pairs 从最近一次交接排到更早
（order = older_to_newer）。乐透主号用集合相交；数字彩只计同一位置相同的数字。
蓝球 / 特别号单独计数，不计入主号重号，也不进入直方图。只读本地开奖。
"""
from __future__ import annotations

import statistics
from collections import Counter

from sqlalchemy.orm import Session

from ..lotteries import LOTTERIES, normalize_type, parse_numbers
from ..models import Draw
from .echo import PROFILES, normalize_query

DISCLAIMER = "重号脉搏只看相邻两期有没有把号码留下来，仅供娱乐，不构成投注建议。"
EMPTY_MESSAGE = "暂无开奖可对照"

POSITION_LABELS = {
    "fc3d": ["百", "十", "个"],
    "pl3": ["百", "十", "个"],
    "pl5": ["万", "千", "百", "十", "个"],
    "qxc": ["1", "2", "3", "4", "5", "6"],
}


def _bounded(limit: int) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = 80
    return max(5, min(value, 200))


def _history_group(items: list, width: int) -> list[str]:
    out: list[str] = []
    for item in items or []:
        text = str(item).strip()
        if not text.isdigit():
            continue
        number = int(text)
        out.append(str(number).zfill(width) if width > 1 else str(number))
    return out


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _sorted_shared(left: list[str], right: list[str]) -> list[str]:
    return sorted(set(left) & set(right), key=lambda item: int(item))


def _profile(lottery_type: str) -> tuple[str, dict]:
    lottery = normalize_type(lottery_type)
    profile = PROFILES.get(lottery)
    if profile is None or lottery not in LOTTERIES:
        raise ValueError("未知彩种")
    return lottery, profile


def _load(db: Session, lottery: str, profile: dict, limit: int) -> tuple[list[dict], str]:
    rows = (
        db.query(Draw)
        .filter(Draw.lottery_type == lottery)
        .order_by(Draw.issue.desc())
        .limit(_bounded(limit))
        .all()
    )
    width = profile["width"]
    draws: list[dict] = []
    for row in rows:
        parsed = parse_numbers(row.numbers)
        main = _history_group(parsed["main"], width)
        if profile["mode"] == "set":
            main = _unique(main)
        if not main:
            continue
        draws.append(
            {
                "issue": row.issue,
                "draw_date": row.draw_date or "",
                "main": main,
                "special": _unique(_history_group(parsed["special"], width)),
                "source": row.source or "seed",
            }
        )
    status = "mixed" if any(item["source"] == "crawl" for item in draws) else "seed"
    return draws, status


def _compare(lottery: str, mode: str, older: dict, newer: dict) -> dict:
    shared_special = _sorted_shared(older["special"], newer["special"])
    if mode == "digit":
        labels = POSITION_LABELS.get(lottery) or []
        positions = []
        shared_main: list[str] = []
        for index, label in enumerate(labels):
            left = older["main"][index] if index < len(older["main"]) else ""
            right = newer["main"][index] if index < len(newer["main"]) else ""
            repeat = bool(left) and left == right
            positions.append({"index": index, "label": label, "repeat": repeat, "from": left, "to": right})
            if repeat:
                shared_main.append(right)
    else:
        shared_main = _sorted_shared(older["main"], newer["main"])
        positions = []
    return {
        "issue_from": older["issue"],
        "issue_to": newer["issue"],
        "overlap": len(shared_main),
        "special_overlap": len(shared_special),
        "main": list(newer["main"]),
        "special": list(newer["special"]),
        "shared_main": shared_main,
        "shared_special": shared_special,
        "positions": positions,
    }


def _distribution(overlaps: list[int]) -> list[dict]:
    if not overlaps:
        return []
    counts = Counter(overlaps)
    total = len(overlaps)
    return [
        {"overlap": number, "count": counts[number], "rate": round(counts[number] / total, 4)}
        for number in range(max(overlaps) + 1)
    ]


def _stats(overlaps: list[int]) -> dict:
    if not overlaps:
        return {"mean": None, "median": None, "max": None}
    return {
        "mean": round(statistics.mean(overlaps), 4),
        "median": statistics.median(overlaps),
        "max": max(overlaps),
    }


def _summary(lottery: str, profile: dict, draws: list[dict], status: str) -> dict:
    pairs = [_compare(lottery, profile["mode"], draws[index + 1], draws[index]) for index in range(len(draws) - 1)]
    overlaps = [item["overlap"] for item in pairs]
    latest = None
    if draws:
        head = draws[0]
        latest = {
            "issue": head["issue"],
            "draw_date": head["draw_date"],
            "main": list(head["main"]),
            "special": list(head["special"]),
        }
    return {
        "lottery_type": lottery,
        "mode": profile["mode"],
        "sample_size": len(draws),
        "pair_count": len(pairs),
        "order": "older_to_newer",
        "latest_draw": latest,
        "distribution": _distribution(overlaps),
        "recent_pairs": pairs,
        "data_status": status,
        "disclaimer": DISCLAIMER,
        **_stats(overlaps),
    }


def repeat_pulse(db: Session, lottery_type: str, limit: int = 80) -> dict:
    """相邻开奖的重号分布。recent_pairs 里 issue_from 是较早一期。"""
    lottery, profile = _profile(lottery_type)
    draws, status = _load(db, lottery, profile, limit)
    return _summary(lottery, profile, draws, status)


def _place(overlap: int | None, overlaps: list[int]) -> tuple[float | None, int | None]:
    if overlap is None or not overlaps:
        return None, None
    percentile = round(sum(item <= overlap for item in overlaps) / len(overlaps), 4)
    rank = 1 + sum(item > overlap for item in overlaps)
    return percentile, rank


def _score_against(lottery: str, profile: dict, query: dict, latest: dict | None) -> dict:
    if latest is None:
        return {
            "overlap": None,
            "special_overlap": None,
            "repeat_main": [],
            "fresh_main": [],
            "repeat_special": [],
            "fresh_special": [],
            "positions": [],
            "message": EMPTY_MESSAGE,
        }
    latest_special = set(latest["special"])
    repeat_special = _sorted_shared(query["special"], latest["special"])
    fresh_special = [item for item in query["special"] if item not in latest_special]
    if profile["mode"] == "digit":
        labels = POSITION_LABELS.get(lottery) or []
        positions = []
        repeat_main: list[str] = []
        fresh_main: list[str] = []
        for index, label in enumerate(labels):
            ticket = query["main"][index] if index < len(query["main"]) else ""
            current = latest["main"][index] if index < len(latest["main"]) else ""
            repeat = bool(ticket) and ticket == current
            positions.append(
                {"index": index, "label": label, "ticket": ticket, "latest": current, "repeat": repeat}
            )
            if repeat:
                repeat_main.append(ticket)
            elif ticket:
                fresh_main.append(ticket)
    else:
        latest_main = set(latest["main"])
        repeat_main = _sorted_shared(query["main"], latest["main"])
        fresh_main = [item for item in query["main"] if item not in latest_main]
        positions = []
    return {
        "overlap": len(repeat_main),
        "special_overlap": len(repeat_special),
        "repeat_main": repeat_main,
        "fresh_main": fresh_main,
        "repeat_special": repeat_special,
        "fresh_special": fresh_special,
        "positions": positions,
        "message": "",
    }


def score_repeat(db: Session, lottery_type: str, main, special=None, limit: int = 80) -> dict:
    """把一注和最新开奖比，并用相邻交接的重号分布给出百分位。"""
    query = normalize_query(lottery_type, main, special)
    pulse = repeat_pulse(db, query["lottery_type"], limit=limit)
    scored = _score_against(query["lottery_type"], PROFILES[query["lottery_type"]], query, pulse["latest_draw"])
    overlaps = [item["overlap"] for item in pulse["recent_pairs"]]
    percentile, rank = _place(scored["overlap"], overlaps)
    return {
        **pulse,
        "query": {"main": query["main"], "special": query["special"]},
        **scored,
        "percentile": percentile,
        "rank": rank,
    }
