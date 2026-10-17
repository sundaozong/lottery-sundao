"""冷热动量：短窗口出现率减去长窗口出现率。

近 limit 期（5–200，默认 80）按期号从新到旧读取。空白主号的行会跳过，
不占窗口名额；limit 先限制查询条数，跳过发生在取出之后。
rate_short = hits_short / short，rate_long = hits_long / long，
delta = rate_short - rate_long。分母始终是请求的窗口，历史更短也不缩小。
delta >= 0.02 记为升温，delta <= -0.02 记为降温，其余持平。
short 限制在 5–30（默认 10），long 限制在 20–200（默认 50）；
若 long <= short，把 long 收到 short + 1。

乐透主号按集合计，同一期里的重复号码只算一次。
数字彩按位置分别统计 0–9。顶层 numbers / rising / falling / flat 留空，
明细在 positions 里，标签与重号脉搏一致（百/十/个、万千百十个、七星彩 1–6）。
蓝球 / 特别号放在 special，不进入主号动量。

给一注打分时，主号动量分 = 升温个数 − 降温个数。特别号另计在 special_ticket，
不并进主号分。名单按这注原来的顺序，不按动量强弱重排。只读本地开奖。
"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction

from sqlalchemy.orm import Session

from ..lotteries import LOTTERIES, normalize_type, parse_numbers
from ..models import Draw
from .echo import PROFILES, normalize_query
from .repeat import POSITION_LABELS

DISCLAIMER = "冷热动量比较短窗口和长窗口的出现率，看号码是在升温还是降温，仅供娱乐，不构成投注建议。"
THRESHOLD = 0.02
_CUT = Fraction("0.02")


def _bounded(value, default: int, lo: int, hi: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(lo, min(number, hi))


def _windows(limit, short, long) -> tuple[int, int, int]:
    limit_n = _bounded(limit, 80, 5, 200)
    short_n = _bounded(short, 10, 5, 30)
    long_n = _bounded(long, 50, 20, 200)
    if long_n <= short_n:
        long_n = short_n + 1
    return limit_n, short_n, long_n


def _profile(lottery_type: str) -> tuple[str, dict]:
    lottery = normalize_type(lottery_type)
    profile = PROFILES.get(lottery)
    if profile is None or lottery not in LOTTERIES:
        raise ValueError("未知彩种")
    return lottery, profile


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


def _pool(bounds: tuple[int, int, int, int], width: int) -> list[str]:
    lo, hi, _, _ = bounds
    return [str(number).zfill(width) if width > 1 else str(number) for number in range(lo, hi + 1)]


def _load(db: Session, lottery: str, profile: dict, limit: int) -> tuple[list[dict], str]:
    rows = (
        db.query(Draw)
        .filter(Draw.lottery_type == lottery)
        .order_by(Draw.issue.desc())
        .limit(limit)
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


def _trend(delta: Fraction) -> str:
    if delta >= _CUT:
        return "rising"
    if delta <= -_CUT:
        return "falling"
    return "flat"


def _as_float(value: Fraction) -> float:
    return round(float(value), 4)


def _count_group(draws: list[dict], key: str) -> Counter:
    counter: Counter = Counter()
    for draw in draws:
        counter.update(set(draw[key]))
    return counter


def _count_position(draws: list[dict], index: int) -> Counter:
    counter: Counter = Counter()
    for draw in draws:
        main = draw["main"]
        if index < len(main) and main[index]:
            counter[main[index]] += 1
    return counter


def _build(pool: list[str], short_hits: Counter, long_hits: Counter, short: int, long: int) -> tuple[list[dict], list[str], list[str], list[str]]:
    rows = []
    for number in pool:
        hits_short = int(short_hits.get(number, 0))
        hits_long = int(long_hits.get(number, 0))
        rate_short = Fraction(hits_short, short)
        rate_long = Fraction(hits_long, long)
        delta = rate_short - rate_long
        rows.append(
            {
                "number": number,
                "hits_short": hits_short,
                "hits_long": hits_long,
                "rate_short": _as_float(rate_short),
                "rate_long": _as_float(rate_long),
                "delta": _as_float(delta),
                "trend": _trend(delta),
            }
        )
    rows.sort(key=lambda item: int(item["number"]))
    rising = [
        item["number"]
        for item in sorted((item for item in rows if item["trend"] == "rising"), key=lambda item: (-item["delta"], int(item["number"])))
    ]
    falling = [
        item["number"]
        for item in sorted((item for item in rows if item["trend"] == "falling"), key=lambda item: (item["delta"], int(item["number"])))
    ]
    flat = [item["number"] for item in rows if item["trend"] == "flat"]
    return rows, rising, falling, flat


def _group_block(draws: list[dict], pool: list[str], key: str, short: int, long: int, label: str | None = None) -> dict:
    rows, rising, falling, flat = _build(pool, _count_group(draws[:short], key), _count_group(draws[:long], key), short, long)
    block = {"numbers": rows, "rising": rising, "falling": falling, "flat": flat}
    if label is not None:
        block["label"] = label
    return block


def _positions(lottery: str, profile: dict, draws: list[dict], short: int, long: int) -> list[dict]:
    labels = POSITION_LABELS.get(lottery) or []
    pool = _pool(profile["main"], profile["width"])
    positions = []
    for index, label in enumerate(labels):
        rows, rising, falling, flat = _build(
            pool,
            _count_position(draws[:short], index),
            _count_position(draws[:long], index),
            short,
            long,
        )
        positions.append(
            {
                "index": index,
                "label": label,
                "numbers": rows,
                "rising": rising,
                "falling": falling,
                "flat": flat,
            }
        )
    return positions


def _special_block(profile: dict, draws: list[dict], short: int, long: int) -> dict | None:
    bounds = profile["special"]
    if bounds is None:
        return None
    block = _group_block(draws, _pool(bounds, profile["width"]), "special", short, long, profile["special_label"])
    return block


def _latest(draws: list[dict]) -> dict | None:
    if not draws:
        return None
    head = draws[0]
    return {
        "issue": head["issue"],
        "draw_date": head["draw_date"],
        "main": list(head["main"]),
        "special": list(head["special"]),
    }


def momentum_summary(db: Session, lottery_type: str, limit: int = 80, short: int = 10, long: int = 50) -> dict:
    """短窗相对长窗的出现率变化。数字彩看 positions，特别号看 special。"""
    lottery, profile = _profile(lottery_type)
    limit_n, short_n, long_n = _windows(limit, short, long)
    draws, status = _load(db, lottery, profile, limit_n)
    if profile["mode"] == "digit":
        numbers: list[dict] = []
        rising: list[str] = []
        falling: list[str] = []
        flat: list[str] = []
        positions = _positions(lottery, profile, draws, short_n, long_n)
    else:
        block = _group_block(draws, _pool(profile["main"], profile["width"]), "main", short_n, long_n)
        numbers = block["numbers"]
        rising = block["rising"]
        falling = block["falling"]
        flat = block["flat"]
        positions = []
    return {
        "lottery_type": lottery,
        "mode": profile["mode"],
        "sample_size": len(draws),
        "short": short_n,
        "long": long_n,
        "threshold": THRESHOLD,
        "numbers": numbers,
        "rising": rising,
        "falling": falling,
        "flat": flat,
        "positions": positions,
        "special": _special_block(profile, draws, short_n, long_n),
        "latest_draw": _latest(draws),
        "data_status": status,
        "disclaimer": DISCLAIMER,
    }


def _empty_ticket() -> dict:
    return {
        "rising": [],
        "falling": [],
        "flat": [],
        "rising_count": 0,
        "falling_count": 0,
        "flat_count": 0,
        "score": 0,
    }


def _finish(buckets: dict[str, list]) -> dict:
    rising = buckets["rising"]
    falling = buckets["falling"]
    flat = buckets["flat"]
    return {
        "rising": rising,
        "falling": falling,
        "flat": flat,
        "rising_count": len(rising),
        "falling_count": len(falling),
        "flat_count": len(flat),
        "score": len(rising) - len(falling),
    }


def _score_main(lottery: str, profile: dict, query: dict, summary: dict) -> dict:
    buckets: dict[str, list] = {"rising": [], "falling": [], "flat": []}
    if profile["mode"] == "digit":
        labels = POSITION_LABELS.get(lottery) or []
        for index, label in enumerate(labels):
            digit = query["main"][index] if index < len(query["main"]) else ""
            if not digit:
                continue
            lookup = {item["number"]: item for item in summary["positions"][index]["numbers"]}
            buckets[lookup[digit]["trend"]].append({"index": index, "label": label, "number": digit})
        return _finish(buckets)
    lookup = {item["number"]: item for item in summary["numbers"]}
    for number in query["main"]:
        buckets[lookup[number]["trend"]].append(number)
    return _finish(buckets)


def _score_special(query: dict, summary: dict) -> dict:
    special = summary.get("special")
    if not query["special"] or not special:
        return _empty_ticket()
    lookup = {item["number"]: item for item in special["numbers"]}
    buckets: dict[str, list] = {"rising": [], "falling": [], "flat": []}
    for number in query["special"]:
        buckets[lookup[number]["trend"]].append(number)
    return _finish(buckets)


def score_momentum(db: Session, lottery_type: str, main, special=None, limit: int = 80, short: int = 10, long: int = 50) -> dict:
    """同一份动量摘要上，给一注主号打分；特别号单独打分。"""
    query = normalize_query(lottery_type, main, special)
    summary = momentum_summary(db, query["lottery_type"], limit=limit, short=short, long=long)
    profile = PROFILES[query["lottery_type"]]
    return {
        **summary,
        "query": {"main": query["main"], "special": query["special"]},
        "ticket": _score_main(query["lottery_type"], profile, query, summary),
        "special_ticket": _score_special(query, summary),
    }
