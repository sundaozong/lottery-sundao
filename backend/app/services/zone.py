"""区位脉动：主号按数值区间分成三区，看个数配比和区位偏度的短长窗升降。

近 limit 期（5–200，默认 80）按期号从新到旧读取。空白主号的行会跳过，
不占窗口名额；limit 先限制查询条数，跳过发生在取出之后。
乐透把主号去重后，按该彩种主号 lo–hi 均分成三区（向上取整，后区可能略短），
特别号不计入主号；有特别号时按特别号自己的 lo–hi 另分三区。
数字彩按整注各位分成 0–3、4–6、7–9，0 和 9 不绕圈；特别号同样按这三档。
区位偏度 = 三区个数的最大减最小。三区比写成「2:1:3」。

短窗、长窗用这段里实际有的期数求平均，历史更短时不把缺口当成偏度 0。
pulse = 短窗平均 − 长窗平均。pulse >= 0.5 记为更偏，<= -0.5 记为更匀，其余持平。
short 限制在 5–30（默认 10），long 限制在 20–200（默认 50）；
若 long <= short，把 long 收到 short + 1。

给一注打分时，对照这份区位偏度分布给出分位、出现率和常见 / 居中 / 少见，
并说明它跟短窗脉动是同向、反向，还是没有明显顺逆。特别号单独打分，不并进主号。
只读本地开奖。号码形态里的静态分区比保持原样。
"""
from __future__ import annotations

import statistics
from collections import Counter

from sqlalchemy.orm import Session

from ..lotteries import LOTTERIES, normalize_type, parse_numbers
from ..models import Draw
from .echo import PROFILES, normalize_query

DISCLAIMER = "区位脉动看主号三区个数配比和区位偏度，以及短窗相对长窗是更偏还是更匀，仅供娱乐，不构成投注建议。"
SET_NOTE = "主号去重后按数值区间分成三区，区位偏度是最多的一区减去最少的一区。特别号不计入主号。"
DIGIT_NOTE = "整注各位数字按 0–3、4–6、7–9 分成低区、中区、高区，0 和 9 不绕圈，区位偏度是最多的一区减去最少的一区。特别号不计入主号。"
THRESHOLD = 0.5
COMMON_LIMIT = 8
ZONE_ORDER = ("1", "2", "3")

_RARITY_WORD = {"common": "常见", "typical": "居中", "rare": "少见"}
_DIGIT_ZONES = (
    ("1", "低区", 0, 3),
    ("2", "中区", 4, 6),
    ("3", "高区", 7, 9),
)
_SET_NAMES = ("一区", "二区", "三区")


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


def _split_range(lo: int, hi: int) -> list[tuple[int, int]]:
    span = hi - lo + 1
    size = (span + 2) // 3
    bounds: list[tuple[int, int]] = []
    start = lo
    for index in range(3):
        end = hi if index == 2 else min(hi, start + size - 1)
        bounds.append((start, end))
        start = end + 1
    return bounds


def _zone_defs(profile: dict, special: bool = False) -> list[dict]:
    if profile["mode"] == "digit":
        bands = _DIGIT_ZONES
    else:
        bounds = profile["special"] if special else profile["main"]
        if not bounds:
            return []
        edges = _split_range(bounds[0], bounds[1])
        bands = tuple((str(index + 1), _SET_NAMES[index], edges[index][0], edges[index][1]) for index in range(3))
    return [{"key": key, "name": name, "lo": lo, "hi": hi} for key, name, lo, hi in bands]


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


def _zone_key(number: int, zones: list[dict]) -> str:
    for zone in zones:
        if zone["lo"] <= number <= zone["hi"]:
            return zone["key"]
    if number < zones[0]["lo"]:
        return zones[0]["key"]
    return zones[-1]["key"]


def _counts_of(numbers: list[str], zones: list[dict]) -> dict[str, int] | None:
    if not numbers or not zones:
        return None
    counts = {zone["key"]: 0 for zone in zones}
    for item in numbers:
        counts[_zone_key(int(item), zones)] += 1
    return counts


def _ratio(counts: dict[str, int] | None) -> str | None:
    if not counts:
        return None
    return ":".join(str(counts[key]) for key in ZONE_ORDER)


def _imbalance(counts: dict[str, int] | None) -> int | None:
    if not counts:
        return None
    values = [counts[key] for key in ZONE_ORDER]
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
    return {key: round(sum(item[key] for item in rows) / total, 4) for key in ZONE_ORDER}


def _distribution(values: list[int]) -> list[dict]:
    if not values:
        return []
    counts = Counter(values)
    total = len(values)
    return [
        {"imbalance": number, "count": counts[number], "rate": round(counts[number] / total, 4)}
        for number in range(min(values), max(values) + 1)
    ]


