"""脉动综合：用已有的单注打分函数给一批候选票排序。

每个模块仍走自己的 score_*，窗口参数用该函数的默认值。
新的打分函数只要接受 (db, lottery_type, main, special)，
并且返回 ticket 上的 typicality / alignment / rarity，
或动量、邻号、重号这几种现成形状，就可以在 PULSE_MODULES 里加一行。

撞车、回声、结伴、形态没有单注打分，不参与综合。
分数只说明这注像不像近期样本里的形态，不是中奖预测。
"""
from __future__ import annotations

import importlib
import random
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..lotteries import normalize_type
from .analyze import analyze
from .cluster import score_cluster
from .echo import PROFILES
from .momentum import score_momentum
from .neighbor import score_neighbor
from .parity import score_parity
from .prime import score_prime
from .predict import DISCLAIMER
from .ac import score_ac
from .hewei import score_hewei
from .daxiao import score_daxiao
from .shengping import score_shengping
from .zhenfu import score_zhenfu
from .tail import score_tail
from .zone import score_zone
from .repeat import score_repeat
from .road import score_road
from .span import score_span
from .sum_pulse import score_sum

# (主号个数, 特别号个数, 主号是否允许重复)
TICKET_SHAPE = {
    "ssq": (6, 1, False),
    "dlt": (5, 2, False),
    "fc3d": (3, 0, True),
    "pl3": (3, 0, True),
    "pl5": (5, 0, True),
    "qxc": (6, 1, True),
    "qlc": (7, 0, False),
    "kl8": (20, 0, False),
}

_ALIGNMENT = {"aligned": 1.0, "neutral": 0.5, "against": 0.0}
_RARITY = {"common": 1.0, "typical": 0.6, "rare": 0.2}

SKIPPED_MODULES = [
    {"module": "collision", "reason": "只比较多注之间的撞车，没有单注打分"},
    {"module": "echo", "reason": "回声检索历史重合期次，不是脉动打分"},
    {"module": "affinity", "reason": "结伴统计没有单注打分接口"},
    {"module": "shape", "reason": "形态统计没有单注打分接口"},
]

_MEMO_TARGETS = (
    ("app.services.repeat", "repeat_pulse"),
    ("app.services.momentum", "momentum_summary"),
    ("app.services.neighbor", "neighbor_summary"),
    ("app.services.neighbor", "_load"),
    ("app.services.span", "span_summary"),
    ("app.services.cluster", "cluster_summary"),
    ("app.services.road", "road_summary"),
    ("app.services.sum_pulse", "sum_summary"),
    ("app.services.parity", "parity_summary"),
    ("app.services.prime", "prime_summary"),
    ("app.services.zone", "zone_summary"),
    ("app.services.tail", "tail_summary"),
    ("app.services.ac", "ac_summary"),
    ("app.services.hewei", "hewei_summary"),
    ("app.services.daxiao", "daxiao_summary"),
    ("app.services.shengping", "shengping_summary"),
    ("app.services.zhenfu", "zhenfu_summary"),
)


@dataclass(frozen=True)
class PulseModule:
    key: str
    label: str
    score: Callable


PULSE_MODULES = [
    PulseModule("repeat", "重号", score_repeat),
    PulseModule("momentum", "动量", score_momentum),
    PulseModule("neighbor", "邻号", score_neighbor),
    PulseModule("span", "跨度", score_span),
    PulseModule("cluster", "连号簇", score_cluster),
    PulseModule("road", "012路", score_road),
    PulseModule("sum", "和值", score_sum),
    PulseModule("parity", "奇偶", score_parity),
    PulseModule("prime", "质合", score_prime),
    PulseModule("zone", "区位", score_zone),
    PulseModule("tail", "尾数", score_tail),
    PulseModule("ac", "AC值", score_ac),
    PulseModule("hewei", "和尾", score_hewei),
    PulseModule("daxiao", "大小", score_daxiao),
    PulseModule("shengping", "升平降", score_shengping),
    PulseModule("zhenfu", "振幅", score_zhenfu),
]


def _freeze(value):
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _install_memo():
    """同一轮推荐里，每份历史摘要只算一次。score_* 本身不改。"""
    saved = []
    cache: dict = {}

    def wrap(fn):
        def wrapped(*args, **kwargs):
            key = (id(fn), _freeze(args[1:]), _freeze(kwargs))
            if key not in cache:
                cache[key] = fn(*args, **kwargs)
            return cache[key]

        return wrapped

    for module_name, attr in _MEMO_TARGETS:
        module = importlib.import_module(module_name)
        original = getattr(module, attr)
        saved.append((module, attr, original))
        setattr(module, attr, wrap(original))
    return saved


