"""复式 / 胆拖展开成单注。

只做组合计数和分页，不读开奖，也不做脉动。常见带由调用方传入。
金额沿用奖金估算的 2 元/注。
"""
from __future__ import annotations

import math
from typing import Any, Optional

from ..lotteries import normalize_type
from .prize import MAX_BETS, STAKE

LIST_CAP = 5000
FILTER_SCAN_CAP = 20_000
PAGE_DEFAULT = 60
PAGE_MAX = 200
DISCLAIMER = "复式和胆拖只是把选号展开成单注并按 2 元计数，不预测中奖。仅供娱乐，不构成投注建议。"

MODE_ALIAS = {
    "compound": "compound",
    "复式": "compound",
    "banker": "banker",
    "胆拖": "banker",
}


def comb(n: int, k: int) -> int:
    if k < 0 or n < 0 or k > n:
        return 0
    return math.comb(n, k)


def combination_at(pool: list[str], k: int, index: int) -> list[str]:
    """按字典序取出第 index 个组合，0 是最小的 k 个号码。"""
    if k == 0:
        return []
    chosen: list[str] = []
    remaining = k
    start = 0
    cursor = index
    total = len(pool)
    while remaining:
        for pos in range(start, total - remaining + 1):
            block = comb(total - pos - 1, remaining - 1)
            if cursor < block:
                chosen.append(pool[pos])
                start = pos + 1
                remaining -= 1
                break
            cursor -= block
        else:
            break
    return chosen


def _zone(key, label, lo, hi, width, pick, max_count, banker, color):
    return {
        "key": key,
        "label": label,
        "lo": lo,
        "hi": hi,
        "width": width,
        "pick": pick,
        "max": max_count,
        "banker": banker,
        "color": color,
    }


def _pos(label, lo, hi, color, special=False):
    return {
        "label": label,
        "lo": lo,
        "hi": hi,
        "width": 1,
        "color": color,
        "special": special,
    }


def _digit(name, labels, colors, special_index=None, special_hi=None, special_color=None, special_label="特别号"):
    positions = []
    for index, label in enumerate(labels):
        positions.append(_pos(label, 0, 9, colors))
    if special_index is not None:
        positions.append(_pos(special_label, 0, special_hi, special_color, special=True))
    return {"name": name, "kind": "digit", "positions": positions, "zones": [], "pick_min": None, "pick_max": None}


GAMES = {
    "ssq": {
        "name": "双色球",
        "kind": "set",
        "pick_min": None,
        "pick_max": None,
        "positions": [],
        "zones": [
            _zone("main", "红球", 1, 33, 2, 6, 20, True, "red"),
            _zone("special", "蓝球", 1, 16, 2, 1, 16, False, "blue"),
        ],
    },
    "dlt": {
        "name": "大乐透",
        "kind": "set",
        "pick_min": None,
        "pick_max": None,
        "positions": [],
        "zones": [
            _zone("main", "前区", 1, 35, 2, 5, 20, True, "red"),
            _zone("special", "后区", 1, 12, 2, 2, 12, True, "blue"),
        ],
    },
    "qlc": {
        "name": "七乐彩",
        "kind": "set",
        "pick_min": None,
        "pick_max": None,
        "positions": [],
        "zones": [_zone("main", "基本号", 1, 30, 2, 7, 16, True, "red")],
    },
    "kl8": {
        "name": "快乐八",
        "kind": "set",
        "pick_min": 1,
        "pick_max": 10,
        "positions": [],
        "zones": [_zone("main", "号码", 1, 80, 2, None, 20, True, "orange")],
    },
    "fc3d": _digit("福彩3D", ["百位", "十位", "个位"], "green"),
    "pl3": _digit("排列三", ["百位", "十位", "个位"], "green"),
    "pl5": _digit("排列五", ["万位", "千位", "百位", "十位", "个位"], "green"),
    "qxc": _digit("七星彩", ["第1位", "第2位", "第3位", "第4位", "第5位", "第6位"], "purple", 6, 14, "orange"),
}


def expand_rules() -> dict:
    games = {}
    for code, game in GAMES.items():
        public = {
            "name": game["name"],
            "kind": game["kind"],
            "pick_min": game["pick_min"],
            "pick_max": game["pick_max"],
        }
        if game["kind"] == "set":
            public["zones"] = [
                {key: zone[key] for key in ("key", "label", "lo", "hi", "width", "pick", "max", "banker", "color")}
                for zone in game["zones"]
            ]
        else:
            public["positions"] = [
                {
                    "key": str(index),
                    "label": pos["label"],
                    "lo": pos["lo"],
                    "hi": pos["hi"],
                    "width": 1,
                    "color": pos["color"],
                    "special": pos["special"],
                    "max": pos["hi"] - pos["lo"] + 1,
                }
                for index, pos in enumerate(game["positions"])
            ]
        games[code] = public
    return {
        "stake": STAKE,
        "list_cap": LIST_CAP,
        "page_size": PAGE_DEFAULT,
        "disclaimer": DISCLAIMER,
        "games": games,
    }


