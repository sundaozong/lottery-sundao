"""升平降脉动：相邻两期同位比较后，用升的个数看短窗相对长窗是走高还是走低。

乐透（mode 不是 digit）把两期主号各自去重后升序，按该彩种标准主号个数对齐。
两边都够时只比前 N 位；任一侧短于 N，这一期主号升平降跳过，不占样本。
数字彩按位比较，保留重复和位置，不排序。0 和 9 不绕圈。
当期同位更大为升，相等为平，更小为降。主指标是 rise_count。

特别号不计入主号。有特别号时按同样的升平降另算：乐透特别号升序对齐，
数字彩特别号按位比较。没有特别号的彩种不做 special。

这和「邻号脉动」不同：邻号看的是后几期会不会开出 ±1 的旁号。
这和「重号脉动」不同：重号看的是两期号码重合了几个。
这和「大小脉动」「区位脉动」不同：大小看大号个数，区位看三区配比。
竞品常见的静态升平降走势表只做对照；这里用短窗平均减长窗平均，并给一注打分，等权纳入脉动综合。

近 limit 期（5–200，默认 80）按期号从新到旧读取。空白主号的行会跳过，
不占窗口名额；limit 先限制查询条数，跳过发生在取出之后。
最早一期没有上期，不能计算，也不进入样本。

短窗、长窗用这段里实际算出升的个数的期数求平均，历史更短时不把缺口当成 0。
pulse = 短窗平均 − 长窗平均。pulse >= 0.5 记为走高，<= -0.5 记为走低，其余持平。
short 限制在 5–30（默认 10），long 限制在 20–200（默认 50）；
若 long <= short，把 long 收到 short + 1。

给一注打分时，用候选号相对最新一期开奖算出升的个数，对照历史分布给分位、
出现率和常见 / 居中 / 少见，并说明它跟短窗脉动是同向、反向，还是没有明显顺逆。
特别号单独打分，不并进主号。
只读本地开奖。仅供娱乐，不构成投注建议。
"""
from __future__ import annotations

import statistics
from collections import Counter

from sqlalchemy.orm import Session

from ..lotteries import LOTTERIES, normalize_type, parse_numbers
from ..models import Draw
from .echo import PROFILES, normalize_query

DISCLAIMER = "升平降脉动看主号升的个数的历史分布，以及短窗相对长窗是走高还是走低，仅供娱乐，不构成投注建议。"
DIGIT_NOTE = "按位比较相邻两期，保留重复和位置，不排序。当期位更大为升、相等为平、更小为降。特别号不计入主号。这不是邻号±1，也不是重号个数，也不是大小或区位。"
SET_NOTE = "主号去重后升序，按该彩种主号个数逐位比较。号码不足的期跳过。当期位更大为升、相等为平、更小为降。特别号不计入主号，有特别号时升序另算。这不是邻号±1，也不是重号个数，也不是大小或区位。"
THRESHOLD = 0.5
COMMON_LIMIT = 8

# 标准主号个数、特别号个数。乐透按这个长度对齐；0 表示该彩种没有特别号。
_ALIGN = {
    "ssq": (6, 1),
    "dlt": (5, 2),
    "qlc": (7, 1),
    "kl8": (20, 0),
    "fc3d": (3, 0),
    "pl3": (3, 0),
    "pl5": (5, 0),
    "qxc": (6, 1),
}

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
    if profile is None or lottery not in LOTTERIES or lottery not in _ALIGN:
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


def _prepare(numbers: list[str], mode: str) -> list[str]:
    items = list(numbers or [])
    if mode == "digit":
        return items
    return sorted(_unique(items), key=lambda item: int(item))


def _compare(current: list[str], previous: list[str], mode: str, need: int) -> tuple[int, int, int] | None:
    if need <= 0:
        return None
    cur = _prepare(current, mode)
    prev = _prepare(previous, mode)
    if len(cur) < need or len(prev) < need:
        return None
    rise = flat = fall = 0
    for index in range(need):
        left = int(cur[index])
        right = int(prev[index])
        if left > right:
            rise += 1
        elif left == right:
            flat += 1
        else:
            fall += 1
    return rise, flat, fall


def _pattern(rise: int, flat: int, fall: int) -> str:
    return f"{rise}升{flat}平{fall}降"


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
        {"rise_count": number, "count": counts[number], "rate": round(counts[number] / total, 4)}
        for number in range(slots + 1)
    ]