def _restore_memo(saved) -> None:
    for module, attr, original in saved:
        setattr(module, attr, original)


def _shape_score(ticket: dict) -> float | None:
    if not isinstance(ticket, dict):
        return None
    parts = []
    if ticket.get("typicality") is not None:
        parts.append(float(ticket["typicality"]))
    alignment = ticket.get("alignment")
    if alignment in _ALIGNMENT:
        parts.append(_ALIGNMENT[alignment])
    rarity = ticket.get("rarity")
    if rarity in _RARITY:
        parts.append(_RARITY[rarity])
    if not parts:
        return None
    return round(sum(parts) / len(parts), 4)


def _blend(main_score: float | None, special_score: float | None) -> float | None:
    if main_score is None:
        return special_score
    if special_score is None:
        return main_score
    return round(main_score * 0.75 + special_score * 0.25, 4)


def _trend_score(ticket: dict) -> float | None:
    if not isinstance(ticket, dict) or "rising_count" not in ticket:
        return None
    rising = int(ticket.get("rising_count") or 0)
    falling = int(ticket.get("falling_count") or 0)
    flat = int(ticket.get("flat_count") or 0)
    total = rising + falling + flat
    if total <= 0:
        return None
    return round((rising + 0.5 * flat) / total, 4)


def _neighbor_score(ticket: dict) -> float | None:
    if not isinstance(ticket, dict) or "pulled_count" not in ticket:
        return None
    pulled = int(ticket.get("pulled_count") or 0)
    idle = int(ticket.get("idle_count") or 0)
    total = pulled + idle
    if total <= 0:
        return None
    ratio = pulled / total
    strength = float(ticket.get("strength") or 0)
    lift = min(1.0, strength / max(pulled, 1))
    return round(min(1.0, ratio + (1 - ratio) * 0.5 * lift), 4)


def _repeat_score(result: dict) -> tuple[float | None, str]:
    overlap = result.get("overlap")
    if overlap is None:
        return None, ""
    rates = {
        item.get("overlap"): float(item.get("rate") or 0)
        for item in (result.get("distribution") or [])
        if isinstance(item, dict)
    }
    typicality = rates.get(overlap)
    note = f"重号 {overlap} 个"
    mean = result.get("mean")
    if mean is not None:
        span = max(int(result.get("max") or 0), 1)
        closeness = 1 - min(1.0, abs(float(overlap) - float(mean)) / span)
        if typicality is None:
            return round(closeness, 4), note
        return round(0.6 * typicality + 0.4 * closeness, 4), note
    if typicality is not None:
        return round(typicality, 4), note
    percentile = result.get("percentile")
    if percentile is None:
        return None, ""
    return round(float(percentile), 4), note


def contribution(result: dict) -> tuple[float | None, str]:
    """把各模块的票面字段收成 0–1。对不上已知形状时返回 None，不拉低总分。"""
    if not isinstance(result, dict):
        return None, ""
    ticket = result.get("ticket")
    if isinstance(ticket, dict):
        if any(key in ticket for key in ("typicality", "alignment", "rarity")):
            score = _blend(_shape_score(ticket), _shape_score(result.get("special_ticket") or {}))
            note = str(ticket.get("note") or "").strip()
            special = result.get("special_ticket")
            if not note and isinstance(special, dict):
                note = str(special.get("note") or "").strip()
            return score, note
        if "rising_count" in ticket:
            score = _blend(_trend_score(ticket), _trend_score(result.get("special_ticket") or {}))
            note = f"上升 {int(ticket.get('rising_count') or 0)}，回落 {int(ticket.get('falling_count') or 0)}，持平 {int(ticket.get('flat_count') or 0)}"
            return score, note
        if "pulled_count" in ticket:
            score = _blend(_neighbor_score(ticket), _neighbor_score(result.get("special_ticket") or {}))
            pulled = int(ticket.get("pulled_count") or 0)
            idle = int(ticket.get("idle_count") or 0)
            return score, f"邻号拉动 {pulled}/{pulled + idle}"
        raw = ticket.get("score")
        if isinstance(raw, (int, float)) and not isinstance(raw, bool) and 0 <= float(raw) <= 1:
            return round(float(raw), 4), str(ticket.get("note") or "").strip()
    if "overlap" in result or result.get("percentile") is not None:
        return _repeat_score(result)
    return None, ""


