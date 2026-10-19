"""历史回放：一注对照本地开奖，以及机选条件的逐期前推。

奖级金额走奖金计算。逐期前推只把该期之前的开奖交给现有机选，不改脉动综合。
"""
from __future__ import annotations

import random
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..lotteries import LOTTERIES, normalize_type, parse_numbers
from ..models import Draw
from .predict import constraints_requested, generate
from .prize import calculate, money_label

DISCLAIMER = "回放只对照本地开奖，浮动奖为参考金额，仅供娱乐，不代表以后会中奖。"
NOTE = "彩票每期开奖是独立随机事件。回放只说明本地历史上的示意结果，不代表未来。"
STRATEGY_NOTE = NOTE + "旁边的纯随机不带胆杀和形态条件，两边都不用当期和之后的开奖。"

MAX_TICKET_PERIODS = 3000
MAX_STRATEGY_PERIODS = 300
REPLAY_ATTEMPTS = 800
HIT_LIMIT = 40

STRATEGY_LABELS = {
    "hot": "热号加权",
    "cold": "冷号加权",
    "hybrid": "冷热混合",
    "random": "纯随机",
}
ALLOWED_STRATEGIES = set(STRATEGY_LABELS)


def parse_window(window: Any) -> tuple[str, Optional[int]]:
    if isinstance(window, bool) or window is None:
        raise ValueError("期数请选 30、100、300 或全部")
    text = str(window).strip().lower()
    if text in {"all", "全部", "*"}:
        return "all", None
    if text.isdigit():
        number = int(text)
        if number >= 1:
            return str(number), number
    raise ValueError("期数请选 30、100、300 或全部")


def _amount_label(amount: float, floating: bool) -> str:
    text = money_label(amount, floating)
    if floating:
        return f"{text} · 参考"
    return text


def _level_rows(table: list[dict], buckets: dict[str, dict]) -> list[dict]:
    order: list[str] = []
    floating: dict[str, bool] = {}
    for row in table or []:
        level = row["level"]
        floating[level] = floating.get(level, False) or bool(row["floating"])
        if level not in order:
            order.append(level)
    for level in buckets:
        if level not in order:
            order.append(level)
    rows = []
    for level in order:
        found = buckets.get(level)
        count = int(found["count"]) if found else 0
        amount = round(found["amount"], 2) if found else 0
        is_float = bool(found["floating"]) if found else floating.get(level, False)
        if found and floating.get(level):
            is_float = True
        rows.append(
            {
                "level": level,
                "count": count,
                "amount": amount,
                "floating": is_float,
                "amount_label": _amount_label(amount, is_float and count > 0),
            }
        )
    return rows


def _better(current: Optional[dict], candidate: dict) -> dict:
    if current is None:
        return candidate
    if candidate["amount"] > current["amount"]:
        return candidate
    if candidate["amount"] == current["amount"] and str(candidate["issue"]) > str(current["issue"]):
        return candidate
    return current


def _summarize(table: list[dict], events: list[dict]) -> dict:
    buckets: dict[str, dict] = {}
    best = None
    prize = 0.0
    spent = 0.0
    wins = 0
    longest = 0
    streak = 0
    hits = []
    for event in events:
        result = event["result"]
        amount = round(float(result["amount"] or 0), 2)
        spent += float(result["cost"] or 0)
        prize += amount
        won = amount > 0
        if won:
            wins += 1
            streak = 0
            floating = False
            for row in result["breakdown"]:
                level = row["level"]
                slot = buckets.setdefault(level, {"count": 0, "amount": 0.0, "floating": False})
                slot["count"] += int(row["count"])
                slot["amount"] += float(row["amount"])
                slot["floating"] = slot["floating"] or bool(row["floating"])
                floating = floating or bool(row["floating"])
            hit = {
                "issue": event["issue"],
                "draw_date": event.get("draw_date") or "",
                "level": result["level"],
                "amount": amount,
                "floating": floating,
                "amount_label": _amount_label(amount, floating),
                "main_hit": result["main_hit"],
                "special_hit": result["special_hit"],
                "numbers": event["numbers"],
            }
            hits.append(hit)
            best = _better(best, hit)
        else:
            streak += 1
            longest = max(longest, streak)
    prize = round(prize, 2)
    spent = round(spent, 2)
    reference = any(row["amount"] > 0 and row["floating"] for row in buckets.values())
    hits.sort(key=lambda item: str(item["issue"]), reverse=True)
    return {
        "sample_size": len(events),
        "win_draws": wins,
        "levels": _level_rows(table, buckets),
        "best": best,
        "spent": spent,
        "prize": prize,
        "prize_is_reference": reference,
        "return_rate": round(prize / spent, 4) if spent else None,
        "longest_miss": longest,
        "hits": hits[:HIT_LIMIT],
    }


