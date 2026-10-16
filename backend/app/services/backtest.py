"""用当前投注对照本地历史开奖，估算示意中奖次数。不写入任何记录。"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from ..lotteries import LOTTERIES, normalize_type, parse_numbers
from ..models import Draw
from .prize import calculate

DISCLAIMER = "回测只对照本地开奖样本，浮动奖为示意金额，仅供娱乐，不代表以后会中奖。"


def backtest_ticket(
    db: Session,
    lottery_type: str,
    bet_numbers: Any,
    limit: int = 30,
    multiple: int = 1,
    play: Optional[str] = None,
    pick: Optional[int] = None,
) -> dict:
    t = normalize_type(lottery_type)
    if t not in LOTTERIES:
        raise ValueError("未知彩种")
    preview = calculate(t, bet_numbers, None, multiple, play=play, pick=pick)
    rows = (
        db.query(Draw)
        .filter(Draw.lottery_type == t)
        .order_by(Draw.issue.desc())
        .limit(limit)
        .all()
    )
    hits = []
    total = 0.0
    for row in rows:
        result = calculate(
            t,
            bet_numbers,
            parse_numbers(row.numbers),
            multiple,
            play=play,
            pick=pick,
        )
        if result["amount"] > 0:
            total += result["amount"]
            hits.append(
                {
                    "issue": row.issue,
                    "draw_date": row.draw_date or "",
                    "level": result["level"],
                    "amount": result["amount"],
                    "main_hit": result["main_hit"],
                    "special_hit": result["special_hit"],
                    "floating": any(item["floating"] for item in result["breakdown"]),
                }
            )
    sample = len(rows)
    spent = round(preview["cost"] * sample, 2)
    amount = round(total, 2)
    return {
        "lottery_type": t,
        "sample_size": sample,
        "win_count": len(hits),
        "cost_each": preview["cost"],
        "illustrative_spent": spent,
        "illustrative_amount": amount,
        "illustrative_net": round(amount - spent, 2),
        "play_name": preview["play_name"],
        "hits": hits,
        "disclaimer": DISCLAIMER,
    }