def combine_scores(rows: list[dict]) -> float | None:
    numerator = 0.0
    denominator = 0.0
    for row in rows:
        score = row.get("score")
        weight = float(row.get("weight", 1) or 0)
        if score is None or weight <= 0:
            continue
        numerator += weight * float(score)
        denominator += weight
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _rationale(breakdown: list[dict], total: float | None) -> str:
    if total is None:
        return "近期样本不足，脉动模块暂无对照。仅供娱乐，不构成投注建议。"
    ranked = sorted(
        (row for row in breakdown if isinstance(row.get("score"), (int, float))),
        key=lambda row: row["score"],
        reverse=True,
    )
    lead = "、".join(f"{row['label']} {row['score']:.2f}" for row in ranked[:3])
    if not lead:
        return "近期样本不足，脉动模块暂无对照。仅供娱乐，不构成投注建议。"
    return f"综合 {total:.2f}，较高的是{lead}。只是近期形态对照，仅供娱乐，不构成投注建议。"


def _require_lottery(lottery_type: str) -> str:
    lottery = normalize_type(lottery_type)
    if lottery not in PROFILES or lottery not in TICKET_SHAPE:
        raise ValueError("脉动综合暂不支持该彩种")
    return lottery


def _normalize_weights(weights: dict | None, modules: list[PulseModule]) -> dict[str, float]:
    allowed = [module.key for module in modules]
    if not weights:
        return {key: 1.0 for key in allowed}
    cleaned: dict[str, float] = {}
    for key, value in weights.items():
        if key not in allowed:
            raise ValueError(f"未知脉动权重：{key}")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("权重需要是非负数") from exc
        if number < 0:
            raise ValueError("权重需要是非负数")
        cleaned[key] = number
    for key in allowed:
        cleaned.setdefault(key, 1.0)
    if all(value <= 0 for value in cleaned.values()):
        raise ValueError("权重不能全为 0")
    return cleaned


def _score_one(db: Session, lottery: str, ticket: dict, modules: list[PulseModule], weights: dict[str, float]) -> dict:
    breakdown = []
    for module in modules:
        raw = module.score(db, lottery, ticket["main"], ticket.get("special") or [])
        score, note = contribution(raw)
        breakdown.append(
            {
                "module": module.key,
                "label": module.label,
                "score": score,
                "note": note,
                "weight": weights.get(module.key, 1.0),
            }
        )
    total = combine_scores(breakdown)
    return {
        "main": list(ticket["main"]),
        "special": list(ticket.get("special") or []),
        "score": total,
        "rationale": _rationale(breakdown, total),
        "breakdown": breakdown,
    }


def score_ticket(db: Session, lottery_type: str, main, special=None, weights: dict | None = None, modules: list[PulseModule] | None = None) -> dict:
    lottery = _require_lottery(lottery_type)
    chosen = list(modules or PULSE_MODULES)
    parsed_weights = _normalize_weights(weights, chosen)
    saved = _install_memo()
    try:
        return _score_one(
            db,
            lottery,
            {"main": list(main or []), "special": list(special or [])},
            chosen,
            parsed_weights,
        )
    finally:
        _restore_memo(saved)


def _weights_for(counts: list[int], mode: str) -> list[float]:
    if mode == "hot":
        return [count + 1 for count in counts]
    if mode == "cold":
        peak = max(counts) if counts else 1
        return [peak - count + 1 for count in counts]
    if mode == "hybrid":
        return [(count + 1) * 0.6 + 1 for count in counts]
    return [1.0] * len(counts)


def _choose_one(pool: list[str], weights: list[float], rng: random.Random) -> str:
    total = sum(weights) or 1.0
    cursor = rng.random() * total
    acc = 0.0
    for item, weight in zip(pool, weights):
        acc += weight
        if acc >= cursor:
            return item
    return pool[-1]


def _sample_without(pool: list[str], weights: list[float], k: int, rng: random.Random) -> list[str]:
    items = list(zip(pool, weights))
    chosen = []
    for _ in range(min(k, len(items))):
        names = [item for item, _weight in items]
        values = [weight for _item, weight in items]
        pick = _choose_one(names, values, rng)
        chosen.append(pick)
        items = [(item, weight) for item, weight in items if item != pick]
    return chosen


def _as_ticket(main: list[str], special: list[str], allow_dup: bool) -> dict:
    if not allow_dup:
        main = sorted(main, key=lambda item: int(item))
        special = sorted(special, key=lambda item: int(item))
    return {"main": main, "special": special}


def _sample_ticket(pools: dict, mode: str, rng: random.Random) -> dict:
    main_weights = _weights_for(pools["main_counts"], mode)
    if pools["allow_dup"]:
        main = [_choose_one(pools["main"], main_weights, rng) for _ in range(pools["need_main"])]
    else:
        main = _sample_without(pools["main"], main_weights, pools["need_main"], rng)
    special = []
    if pools["need_spec"]:
        special = _sample_without(
            pools["special"],
            _weights_for(pools["special_counts"], mode),
            pools["need_spec"],
            rng,
        )
    return _as_ticket(main, special, pools["allow_dup"])


