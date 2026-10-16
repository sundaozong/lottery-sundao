"""购买记录的按月汇总、花费节奏与 CSV 导出。只读，不改记录本身。"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import date, datetime

from ..lotteries import LOTTERIES, load_bet, normalize_type
from ..models import PurchaseRecord
from .prize import play_name

UNDATED = "未填日期"
RHYTHM_NOTE = "只对照你自己的账本，看花费节奏和有没有重复买同一注。不是劝买，也不是劝停。"
SET_TYPES = {"ssq", "dlt", "qlc", "kl8"}


def month_key(purchased_at: str | None) -> str:
    text = (purchased_at or "").strip()
    matched = re.match(r"^(\d{4})[-/](\d{2})", text)
    if matched and 1 <= int(matched.group(2)) <= 12:
        return f"{matched.group(1)}-{matched.group(2)}"
    compact = re.match(r"^(\d{4})(\d{2})\d{2}$", text)
    if compact and 1 <= int(compact.group(2)) <= 12:
        return f"{compact.group(1)}-{compact.group(2)}"
    return UNDATED


def monthly_summary(rows: list[PurchaseRecord]) -> dict:
    buckets: dict[str, dict] = {}
    for row in rows:
        key = month_key(row.purchased_at)
        bucket = buckets.setdefault(
            key,
            {"month": key, "count": 0, "total_cost": 0.0, "total_prize": 0.0},
        )
        bucket["count"] += 1
        bucket["total_cost"] += row.cost or 0
        bucket["total_prize"] += row.prize or 0
    months = []
    for bucket in buckets.values():
        bucket["total_cost"] = round(bucket["total_cost"], 2)
        bucket["total_prize"] = round(bucket["total_prize"], 2)
        bucket["net"] = round(bucket["total_prize"] - bucket["total_cost"], 2)
        months.append(bucket)
    dated = [item for item in months if item["month"] != UNDATED]
    undated = [item for item in months if item["month"] == UNDATED]
    dated.sort(key=lambda item: item["month"], reverse=True)
    return {"months": dated + undated}


def _csv_safe(value) -> str:
    text = "" if value is None else str(value)
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


def parse_day(value: str | None) -> date | None:
    text = (value or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", text):
        chunk, fmt = text[:10], "%Y-%m-%d"
    elif re.match(r"^\d{4}/\d{2}/\d{2}", text):
        chunk, fmt = text[:10], "%Y/%m/%d"
    elif re.match(r"^\d{8}", text):
        chunk, fmt = text[:8], "%Y%m%d"
    else:
        return None
    try:
        return datetime.strptime(chunk, fmt).date()
    except ValueError:
        return None


def ticket_signature(lottery_type: str, bet: dict) -> str:
    """同一注的指纹。号码集合忽略顺序；定位玩法保留位次，忽略倍数。"""
    t = normalize_type(lottery_type)
    play = bet.get("play") or ""
    positions = bet.get("positions") or []
    if any(positions):
        core = [sorted(str(n) for n in pos) for pos in positions]
    elif t in SET_TYPES or play.startswith("group"):
        core = [
            sorted(str(n) for n in (bet.get("main") or [])),
            sorted(str(n) for n in (bet.get("special") or [])),
        ]
    else:
        core = [str(n) for n in (bet.get("main") or [])] + [str(n) for n in (bet.get("special") or [])]
    return json.dumps(
        {"t": t, "play": play, "pick": bet.get("pick"), "core": core},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _month_slice(rows: list[PurchaseRecord], month: str) -> dict:
    chosen = [row for row in rows if month_key(row.purchased_at) == month]
    cost = round(sum((row.cost or 0) for row in chosen), 2)
    prize = round(sum((row.prize or 0) for row in chosen), 2)
    return {
        "count": len(chosen),
        "total_cost": cost,
        "total_prize": prize,
        "net": round(prize - cost, 2),
    }


def _previous_month(day: date) -> str:
    year = day.year
    month = day.month - 1
    if month == 0:
        year -= 1
        month = 12
    return f"{year:04d}-{month:02d}"


def rhythm(rows: list[PurchaseRecord], today: date | None = None) -> dict:
    today = today or date.today()
    current_month = f"{today.year:04d}-{today.month:02d}"
    previous_month = _previous_month(today)
    current = _month_slice(rows, current_month)
    previous = _month_slice(rows, previous_month)
    groups: dict[str, dict] = {}
    for row in rows:
        bet = load_bet(row.numbers)
        key = ticket_signature(row.lottery_type, bet)
        group = groups.setdefault(key, {"bet": bet, "lottery_type": row.lottery_type, "rows": []})
        group["rows"].append(row)
    repeats = []
    for group in groups.values():
        grouped = group["rows"]
        if len(grouped) < 2:
            continue
        cost = round(sum((row.cost or 0) for row in grouped), 2)
        prize = round(sum((row.prize or 0) for row in grouped), 2)
        repeats.append(
            {
                "lottery_type": group["lottery_type"],
                "name": LOTTERIES.get(group["lottery_type"], {}).get("name", group["lottery_type"]),
                "play_name": play_name(group["lottery_type"], group["bet"]),
                "numbers_text": repeat_numbers_text(group["lottery_type"], group["bet"]),
                "count": len(grouped),
                "issues": [row.issue for row in grouped],
                "total_cost": cost,
                "total_prize": prize,
            }
        )
    repeats.sort(key=lambda item: (-item["count"], item["name"], item["numbers_text"]))
    days = sorted({day for day in (parse_day(row.purchased_at) for row in rows) if day})
    gaps = [(b - a).days for a, b in zip(days, days[1:])]
    total_cost = round(sum((row.cost or 0) for row in rows), 2)
    return {
        "as_of": today.isoformat(),
        "current_month": current_month,
        "previous_month": previous_month,
        "current": current,
        "previous": previous,
        "cost_delta": round(current["total_cost"] - previous["total_cost"], 2),
        "slip_count": len(rows),
        "avg_cost": round(total_cost / len(rows), 2) if rows else None,
        "distinct_days": len(days),
        "longest_gap_days": max(gaps) if gaps else None,
        "repeat_groups": repeats,
        "disclaimer": RHYTHM_NOTE,
    }


def _ordered(values) -> list[str]:
    return sorted((str(n) for n in values), key=lambda item: (int(item) if item.isdigit() else 9999, item))


def repeat_numbers_text(lottery_type: str, bet: dict) -> str:
    """同一注展示用。集合玩法按大小排，定位玩法保留位次。"""
    positions = bet.get("positions") or []
    if any(positions):
        return numbers_text(bet)
    play = bet.get("play") or ""
    if normalize_type(lottery_type) in SET_TYPES or play.startswith("group"):
        main = " ".join(_ordered(bet.get("main") or []))
        special = " ".join(_ordered(bet.get("special") or []))
        if special:
            return f"{main} + {special}" if main else special
        return main
    return numbers_text(bet)


def numbers_text(bet: dict) -> str:
    positions = bet.get("positions") or []
    if any(positions):
        return " | ".join(" ".join(str(n) for n in pos) for pos in positions)
    main = " ".join(str(n) for n in (bet.get("main") or []))
    special = " ".join(str(n) for n in (bet.get("special") or []))
    if special:
        return f"{main} + {special}" if main else special
    return main


def records_csv(rows: list[PurchaseRecord]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["彩种", "期号", "玩法", "号码", "投入", "奖金", "盈亏", "购买日期", "备注"])
    for row in rows:
        bet = load_bet(row.numbers)
        name = LOTTERIES.get(row.lottery_type, {}).get("name", row.lottery_type)
        profit = round((row.prize or 0) - (row.cost or 0), 2)
        writer.writerow(
            [
                _csv_safe(name),
                _csv_safe(row.issue),
                _csv_safe(play_name(row.lottery_type, bet)),
                _csv_safe(numbers_text(bet)),
                row.cost,
                row.prize,
                profit,
                _csv_safe(row.purchased_at),
                _csv_safe(row.note),
            ]
        )
    return buffer.getvalue()
