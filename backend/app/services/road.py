"""012路脉动：主号除三余数配比的路偏度历史分布，以及短窗相对长窗是更偏还是更匀。

近 limit 期（5–200，默认 80）按期号从新到旧读取。空白主号的行会跳过，
不占窗口名额；limit 先限制查询条数，跳过发生在取出之后。
每个号码的路是它除以 3 的余数。乐透把主号去重后计数，特别号不计入主号；
有特别号时另计 special。数字彩按整注各位计数，0 和 9 不绕圈。
路偏度 = 三路个数的最大减最小。

短窗、长窗用这段里实际有的期数求平均，历史更短时不把缺口当成路偏度 0。
pulse = 短窗平均 − 长窗平均。pulse >= 0.5 记为更偏，<= -0.5 记为更匀，其余持平。
short 限制在 5–30（默认 10），long 限制在 20–200（默认 50）；
若 long <= short，把 long 收到 short + 1。

给一注打分时，对照这份路偏度分布给出分位、出现率和常见 / 居中 / 少见，
并说明它跟短窗脉动是同向、反向，还是没有明显顺逆。特别号单独打分，不并进主号。
只读本地开奖。
"""
from __future__ import annotations

import statistics
from collections import Counter

from sqlalchemy.orm import Session

from ..lotteries import LOTTERIES, normalize_type, parse_numbers
from ..models import Draw
from .echo import PROFILES, normalize_query

DISCLAIMER = "012路脉动看主号除以 3 的余数配比和路偏度，以及短窗相对长窗是更偏还是更匀，仅供娱乐，不构成投注建议。"
SET_NOTE = "主号去重后按除以 3 的余数分成 0路、1路、2路，路偏度是最多的一路减去最少的一路。特别号不计入主号。"
DIGIT_NOTE = "整注各位数字按除以 3 的余数分成 0路、1路、2路，0 和 9 不绕圈，路偏度是最多的一路减去最少的一路。特别号不计入主号。"
THRESHOLD = 0.5
COMMON_LIMIT = 8
ROADS = ("0", "1", "2")

_RARITY_WORD = {"common": "常见", "typical": "居中", "rare": "少见"}


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


def _counts_of(numbers: list[str]) -> dict[str, int] | None:
    if not numbers:
        return None
    counts = {road: 0 for road in ROADS}
    for item in numbers:
        counts[str(int(item) % 3)] += 1
    return counts


def _imbalance(counts: dict[str, int] | None) -> int | None:
    if not counts:
        return None
    values = [counts[road] for road in ROADS]
    return max(values) - min(values)


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


