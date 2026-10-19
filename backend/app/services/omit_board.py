"""遗漏看板：当前、平均、最大遗漏与出现率。不参与脉动综合。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..lotteries import LOTTERIES, normalize_type, number_pools, parse_numbers
from ..models import Draw

COLD_RATIO = 1.5
COLD_EXTRA = 3
SORTS = ("n", "current", "ratio", "max", "count")
DISCLAIMER = (
    "遗漏看板仅供娱乐，不构成投注建议。"
    "平均遗漏 =（样本期数 − 出现次数）/ 出现次数；平均为 0 时比值记 0。"
    "窗口内从未出现的号码，当前、平均、最大遗漏都等于样本期数。"
    "最大遗漏是窗口内最长连续未开出，含首尾未完成的一段。"
    "数字彩按号码出现在任一位计 1 次，同一期重复不算多次。"
    "不参与脉动综合。"
)
COLD_RULE = "未出现，或当前/平均 ≥ 1.5，或当前 ≥ 平均 + 3"


def _canon(raw, pool: set[str]) -> str | None:
    text = str(raw).strip()
    if text in pool:
        return text
    if text.isdigit():
        plain = str(int(text))
        if plain in pool:
            return plain
        padded = plain.zfill(2)
        if padded in pool:
            return padded
    return None


def _present(values, pool: set[str]) -> set[str]:
    found: set[str] = set()
    for raw in values or []:
        matched = _canon(raw, pool)
        if matched:
            found.add(matched)
    return found


def _stat(flags: list[bool], issues: list[str]) -> dict:
    size = len(flags)
    streak = 0
    max_omit = 0
    count = 0
    last_issue = None
    for hit, issue in zip(flags, issues):
        if hit:
            max_omit = max(max_omit, streak)
            streak = 0
            count += 1
            last_issue = issue
        else:
            streak += 1
    max_omit = max(max_omit, streak)
    current = streak
    if count == 0:
        avg = float(size)
        ratio = 1.0 if size else 0.0
    else:
        avg = (size - count) / count
        ratio = 0.0 if avg == 0 else current / avg
    rate = (count / size) if size else 0.0
    cold = bool(size) and (count == 0 or ratio >= COLD_RATIO or current >= avg + COLD_EXTRA)
    return {
        "current": current,
        "avg": round(avg, 4),
        "max": max_omit,
        "count": count,
        "rate": round(rate, 4),
        "ratio": round(ratio, 4),
        "last_issue": last_issue,
        "cold": cold,
    }


def _number_key(value: str):
    text = str(value)
    return (0, int(text)) if text.isdigit() else (1, text)


def _sort_key(sort: str):
    def key(row: dict):
        if sort == "n":
            return _number_key(row["n"])
        return (-row[sort], _number_key(row["n"]))

    return key


def _zone(pool: list[str], oldest: list[dict], field: str) -> list[dict]:
    pool_set = set(pool)
    issues = [str(row.get("issue") or "") for row in oldest]
    seen = [_present(row.get(field), pool_set) for row in oldest]
    rows = []
    for number in pool:
        stat = _stat([number in hits for hits in seen], issues)
        stat["n"] = number
        rows.append(stat)
    return rows


def board_from_history(lottery_type: str, draws: list[dict] | None, limit: int = 80, sort: str = "n") -> dict:
    lottery = normalize_type(lottery_type)
    if lottery not in LOTTERIES:
        raise ValueError("未知彩种")
    if sort not in SORTS:
        raise ValueError("排序只支持 n、current、ratio、max、count")
    if limit < 1:
        raise ValueError("样本窗至少 1 期")
    main_pool, spec_pool = number_pools(lottery)
    newest = sorted(draws or [], key=lambda row: str(row.get("issue") or ""), reverse=True)[:limit]
    oldest = list(reversed(newest))
    main = _zone(main_pool, oldest, "main")
    special = _zone(spec_pool, oldest, "special")
    main.sort(key=_sort_key(sort))
    special.sort(key=_sort_key(sort))
    return {
        "lottery_type": lottery,
        "limit": limit,
        "sample_size": len(oldest),
        "sort": sort,
        "cold_rule": COLD_RULE,
        "main": main,
        "special": special,
        "data_status": "mixed" if any(row.get("source") == "crawl" for row in newest) else "seed",
        "disclaimer": DISCLAIMER,
    }


def omit_board(db: Session, lottery_type: str, limit: int = 80, sort: str = "n") -> dict:
    lottery = normalize_type(lottery_type)
    if lottery not in LOTTERIES:
        raise ValueError("未知彩种")
    rows = (
        db.query(Draw)
        .filter(Draw.lottery_type == lottery)
        .order_by(Draw.issue.desc())
        .limit(limit)
        .all()
    )
    draws = []
    for row in rows:
        nums = parse_numbers(row.numbers)
        draws.append({
            "issue": row.issue,
            "main": nums["main"],
            "special": nums["special"],
            "source": row.source,
        })
    return board_from_history(lottery, draws, limit=limit, sort=sort)
