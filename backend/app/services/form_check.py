"""一注体检：把一注号码对照本地历史的静态形态区间。

看和值、跨度、奇数个数、区位偏度、AC、尾数种类、和尾、012 路偏度
落在历史 p25–p75 常见带的哪一侧。特别号单独计算，不并进主号。
这里没有短窗、长窗，也不给下期号码。只读本地开奖。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..lotteries import normalize_type, parse_numbers
from ..models import Draw
from .ac import _ac_of
from .echo import PROFILES, normalize_query
from .hewei import _hewei_of
from .parity import _parity_of
from .road import _counts_of as _road_counts
from .road import _imbalance as _road_imbalance
from .span import _span_of
from .sum_pulse import _sum_of
from .tail import _tails_of
from .zone import _counts_of as _zone_counts
from .zone import _imbalance as _zone_imbalance
from .zone import _ratio as _zone_ratio
from .zone import _zone_defs

DISCLAIMER = "一注体检对照本地历史开奖的形态区间，看这注偏不偏，不是推荐下期号码。仅供娱乐，不构成投注建议。"

METRIC_SPEC = (
    ("sum", "和值", ""),
    ("span", "跨度", ""),
    ("odd", "奇偶", "奇数个数"),
    ("zone", "区位", "偏度"),
    ("ac", "AC", ""),
    ("tail", "尾数", ""),
    ("hewei", "和尾", ""),
    ("road", "012路", "路偏"),
)
ROAD_ORDER = ("0", "1", "2")
_STANCE_LABEL = {"low": "偏低", "center": "居中", "high": "偏高"}


def _limit_of(limit) -> int:
    try:
        number = int(limit)
    except (TypeError, ValueError):
        number = 80
    return max(1, min(number, 200))


def _fmt(value) -> str:
    if value is None:
        return ""
    rounded = round(float(value), 2)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def _as_number(value):
    rounded = round(float(value), 2)
    if rounded == int(rounded):
        return int(rounded)
    return rounded


def _quantile(values: list, q: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (len(ordered) - 1) * q
    lower = int(pos)
    upper = min(lower + 1, len(ordered) - 1)
    frac = pos - lower
    return ordered[lower] * (1 - frac) + ordered[upper] * frac


def _blank_place(label: str, sample_size: int) -> dict:
    return {
        "percentile": None,
        "band_low": None,
        "band_high": None,
        "band_label": "",
        "history_min": None,
        "history_max": None,
        "stance": "unavailable",
        "stance_label": label,
        "sample_size": sample_size,
    }


def place_value(value, history) -> dict:
    """对照一段历史给出 p25–p75、百分位和偏低 / 居中 / 偏高。

    百分位是「小于等于当前值的期数 / 样本数」，和已有打分里的分位同一算法。
    常见带含两端：等于 p25 或 p75 仍算居中。值为空时记不适用。
    """
    series = [item for item in (history or []) if item is not None]
    if value is None:
        return _blank_place("不适用", len(series))
    if not series:
        return _blank_place("样本不足", 0)
    band_low = _as_number(_quantile(series, 0.25))
    band_high = _as_number(_quantile(series, 0.75))
    current = float(value)
    if current < float(band_low):
        stance = "low"
    elif current > float(band_high):
        stance = "high"
    else:
        stance = "center"
    percentile = round(sum(item <= current for item in series) / len(series), 4)
    if band_low == band_high:
        band_label = _fmt(band_low)
    else:
        band_label = f"{_fmt(band_low)}–{_fmt(band_high)}"
    return {
        "percentile": percentile,
        "band_low": band_low,
        "band_high": band_high,
        "band_label": band_label,
        "history_min": min(series),
        "history_max": max(series),
        "stance": stance,
        "stance_label": _STANCE_LABEL[stance],
        "sample_size": len(series),
    }


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
                "main": main,
                "special": _unique(_history_group(parsed["special"], width)),
                "source": row.source or "seed",
            }
        )
    status = "mixed" if any(item["source"] == "crawl" for item in draws) else "seed"
    return draws, status


def _road_ratio(counts: dict[str, int] | None) -> str:
    if not counts:
        return ""
    return ":".join(str(counts[key]) for key in ROAD_ORDER)


def _present(numbers: list[str], profile: dict, special: bool) -> dict[str, tuple]:
    """返回 key -> (数值, 展示)。特别号少于两个时不算跨度和 AC。"""
    if not numbers:
        return {}
    found: dict[str, tuple] = {}
    total = _sum_of(numbers)
    found["sum"] = (total, _fmt(total))
    if not special or len(numbers) >= 2:
        span = _span_of(numbers)
        found["span"] = (span, _fmt(span))
    parity = _parity_of(numbers)
    if parity:
        odd, even, _gap = parity
        found["odd"] = (odd, f"{odd}奇{even}偶")
    zones = _zone_defs(profile, special=special)
    zone_counts = _zone_counts(numbers, zones) if zones else None
    if zone_counts:
        found["zone"] = (_zone_imbalance(zone_counts), _zone_ratio(zone_counts) or "")
    ac = _ac_of(numbers)
    if not special or ac is not None:
        found["ac"] = (ac, _fmt(ac))
    tails = _tails_of(numbers)
    if tails:
        found["tail"] = (tails[2], f"{tails[2]}种")
    hewei = _hewei_of(numbers)
    found["hewei"] = (hewei, _fmt(hewei))
    roads = _road_counts(numbers)
    if roads:
        found["road"] = (_road_imbalance(roads), _road_ratio(roads))
    return found


def _note(label: str, display: str, placed: dict, compared: str) -> str:
    shown = display or "—"
    if placed["stance_label"] == "不适用":
        return f"{label}算不出来。"
    if placed["stance"] == "unavailable":
        return f"{label} {shown}，还没有历史可对照。"
    band = placed["band_label"]
    if compared:
        band = f"{compared} {band}"
    return f"{label} {shown}，常见带 {band}，{placed['stance_label']}。"


def _metric(key: str, label: str, compared: str, value, display: str, history: list) -> dict:
    placed = place_value(value, history)
    shown = display if value is not None else ""
    return {
        "key": key,
        "label": label,
        "value": value,
        "display": shown,
        "compared": compared,
        "note": _note(label, shown, placed, compared),
        **placed,
    }


def _rows(present: dict[str, tuple], histories: dict[str, list], require_all: bool) -> list[dict]:
    rows = []
    for key, label, compared in METRIC_SPEC:
        if key not in present:
            if not require_all:
                continue
            value, display = None, ""
        else:
            value, display = present[key]
        if not require_all and value is None:
            continue
        rows.append(_metric(key, label, compared, value, display, histories.get(key, [])))
    return rows


def _summary(metrics: list[dict]) -> dict:
    return {
        "centered": sum(item["stance"] == "center" for item in metrics),
        "low": sum(item["stance"] == "low" for item in metrics),
        "high": sum(item["stance"] == "high" for item in metrics),
        "unavailable": sum(item["stance"] == "unavailable" for item in metrics),
    }


def _glance(metrics: list[dict]) -> str:
    if metrics and all(item["stance"] == "unavailable" for item in metrics):
        if any(item["value"] is not None for item in metrics):
            return "还没有历史可对照"
        return "这注形态算不出来"
    summary = _summary(metrics)
    if summary["low"] == 0 and summary["high"] == 0 and summary["unavailable"] == 0 and summary["centered"]:
        return "形态居中"
    parts = []
    if summary["centered"]:
        parts.append(f"{summary['centered']} 项居中")
    if summary["low"]:
        parts.append(f"{summary['low']} 项偏低")
    if summary["high"]:
        parts.append(f"{summary['high']} 项偏高")
    if summary["unavailable"]:
        parts.append(f"{summary['unavailable']} 项暂无")
    return " · ".join(parts)


def _collect(draws: list[dict], profile: dict, field: str, special: bool) -> dict[str, list]:
    histories = {key: [] for key, _label, _compared in METRIC_SPEC}
    for draw in draws:
        numbers = draw[field]
        if not numbers:
            continue
        for key, (value, _display) in _present(numbers, profile, special=special).items():
            if value is not None:
                histories[key].append(value)
    return histories


def center_bands(db: Session, lottery_type: str, limit: int = 80) -> dict:
    """主号和值、跨度、奇数个数的 p25–p75，算法与一注体检的常见带相同。"""
    lottery = normalize_type(lottery_type)
    if lottery not in PROFILES:
        raise ValueError("未知彩种")
    profile = PROFILES[lottery]
    limit_n = _limit_of(limit)
    draws, status = _load(db, lottery, profile, limit_n)
    histories = _collect(draws, profile, "main", special=False)
    bands: dict[str, dict] = {}
    ready = True
    for key, label in (("sum", "和值"), ("span", "跨度"), ("odd", "奇数")):
        series = [item for item in histories.get(key, []) if item is not None]
        if not series:
            ready = False
            break
        low = _as_number(_quantile(series, 0.25))
        high = _as_number(_quantile(series, 0.75))
        bands[key] = {
            "low": low,
            "high": high,
            "label": label,
            "band_label": _fmt(low) if low == high else f"{_fmt(low)}–{_fmt(high)}",
        }
    return {
        "lottery_type": lottery,
        "sample_size": len(draws),
        "limit": limit_n,
        "ready": ready,
        "bands": bands if ready else {},
        "data_status": status,
        "disclaimer": DISCLAIMER,
    }


def _assemble(query: dict, profile: dict, draws: list, status: str, limit_n: int, main_history: dict, special_history: dict) -> dict:
    metrics = _rows(_present(query["main"], profile, special=False), main_history, require_all=True)
    special_metrics = []
    if query["special"]:
        special_metrics = _rows(
            _present(query["special"], profile, special=True),
            special_history,
            require_all=False,
        )
    return {
        "lottery_type": query["lottery_type"],
        "mode": profile["mode"],
        "sample_size": len(draws),
        "limit": limit_n,
        "band": "p25-p75",
        "query": {"main": query["main"], "special": query["special"]},
        "metrics": metrics,
        "special_metrics": special_metrics,
        "summary": _summary(metrics),
        "glance": _glance(metrics),
        "data_status": status,
        "disclaimer": DISCLAIMER,
        "number_scope": "主号",
    }


def _prepare(db: Session, lottery: str, profile: dict, limit: int):
    limit_n = _limit_of(limit)
    draws, status = _load(db, lottery, profile, limit_n)
    return (
        limit_n,
        draws,
        status,
        _collect(draws, profile, "main", special=False),
        _collect(draws, profile, "special", special=True),
    )


def check_form(db: Session, lottery_type: str, main, special=None, limit: int = 80) -> dict:
    """给一注做形态体检。main / special 的个数和范围跟回声、脉动打分同一套规则。"""
    query = normalize_query(lottery_type, main, special)
    lottery = query["lottery_type"]
    profile = PROFILES[lottery]
    limit_n, draws, status, main_history, special_history = _prepare(db, lottery, profile, limit)
    return _assemble(query, profile, draws, status, limit_n, main_history, special_history)


BATCH_LIMIT = 200


def _ticket_fields(ticket) -> tuple[str, object, object]:
    if not isinstance(ticket, dict):
        raise ValueError("注的格式不对")
    ticket_id = str(ticket.get("id") or "")
    main = ticket.get("main")
    special = ticket.get("special")
    numbers = ticket.get("numbers")
    if main is None and numbers is not None:
        if isinstance(numbers, dict):
            main = numbers.get("main", numbers.get("red", numbers.get("front")))
            if special is None:
                special = numbers.get("special", numbers.get("blue", numbers.get("back")))
        else:
            main = numbers
    return ticket_id, main, special


def check_form_batch(db: Session, lottery_type: str, tickets, limit: int = 80) -> dict:
    """同一彩种多注一次对照历史分位。每注结果与 check_form 相同，失败的注单独标出。"""
    lottery = normalize_type(lottery_type)
    if lottery not in PROFILES:
        raise ValueError("未知彩种")
    if tickets is None:
        tickets = []
    if not isinstance(tickets, list):
        raise ValueError("请给出要打分的注")
    if len(tickets) > BATCH_LIMIT:
        raise ValueError(f"一次最多打分 {BATCH_LIMIT} 注")
    profile = PROFILES[lottery]
    limit_n, draws, status, main_history, special_history = _prepare(db, lottery, profile, limit)
    items = []
    for index, ticket in enumerate(tickets):
        ticket_id = str(ticket.get("id") or "") if isinstance(ticket, dict) else ""
        try:
            ticket_id, main, special = _ticket_fields(ticket)
            query = normalize_query(lottery, main, special)
            report = _assemble(query, profile, draws, status, limit_n, main_history, special_history)
            items.append({"id": ticket_id, "index": index, "ok": True, "error": "", "report": report})
        except ValueError as exc:
            items.append({"id": ticket_id, "index": index, "ok": False, "error": str(exc), "report": None})
    return {
        "lottery_type": lottery,
        "limit": limit_n,
        "sample_size": len(draws),
        "band": "p25-p75",
        "data_status": status,
        "disclaimer": DISCLAIMER,
        "items": items,
    }