def _avg(values: list[int]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _median(values: list[int]):
    if not values:
        return None
    return statistics.median(values)


def _avg_counts(rows: list[dict[str, int]]) -> dict[str, float] | None:
    if not rows:
        return None
    total = len(rows)
    return {road: round(sum(item[road] for item in rows) / total, 4) for road in ROADS}


def _distribution(values: list[int]) -> list[dict]:
    if not values:
        return []
    counts = Counter(values)
    total = len(values)
    return [
        {"imbalance": number, "count": counts[number], "rate": round(counts[number] / total, 4)}
        for number in range(min(values), max(values) + 1)
    ]


def _common(values: list[int]) -> list[dict]:
    if not values:
        return []
    counts = Counter(values)
    total = len(values)
    ranked = sorted(counts, key=lambda number: (-counts[number], number))
    return [
        {"imbalance": number, "count": counts[number], "rate": round(counts[number] / total, 4)}
        for number in ranked[:COMMON_LIMIT]
    ]


def _drift(pulse: float | None) -> str | None:
    if pulse is None:
        return None
    if pulse >= THRESHOLD:
        return "rising"
    if pulse <= -THRESHOLD:
        return "falling"
    return "flat"


def _pulse(values: list[int], short: int, long: int) -> tuple[float | None, float | None, float | None, str | None]:
    short_avg = _avg(values[:short])
    long_avg = _avg(values[:long])
    if short_avg is None or long_avg is None:
        return None, None, None, None
    pulse = round(short_avg - long_avg, 4)
    return short_avg, long_avg, pulse, _drift(pulse)


def _block(values: list[int], short: int, long: int, label: str | None = None) -> dict:
    short_avg, long_avg, pulse, drift = _pulse(values, short, long)
    block = {
        "sample_size": len(values),
        "distribution": _distribution(values),
        "common": _common(values),
        "mean": _avg(values),
        "median": _median(values),
        "short_avg": short_avg,
        "long_avg": long_avg,
        "pulse": pulse,
        "drift": drift,
    }
    if label is not None:
        block = {"label": label, **block}
    return block


def _series(draws: list[dict], special: bool = False) -> tuple[list[int], list[dict[str, int]]]:
    imbalances: list[int] = []
    rows: list[dict[str, int]] = []
    for draw in draws:
        numbers = draw["special"] if special else draw["main"]
        if special and not numbers:
            continue
        counts = _counts_of(numbers)
        imbalance = _imbalance(counts)
        if counts is None or imbalance is None:
            continue
        imbalances.append(imbalance)
        rows.append(counts)
    return imbalances, rows


def _latest(draws: list[dict]) -> dict | None:
    if not draws:
        return None
    head = draws[0]
    counts = _counts_of(head["main"])
    if head["special"]:
        special_counts = _counts_of(head["special"])
        special_imbalance = _imbalance(special_counts)
    else:
        special_counts = None
        special_imbalance = None
    return {
        "issue": head["issue"],
        "draw_date": head["draw_date"],
        "main": list(head["main"]),
        "special": list(head["special"]),
        "counts": counts,
        "imbalance": _imbalance(counts),
        "special_counts": special_counts,
        "special_imbalance": special_imbalance,
    }


def road_summary(db: Session, lottery_type: str, limit: int = 80, short: int = 10, long: int = 50) -> dict:
    """主号路偏度直方图，以及短窗平均相对长窗平均的脉动。"""
    lottery, profile = _profile(lottery_type)
    limit_n, short_n, long_n = _windows(limit, short, long)
    draws, status = _load(db, lottery, profile, limit_n)
    imbalances, count_rows = _series(draws)
    block = _block(imbalances, short_n, long_n)
    special_imbalances, special_rows = _series(draws, special=True)
    special = None
    if special_imbalances:
        special = _block(special_imbalances, short_n, long_n, profile["special_label"])
        special["avg_road_counts"] = _avg_counts(special_rows)
    return {
        "lottery_type": lottery,
        "mode": profile["mode"],
        "basis": "digits" if profile["mode"] == "digit" else "main",
        "sample_size": len(draws),
        "short": short_n,
        "long": long_n,
        "threshold": THRESHOLD,
        "distribution": block["distribution"],
        "common": block["common"],
        "mean": block["mean"],
        "median": block["median"],
        "short_avg": block["short_avg"],
        "long_avg": block["long_avg"],
        "pulse": block["pulse"],
        "drift": block["drift"],
        "avg_road_counts": _avg_counts(count_rows),
        "note": DIGIT_NOTE if profile["mode"] == "digit" else SET_NOTE,
        "latest_draw": _latest(draws),
        "special": special,
        "data_status": status,
        "disclaimer": DISCLAIMER,
    }


def _expand(distribution: list[dict]) -> list[int]:
    values: list[int] = []
    for bucket in distribution or []:
        values.extend([int(bucket["imbalance"])] * int(bucket["count"]))
    return values


def _num(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _percent(value: float) -> str:
    text = f"{round(value * 100, 2):.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def _counts_text(counts: dict[str, int]) -> str:
    return f"0路 {counts['0']}、1路 {counts['1']}、2路 {counts['2']}"


def _place(imbalance: int, values: list[int]) -> tuple[float | None, float | None, str | None]:
    if not values:
        return None, None, None
    total = len(values)
    count = sum(item == imbalance for item in values)
    percentile = round(sum(item <= imbalance for item in values) / total, 4)
    typicality = round(count / total, 4)
    max_count = max(Counter(values).values())
    if count > 0 and count == max_count:
        rarity = "common"
    elif count == 0 or percentile <= 0.1 or percentile >= 0.9:
        rarity = "rare"
    else:
        rarity = "typical"
    return percentile, typicality, rarity


def _alignment(imbalance: int, drift: str | None, short_avg: float | None) -> str | None:
    if drift is None or short_avg is None:
        return None
    if drift == "flat":
        return "neutral"
    if drift == "rising":
        return "aligned" if imbalance >= short_avg else "against"
    if drift == "falling":
        return "aligned" if imbalance <= short_avg else "against"
    return None


def _note(imbalance, counts, percentile, typicality, rarity, alignment, short_avg, long_avg, drift) -> str:
    if imbalance is None or counts is None:
        return ""
    parts = [f"路偏度 {imbalance}", _counts_text(counts)]
    if percentile is None:
        parts.append("还没有历史可对照")
    else:
        parts.append(f"历史分位 {_percent(percentile)}")
        parts.append(f"出现率 {_percent(typicality)}")
        parts.append(_RARITY_WORD[rarity])
    if drift == "rising":
        parts.append(f"短窗 {_num(short_avg)} 比长窗 {_num(long_avg)} 更偏")
    elif drift == "falling":
        parts.append(f"短窗 {_num(short_avg)} 比长窗 {_num(long_avg)} 更匀")
    elif drift == "flat":
        parts.append(f"短窗 {_num(short_avg)} 和长窗 {_num(long_avg)} 差不多")
    if alignment == "aligned":
        parts.append("和短窗脉动同向")
    elif alignment == "against":
        parts.append("和短窗脉动反向")
    elif alignment == "neutral":
        parts.append("没有明显顺逆")
    return "，".join(parts) + "。仅供娱乐，不构成投注建议。"


def _empty_ticket() -> dict:
    return {
        "imbalance": None,
        "counts": None,
        "percentile": None,
        "typicality": None,
        "rarity": None,
        "alignment": None,
        "note": "",
    }


def _score_value(counts: dict[str, int] | None, values: list[int], stats: dict | None) -> dict:
    imbalance = _imbalance(counts)
    if counts is None or imbalance is None:
        return _empty_ticket()
    short_avg = None if stats is None else stats.get("short_avg")
    long_avg = None if stats is None else stats.get("long_avg")
    drift = None if stats is None else stats.get("drift")
    percentile, typicality, rarity = _place(imbalance, values)
    alignment = _alignment(imbalance, drift, short_avg)
    return {
        "imbalance": imbalance,
        "counts": counts,
        "percentile": percentile,
        "typicality": typicality,
        "rarity": rarity,
        "alignment": alignment,
        "note": _note(imbalance, counts, percentile, typicality, rarity, alignment, short_avg, long_avg, drift),
    }


def score_road(db: Session, lottery_type: str, main, special=None, limit: int = 80, short: int = 10, long: int = 50) -> dict:
    """对照路偏度分布给一注打分，并说明它和短窗脉动是否同向。"""
    query = normalize_query(lottery_type, main, special)
    summary = road_summary(db, query["lottery_type"], limit=limit, short=short, long=long)
    special_numbers = query["special"]
    if special_numbers:
        special_ticket = _score_value(
            _counts_of(special_numbers),
            _expand((summary["special"] or {}).get("distribution")),
            summary["special"],
        )
    else:
        special_ticket = _empty_ticket()
    return {
        **summary,
        "query": {"main": query["main"], "special": query["special"]},
        "ticket": _score_value(_counts_of(query["main"]), _expand(summary["distribution"]), summary),
        "special_ticket": special_ticket,
    }
