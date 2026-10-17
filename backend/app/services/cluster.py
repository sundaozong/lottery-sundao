"""连号簇脉动：主号连号簇最长长度的历史分布，以及短窗相对长窗是变长还是变短。

近 limit 期（5–200，默认 80）按期号从新到旧读取。空白主号的行会跳过，
不占窗口名额；limit 先限制查询条数，跳过发生在取出之后。
乐透把主号去重后排序，相邻差为 1 的极大连续段且长度至少为 2 算一簇。
没有这样的簇时，最长簇记为 1，便于和「有连号」放在同一张直方图里。
数字彩按位从左到右，相邻位数值差为 1 算连号，0 和 9 不绕圈。
特别号不并入主号；一期里有至少两个特别号时，另按同样规则计 special，否则省略。

短窗、长窗用这段里实际有的期数求平均，历史更短时不把缺口当成最长簇 0。
主脉动看最长簇：pulse = 短窗平均 − 长窗平均。
pulse >= 0.5 记为变长，<= -0.5 记为变短，其余持平。
簇个数另给一份短窗、长窗和脉动，不参与主打分。
short 限制在 5–30（默认 10），long 限制在 20–200（默认 50）；
若 long <= short，把 long 收到 short + 1。

给一注打分时，对照这份最长簇分布给出分位、出现率和常见 / 居中 / 少见，
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

DISCLAIMER = "连号簇脉动看主号连号簇最长长度的历史分布，以及短窗相对长窗是变长还是变短，仅供娱乐，不构成投注建议。"
SET_NOTE = "主号去重排序后，相邻差为 1 的极大连续段且长度至少为 2 算一簇；没有连号时最长簇记为 1。特别号不并入主号。"
DIGIT_NOTE = "按位从左到右，相邻位数值差为 1 的极大连续段且长度至少为 2 算一簇，0 和 9 不绕圈；没有连号时最长簇记为 1。特别号不并入主号。"
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


def _cluster_lengths(values: list[int]) -> list[int]:
    """相邻差绝对值为 1 的极大连续段，长度至少为 2。"""
    lengths: list[int] = []
    run = 1
    for prev, curr in zip(values, values[1:]):
        if abs(curr - prev) == 1:
            run += 1
            continue
        if run >= 2:
            lengths.append(run)
        run = 1
    if run >= 2:
        lengths.append(run)
    return lengths


def _measure(numbers: list[str], ordered: bool) -> tuple[int, int] | None:
    """返回 (最长簇, 簇个数)。没有长度 ≥2 的簇时，最长簇记为 1、簇个数为 0。"""
    if not numbers:
        return None
    if ordered:
        values = [int(item) for item in numbers]
    else:
        values = sorted({int(item) for item in numbers})
    if not values:
        return None
    lengths = _cluster_lengths(values)
    if not lengths:
        return 1, 0
    return max(lengths), len(lengths)


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


def _distribution(values: list[int], key: str) -> list[dict]:
    if not values:
        return []
    counts = Counter(values)
    total = len(values)
    return [
        {key: number, "count": counts[number], "rate": round(counts[number] / total, 4)}
        for number in range(min(values), max(values) + 1)
    ]


def _common(values: list[int], key: str) -> list[dict]:
    if not values:
        return []
    counts = Counter(values)
    total = len(values)
    ranked = sorted(counts, key=lambda number: (-counts[number], number))
    return [
        {key: number, "count": counts[number], "rate": round(counts[number] / total, 4)}
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


def _block(values: list[int], short: int, long: int, key: str, label: str | None = None) -> dict:
    short_avg, long_avg, pulse, drift = _pulse(values, short, long)
    block = {
        "sample_size": len(values),
        "distribution": _distribution(values, key),
        "common": _common(values, key),
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


def _series(draws: list[dict], ordered: bool, special: bool = False) -> tuple[list[int], list[int]]:
    lengths: list[int] = []
    counts: list[int] = []
    for draw in draws:
        numbers = draw["special"] if special else draw["main"]
        if special and len(numbers) < 2:
            continue
        measured = _measure(numbers, ordered)
        if measured is None:
            continue
        lengths.append(measured[0])
        counts.append(measured[1])
    return lengths, counts


def _latest(draws: list[dict], ordered: bool) -> dict | None:
    if not draws:
        return None
    head = draws[0]
    measured = _measure(head["main"], ordered)
    max_len, clusters = measured if measured is not None else (None, None)
    if len(head["special"]) >= 2:
        special_measured = _measure(head["special"], ordered)
        special_max_len, special_clusters = special_measured if special_measured is not None else (None, None)
    else:
        special_max_len, special_clusters = None, None
    return {
        "issue": head["issue"],
        "draw_date": head["draw_date"],
        "main": list(head["main"]),
        "special": list(head["special"]),
        "max_len": max_len,
        "clusters": clusters,
        "special_max_len": special_max_len,
        "special_clusters": special_clusters,
    }


def cluster_summary(db: Session, lottery_type: str, limit: int = 80, short: int = 10, long: int = 50) -> dict:
    """主号最长连号簇的直方图，以及短窗平均相对长窗平均的脉动。"""
    lottery, profile = _profile(lottery_type)
    limit_n, short_n, long_n = _windows(limit, short, long)
    ordered = profile["mode"] == "digit"
    draws, status = _load(db, lottery, profile, limit_n)
    lengths, counts = _series(draws, ordered)
    block = _block(lengths, short_n, long_n, "max_len")
    special_lengths, special_counts = _series(draws, ordered, special=True)
    special = None
    if special_lengths:
        special = _block(special_lengths, short_n, long_n, "max_len", profile["special_label"])
        special["cluster_counts"] = _block(special_counts, short_n, long_n, "clusters")
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
        "cluster_counts": _block(counts, short_n, long_n, "clusters"),
        "note": DIGIT_NOTE if profile["mode"] == "digit" else SET_NOTE,
        "latest_draw": _latest(draws, ordered),
        "special": special,
        "data_status": status,
        "disclaimer": DISCLAIMER,
    }


def _expand(distribution: list[dict]) -> list[int]:
    values: list[int] = []
    for bucket in distribution or []:
        values.extend([int(bucket["max_len"])] * int(bucket["count"]))
    return values


def _num(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _percent(value: float) -> str:
    text = f"{round(value * 100, 2):.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def _place(max_len: int, values: list[int]) -> tuple[float | None, float | None, str | None]:
    if not values:
        return None, None, None
    total = len(values)
    count = sum(item == max_len for item in values)
    percentile = round(sum(item <= max_len for item in values) / total, 4)
    typicality = round(count / total, 4)
    max_count = max(Counter(values).values())
    if count > 0 and count == max_count:
        rarity = "common"
    elif count == 0 or percentile <= 0.1 or percentile >= 0.9:
        rarity = "rare"
    else:
        rarity = "typical"
    return percentile, typicality, rarity


def _alignment(max_len: int, drift: str | None, short_avg: float | None) -> str | None:
    if drift is None or short_avg is None:
        return None
    if drift == "flat":
        return "neutral"
    if drift == "rising":
        return "aligned" if max_len >= short_avg else "against"
    if drift == "falling":
        return "aligned" if max_len <= short_avg else "against"
    return None


def _note(max_len, clusters, percentile, typicality, rarity, alignment, short_avg, long_avg, drift) -> str:
    if max_len is None:
        return ""
    parts = [f"最长簇 {max_len}"]
    if clusters is not None:
        parts.append(f"{clusters} 个簇")
    if percentile is None:
        parts.append("还没有历史可对照")
    else:
        parts.append(f"历史分位 {_percent(percentile)}")
        parts.append(f"出现率 {_percent(typicality)}")
        parts.append(_RARITY_WORD[rarity])
    if drift == "rising":
        parts.append(f"短窗 {_num(short_avg)} 比长窗 {_num(long_avg)} 变长")
    elif drift == "falling":
        parts.append(f"短窗 {_num(short_avg)} 比长窗 {_num(long_avg)} 变短")
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
        "max_len": None,
        "clusters": None,
        "percentile": None,
        "typicality": None,
        "rarity": None,
        "alignment": None,
        "note": "",
    }


def _score_value(measured: tuple[int, int] | None, values: list[int], stats: dict | None) -> dict:
    if measured is None:
        return _empty_ticket()
    max_len, clusters = measured
    short_avg = None if stats is None else stats.get("short_avg")
    long_avg = None if stats is None else stats.get("long_avg")
    drift = None if stats is None else stats.get("drift")
    percentile, typicality, rarity = _place(max_len, values)
    alignment = _alignment(max_len, drift, short_avg)
    return {
        "max_len": max_len,
        "clusters": clusters,
        "percentile": percentile,
        "typicality": typicality,
        "rarity": rarity,
        "alignment": alignment,
        "note": _note(max_len, clusters, percentile, typicality, rarity, alignment, short_avg, long_avg, drift),
    }


def score_cluster(db: Session, lottery_type: str, main, special=None, limit: int = 80, short: int = 10, long: int = 50) -> dict:
    """对照最长簇分布给一注打分，并说明它和短窗脉动是否同向。"""
    query = normalize_query(lottery_type, main, special)
    summary = cluster_summary(db, query["lottery_type"], limit=limit, short=short, long=long)
    ordered = query["mode"] == "digit"
    special_numbers = query["special"]
    if len(special_numbers) >= 2:
        special_ticket = _score_value(
            _measure(special_numbers, ordered),
            _expand((summary["special"] or {}).get("distribution")),
            summary["special"],
        )
    else:
        special_ticket = _empty_ticket()
    return {
        **summary,
        "query": {"main": query["main"], "special": query["special"]},
        "ticket": _score_value(_measure(query["main"], ordered), _expand(summary["distribution"]), summary),
        "special_ticket": special_ticket,
    }