def _mutate(ticket: dict, pools: dict, rng: random.Random) -> dict:
    main = list(ticket["main"])
    special = list(ticket["special"])
    if pools["need_spec"] and special and rng.random() < 0.25:
        index = rng.randrange(len(special))
        used = set(special)
        options = [item for item in pools["special"] if item not in used]
        if not options:
            options = [item for item in pools["special"] if item != special[index]]
        if options:
            special[index] = rng.choice(options)
    else:
        index = rng.randrange(len(main))
        if pools["allow_dup"]:
            options = [item for item in pools["main"] if item != main[index]] or list(pools["main"])
            main[index] = rng.choice(options)
        else:
            used = set(main)
            options = [item for item in pools["main"] if item not in used]
            if options:
                main[index] = rng.choice(options)
    return _as_ticket(main, special, pools["allow_dup"])


def _ticket_key(ticket: dict) -> tuple:
    return (tuple(ticket["main"]), tuple(ticket["special"]))


def _fill_unique(target: int, existing: dict, maker) -> None:
    guard = 0
    limit = max(target * 30, 30)
    while len(existing) < target and guard < limit:
        guard += 1
        ticket = maker()
        key = _ticket_key(ticket)
        if key not in existing:
            existing[key] = ticket


def _rank(scored: list[dict], count: int) -> list[dict]:
    scored.sort(
        key=lambda item: (
            -(item["score"] if item["score"] is not None else -1.0),
            tuple(item["main"]),
            tuple(item["special"]),
        )
    )
    return scored[:count]


def generate_pulse(
    db: Session,
    lottery_type: str,
    count: int = 1,
    weights: dict | None = None,
    modules: list[PulseModule] | None = None,
    candidate_count: int = 120,
    rng: random.Random | None = None,
) -> dict:
    count = int(count)
    if count < 1 or count > 10:
        raise ValueError("组数需要 1–10")
    lottery = _require_lottery(lottery_type)
    chosen = list(modules or PULSE_MODULES)
    parsed_weights = _normalize_weights(weights, chosen)
    rng = rng or random.Random()
    target = max(count, min(int(candidate_count or 120), 200))

    stats = analyze(db, lottery, limit=50)
    need_main, need_spec, allow_dup = TICKET_SHAPE[lottery]
    main_freq = stats["main_freq"]
    special_freq = stats["special_freq"]
    if len(main_freq) < need_main or (need_spec and len(special_freq) < need_spec):
        raise ValueError("脉动综合暂不支持该彩种")
    pools = {
        "main": [item["n"] for item in main_freq],
        "main_counts": [item["count"] for item in main_freq],
        "special": [item["n"] for item in special_freq],
        "special_counts": [item["count"] for item in special_freq],
        "need_main": need_main,
        "need_spec": need_spec,
        "allow_dup": allow_dup,
    }
    modes = ("hot", "random", "cold", "hybrid")
    unique: dict = {}
    base_target = max(count, int(target * 0.75))
    cursor = {"n": 0}

    def make_base():
        mode = modes[cursor["n"] % len(modes)]
        cursor["n"] += 1
        return _sample_ticket(pools, mode, rng)

    _fill_unique(base_target, unique, make_base)
    saved = _install_memo()
    try:
        scored = [_score_one(db, lottery, ticket, chosen, parsed_weights) for ticket in unique.values()]
        ranked = _rank(scored, len(scored))
        seeds = ranked[: min(8, len(ranked))]
        spin = {"n": 0}

        def make_mutation():
            parent = seeds[spin["n"] % len(seeds)] if seeds else make_base()
            spin["n"] += 1
            return _mutate(parent, pools, rng)

        if seeds:
            _fill_unique(target, unique, make_mutation)
        pending = [ticket for key, ticket in unique.items() if key not in {_ticket_key(item) for item in scored}]
        scored.extend(_score_one(db, lottery, ticket, chosen, parsed_weights) for ticket in pending)
    finally:
        _restore_memo(saved)

    recommendations = _rank(scored, count)
    return {
        "lottery_type": lottery,
        "strategy": "pulse",
        "recommendations": recommendations,
        "modules": [module.key for module in chosen],
        "skipped_modules": list(SKIPPED_MODULES),
        "candidate_count": len(scored),
        "weights": parsed_weights,
        "disclaimer": DISCLAIMER,
        "entertainment_only": True,
        "data_status": stats.get("data_status", "seed"),
    }
