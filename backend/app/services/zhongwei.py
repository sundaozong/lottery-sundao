"""中位数脉动：主号中位数的历史分布，以及短窗相对长窗是走高还是走低。

中位数 = 主号的中位数，用 Python statistics.median：奇数个取正中间，
偶数个取中间两数的平均。乐透先去重再取中位数，重复只算一次，票面不排序；
数字彩按抽出的各位取中位数，保留重复和位置，不排序。特别号不并进主号。
有特别号的彩种按同样规则另算特别号中位数：乐透去重后取中位数，数字彩按位取。
没有特别号则不做 special。

这和「均值」不同：均值是算术平均，极端号会把均值拉开，中位数更抗极端号。
这和「和值」不同：和值是主号相加的总和。
这和「和尾」不同：和尾是总和的个位。
这和「跨度」不同：跨度是同一期内最大号减最小号。
这和「区位」不同：区位看的是三区个数。
这和「大小」不同：大小看的是大号个数。
竞品常见的静态中位数、平均值表只做对照；这里用短窗中位数平均减长窗中位数平均，
并给一注打分，等权纳入脉动综合。

近 limit 期（5–200，默认 80）按期号从新到旧读取。空白主号的行会跳过，
不占窗口名额；limit 先限制查询条数，跳过发生在取出之后。

票面和直方图上的中位数保留两位小数。短窗、长窗、总平均、中位和脉动用未舍入的
中位数再保留四位，避免两位舍入把门槛附近的升降挪档。
数字彩不同中位数不多，直方图只列四舍五入后的精确键。
乐透同样先保留两位；最大键与最小键相差不超过 1 时，按 0.01 补上细桶，
否则只列出出现过的键，避免空洞把直方图撑满。

短窗、长窗用这段里实际有中位数的期数求平均，历史更短时不把缺口当成 0。
pulse = 短窗中位数平均 − 长窗中位数平均。pulse >= 0.5 记为走高，<= -0.5 记为走低，其余持平。
数字彩的中位数落在 0–9，0.5 大约是半个数字，仍然沿用同一阈值，不另设更小门槛，
这样和均值、和值、和尾、振幅等模块的走高走低口径一致。
short 限制在 5–30（默认 10），long 限制在 20–200（默认 50）；
若 long <= short，把 long 收到 short + 1。

给一注打分时，对照这份中位数分布给出分位、出现率和常见 / 居中 / 少见，
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

DISCLAIMER = "中位数脉动看主号中位数的历史分布，以及短窗相对长窗是走高还是走低，仅供娱乐，不构成投注建议。"
SET_NOTE = "主号去重后取中位数，重复只算一次。偶数个取中间两数的平均。中位数保留两位小数；相差不超过 1 时按 0.01 补细桶，否则只列出出现过的中位数。阈值是 0.5。特别号不计入主号，有特别号时去重后另算。这不是均值，也不是和值，也不是和尾，也不是跨度，也不是区位，也不是大小。"
DIGIT_NOTE = "整注各位数字取中位数，保留重复和位置，不排序。偶数个取中间两数的平均。中位数保留两位小数；短窗、长窗和脉动用更高精度。阈值仍是 0.5，和其它脉动一致，不因数字彩 0–9 而缩小。特别号不计入主号，有特别号时按位另算。这不是均值，也不是和值，也不是和尾，也不是跨度，也不是区位，也不是大小。"
THRESHOLD = 0.5
COMMON_LIMIT = 8
DISPLAY_PLACES = 2
FINE_SPAN = 1.0

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


def _display(value: float) -> float:
    return round(float(value) + 1e-12, DISPLAY_PLACES)


def _median_of(numbers: list[str], mode: str) -> float | None:
    items = list(numbers or [])
    if mode != "digit":
        items = _unique(items)
    if not items:
        return None
    return float(statistics.median([int(item) for item in items]))


def _load(db: Session, lottery: str, profile: dict, limit: int) -> tuple[list[dict], str]:
    rows = (
        db.query(Draw)
        .filter(Draw.lottery_type == lottery)
        .order_by(Draw.issue.desc())
        .limit(limit)
        .all()
    )
    width = profile["width"]
    mode = profile["mode"]
    draws: list[dict] = []
    for row in rows:
        parsed = parse_numbers(row.numbers)
        main = _history_group(parsed["main"], width)
        if mode != "digit":
            main = _unique(main)
        if not main:
            continue
        special = _history_group(parsed["special"], width)
        if mode != "digit":
            special = _unique(special)
        exact = _median_of(main, mode)
        special_exact = _median_of(special, mode) if profile["special"] is not None and special else None
        draws.append(
            {
                "issue": row.issue,
                "draw_date": row.draw_date or "",
                "main": main,
                "special": special,
                "median_exact": exact,
                "median_value": None if exact is None else _display(exact),
                "special_exact": special_exact,
                "special_median_value": None if special_exact is None else _display(special_exact),
                "source": row.source or "seed",
            }
        )
    status = "mixed" if any(item["source"] == "crawl" for item in draws) else "seed"
    return draws, status


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _median(values: list[float]):
    if not values:
        return None
    return round(float(statistics.median(values)), 4)


def _keys(rounded: list[float], mode: str) -> list[float]:
    if not rounded:
        return []
    counts = Counter(rounded)
    if mode == "digit":
        return sorted(counts)
    lo = min(counts)
    hi = max(counts)
    start = int(round(lo * 100))
    end = int(round(hi * 100))
    if end - start <= int(round(FINE_SPAN * 100)):
        return [cents / 100 for cents in range(start, end + 1)]
    return sorted(counts)


def _distribution(values: list[float], mode: str) -> list[dict]:
    if not values:
        return []
    rounded = [_display(value) for value in values]
    counts = Counter(rounded)
    total = len(rounded)
    return [
        {
            "median_value": key,
            "count": counts.get(key, 0),
            "rate": round(counts.get(key, 0) / total, 4),
        }
        for key in _keys(rounded, mode)
    ]


def _common(values: list[float]) -> list[dict]:
    if not values:
        return []
    counts = Counter(_display(value) for value in values)
    total = len(values)
    ranked = sorted(counts, key=lambda number: (-counts[number], number))
    return [
        {"median_value": number, "count": counts[number], "rate": round(counts[number] / total, 4)}
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


def _pulse(values: list[float], short: int, long: int) -> tuple[float | None, float | None, float | None, str | None]:
    short_avg = _avg(values[:short])
    long_avg = _avg(values[:long])
    if short_avg is None or long_avg is None:
        return None, None, None, None
    pulse = round(short_avg - long_avg, 4)
    return short_avg, long_avg, pulse, _drift(pulse)


def _block(values: list[float], mode: str, short: int, long: int, label: str | None = None) -> dict:
    short_avg, long_avg, pulse, drift = _pulse(values, short, long)
    block = {
        "sample_size": len(values),
        "distribution": _distribution(values, mode),
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
    return {
        "issue": head["issue"],
        "draw_date": head["draw_date"],
        "main": list(head["main"]),
        "special": list(head["special"]),
        "median_value": head["median_value"],
        "special_median_value": head["special_median_value"],
    }


def zhongwei_summary(db: Session, lottery_type: str, limit: int = 80, short: int = 10, long: int = 50) -> dict:
    """主号中位数直方图，以及短窗平均相对长窗平均的脉动。"""
    lottery, profile = _profile(lottery_type)
    limit_n, short_n, long_n = _windows(limit, short, long)
    draws, status = _load(db, lottery, profile, limit_n)
    mode = profile["mode"]
    values = [draw["median_exact"] for draw in draws if draw["median_exact"] is not None]
    block = _block(values, mode, short_n, long_n)
    special = None
    if profile["special"] is not None:
        special_values = [draw["special_exact"] for draw in draws if draw["special_exact"] is not None]
        if special_values:
            special = _block(special_values, mode, short_n, long_n, profile["special_label"])
    return {
        "lottery_type": lottery,
        "mode": mode,
        "basis": "digits" if mode == "digit" else "main",
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
        "note": DIGIT_NOTE if mode == "digit" else SET_NOTE,
        "latest_draw": _latest(draws),
        "special": special,
        "data_status": status,
        "disclaimer": DISCLAIMER,
    }


def _expand(distribution: list[dict] | None) -> list[float]:
    values: list[float] = []
    for bucket in distribution or []:
        values.extend([float(bucket["median_value"])] * int(bucket["count"]))
    return values


def _num(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _percent(value: float) -> str:
    text = f"{round(value * 100, 2):.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def _place(total: float, values: list[float]) -> tuple[float | None, float | None, str | None]:
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


def _alignment(total: float, drift: str | None, short_avg: float | None) -> str | None:
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
    parts = [f"中位数 {_num(total)}"]
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
        "median_value": None,
        "percentile": None,
        "typicality": None,
        "rarity": None,
        "alignment": None,
        "note": "",
    }


def _score_value(total: float | None, values: list[float], stats: dict | None) -> dict:
    if total is None:
        return _empty_ticket()
    short_avg = None if stats is None else stats.get("short_avg")
    long_avg = None if stats is None else stats.get("long_avg")
    drift = None if stats is None else stats.get("drift")
    percentile, typicality, rarity = _place(total, values)
    alignment = _alignment(total, drift, short_avg)
    return {
        "median_value": total,
        "percentile": percentile,
        "typicality": typicality,
        "rarity": rarity,
        "alignment": alignment,
        "note": _note(total, percentile, typicality, rarity, alignment, short_avg, long_avg, drift),
    }


def score_zhongwei(db: Session, lottery_type: str, main, special=None, limit: int = 80, short: int = 10, long: int = 50) -> dict:
    """对照中位数分布给一注打分，并说明它和短窗脉动是否同向。"""
    query = normalize_query(lottery_type, main, special)
    summary = zhongwei_summary(db, query["lottery_type"], limit=limit, short=short, long=long)
    _lottery, profile = _profile(query["lottery_type"])
    mode = profile["mode"]
    ticket = _score_value(_display_or_none(_median_of(query["main"], mode)), _expand(summary["distribution"]), summary)
    if query["special"] and profile["special"] is not None:
        special_ticket = _score_value(
            _display_or_none(_median_of(query["special"], mode)),
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


def _display_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return _display(value)