def _common(rows: list[dict[str, int]]) -> list[dict]:
    if not rows:
        return []
    keyed = [tuple(item[key] for key in ZONE_ORDER) for item in rows]
    counts = Counter(keyed)
    total = len(keyed)
    ranked = sorted(counts, key=lambda item: (-counts[item], item))
    return [
        {
            "zone_counts": {key: item[index] for index, key in enumerate(ZONE_ORDER)},
            "ratio": ":".join(str(part) for part in item),
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


def _block(values: list[int], rows: list[dict[str, int]], short: int, long: int, zones: list[dict], label: str | None = None) -> dict:
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
        "avg_zone_counts": _avg_counts(rows),
        "zones": zones,
    }
    if label is not None:
        block = {"label": label, **block}
    return block


def _series(draws: list[dict], zones: list[dict], special: bool = False) -> tuple[list[int], list[dict[str, int]]]:
    imbalances: list[int] = []
    rows: list[dict[str, int]] = []
    if not zones:
        return imbalances, rows
    for draw in draws:
        numbers = draw["special"] if special else draw["main"]
        if special and not numbers:
            continue
        counts = _counts_of(numbers, zones)
        imbalance = _imbalance(counts)
        if counts is None or imbalance is None:
            continue
        imbalances.append(imbalance)
        rows.append(counts)
    return imbalances, rows


def _latest(draws: list[dict], main_zones: list[dict], special_zones: list[dict]) -> dict | None:
    if not draws:
        return None
    head = draws[0]
    counts = _counts_of(head["main"], main_zones)
    if head["special"] and special_zones:
        special_counts = _counts_of(head["special"], special_zones)
        special_ratio = _ratio(special_counts)
        special_imbalance = _imbalance(special_counts)
    else:
        special_counts = None
        special_ratio = None
        special_imbalance = None
    return {
        "issue": head["issue"],
        "draw_date": head["draw_date"],
        "main": list(head["main"]),
        "special": list(head["special"]),
        "zone_counts": counts,
        "ratio": _ratio(counts),
        "imbalance": _imbalance(counts),
        "special_zone_counts": special_counts,
        "special_ratio": special_ratio,
        "special_imbalance": special_imbalance,
    }


def zone_summary(db: Session, lottery_type: str, limit: int = 80, short: int = 10, long: int = 50) -> dict:
    """主号区位偏度直方图，以及短窗平均相对长窗平均的脉动。"""
    lottery, profile = _profile(lottery_type)
    limit_n, short_n, long_n = _windows(limit, short, long)
    draws, status = _load(db, lottery, profile, limit_n)
    main_zones = _zone_defs(profile)
    special_zones = _zone_defs(profile, special=True) if profile.get("special") else []
    imbalances, count_rows = _series(draws, main_zones)
    block = _block(imbalances, count_rows, short_n, long_n, main_zones)
    special_imbalances, special_rows = _series(draws, special_zones, special=True)
    special = None
    if special_imbalances:
        special = _block(special_imbalances, special_rows, short_n, long_n, special_zones, profile["special_label"])
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
        "avg_zone_counts": block["avg_zone_counts"],
        "zones": main_zones,
        "note": DIGIT_NOTE if profile["mode"] == "digit" else SET_NOTE,
        "latest_draw": _latest(draws, main_zones, special_zones),
        "special": special,
        "data_status": status,
        "disclaimer": DISCLAIMER,
    }


def _expand(distribution: list[dict] | None) -> list[int]:
    values: list[int] = []
    for bucket in distribution or []:
        values.extend([int(bucket["imbalance"])] * int(bucket["count"]))
    return values


def _num(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _percent(value: float) -> str:
    text = f"{round(value * 100, 2):.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


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
    parts = [f"区位偏度 {imbalance}", f"三区比 {_ratio(counts)}"]
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
        "zone_counts": None,
        "ratio": None,
        "imbalance": None,
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
        "zone_counts": counts,
        "ratio": _ratio(counts),
        "imbalance": imbalance,
        "percentile": percentile,
        "typicality": typicality,
        "rarity": rarity,
        "alignment": alignment,
        "note": _note(imbalance, counts, percentile, typicality, rarity, alignment, short_avg, long_avg, drift),
    }


def score_zone(db: Session, lottery_type: str, main, special=None, limit: int = 80, short: int = 10, long: int = 50) -> dict:
    """对照区位偏度分布给一注打分，并说明它和短窗脉动是否同向。"""
    query = normalize_query(lottery_type, main, special)
    summary = zone_summary(db, query["lottery_type"], limit=limit, short=short, long=long)
    special_numbers = query["special"]
    if special_numbers:
        special_zones = (summary["special"] or {}).get("zones")
        if not special_zones:
            _lottery, profile = _profile(query["lottery_type"])
            special_zones = _zone_defs(profile, special=True)
        special_ticket = _score_value(
            _counts_of(special_numbers, special_zones),
            _expand((summary["special"] or {}).get("distribution")),
            summary["special"],
        )
    else:
        special_ticket = _empty_ticket()
    return {
        **summary,
        "query": {"main": query["main"], "special": query["special"]},
        "ticket": _score_value(_counts_of(query["main"], summary["zones"]), _expand(summary["distribution"]), summary),
        "special_ticket": special_ticket,
    }
