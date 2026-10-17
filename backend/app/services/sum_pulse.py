"""和值脉动：主号和值的历史分布，以及短窗相对长窗是走高还是走低。

近 limit 期（5–200，默认 80）按期号从新到旧读取。空白主号的行会跳过，
不占窗口名额；limit 先限制查询条数，跳过发生在取出之后。
和值 = 号码相加。乐透看主号集合，特别号不计入；一期里有至少两个
特别号时，另计 special 和值，否则省略。数字彩看整注各位数字，0 和 9 不绕圈。

短窗、长窗用这段里实际有的期数求平均，历史更短时不把缺口当成和值 0。
pulse = 短窗平均 − 长窗平均。pulse >= 0.5 记为走高，<= -0.5 记为走低，其余持平。
short 限制在 5–30（默认 10），long 限制在 20–200（默认 50）；
若 long <= short，把 long 收到 short + 1。

给一注打分时，对照这份和值分布给出分位、出现率和常见 / 居中 / 少见，
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

DISCLAIMER = "和值脉动看主号和值的历史分布，以及短窗相对长窗是走高还是走低，仅供娱乐，不构成投注建议。"
SET_NOTE = "主号集合里各号相加，特别号不计入。"
DIGIT_NOTE = "整注各位数字相加，0 和 9 不绕圈，特别号不计入主号和值。"
THRESHOLD = 0.5
COMMON_LIMIT = 8

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


def _sum_of(numbers: list[str]) -> int | None:
    if not numbers:
        return None
    return sum(int(item) for item in numbers)


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


def _distribution(values: list[int]) -> list[dict]:
    if not values:
        return []
    counts = Counter(values)
    total = len(values)
    return [
        {"sum": number, "count": counts[number], "rate": round(counts[number] / total, 4)}
        for number in range(min(values), max(values) + 1)
    ]


def _common(values: list[int]) -> list[dict]:
    if not values:
        return []
    counts = Counter(values)
    total = len(values)
    ranked = sorted(counts, key=lambda number: (-counts[number], number))
    return [
        {"sum": number, "count": counts[number], "rate": round(counts[number] / total, 4)}
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


def _latest(draws: list[dict]) -> dict | None:
    if not draws:
        return None
    head = draws[0]
    special_sum = _sum_of(head["special"]) if len(head["special"]) >= 2 else None
    return {
        "issue": head["issue"],
        "draw_date": head["draw_date"],
        "main": list(head["main"]),
        "special": list(head["special"]),
        "sum": _sum_of(head["main"]),
        "special_sum": special_sum,
    }


def _special_values(draws: list[dict]) -> list[int]:
    values: list[int] = []
    for draw in draws:
        if len(draw["special"]) < 2:
            continue
        total = _sum_of(draw["special"])
        if total is not None:
            values.append(total)
    return values


def sum_summary(db: Session, lottery_type: str, limit: int = 80, short: int = 10, long: int = 50) -> dict:
    """主号和值直方图，以及短窗平均相对长窗平均的脉动。"""
    lottery, profile = _profile(lottery_type)
    limit_n, short_n, long_n = _windows(limit, short, long)
    draws, status = _load(db, lottery, profile, limit_n)
    values = [total for total in (_sum_of(draw["main"]) for draw in draws) if total is not None]
    block = _block(values, short_n, long_n)
    special_values = _special_values(draws)
    special = _block(special_values, short_n, long_n, profile["special_label"]) if special_values else None
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
        "note": DIGIT_NOTE if profile["mode"] == "digit" else SET_NOTE,
        "latest_draw": _latest(draws),
        "special": special,
        "data_status": status,
        "disclaimer": DISCLAIMER,
    }


def _expand(distribution: list[dict]) -> list[int]:
    values: list[int] = []
    for bucket in distribution or []:
        values.extend([int(bucket["sum"])] * int(bucket["count"]))
    return values


def _num(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _percent(value: float) -> str:
    text = f"{round(value * 100, 2):.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def _place(total: int, values: list[int]) -> tuple[float | None, float | None, str | None]:
    if not values:
        return None, None, None
    count = sum(item == total for item in values)
    length = len(values)
    percentile = round(sum(item <= total for item in values) / length, 4)
    typicality = round(count / length, 4)
    max_count = max(Counter(values).values())
    if count > 0 and count == max_count:
        rarity = "common"
    elif count == 0 or percentile <= 0.1 or percentile >= 0.9:
        rarity = "rare"
    else:
        rarity = "typical"
    return percentile, typicality, rarity


def _alignment(total: int, drift: str | None, short_avg: float | None) -> str | None:
    if drift is None or short_avg is None:
        return None
    if drift == "flat":
        return "neutral"
    if drift == "rising":
        return "aligned" if total >= short_avg else "against"
    if drift == "falling":
        return "aligned" if total <= short_avg else "against"
    return None


def _note(total, percentile, typicality, rarity, alignment, short_avg, long_avg, drift) -> str:
    if total is None:
        return ""
    parts = [f"和值 {total}"]
    if percentile is None:
        parts.append("还没有历史可对照")
    else:
        parts.append(f"历史分位 {_percent(percentile)}")
        parts.append(f"出现率 {_percent(typicality)}")
        parts.append(_RARITY_WORD[rarity])
    if drift == "rising":
        parts.append(f"短窗 {_num(short_avg)} 比长窗 {_num(long_avg)} 走高")
    elif drift == "falling":
        parts.append(f"短窗 {_num(short_avg)} 比长窗 {_num(long_avg)} 走低")
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
        "sum": None,
        "percentile": None,
        "typicality": None,
        "rarity": None,
        "alignment": None,
        "note": "",
    }


def _score_value(total: int | None, values: list[int], stats: dict | None) -> dict:
    if total is None:
        return _empty_ticket()
    short_avg = None if stats is None else stats.get("short_avg")
    long_avg = None if stats is None else stats.get("long_avg")
    drift = None if stats is None else stats.get("drift")
    percentile, typicality, rarity = _place(total, values)
    alignment = _alignment(total, drift, short_avg)
    return {
        "sum": total,
        "percentile": percentile,
        "typicality": typicality,
        "rarity": rarity,
        "alignment": alignment,
        "note": _note(total, percentile, typicality, rarity, alignment, short_avg, long_avg, drift),
    }


def score_sum(db: Session, lottery_type: str, main, special=None, limit: int = 80, short: int = 10, long: int = 50) -> dict:
    """对照和值分布给一注打分，并说明它和短窗脉动是否同向。"""
    query = normalize_query(lottery_type, main, special)
    summary = sum_summary(db, query["lottery_type"], limit=limit, short=short, long=long)
    special_numbers = query["special"]
    if len(special_numbers) >= 2:
        special_ticket = _score_value(
            _sum_of(special_numbers),
            _expand((summary["special"] or {}).get("distribution")),
            summary["special"],
        )
    else:
        special_ticket = _empty_ticket()
    return {
        **summary,
        "query": {"main": query["main"], "special": query["special"]},
        "ticket": _score_value(_sum_of(query["main"]), _expand(summary["distribution"]), summary),
        "special_ticket": special_ticket,
    }
