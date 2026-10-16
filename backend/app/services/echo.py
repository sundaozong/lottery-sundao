"""开奖回声：在近期开奖里找出与一注号码重合最多的期次。

乐透按号码集合相交；数字彩（福彩3D / 排列三 / 排列五 / 七星彩）按位比较，
同一位置数字相同才计入。只读本地开奖，不改其他分析接口。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..lotteries import LOTTERIES, normalize_type, parse_numbers
from ..models import Draw

DISCLAIMER = "回声对照仅供娱乐，不代表下期结果；请理性购彩。"

# main / special: (lo, hi, min_count, max_count)。special 为 None 表示该彩种没有特别号。
PROFILES = {
    "ssq": {
        "mode": "set",
        "width": 2,
        "main": (1, 33, 1, 20),
        "special": (1, 16, 0, 16),
        "main_label": "红球",
        "special_label": "蓝球",
    },
    "dlt": {
        "mode": "set",
        "width": 2,
        "main": (1, 35, 1, 20),
        "special": (1, 12, 0, 12),
        "main_label": "前区",
        "special_label": "后区",
    },
    "qlc": {
        "mode": "set",
        "width": 2,
        "main": (1, 30, 1, 16),
        "special": (1, 30, 0, 1),
        "main_label": "基本号",
        "special_label": "特别号",
    },
    "kl8": {
        "mode": "set",
        "width": 2,
        "main": (1, 80, 1, 20),
        "special": None,
        "main_label": "号码",
        "special_label": "特别号",
    },
    "fc3d": {
        "mode": "digit",
        "width": 1,
        "main": (0, 9, 3, 3),
        "special": None,
        "main_label": "号码",
        "special_label": "特别号",
    },
    "pl3": {
        "mode": "digit",
        "width": 1,
        "main": (0, 9, 3, 3),
        "special": None,
        "main_label": "号码",
        "special_label": "特别号",
    },
    "pl5": {
        "mode": "digit",
        "width": 1,
        "main": (0, 9, 5, 5),
        "special": None,
        "main_label": "号码",
        "special_label": "特别号",
    },
    "qxc": {
        "mode": "digit",
        "width": 1,
        "main": (0, 9, 6, 6),
        "special": (0, 14, 0, 1),
        "main_label": "前位",
        "special_label": "特别号",
    },
}


def _tokens(raw: Any) -> list:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [part for part in raw.replace("，", " ").replace(",", " ").split() if part]
    if isinstance(raw, (list, tuple)):
        return list(raw)
    raise ValueError("号码格式无效")


def _format_ball(raw: Any, width: int, lo: int, hi: int, label: str) -> str:
    text = str(raw).strip()
    if not text.isdigit():
        raise ValueError(f"{label}号码无效：{text}")
    number = int(text)
    if number < lo or number > hi:
        raise ValueError(f"{label}超出 {lo}–{hi}：{text}")
    return str(number).zfill(width) if width > 1 else str(number)


def _normalize_group(
    raw: Any,
    width: int,
    bounds: tuple[int, int, int, int],
    label: str,
    allow_dup: bool,
) -> list[str]:
    lo, hi, min_count, max_count = bounds
    out: list[str] = []
    seen: set[str] = set()
    for item in _tokens(raw):
        key = _format_ball(item, width, lo, hi, label)
        if key in seen and not allow_dup:
            raise ValueError(f"{label}重复：{key}")
        seen.add(key)
        out.append(key)
    if len(out) < min_count or len(out) > max_count:
        if min_count == max_count:
            raise ValueError(f"{label}需要 {min_count} 个")
        raise ValueError(f"{label}需要 {min_count}–{max_count} 个")
    return out


def _history_group(items: list, width: int) -> list[str]:
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text.isdigit():
            continue
        number = int(text)
        out.append(str(number).zfill(width) if width > 1 else str(number))
    return out


def normalize_query(lottery_type: str, main: Any, special: Any = None) -> dict:
    t = normalize_type(lottery_type)
    profile = PROFILES.get(t)
    if profile is None or t not in LOTTERIES:
        raise ValueError("未知彩种")
    allow_dup = profile["mode"] == "digit"
    query_main = _normalize_group(main, profile["width"], profile["main"], profile["main_label"], allow_dup)
    spec_bounds = profile["special"]
    if spec_bounds is None:
        if _tokens(special):
            raise ValueError("该彩种没有特别号")
        query_special: list[str] = []
    else:
        query_special = _normalize_group(
            special,
            profile["width"],
            spec_bounds,
            profile["special_label"],
            allow_dup=False,
        )
    return {
        "lottery_type": t,
        "mode": profile["mode"],
        "width": profile["width"],
        "main": query_main,
        "special": query_special,
    }


def _sorted_shared(left: list[str], right: list[str]) -> list[str]:
    return sorted(set(left) & set(right), key=lambda item: int(item))


def compare_ticket(mode: str, query_main: list[str], query_special: list[str], draw_main: list[str], draw_special: list[str]) -> dict:
    """mode=set 用集合相交；mode=digit 的主号按位置逐位相等。"""
    if mode == "digit":
        shared_main = [left for left, right in zip(query_main, draw_main) if left == right]
        exact_main = query_main == draw_main
    else:
        shared_main = _sorted_shared(query_main, draw_main)
        exact_main = len(query_main) == len(draw_main) and set(query_main) == set(draw_main)
    shared_special = _sorted_shared(query_special, draw_special)
    exact_special = len(query_special) == len(draw_special) and set(query_special) == set(draw_special)
    main_shared = len(shared_main)
    special_shared = len(shared_special)
    return {
        "main_shared": main_shared,
        "special_shared": special_shared,
        "score": main_shared * 10 + special_shared,
        "shared_main": shared_main,
        "shared_special": shared_special,
        "exact_match": exact_main and exact_special,
    }


def find_echoes(
    db: Session,
    lottery_type: str,
    main: Any,
    special: Any = None,
    limit: int = 80,
    top: int = 8,
) -> dict:
    query = normalize_query(lottery_type, main, special)
    t = query["lottery_type"]
    sample_limit = max(1, min(int(limit or 80), 200))
    top_n = max(1, min(int(top or 8), 20))
    rows = (
        db.query(Draw)
        .filter(Draw.lottery_type == t)
        .order_by(Draw.issue.desc())
        .limit(sample_limit)
        .all()
    )
    echoes = []
    for row in rows:
        parsed = parse_numbers(row.numbers)
        draw_main = _history_group(parsed["main"], query["width"])
        draw_special = _history_group(parsed["special"], query["width"])
        scored = compare_ticket(query["mode"], query["main"], query["special"], draw_main, draw_special)
        if scored["score"] <= 0:
            continue
        echoes.append(
            {
                "issue": row.issue,
                "draw_date": row.draw_date or "",
                "main": draw_main,
                "special": draw_special,
                **scored,
            }
        )
    echoes.sort(key=lambda item: (item["score"], item["draw_date"] or "", item["issue"] or ""), reverse=True)
    return {
        "lottery_type": t,
        "query": {"main": query["main"], "special": query["special"]},
        "sample_size": len(rows),
        "top": top_n,
        "mode": query["mode"],
        "echoes": echoes[:top_n],
        "disclaimer": DISCLAIMER,
        "data_status": "mixed" if any(row.source == "crawl" for row in rows) else "seed",
    }
