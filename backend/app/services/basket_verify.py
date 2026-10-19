"""选号篮对照本地开奖。只计算示意奖金，不写购彩记录。"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from ..lotteries import LOTTERIES, normalize_type, parse_numbers
from ..models import Draw
from .prize import calculate

DISCLAIMER = "示意金额，浮动奖未按当期奖池计算。请以官方开奖与兑奖为准，不构成投注建议。"


def verify_basket(
    db: Session,
    lottery_type: str,
    issue: str = "",
    tickets: Optional[list[Any]] = None,
    multiple: int = 1,
) -> dict:
    kind = normalize_type(lottery_type)
    if kind not in LOTTERIES:
        raise ValueError("未知彩种")
    times = multiple if isinstance(multiple, int) and multiple >= 1 else 1
    draw, resolved = _resolve_draw(db, kind, issue)
    rows = list(tickets or [])
    items: list[dict] = []
    for index, ticket in enumerate(rows):
        items.append(_score_ticket(kind, ticket, draw, times, index))
    return {
        "lottery_type": kind,
        "issue": resolved,
        "draw_numbers": parse_numbers(draw.numbers) if draw is not None else None,
        "draw_date": draw.draw_date if draw is not None else "",
        "disclaimer": DISCLAIMER,
        "message": _message(rows, draw),
        "summary": _summary(items),
        "items": items,
    }


def _resolve_draw(db: Session, lottery_type: str, issue: str) -> tuple[Optional[Draw], str]:
    query = db.query(Draw).filter(Draw.lottery_type == lottery_type)
    wanted = (issue or "").strip()
    if wanted:
        row = query.filter(Draw.issue == wanted).order_by(Draw.id.desc()).first()
        return row, wanted
    row = query.order_by(Draw.issue.desc()).first()
    return row, (row.issue if row is not None else "")


def _score_ticket(lottery_type: str, ticket: Any, draw: Optional[Draw], multiple: int, index: int) -> dict:
    numbers = _field(ticket, "numbers")
    play = _field(ticket, "play")
    pick = _field(ticket, "pick")
    ticket_id = _field(ticket, "id")
    try:
        result = calculate(
            lottery_type,
            numbers,
            draw.numbers if draw is not None else None,
            multiple=multiple,
            play=play or None,
            pick=pick,
        )
    except ValueError as exc:
        message = str(exc).strip() or "号码无效"
        if draw is not None and _draw_fault(message):
            return _error_item(ticket_id, index, multiple, message)
        raise
    status = "ok" if draw is not None else "no_draw"
    amount = round(float(result.get("amount") or 0), 2) if status == "ok" else 0
    return {
        "id": ticket_id if ticket_id else None,
        "index": index,
        "status": status,
        "level": result.get("level") or "",
        "main_hit": result.get("main_hit"),
        "special_hit": result.get("special_hit"),
        "amount": amount,
        "cost": round(float(result.get("cost") or 0), 2),
        "bets": result.get("bets") or 0,
        "play": result.get("play") or "",
        "play_name": result.get("play_name") or "",
        "multiple": result.get("multiple") or multiple,
        "numbers": result.get("bet") or {"main": [], "special": []},
        "message": "",
    }


def _error_item(ticket_id: Any, index: int, multiple: int, message: str) -> dict:
    return {
        "id": ticket_id if ticket_id else None,
        "index": index,
        "status": "error",
        "level": "",
        "main_hit": None,
        "special_hit": None,
        "amount": 0,
        "cost": 0,
        "bets": 0,
        "play": "",
        "play_name": "",
        "multiple": multiple,
        "numbers": {"main": [], "special": []},
        "message": message,
    }


def _draw_fault(message: str) -> bool:
    return "开奖" in message


def _field(ticket: Any, name: str) -> Any:
    if isinstance(ticket, dict):
        return ticket.get(name)
    return getattr(ticket, name, None)


def _message(tickets: list[Any], draw: Optional[Draw]) -> str:
    empty = not tickets
    missing = draw is None
    if empty and missing:
        return "当前彩种选号篮是空的，本地也没有开奖。"
    if empty:
        return "当前彩种选号篮是空的。"
    if missing:
        return "本地没有这一期开奖。"
    return ""


def _summary(items: list[dict]) -> dict:
    amount = round(sum(float(item["amount"] or 0) for item in items), 2)
    cost = round(sum(float(item["cost"] or 0) for item in items), 2)
    wins = sum(1 for item in items if item["status"] == "ok" and float(item["amount"] or 0) > 0)
    return {
        "total": len(items),
        "win_count": wins,
        "illustrative_amount": amount,
        "cost": cost,
        "net": round(amount - cost, 2),
    }