def _load_draws(db: Session, lottery_type: str) -> list[Draw]:
    return (
        db.query(Draw)
        .filter(Draw.lottery_type == lottery_type)
        .order_by(Draw.issue.asc())
        .all()
    )


def replay_ticket(
    db: Session,
    lottery_type: str,
    bet_numbers: Any,
    window: Any = 30,
    multiple: int = 1,
    play: Optional[str] = None,
    pick: Optional[int] = None,
) -> dict:
    lottery = normalize_type(lottery_type)
    if lottery not in LOTTERIES:
        raise ValueError("未知彩种")
    window_label, limit = parse_window(window)
    preview = calculate(lottery, bet_numbers, None, multiple, play=play, pick=pick)
    rows = _load_draws(db, lottery)
    history_size = len(rows)
    if limit is None:
        chosen = rows[-MAX_TICKET_PERIODS:]
        capped = history_size > MAX_TICKET_PERIODS
    else:
        span = min(limit, MAX_TICKET_PERIODS)
        chosen = rows[-span:]
        capped = limit > MAX_TICKET_PERIODS and history_size > MAX_TICKET_PERIODS
    events = []
    skipped = 0
    for row in chosen:
        try:
            result = calculate(
                lottery,
                bet_numbers,
                parse_numbers(row.numbers),
                multiple,
                play=play,
                pick=pick,
            )
        except ValueError:
            skipped += 1
            continue
        events.append(
            {
                "issue": row.issue,
                "draw_date": row.draw_date or "",
                "result": result,
                "numbers": {"main": preview["bet"]["main"], "special": preview["bet"]["special"]},
            }
        )
    summary = _summarize(preview["table"], events)
    return {
        "lottery_type": lottery,
        "window": window_label,
        "history_size": history_size,
        "capped": capped,
        "cap_note": f"期数较多，只回放了最近 {summary['sample_size'] + skipped} 期。" if capped else "",
        "skipped_draws": skipped,
        "play_name": preview["play_name"],
        "bets": preview["bets"],
        "multiple": preview["multiple"],
        "bet": preview["bet"],
        "disclaimer": DISCLAIMER,
        "note": NOTE,
        **summary,
    }


def _tickets_of(recommendations: list[dict]) -> list[dict]:
    return [{"main": list(item["main"]), "special": list(item.get("special") or [])} for item in recommendations]


