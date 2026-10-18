"""尾数脉动：主号不重复个位的种类数，以及短窗相对长窗是更散还是更集中。

近 limit 期（5–200，默认 80）按期号从新到旧读取。空白主号的行会跳过，
不占窗口名额；limit 先限制查询条数，跳过发生在取出之后。
乐透把主号去重后，取每位的个位（23→3）。同一尾数的不同号码只算一种。
数字彩各位本身就是尾数，重复数字不另计，0 和 9 不绕圈。
特别号单独取个位，不并进主号；七星彩特别号若超过 9，也只看个位。

尾数种类 = 不重复的个位个数。这不是除以 3 的余数，不是数值区间，也不是跨度或和值。

短窗、长窗用这段里实际有的期数求平均，历史更短时不把缺口当成种类数 0。
pulse = 短窗平均 − 长窗平均。pulse >= 0.5 记为更散，<= -0.5 记为更集中，其余持平。
short 限制在 5–30（默认 10），long 限制在 20–200（默认 50）；
若 long <= short，把 long 收到 short + 1。

给一注打分时，对照这份尾数种类分布给出分位、出现率和常见 / 居中 / 少见，
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

DISCLAIMER = "尾数脉动看主号不重复尾数的种类数，以及短窗相对长窗是更散还是更集中，仅供娱乐，不构成投注建议。"
SET_NOTE = "主号去重后取每位的个位，尾数种类是不重复的个位个数。同一尾数只算一种，0 和 9 不绕圈。特别号不计入主号。"
DIGIT_NOTE = "整注各位数字本身就是尾数，尾数种类是不重复的数字个数，0 和 9 不绕圈。特别号不计入主号。"
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


def _tails_of(numbers: list[str]) -> tuple[list[str], str, int] | None:
    if not numbers:
        return None
    tails = sorted({str(int(item) % 10) for item in numbers}, key=int)
    return tails, ",".join(tails), len(tails)


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
        {"unique_tail_count": number, "count": counts[number], "rate": round(counts[number] / total, 4)}
        for number in range(min(values), max(values) + 1)
    ]


def _common(rows: list[tuple[list[str], str, int]]) -> list[dict]:
    if not rows:
        return []
    keyed = [tuple(int(digit) for digit in tails) for tails, _pattern, _count in rows]
    counts = Counter(keyed)
    total = len(keyed)
    ranked = sorted(counts, key=lambda item: (-counts[item], item))
    return [
        {
            "tails": [str(digit) for digit in item],
            "pattern": ",".join(str(digit) for digit in item),
            "unique_tail_count": len(item),
            "count": counts[item],
            "rate": round(counts[item] / total, 4),
        }
        for item in ranked[:COMMON_LIMIT]
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


def _block(values: list[int], rows: list[tuple[list[str], str, int]], short: int, long: int, label: str | None = None) -> dict:
    short_avg, long_avg, pulse, drift = _pulse(values, short, long)
    block = {
        "sample_size": len(values),
        "distribution": _distribution(values),
        "common": _common(rows),
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


def _series(draws: list[dict], special: bool = False) -> tuple[list[int], list[tuple[list[str], str, int]]]:
    values: list[int] = []
    rows: list[tuple[list[str], str, int]] = []
    for draw in draws:
        numbers = draw["special"] if special else draw["main"]
        if special and not numbers:
            continue
        parsed = _tails_of(numbers)
        if parsed is None:
            continue
        _tails, _pattern, count = parsed
        values.append(count)
        rows.append(parsed)
    return values, rows


def _latest(draws: list[dict]) -> dict | None:
    if not draws:
        return None
    head = draws[0]
    tails, pattern, count = _tails_of(head["main"])
    if head["special"]:
        special_tails, special_pattern, special_count = _tails_of(head["special"])
    else:
        special_tails = None
        special_pattern = None
        special_count = None
    return {
        "issue": head["issue"],
        "draw_date": head["draw_date"],
        "main": list(head["main"]),
        "special": list(head["special"]),
        "tails": tails,
        "pattern": pattern,
        "unique_tail_count": count,
        "special_tails": special_tails,
        "special_pattern": special_pattern,
        "special_unique_tail_count": special_count,
    }


def tail_summary(db: Session, lottery_type: str, limit: int = 80, short: int = 10, long: int = 50) -> dict:
    """主号尾数种类直方图，以及短窗平均相对长窗平均的脉动。"""
    lottery, profile = _profile(lottery_type)
    limit_n, short_n, long_n = _windows(limit, short, long)
    draws, status = _load(db, lottery, profile, limit_n)
    values, rows = _series(draws)
    block = _block(values, rows, short_n, long_n)
    special_values, special_rows = _series(draws, special=True)
    special = _block(special_values, special_rows, short_n, long_n, profile["special_label"]) if special_values else None
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


def _expand(distribution: list[dict] | None) -> list[int]:
    values: list[int] = []
    for bucket in distribution or []:
        values.extend([int(bucket["unique_tail_count"])] * int(bucket["count"]))
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


def _spoken(tails: list[str]) -> str:
    return "、".join(tails)


def _note(count, tails, percentile, typicality, rarity, alignment, short_avg, long_avg, drift) -> str:
    if count is None or tails is None:
        return ""
    parts = [f"尾数种类 {count}", f"尾数组合 {_spoken(tails)}"]
    if percentile is None:
        parts.append("还没有历史可对照")
    else:
        parts.append(f"历史分位 {_percent(percentile)}")
        parts.append(f"出现率 {_percent(typicality)}")
        parts.append(_RARITY_WORD[rarity])
    if drift == "rising":
        parts.append(f"短窗 {_num(short_avg)} 比长窗 {_num(long_avg)} 更散")
    elif drift == "falling":
        parts.append(f"短窗 {_num(short_avg)} 比长窗 {_num(long_avg)} 更集中")
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
        "tails": None,
        "pattern": None,
        "unique_tail_count": None,
        "percentile": None,
        "typicality": None,
        "rarity": None,
        "alignment": None,
        "note": "",
    }


def _score_value(parsed: tuple[list[str], str, int] | None, values: list[int], stats: dict | None) -> dict:
    if parsed is None:
        return _empty_ticket()
    tails, pattern, count = parsed
    short_avg = None if stats is None else stats.get("short_avg")
    long_avg = None if stats is None else stats.get("long_avg")
    drift = None if stats is None else stats.get("drift")
    percentile, typicality, rarity = _place(count, values)
    alignment = _alignment(count, drift, short_avg)
    return {
        "tails": tails,
        "pattern": pattern,
        "unique_tail_count": count,
        "percentile": percentile,
        "typicality": typicality,
        "rarity": rarity,
        "alignment": alignment,
        "note": _note(count, tails, percentile, typicality, rarity, alignment, short_avg, long_avg, drift),
    }


def score_tail(db: Session, lottery_type: str, main, special=None, limit: int = 80, short: int = 10, long: int = 50) -> dict:
    """对照尾数种类分布给一注打分，并说明它和短窗脉动是否同向。"""
    query = normalize_query(lottery_type, main, special)
    summary = tail_summary(db, query["lottery_type"], limit=limit, short=short, long=long)
    special_numbers = query["special"]
    if special_numbers:
        special_ticket = _score_value(
            _tails_of(special_numbers),
            _expand((summary["special"] or {}).get("distribution")),
            summary["special"],
        )
    else:
        special_ticket = _empty_ticket()
    return {
        **summary,
        "query": {"main": query["main"], "special": query["special"]},
        "ticket": _score_value(_tails_of(query["main"]), _expand(summary["distribution"]), summary),
        "special_ticket": special_ticket,
    }
