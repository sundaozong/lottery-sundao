"""大小脉动：主号大号个数的历史分布，以及短窗相对长窗是走高还是走低。

大号个数 = 主号里「大号」的个数。
乐透按该彩种号码池 [min, max] 的中点 mid = (min + max) // 2：小于等于 mid 为小，大于 mid 为大。
数字彩各位 0–4 为小、5–9 为大，重复数字保留，0 和 9 不绕圈。
特别号不计入主号；特别号自己至少有一个时，按同一规则另算 special 的大号个数。

这和「区位脉动」不同：区位看三区个数配比。
这和「奇偶脉动」不同：奇偶看奇数个数。
号码形态里的静态大小表、以及竞品常见的静态大小比，只做对照；这里用短窗平均减长窗平均看升降，并给一注打分，等权纳入脉动综合。

近 limit 期（5–200，默认 80）按期号从新到旧读取。空白主号的行会跳过，
不占窗口名额；limit 先限制查询条数，跳过发生在取出之后。

短窗、长窗用这段里实际算出大号个数的期数求平均，历史更短时不把缺口当成 0。
pulse = 短窗平均 − 长窗平均。pulse >= 0.5 记为走高，<= -0.5 记为走低，其余持平。
short 限制在 5–30（默认 10），long 限制在 20–200（默认 50）；
若 long <= short，把 long 收到 short + 1。

历史分布按可能的大号个数铺开，从 0 到这段主号个数的最大值。
给一注打分时，对照这份分布给出分位、出现率和常见 / 居中 / 少见，
并说明它跟短窗脉动是同向、反向，还是没有明显顺逆。特别号单独打分，不并进主号。
只读本地开奖。仅供娱乐，不构成投注建议。
"""
from __future__ import annotations

import statistics
from collections import Counter

from sqlalchemy.orm import Session

from ..lotteries import LOTTERIES, normalize_type, parse_numbers
from ..models import Draw
from .echo import PROFILES, normalize_query

DISCLAIMER = "大小脉动看主号大号个数的历史分布，以及短窗相对长窗是走高还是走低，仅供娱乐，不构成投注建议。"
DIGIT_NOTE = "整注各位数字里，0–4 为小、5–9 为大，重复数字保留。特别号不计入主号。这不是三区比，也不是奇偶个数，也不是静态大小表。"
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