def _common(triples: list[tuple[int, int, int]]) -> list[dict]:
    if not triples:
        return []
    counts = Counter(triples)
    total = len(triples)
    ranked = sorted(counts, key=lambda item: (-counts[item], item[0], item[1], item[2]))
    return [
        {
            "rise_count": rise,
            "flat_count": flat,
            "fall_count": fall,
            "pattern": _pattern(rise, flat, fall),
            "count": counts[(rise, flat, fall)],
            "rate": round(counts[(rise, flat, fall)] / total, 4),
        }
        for rise, flat, fall in ranked[:COMMON_LIMIT]
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


def _block(values: list[int], triples: list[tuple[int, int, int]], slots: int, short: int, long: int, label: str | None = None) -> dict:
    short_avg, long_avg, pulse, drift = _pulse(values, short, long)
    block = {
        "sample_size": len(values),
        "distribution": _distribution(values, slots),
        "common": _common(triples),
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


def _series(draws: list[dict], mode: str, need: int, special: bool = False) -> tuple[list[int], list[tuple[int, int, int]]]:
    values: list[int] = []
    triples: list[tuple[int, int, int]] = []
    key = "special" if special else "main"
    for index in range(len(draws) - 1):
        parsed = _compare(draws[index][key], draws[index + 1][key], mode, need)
        if parsed is None:
            continue
        values.append(parsed[0])
        triples.append(parsed)
    return values, triples


def _counts(parsed: tuple[int, int, int] | None) -> dict:
    if parsed is None:
        return {
            "rise_count": None,
            "flat_count": None,
            "fall_count": None,
            "pattern": None,
        }
    rise, flat, fall = parsed
    return {
        "rise_count": rise,
        "flat_count": flat,
        "fall_count": fall,
        "pattern": _pattern(rise, flat, fall),
    }


def _latest(draws: list[dict], mode: str, need_main: int, need_special: int) -> dict | None:
    if not draws:
        return None
    head = draws[0]
    main_stats = None
    special_stats = None
    if len(draws) > 1:
        main_stats = _compare(head["main"], draws[1]["main"], mode, need_main)
        if need_special:
            special_stats = _compare(head["special"], draws[1]["special"], mode, need_special)
    main = _counts(main_stats)
    special = _counts(special_stats)
    return {
        "issue": head["issue"],
        "draw_date": head["draw_date"],
        "main": list(head["main"]),
        "special": list(head["special"]),
        "rise_count": main["rise_count"],
        "flat_count": main["flat_count"],
        "fall_count": main["fall_count"],
        "pattern": main["pattern"],
        "special_rise_count": special["rise_count"],
        "special_flat_count": special["flat_count"],
        "special_fall_count": special["fall_count"],
        "special_pattern": special["pattern"],
    }


def shengping_summary(db: Session, lottery_type: str, limit: int = 80, short: int = 10, long: int = 50) -> dict:
    """主号升的个数直方图，以及短窗平均相对长窗平均的脉动。"""
    lottery, profile = _profile(lottery_type)
    limit_n, short_n, long_n = _windows(limit, short, long)
    draws, status = _load(db, lottery, profile, limit_n)
    need_main, need_special = _ALIGN[lottery]
    mode = profile["mode"]
    values, triples = _series(draws, mode, need_main)
    block = _block(values, triples, need_main, short_n, long_n)
    special = None
    if need_special:
        special_values, special_triples = _series(draws, mode, need_special, special=True)
        if special_values:
            special = _block(
                special_values,
                special_triples,
                need_special,
                short_n,
                long_n,
                profile["special_label"],
            )
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
        "latest_draw": _latest(draws, mode, need_main, need_special),
        "special": special,
        "data_status": status,
        "disclaimer": DISCLAIMER,
    }


def _expand(distribution: list[dict] | None) -> list[int]:
    values: list[int] = []
    for bucket in distribution or []:
        values.extend([int(bucket["rise_count"])] * int(bucket["count"]))
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


def _note(rise, flat, fall, percentile, typicality, rarity, alignment, short_avg, long_avg, drift) -> str:
    if rise is None:
        return ""
    head = f"升的个数 {rise}"
    if flat is not None and fall is not None:
        head = f"升的个数 {rise}（{_pattern(rise, flat, fall)}）"
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
        "rise_count": None,
        "flat_count": None,
        "fall_count": None,
        "pattern": None,
        "percentile": None,
        "typicality": None,
        "rarity": None,
        "alignment": None,
        "note": "",
    }


def _score_value(parsed: tuple[int, int, int] | None, values: list[int], stats: dict | None) -> dict:
    if parsed is None:
        return _empty_ticket()
    rise, flat, fall = parsed
    short_avg = None if stats is None else stats.get("short_avg")
    long_avg = None if stats is None else stats.get("long_avg")
    drift = None if stats is None else stats.get("drift")
    percentile, typicality, rarity = _place(rise, values)
    alignment = _alignment(rise, drift, short_avg)
    return {
        "rise_count": rise,
        "flat_count": flat,
        "fall_count": fall,
        "pattern": _pattern(rise, flat, fall),
        "percentile": percentile,
        "typicality": typicality,
        "rarity": rarity,
        "alignment": alignment,
        "note": _note(rise, flat, fall, percentile, typicality, rarity, alignment, short_avg, long_avg, drift),
    }


def score_shengping(db: Session, lottery_type: str, main, special=None, limit: int = 80, short: int = 10, long: int = 50) -> dict:
    """对照升的个数分布给一注打分，并说明它和短窗脉动是否同向。"""
    query = normalize_query(lottery_type, main, special)
    summary = shengping_summary(db, query["lottery_type"], limit=limit, short=short, long=long)
    _lottery, profile = _profile(query["lottery_type"])
    need_main, need_special = _ALIGN[query["lottery_type"]]
    latest = summary["latest_draw"]
    if latest is None:
        ticket = _empty_ticket()
        special_ticket = _empty_ticket()
    else:
        ticket = _score_value(
            _compare(query["main"], latest["main"], profile["mode"], need_main),
            _expand(summary["distribution"]),
            summary,
        )
        if query["special"] and need_special:
            special_ticket = _score_value(
                _compare(query["special"], latest["special"], profile["mode"], need_special),
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