def _tokens(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [part for part in raw.replace("，", " ").replace(",", " ").split() if part]
    if isinstance(raw, (list, tuple)):
        tokens: list[str] = []
        for item in raw:
            tokens.extend(_tokens(item))
        return tokens
    return _tokens(str(raw))


def _has_values(raw: Any) -> bool:
    return bool(_tokens(raw))


def _parse_balls(raw: Any, label: str, lo: int, hi: int, width: int) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    balls: list[str] = []
    seen: set[str] = set()
    for token in _tokens(raw):
        if not str(token).isdigit():
            errors.append(f"{label}号码无效：{token}")
            continue
        number = int(token)
        if number < lo or number > hi:
            errors.append(f"{label}超出 {lo}–{hi}：{token}")
            continue
        key = str(number).zfill(width) if width > 1 else str(number)
        if key in seen:
            errors.append(f"{label}重复：{key}")
            continue
        seen.add(key)
        balls.append(key)
    balls.sort(key=lambda item: int(item))
    return balls, errors


def _blank(lottery_type: str, mode: str, pick, offset: int, limit: int) -> dict:
    return {
        "lottery_type": lottery_type,
        "name": "",
        "mode": mode if mode in ("compound", "banker") else "",
        "pick": pick if isinstance(pick, int) else None,
        "valid": False,
        "bet_count": 0,
        "stake": STAKE,
        "cost": 0,
        "messages": [],
        "notes": [],
        "warnings": [],
        "expanded": False,
        "truncated": False,
        "offset": offset,
        "limit": limit,
        "returned": 0,
        "matched": None,
        "has_more": False,
        "tickets": [],
        "disclaimer": DISCLAIMER,
    }


def _finish(base: dict, **changes) -> dict:
    base.update(changes)
    base["returned"] = len(base["tickets"])
    base["cost"] = base["bet_count"] * STAKE
    listed = base["matched"] if base["matched"] is not None else base["bet_count"]
    base["has_more"] = bool(base["expanded"] and base["offset"] + base["returned"] < listed)
    return base


def _resolve_pick(game: dict, pick) -> tuple[Optional[int], list[str]]:
    if game["pick_min"] is None:
        return None, []
    if pick is None or pick == "":
        return None, ["请选择选几（选一到选十）"]
    try:
        value = int(pick)
    except (TypeError, ValueError):
        return None, ["选几只能是选一到选十"]
    if value < game["pick_min"] or value > game["pick_max"]:
        return None, ["选几只能是选一到选十"]
    return value, []


def _compound_plan(balls: list[str], pick: int) -> dict:
    pool = balls

    def at(index: int) -> list[str]:
        return combination_at(pool, pick, index)

    return {"count": comb(len(pool), pick), "at": at, "banker": False}


def _banker_plan(bankers: list[str], drags: list[str], pick: int) -> dict:
    need = pick - len(bankers)

    def at(index: int) -> list[str]:
        chosen = combination_at(drags, need, index)
        return sorted(bankers + chosen, key=lambda item: int(item))

    return {"count": comb(len(drags), need), "at": at, "banker": True}


def _count_error(label: str, count: int, low: int, high: int) -> str:
    return f"复式{label}需要 {low}–{high} 个"


def _set_zone_plan(zone: dict, raw: Optional[dict], mode: str, pick_override: Optional[int]) -> tuple[Optional[dict], list[str]]:
    label = zone["label"]
    pick = pick_override if zone["pick"] is None else zone["pick"]
    raw = raw or {}
    errors: list[str] = []
    if mode == "compound" and (_has_values(raw.get("bankers")) or _has_values(raw.get("drags"))):
        return None, ["复式不要填写胆码"]
    if mode == "banker" and not zone["banker"]:
        if _has_values(raw.get("bankers")) or _has_values(raw.get("drags")):
            return None, [f"{label}不能设胆码，请直接选择号码"]
        balls, parse_errors = _parse_balls(raw.get("numbers"), label, zone["lo"], zone["hi"], zone["width"])
        if parse_errors:
            return None, parse_errors
        if not (pick <= len(balls) <= zone["max"]):
            return None, [_count_error(label, len(balls), pick, zone["max"])]
        return _compound_plan(balls, pick), []

    if mode == "compound" or not zone["banker"]:
        balls, parse_errors = _parse_balls(raw.get("numbers"), label, zone["lo"], zone["hi"], zone["width"])
        if parse_errors:
            return None, parse_errors
        if not (pick <= len(balls) <= zone["max"]):
            return None, [_count_error(label, len(balls), pick, zone["max"])]
        return _compound_plan(balls, pick), []

    bankers, banker_errors = _parse_balls(raw.get("bankers"), f"{label}胆码", zone["lo"], zone["hi"], zone["width"])
    if banker_errors:
        errors.extend(banker_errors)
    use_drags = _has_values(raw.get("drags"))
    use_numbers = _has_values(raw.get("numbers"))
    if not bankers and use_drags and use_numbers:
        errors.append(f"{label}拖码和号码请只填一处")
    pool_raw = raw.get("drags") if use_drags or bankers else raw.get("numbers")
    pool_label = f"{label}拖码" if bankers or use_drags else label
    pool, pool_errors = _parse_balls(pool_raw, pool_label, zone["lo"], zone["hi"], zone["width"])
    if pool_errors:
        errors.extend(pool_errors)
    if errors:
        return None, errors
    if not bankers:
        if not (pick <= len(pool) <= zone["max"]):
            return None, [_count_error(label, len(pool), pick, zone["max"])]
        return _compound_plan(pool, pick), []

    cap = pick - 1
    if len(bankers) > cap:
        if cap == 1:
            errors.append(f"{label}胆码只能有 1 个")
        else:
            errors.append(f"{label}胆码需要 1–{cap} 个")
    overlap = [item for item in bankers if item in set(pool)]
    if overlap:
        errors.append(f"{label}胆码与拖码重复：" + "、".join(overlap))
    if len(pool) < 2:
        errors.append(f"{label}拖码至少 2 个")
    if len(bankers) + len(pool) < pick + 1:
        errors.append(f"{label}胆码加拖码至少 {pick + 1} 个")
    if len(bankers) + len(pool) > zone["max"]:
        errors.append(f"{label}胆码加拖码最多 {zone['max']} 个")
    if errors:
        return None, errors
    return _banker_plan(bankers, pool, pick), []


def _digit_plan(pos: dict, raw: Optional[dict], mode: str) -> tuple[Optional[dict], list[str]]:
    label = pos["label"]
    raw = raw or {}
    if mode == "compound":
        if _has_values(raw.get("bankers")) or _has_values(raw.get("drags")):
            return None, ["复式不要填写胆码"]
        balls, errors = _parse_balls(raw.get("numbers"), label, pos["lo"], pos["hi"], 1)
        if errors:
            return None, errors
        if not balls:
            return None, [f"{label}至少选 1 个号码"]

        def at(index: int, pool=balls) -> list[str]:
            return [pool[index]]

        return {"count": len(balls), "at": at, "banker": False}, []

    if _has_values(raw.get("numbers")):
        return None, [f"{label}请用胆码和拖码，不要混用复式号码"]
    bankers, banker_errors = _parse_balls(raw.get("bankers"), label, pos["lo"], pos["hi"], 1)
    drags, drag_errors = _parse_balls(raw.get("drags"), label, pos["lo"], pos["hi"], 1)
    errors = banker_errors + drag_errors
    if errors:
        return None, errors
    if len(bankers) > 1:
        return None, [f"{label}胆码只能有 1 个"]
    if len(bankers) == 1 and drags:
        return None, [f"{label}已锁胆码，不能再加拖码"]
    if len(bankers) == 1:
        locked = bankers[0]

        def at_locked(_index: int, number=locked) -> list[str]:
            return [number]

        return {"count": 1, "at": at_locked, "banker": True}, []
    if not drags:
        return None, [f"{label}请锁定胆码或选择拖码"]

    def at_drag(index: int, pool=drags) -> list[str]:
        return [pool[index]]

    return {"count": len(drags), "at": at_drag, "banker": False}, []


def _build_plans(game: dict, mode: str, pick_value: Optional[int], main, special, positions) -> tuple[list[dict], list[str]]:
    if game["kind"] == "digit":
        if positions is None:
            return [], ["请按位选择号码"]
        if len(positions) != len(game["positions"]):
            return [], [f"{game['name']}需要 {len(game['positions'])} 位"]
        plans = []
        errors = []
        for pos, raw in zip(game["positions"], positions):
            plan, zone_errors = _digit_plan(pos, raw, mode)
            if zone_errors:
                errors.extend(zone_errors)
            elif plan:
                plans.append(plan)
        return plans, errors

    if _has_values((special or {}).get("numbers")) or _has_values((special or {}).get("bankers")) or _has_values((special or {}).get("drags")):
        if not any(zone["key"] == "special" for zone in game["zones"]):
            return [], ["该彩种没有特别号"]
    plans = []
    errors = []
    raw_by_key = {"main": main, "special": special}
    for zone in game["zones"]:
        plan, zone_errors = _set_zone_plan(zone, raw_by_key.get(zone["key"]), mode, pick_value)
        if zone_errors:
            errors.extend(zone_errors)
        elif plan:
            plans.append(plan)
    return plans, errors


def _assemble(game: dict, parts: list[list[str]]) -> dict:
    if game["kind"] == "digit":
        main: list[str] = []
        special: list[str] = []
        for part, pos in zip(parts, game["positions"]):
            if pos["special"]:
                special.extend(part)
            else:
                main.extend(part)
        return {"main": main, "special": special}
    main = parts[0] if parts else []
    special = parts[1] if len(parts) > 1 else []
    return {"main": main, "special": special}


def _ticket_at(plans: list[dict], game: dict, index: int) -> dict:
    parts = []
    cursor = index
    for plan in plans:
        local = cursor % plan["count"]
        cursor //= plan["count"]
        parts.append(plan["at"](local))
    return _assemble(game, parts)


def _inside(ticket: dict, band: dict) -> bool:
    main = ticket.get("main") or []
    if not main:
        return False
    values = [int(item) for item in main]
    checks = {
        "sum": sum(values),
        "span": max(values) - min(values),
        "odd": sum(item % 2 for item in values),
    }
    for key, value in checks.items():
        bounds = band.get(key) or {}
        if "low" not in bounds or "high" not in bounds:
            return False
        current = float(value)
        if current < float(bounds["low"]) or current > float(bounds["high"]):
            return False
    return True


def _scan(plans, game, band, total: int, offset: int, limit: int) -> tuple[int, list[dict]]:
    matched = 0
    tickets = []
    for index in range(total):
        ticket = _ticket_at(plans, game, index)
        if not _inside(ticket, band):
            continue
        if limit > 0 and matched >= offset and len(tickets) < limit:
            tickets.append(ticket)
        matched += 1
    return matched, tickets


def expand_bets(
    lottery_type: str,
    mode: str = "compound",
    pick: Optional[int] = None,
    main: Optional[dict] = None,
    special: Optional[dict] = None,
    positions: Optional[list] = None,
    offset: int = 0,
    limit: int = PAGE_DEFAULT,
    band: Optional[dict] = None,
) -> dict:
    offset_n = max(0, int(offset or 0))
    limit_n = max(0, min(PAGE_MAX, int(limit or 0)))
    normalized = MODE_ALIAS.get(str(mode or "").strip())
    base = _blank(lottery_type, normalized or "", pick if isinstance(pick, int) else None, offset_n, limit_n)
    code = normalize_type(lottery_type)
    game = GAMES.get(code)
    if game is None:
        base["messages"] = ["未知彩种"]
        return base
    base["lottery_type"] = code
    base["name"] = game["name"]
    if normalized is None:
        base["messages"] = ["玩法只能是复式或胆拖"]
        return base
    base["mode"] = normalized
    pick_value, pick_errors = _resolve_pick(game, pick)
    if pick_errors:
        base["messages"] = pick_errors
        return base
    if pick_value is not None:
        base["pick"] = pick_value
    if normalized == "banker" and pick_value == 1:
        base["messages"] = ["选一没有胆拖"]
        return base

    plans, errors = _build_plans(game, normalized, pick_value, main, special, positions)
    if errors:
        base["messages"] = errors
        return base
    if normalized == "banker" and not any(plan["banker"] for plan in plans):
        base["messages"] = ["胆拖至少要有一组胆码"]
        return base

    total = 1
    for plan in plans:
        total *= plan["count"]
    notes: list[str] = []
    warnings: list[str] = []
    if total == 1:
        notes.append("当前是单式，共 1 注")
    if total > MAX_BETS:
        return _finish(
            base,
            valid=False,
            bet_count=total,
            messages=[f"注数 {total} 超过上限 {MAX_BETS}，请减少号码"],
            notes=notes,
        )

    tickets: list[dict] = []
    matched = None
    expanded = False
    truncated = False
    if band is not None and total > FILTER_SCAN_CAP:
        warnings.append(f"共 {total} 注，常见带过滤最多扫描 {FILTER_SCAN_CAP} 注")
        truncated = True
    elif band is not None:
        matched, tickets = _scan(plans, game, band, total, offset_n, limit_n)
        expanded = limit_n > 0
        if matched == 0:
            notes.append("没有落在常见带内的单注")
    elif limit_n <= 0:
        expanded = False
    elif total > LIST_CAP:
        warnings.append(f"共 {total} 注，超过 {LIST_CAP} 注不再逐注展开")
        truncated = True
    else:
        end = min(total, offset_n + limit_n)
        if offset_n < total:
            tickets = [_ticket_at(plans, game, index) for index in range(offset_n, end)]
        expanded = True

    return _finish(
        base,
        valid=True,
        bet_count=total,
        notes=notes,
        warnings=warnings,
        expanded=expanded,
        truncated=truncated,
        matched=matched,
        tickets=tickets,
    )
