"""号码撞车：同一彩种多注之间的撞号与覆盖空洞。

乐透按主号集合相交，特别号单独计；数字彩按位比较，同位相同才算撞号，
另给出不计位置的数字多重集重合。只读购彩记录，不改其他分析接口。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..lotteries import LOTTERIES, load_bet, normalize_type
from ..models import Draw, PurchaseRecord
from .echo import PROFILES, normalize_query

DISCLAIMER = "预测/分析仅供娱乐，不构成投注建议。"
INSUFFICIENT = "购彩记录不足 2 注，先记下至少两注再看撞号。"
MIN_TICKETS = 2
MAX_TICKETS = 20
HOLE_LIMIT = 24

POSITION_LABELS = {
    "fc3d": ["百", "十", "个"],
    "pl3": ["百", "十", "个"],
    "pl5": ["万", "千", "百", "十", "个"],
    "qxc": ["1", "2", "3", "4", "5", "6"],
}


def _profile(lottery_type: str) -> tuple[str, dict]:
    lottery = normalize_type(lottery_type)
    profile = PROFILES.get(lottery)
    if profile is None or lottery not in LOTTERIES:
        raise ValueError("未知彩种")
    return lottery, profile


def _position_label(lottery: str, position: int) -> str:
    labels = POSITION_LABELS.get(lottery) or []
    if 0 <= position < len(labels):
        return labels[position]
    return str(position + 1)


def _multiset_overlap(left: list[str], right: list[str]) -> int:
    counts: dict[str, int] = {}
    for item in left:
        counts[item] = counts.get(item, 0) + 1
    total = 0
    for item in right:
        left_count = counts.get(item, 0)
        if left_count <= 0:
            continue
        total += 1
        counts[item] = left_count - 1
    return total


def _sorted_shared(left: list[str], right: list[str]) -> list[str]:
    return sorted(set(left) & set(right), key=lambda item: int(item))


def _waste_hint(
    mode: str,
    main_overlap: int,
    special_overlap: int,
    unordered: int,
    left_len: int,
    right_len: int,
    special_label: str | None,
) -> str:
    if main_overlap == 0 and special_overlap == 0 and unordered == 0:
        return "没有撞号，覆盖是拉开的"
    parts: list[str] = []
    if mode == "digit":
        parts.append(f"同位撞了 {main_overlap} 个" if main_overlap else "同位没有撞号")
        extra = unordered - main_overlap
        if extra > 0:
            parts.append(f"不计位置还有 {extra} 个数字重复")
    else:
        parts.append(f"主号撞了 {main_overlap} 个" if main_overlap else "主号没有撞")
    if special_overlap:
        parts.append(f"{special_label or '特别号'}撞了 {special_overlap} 个")
    text = "，".join(parts)
    smaller = min(left_len, right_len) or 1
    threshold = max(2, (smaller + 1) // 2)
    if main_overlap >= threshold:
        text = "浪费偏多：" + text
    return text


def _pool_size(profile: dict) -> int:
    lo, hi, count, _max_count = profile["main"]
    if profile["mode"] == "digit":
        return count * 10
    return hi - lo + 1


def _empty(lottery: str, profile: dict, message: str) -> dict:
    pool = _pool_size(profile)
    return {
        "lottery_type": lottery,
        "mode": profile["mode"],
        "source": "records",
        "record_scope": "",
        "ticket_count": 0,
        "tickets": [],
        "pairs": [],
        "number_hits": [],
        "unique_coverage": {"covered": 0, "pool": pool, "ratio": 0.0},
        "holes": [],
        "summary": message,
        "message": message,
        "disclaimer": DISCLAIMER,
    }


def _pair(mode: str, left: dict, right: dict, left_index: int, right_index: int, special_label: str | None) -> dict:
    if mode == "digit":
        shared_main: list[str] = []
        positions: list[int] = []
        for index, (a, b) in enumerate(zip(left["main"], right["main"])):
            if a == b:
                shared_main.append(a)
                positions.append(index)
        unordered = _multiset_overlap(left["main"], right["main"])
    else:
        shared_main = _sorted_shared(left["main"], right["main"])
        positions = []
        unordered = len(shared_main)
    shared_special = _sorted_shared(left["special"], right["special"])
    overlap_count = len(shared_main)
    special_overlap = len(shared_special)
    return {
        "left": left_index,
        "right": right_index,
        "overlap_count": overlap_count,
        "special_overlap_count": special_overlap,
        "unordered_overlap_count": unordered,
        "overlapping": {"main": shared_main, "special": shared_special, "positions": positions},
        "waste_hint": _waste_hint(
            mode,
            overlap_count,
            special_overlap,
            unordered if mode == "digit" else 0,
            len(left["main"]),
            len(right["main"]),
            special_label,
        ),
    }


def _number_hits(lottery: str, profile: dict, tickets: list[dict]) -> list[dict]:
    mode = profile["mode"]
    main_counts: dict[Any, int] = {}
    special_counts: dict[str, int] = {}
    for ticket in tickets:
        if mode == "digit":
            seen_slots: set[tuple[int, str]] = set()
            for index, number in enumerate(ticket["main"]):
                slot = (index, number)
                if slot in seen_slots:
                    continue
                seen_slots.add(slot)
                main_counts[slot] = main_counts.get(slot, 0) + 1
        else:
            for number in set(ticket["main"]):
                main_counts[number] = main_counts.get(number, 0) + 1
        for number in set(ticket["special"]):
            special_counts[number] = special_counts.get(number, 0) + 1

    hits: list[dict] = []
    if mode == "digit":
        main_rows = [
            {
                "n": number,
                "count": count,
                "collision": count >= 2,
                "kind": "main",
                "position": position,
                "position_label": _position_label(lottery, position),
            }
            for (position, number), count in main_counts.items()
        ]
        main_rows.sort(key=lambda item: (-item["count"], item["position"], int(item["n"])))
    else:
        main_rows = [
            {
                "n": number,
                "count": count,
                "collision": count >= 2,
                "kind": "main",
                "position": None,
                "position_label": "",
            }
            for number, count in main_counts.items()
        ]
        main_rows.sort(key=lambda item: (-item["count"], int(item["n"])))
    hits.extend(main_rows)
    label = profile.get("special_label") or ""
    special_rows = [
        {
            "n": number,
            "count": count,
            "collision": count >= 2,
            "kind": "special",
            "position": None,
            "position_label": label,
        }
        for number, count in special_counts.items()
    ]
    special_rows.sort(key=lambda item: (-item["count"], int(item["n"])))
    hits.extend(special_rows)
    return hits


def _holes(profile: dict, covered: set[str]) -> list[str]:
    if profile["mode"] != "set":
        return []
    lo, hi, _min_count, _max_count = profile["main"]
    width = profile["width"]
    missing: list[str] = []
    for number in range(lo, hi + 1):
        key = str(number).zfill(width) if width > 1 else str(number)
        if key in covered:
            continue
        missing.append(key)
        if len(missing) >= HOLE_LIMIT:
            break
    return missing


def _summary(ticket_count: int, hits: list[dict]) -> str:
    main_repeats = sum(1 for item in hits if item["kind"] == "main" and item["collision"])
    special_repeats = sum(1 for item in hits if item["kind"] == "special" and item["collision"])
    text = f"共 {ticket_count} 注，{main_repeats} 个号码被重复选中"
    if special_repeats:
        text += f"，另有 {special_repeats} 个特别号被重复选中"
    return text


def _covered_count(profile: dict, tickets: list[dict]) -> int:
    if profile["mode"] == "digit":
        return len({(index, number) for ticket in tickets for index, number in enumerate(ticket["main"])})
    return len({number for ticket in tickets for number in ticket["main"]})


def _assemble(lottery: str, profile: dict, tickets: list[dict], source: str, record_scope: str) -> dict:
    mode = profile["mode"]
    pairs = [
        _pair(mode, tickets[left], tickets[right], left + 1, right + 1, profile.get("special_label"))
        for left in range(len(tickets))
        for right in range(left + 1, len(tickets))
    ]
    hits = _number_hits(lottery, profile, tickets)
    covered = {number for ticket in tickets for number in ticket["main"]}
    pool = _pool_size(profile)
    covered_count = _covered_count(profile, tickets)
    return {
        "lottery_type": lottery,
        "mode": mode,
        "source": source,
        "record_scope": record_scope,
        "ticket_count": len(tickets),
        "tickets": tickets,
        "pairs": pairs,
        "number_hits": hits,
        "unique_coverage": {"covered": covered_count, "pool": pool, "ratio": round(covered_count / pool, 4) if pool else 0.0},
        "holes": _holes(profile, covered),
        "summary": _summary(len(tickets), hits),
        "message": "",
        "disclaimer": DISCLAIMER,
    }


def _present(raw: Any) -> bool:
    if raw is None:
        return False
    if isinstance(raw, str):
        return bool(raw.strip())
    if isinstance(raw, (list, tuple)):
        return any(str(item).strip() for item in raw)
    return True


def _normalize_tickets(lottery: str, raw_tickets: list) -> list[dict]:
    if len(raw_tickets) < MIN_TICKETS:
        raise ValueError("至少需要 2 注")
    if len(raw_tickets) > MAX_TICKETS:
        raise ValueError("最多对比 20 注")
    tickets: list[dict] = []
    for index, raw in enumerate(raw_tickets, start=1):
        if hasattr(raw, "model_dump"):
            raw = raw.model_dump()
        if not isinstance(raw, dict):
            raise ValueError(f"第 {index} 注：号码格式无效")
        if PROFILES[lottery]["special"] is None and _present(raw.get("special")):
            raise ValueError(f"第 {index} 注：该彩种没有特别号")
        try:
            parsed = normalize_query(lottery, raw.get("main"), raw.get("special"))
        except ValueError as exc:
            raise ValueError(f"第 {index} 注：{exc}") from exc
        tickets.append(
            {
                "index": index,
                "main": parsed["main"],
                "special": parsed["special"],
                "record_id": raw.get("record_id"),
                "issue": raw.get("issue") or "",
            }
        )
    return tickets


def collide(lottery_type: str, tickets: list) -> dict:
    """手填票面。tickets 为 {main, special} 列表，2–20 注。"""
    lottery, profile = _profile(lottery_type)
    normalized = _normalize_tickets(lottery, tickets or [])
    for ticket in normalized:
        ticket["record_id"] = None
        ticket["issue"] = ""
    return _assemble(lottery, profile, normalized, "tickets", "")


def _first(values: list) -> str:
    if not values:
        return ""
    return str(values[0]).strip()


def _ticket_from_bet(lottery: str, profile: dict, bet: dict) -> dict:
    positions = bet.get("positions") or []
    if profile["mode"] == "digit" and any(positions):
        main_len = profile["main"][2]
        if profile["special"] and len(positions) >= main_len + 1:
            main = [_first(pos) for pos in positions[:main_len]]
            special_number = _first(positions[main_len])
            if all(main):
                special = [special_number] if special_number else []
                return {"main": main, "special": special}
        if len(positions) >= main_len:
            main = [_first(pos) for pos in positions[:main_len]]
            if all(main):
                return {"main": main, "special": list(bet.get("special") or [])}
    return {"main": list(bet.get("main") or []), "special": list(bet.get("special") or [])}


def _is_open(row: PurchaseRecord, drawn_issues: set[str]) -> bool:
    if (row.prize or 0) > 0:
        return False
    issue = (row.issue or "").strip()
    if not issue:
        return True
    return issue not in drawn_issues


def collide_records(db: Session, lottery_type: str) -> dict:
    """优先用未开奖记录；不足 2 注时改用最近记录。仍不足则返回说明。"""
    lottery, profile = _profile(lottery_type)
    rows = [
        row
        for row in db.query(PurchaseRecord).order_by(PurchaseRecord.id.desc()).all()
        if normalize_type(row.lottery_type) == lottery
    ]
    drawn_issues = {
        row.issue
        for row in db.query(Draw).all()
        if normalize_type(row.lottery_type) == lottery and row.issue
    }
    usable: list[tuple[PurchaseRecord, dict]] = []
    for row in rows:
        payload = _ticket_from_bet(lottery, profile, load_bet(row.numbers))
        try:
            parsed = normalize_query(lottery, payload.get("main"), payload.get("special"))
        except ValueError:
            continue
        usable.append((row, parsed))
    open_rows = [(row, parsed) for row, parsed in usable if _is_open(row, drawn_issues)]
    if len(open_rows) >= MIN_TICKETS:
        chosen = open_rows[:MAX_TICKETS]
        scope = "open"
    else:
        chosen = usable[:MAX_TICKETS]
        scope = "latest"
    if len(chosen) < MIN_TICKETS:
        return _empty(lottery, profile, INSUFFICIENT)
    chosen.reverse()
    tickets = [
        {
            "index": index,
            "main": parsed["main"],
            "special": parsed["special"],
            "record_id": row.id,
            "issue": row.issue or "",
        }
        for index, (row, parsed) in enumerate(chosen, start=1)
    ]
    return _assemble(lottery, profile, tickets, "records", scope)