def _boundary(profile: dict, special: bool = False) -> dict | None:
    if special and not profile.get("special"):
        return None
    if profile["mode"] == "digit":
        lo, hi = 0, 9
    else:
        bounds = profile["special"] if special else profile["main"]
        lo, hi = int(bounds[0]), int(bounds[1])
    return {"lo": lo, "hi": hi, "mid": (lo + hi) // 2}


def _set_note(boundary: dict) -> str:
    lo, mid, hi = boundary["lo"], boundary["mid"], boundary["hi"]
    return (
        f"主号去重后，{lo}–{mid} 为小、{mid + 1}–{hi} 为大。"
        "特别号不计入主号，有特别号时按它自己的号码池另算。"
        "这不是三区比，也不是奇偶个数，也不是静态大小表。"
    )


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


def _daxiao_of(numbers: list[str], mid: int) -> tuple[int, int] | None:
    if not numbers:
        return None
    big = sum(1 for item in numbers if int(item) > mid)
    return big, len(numbers) - big


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


def _distribution(values: list[int], slots: int) -> list[dict]:
    if not values:
        return []
    counts = Counter(values)
    total = len(values)
    return [
        {"big_count": number, "count": counts[number], "rate": round(counts[number] / total, 4)}
        for number in range(slots + 1)
    ]


def _ratio(big: int, small: int) -> str:
    return f"{big}大{small}小"


def _common(pairs: list[tuple[int, int]]) -> list[dict]:
    if not pairs:
        return []
    counts = Counter(pairs)
    total = len(pairs)
    ranked = sorted(counts, key=lambda pair: (-counts[pair], pair[0], pair[1]))
    return [
        {
            "big_count": big,
            "small_count": small,
            "ratio": _ratio(big, small),
            "count": counts[(big, small)],
            "rate": round(counts[(big, small)] / total, 4),
        }
        for big, small in ranked[:COMMON_LIMIT]
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


def _block(values: list[int], pairs: list[tuple[int, int]], slots: int, short: int, long: int, boundary: dict, label: str | None = None) -> dict:
    short_avg, long_avg, pulse, drift = _pulse(values, short, long)
    block = {
        "sample_size": len(values),
        "distribution": _distribution(values, slots),
        "common": _common(pairs),
        "mean": _avg(values),
        "median": _median(values),
        "short_avg": short_avg,
        "long_avg": long_avg,
        "pulse": pulse,
        "drift": drift,
        "boundary": boundary,
    }
    if label is not None:
        block = {"label": label, **block}
    return block


def _series(draws: list[dict], mid: int, special: bool = False) -> tuple[list[int], list[tuple[int, int]], int]:
    values: list[int] = []
    pairs: list[tuple[int, int]] = []
    slots = 0
    for draw in draws:
        numbers = draw["special"] if special else draw["main"]
        if special and not numbers:
            continue
        parsed = _daxiao_of(numbers, mid)
        if parsed is None:
            continue
        big, small = parsed
        values.append(big)
        pairs.append((big, small))
        slots = max(slots, len(numbers))
    return values, pairs, slots


def _latest(draws: list[dict], main_mid: int, special_mid: int | None) -> dict | None:
    if not draws:
        return None
    head = draws[0]
    big, small = _daxiao_of(head["main"], main_mid)
    if special_mid is not None and head["special"]:
        special_big, special_small = _daxiao_of(head["special"], special_mid)
    else:
        special_big = None
        special_small = None
    return {
        "issue": head["issue"],
        "draw_date": head["draw_date"],
        "main": list(head["main"]),
        "special": list(head["special"]),
        "big_count": big,
        "small_count": small,
        "special_big_count": special_big,
        "special_small_count": special_small,
    }


def daxiao_summary(db: Session, lottery_type: str, limit: int = 80, short: int = 10, long: int = 50) -> dict:
    """主号大号个数直方图，以及短窗平均相对长窗平均的脉动。"""
    lottery, profile = _profile(lottery_type)
    limit_n, short_n, long_n = _windows(limit, short, long)
    draws, status = _load(db, lottery, profile, limit_n)
    boundary = _boundary(profile)
    values, pairs, slots = _series(draws, boundary["mid"])
    block = _block(values, pairs, slots, short_n, long_n, boundary)
    special_boundary = _boundary(profile, special=True)
    special = None
    if special_boundary is not None:
        special_values, special_pairs, special_slots = _series(draws, special_boundary["mid"], special=True)
        if special_values:
            special = _block(
                special_values,
                special_pairs,
                special_slots,
                short_n,
                long_n,
                special_boundary,
                profile["special_label"],
            )
    return {
        "lottery_type": lottery,
        "mode": profile["mode"],
        "basis": "digits" if profile["mode"] == "digit" else "main",
        "sample_size": len(values),
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
        "boundary": boundary,
        "note": DIGIT_NOTE if profile["mode"] == "digit" else _set_note(boundary),
        "latest_draw": _latest(draws, boundary["mid"], None if special_boundary is None else special_boundary["mid"]),
        "special": special,
        "data_status": status,
        "disclaimer": DISCLAIMER,
    }


def _expand(distribution: list[dict] | None) -> list[int]:
    values: list[int] = []
    for bucket in distribution or []:
        values.extend([int(bucket["big_count"])] * int(bucket["count"]))
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


def _note(big, small, percentile, typicality, rarity, alignment, short_avg, long_avg, drift) -> str:
    if big is None:
        return ""
    head = f"大号个数 {big}"
    if small is not None:
        head = f"大号个数 {big}（{_ratio(big, small)}）"
    parts = [head]
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
        "big_count": None,
        "small_count": None,
        "percentile": None,
        "typicality": None,
        "rarity": None,
        "alignment": None,
        "note": "",
    }


def _score_value(big: int | None, small: int | None, values: list[int], stats: dict | None) -> dict:
    if big is None:
        return _empty_ticket()
    short_avg = None if stats is None else stats.get("short_avg")
    long_avg = None if stats is None else stats.get("long_avg")
    drift = None if stats is None else stats.get("drift")
    percentile, typicality, rarity = _place(big, values)
    alignment = _alignment(big, drift, short_avg)
    return {
        "big_count": big,
        "small_count": small,
        "percentile": percentile,
        "typicality": typicality,
        "rarity": rarity,
        "alignment": alignment,
        "note": _note(big, small, percentile, typicality, rarity, alignment, short_avg, long_avg, drift),
    }


def score_daxiao(db: Session, lottery_type: str, main, special=None, limit: int = 80, short: int = 10, long: int = 50) -> dict:
    """对照大号个数分布给一注打分，并说明它和短窗脉动是否同向。"""
    query = normalize_query(lottery_type, main, special)
    summary = daxiao_summary(db, query["lottery_type"], limit=limit, short=short, long=long)
    _lottery, profile = _profile(query["lottery_type"])
    main_pair = _daxiao_of(query["main"], summary["boundary"]["mid"])
    if main_pair is None:
        ticket = _empty_ticket()
    else:
        ticket = _score_value(*main_pair, _expand(summary["distribution"]), summary)
    special_numbers = query["special"]
    special_boundary = (summary["special"] or {}).get("boundary") if summary["special"] else _boundary(profile, special=True)
    if special_numbers and special_boundary:
        special_pair = _daxiao_of(special_numbers, special_boundary["mid"])
        special_ticket = _score_value(
            *(special_pair or (None, None)),
            _expand((summary["special"] or {}).get("distribution")),
            summary["special"],
        )
    else:
        special_ticket = _empty_ticket()
    return {
        **summary,
        "query": {"main": query["main"], "special": query["special"]},
        "ticket": ticket,
        "special_ticket": special_ticket,
    }