def _walk(db: Session, lottery: str, strategy: str, constraints, tickets: int, targets: list[Draw], prior_of: dict[str, int]) -> dict:
    periods = []
    events = []
    table: list[dict] = []
    skipped = 0
    for row in targets:
        generated = generate(
            db,
            lottery,
            strategy,
            count=tickets,
            constraints=constraints,
            max_attempts=REPLAY_ATTEMPTS,
            before_issue=row.issue,
        )
        picked = _tickets_of(generated["recommendations"])
        draw_numbers = parse_numbers(row.numbers)
        period_events = []
        try:
            for ticket in picked:
                result = calculate(lottery, ticket, draw_numbers)
                if not table:
                    table = result["table"]
                period_events.append({"result": result, "numbers": ticket})
        except ValueError:
            skipped += 1
            continue
        period_prize = round(sum(item["result"]["amount"] for item in period_events), 2)
        period_spent = round(sum(item["result"]["cost"] for item in period_events), 2)
        winner = None
        for item in period_events:
            if item["result"]["amount"] <= 0:
                continue
            candidate = {"amount": item["result"]["amount"], "level": item["result"]["level"], "numbers": item["numbers"]}
            if winner is None or candidate["amount"] > winner["amount"]:
                winner = candidate
        periods.append(
            {
                "issue": row.issue,
                "draw_date": row.draw_date or "",
                "prior_draws": prior_of.get(row.issue, 0),
                "tickets": picked,
                "prize": period_prize,
                "spent": period_spent,
                "win": period_prize > 0,
                "level": winner["level"] if winner else "未中奖",
            }
        )
        for item in period_events:
            events.append(
                {
                    "issue": row.issue,
                    "draw_date": row.draw_date or "",
                    "result": item["result"],
                    "numbers": item["numbers"],
                }
            )
    summary = _summarize(table, events)
    # 一期买多注时，中奖次数按注计；不中期数按整期有没有奖金计。
    longest = 0
    streak = 0
    for period in periods:
        if period["win"]:
            streak = 0
        else:
            streak += 1
            longest = max(longest, streak)
    summary["longest_miss"] = longest
    summary["sample_size"] = len(periods)
    summary["win_draws"] = sum(1 for period in periods if period["win"])
    return {
        "name": strategy,
        "label": STRATEGY_LABELS.get(strategy, strategy),
        "constraints_applied": constraints_requested(constraints),
        "periods": periods,
        "latest_tickets": periods[-1]["tickets"] if periods else [],
        "skipped_draws": skipped,
        **summary,
    }


def replay_strategy(
    db: Session,
    lottery_type: str,
    strategy: str = "hot",
    constraints=None,
    tickets: int = 1,
    window: Any = 30,
    seed: Optional[int] = None,
) -> dict:
    lottery = normalize_type(lottery_type)
    if lottery not in LOTTERIES:
        raise ValueError("未知彩种")
    mode = (strategy or "hot").strip().lower()
    if mode == "pulse":
        raise ValueError("历史回放不包含脉动综合。请改用热号、冷号、混合或随机。")
    if mode not in ALLOWED_STRATEGIES:
        raise ValueError("策略只支持热号、冷号、混合或随机")
    count = int(tickets)
    if count < 1 or count > 5:
        raise ValueError("每期注数为 1–5")
    window_label, limit = parse_window(window)
    if constraints_requested(constraints):
        from .predict import _prepare

        _prepare(lottery, constraints)
    rows = _load_draws(db, lottery)
    history_size = len(rows)
    take = history_size if limit is None else min(limit, history_size)
    capped = False
    if take > MAX_STRATEGY_PERIODS:
        take = MAX_STRATEGY_PERIODS
        capped = True
    targets = rows[-take:] if take else []
    prior_of = {row.issue: index for index, row in enumerate(rows)}
    state = random.getstate()
    try:
        if seed is not None:
            random.seed(int(seed))
        played = _walk(db, lottery, mode, constraints, count, targets, prior_of)
        if seed is not None:
            random.seed(int(seed) + 1)
        baseline = _walk(db, lottery, "random", None, count, targets, prior_of)
    finally:
        random.setstate(state)
    return {
        "lottery_type": lottery,
        "window": window_label,
        "history_size": history_size,
        "sample_size": played["sample_size"],
        "capped": capped,
        "cap_note": f"逐期前推最多对照最近 {MAX_STRATEGY_PERIODS} 期。" if capped else "",
        "tickets_per_draw": count,
        "strategy": played,
        "baseline": baseline,
        "disclaimer": DISCLAIMER,
        "note": STRATEGY_NOTE,
        "entertainment_only": True,
    }
