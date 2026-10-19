"""预测/推荐策略 — 明确仅供娱乐。"""
from __future__ import annotations

import random

from sqlalchemy.orm import Session

from ..lotteries import normalize_type
from .analyze import analyze
from .echo import PROFILES

DISCLAIMER = "仅供娱乐，不保证中奖；彩票有风险，请理性购彩，请勿沉迷。"
MAX_ATTEMPTS = 4000
_NEED_MAIN = {"ssq": 6, "dlt": 5, "fc3d": 3, "pl3": 3, "pl5": 5, "qxc": 6, "qlc": 7, "kl8": 20}
_NEED_SPEC = {"ssq": 1, "dlt": 2, "qxc": 1}


def _pick(pool: list[str], weights: list[float], k: int) -> list[str]:
    if not pool or k <= 0:
        return []
    k = min(k, len(pool))
    # 加权不放回抽样
    chosen = []
    items = list(zip(pool, weights))
    for _ in range(k):
        if not items:
            break
        names, ws = zip(*items)
        total = sum(ws) or 1
        r = random.random() * total
        acc = 0.0
        idx = 0
        for i, w in enumerate(ws):
            acc += w
            if acc >= r:
                idx = i
                break
        chosen.append(names[idx])
        items.pop(idx)
    return sorted(chosen, key=lambda x: int(x) if x.isdigit() else x)


def constraints_requested(constraints) -> bool:
    """任一有效字段即视为用户打开了机选条件。空列表和 null 不算。"""
    if not constraints:
        return False
    data = constraints.model_dump() if hasattr(constraints, "model_dump") else dict(constraints)
    for value in data.values():
        if value is None:
            continue
        if isinstance(value, (list, tuple, str)) and len(value) == 0:
            continue
        return True
    return False


def _as_dict(constraints) -> dict:
    if constraints is None:
        return {}
    if hasattr(constraints, "model_dump"):
        return constraints.model_dump()
    return dict(constraints)


def _format_balls(raw, width: int, lo: int, hi: int, label: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in raw or []:
        text = str(item).strip()
        if not text.isdigit():
            raise ValueError(f"{label}号码无效：{text}")
        number = int(text)
        if number < lo or number > hi:
            raise ValueError(f"{label}超出 {lo}–{hi}：{text}")
        key = str(number).zfill(width) if width > 1 else str(number)
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _ints(numbers: list[str]) -> list[int]:
    return [int(number) for number in numbers]


def _max_run(numbers: list[str]) -> int:
    ordered = sorted(set(_ints(numbers)))
    if not ordered:
        return 0
    best = run = 1
    for previous, current in zip(ordered, ordered[1:]):
        if current == previous + 1:
            run += 1
            best = max(best, run)
        else:
            run = 1
    return best


def _zone_bounds(mode: str, lo: int, hi: int) -> list[tuple[int, int]]:
    if mode == "digit":
        return [(0, 3), (4, 6), (7, 9)]
    span = hi - lo + 1
    size = (span + 2) // 3
    bounds: list[tuple[int, int]] = []
    start = lo
    for index in range(3):
        end = hi if index == 2 else min(hi, start + size - 1)
        bounds.append((start, end))
        start = end + 1
    return bounds


def _zone_index(number: int, zones: list[tuple[int, int]]) -> int:
    for index, (lo, hi) in enumerate(zones):
        if lo <= number <= hi:
            return index
    raise ValueError("号码不在分区内")


def _pool_numbers(lo: int, hi: int, width: int) -> list[str]:
    return [str(number).zfill(width) if width > 1 else str(number) for number in range(lo, hi + 1)]


def _count_range(required: list[str], available: list[str], slots: int, pred) -> tuple[int, int]:
    base = sum(1 for number in required if pred(int(number)))
    avail = sum(1 for number in available if pred(int(number)))
    other = len(available) - avail
    if slots < 0:
        return base, base
    return base + max(0, slots - other), base + min(slots, avail)


def _digit_count_range(required: list[str], usable: list[str], slots: int, pred) -> tuple[int, int]:
    base = sum(1 for number in required if pred(int(number)))
    can = any(pred(int(number)) for number in usable)
    cannot = any(not pred(int(number)) for number in usable)
    if slots <= 0:
        return base, base
    return base + (0 if cannot else slots), base + (slots if can else 0)


def _sum_bounds_set(required: list[str], available: list[str], slots: int) -> tuple[int, int]:
    base = sum(_ints(required))
    if slots <= 0:
        return base, base
    ordered = sorted(_ints(available))
    return base + sum(ordered[:slots]), base + sum(ordered[-slots:])


def _sum_bounds_digit(required: list[str], usable: list[str], slots: int) -> tuple[int, int]:
    base = sum(_ints(required))
    if slots <= 0:
        return base, base
    values = _ints(usable)
    return base + slots * min(values), base + slots * max(values)


def _min_span_set(required: list[str], available: list[str], slots: int) -> int | None:
    values = sorted(set(_ints(required) + _ints(available)))
    need = len(required) + slots
    must = set(_ints(required))
    best: int | None = None
    for start in range(len(values)):
        for end in range(start, len(values)):
            window = values[start : end + 1]
            if len(window) < need or not must <= set(window):
                continue
            span = window[-1] - window[0]
            if best is None or span < best:
                best = span
            break
    return best


def _prepare(lottery: str, constraints) -> dict | None:
    if not constraints_requested(constraints):
        return None
    profile = PROFILES.get(lottery)
    if profile is None or lottery not in _NEED_MAIN:
        raise ValueError("未知彩种")
    raw = _as_dict(constraints)
    mode = profile["mode"]
    width = profile["width"]
    main_lo, main_hi = int(profile["main"][0]), int(profile["main"][1])
    need_main = _NEED_MAIN[lottery]
    need_spec = _NEED_SPEC.get(lottery, 0)
    include_main = _format_balls(raw.get("include_main"), width, main_lo, main_hi, "主号")
    exclude_main = _format_balls(raw.get("exclude_main"), width, main_lo, main_hi, "主号")
    special_bounds = profile.get("special")
    if special_bounds:
        spec_lo, spec_hi = int(special_bounds[0]), int(special_bounds[1])
        include_special = _format_balls(raw.get("include_special"), width, spec_lo, spec_hi, "特别号")
        exclude_special = _format_balls(raw.get("exclude_special"), width, spec_lo, spec_hi, "特别号")
        spec_pool = _pool_numbers(spec_lo, spec_hi, width)
    else:
        if raw.get("include_special"):
            raise ValueError("该彩种没有特别号，不能设置特别号胆码")
        if raw.get("exclude_special"):
            raise ValueError("该彩种没有特别号，不能设置特别号杀号")
        include_special = []
        exclude_special = []
        spec_pool = []

    overlap = [number for number in include_main if number in set(exclude_main)]
    if overlap:
        raise ValueError("胆码与杀号冲突：" + "、".join(overlap))
    if len(include_main) > need_main:
        raise ValueError(f"主号胆码不能超过 {need_main} 个")
    if include_special and need_spec == 0:
        raise ValueError("该彩种没有特别号，不能设置特别号胆码")
    if exclude_special and need_spec == 0:
        raise ValueError("该彩种没有特别号，不能设置特别号杀号")
    spec_overlap = [number for number in include_special if number in set(exclude_special)]
    if spec_overlap:
        raise ValueError("特别号胆码与杀号冲突：" + "、".join(spec_overlap))
    if len(include_special) > need_spec:
        raise ValueError(f"特别号胆码不能超过 {need_spec} 个")

    max_consecutive = raw.get("max_consecutive")
    if max_consecutive is not None:
        max_consecutive = int(max_consecutive)
        if mode == "digit":
            raise ValueError("连号约束只适用于乐透，数字彩请用奇偶、和值或跨度。")
        if max_consecutive < 1:
            raise ValueError("连号上限至少为 1")
        if include_main and _max_run(include_main) > max_consecutive:
            raise ValueError("胆码已形成超过上限的连号")

    main_pool = _pool_numbers(main_lo, main_hi, width)
    banned = set(exclude_main)
    must = set(include_main)
    if mode == "digit":
        usable = [number for number in main_pool if number not in banned]
        if not usable:
            raise ValueError("主号杀号把数字池清空了")
        available = usable
        slots = need_main - len(include_main)
    else:
        available = [number for number in main_pool if number not in banned and number not in must]
        slots = need_main - len(include_main)
        if slots > len(available):
            raise ValueError("杀号之后剩余号码不够组成一注")
    if need_spec:
        spec_available = [number for number in spec_pool if number not in set(exclude_special) and number not in set(include_special)]
        if need_spec - len(include_special) > len(spec_available):
            raise ValueError("特别号杀号之后剩余号码不够")

    odd_count = raw.get("odd_count")
    odd_min = raw.get("odd_min")
    odd_max = raw.get("odd_max")
    if odd_count is not None:
        odd_count = int(odd_count)
    if odd_min is not None:
        odd_min = int(odd_min)
    if odd_max is not None:
        odd_max = int(odd_max)
    if odd_min is not None and odd_max is not None and odd_min > odd_max:
        raise ValueError("奇数个数下限不能大于上限")
    if odd_count is not None and not 0 <= odd_count <= need_main:
        raise ValueError(f"奇数个数超出 0–{need_main}")
    if odd_min is not None and not 0 <= odd_min <= need_main:
        raise ValueError(f"奇数个数超出 0–{need_main}")
    if odd_max is not None and not 0 <= odd_max <= need_main:
        raise ValueError(f"奇数个数超出 0–{need_main}")
    if any(value is not None for value in (odd_count, odd_min, odd_max)):
        if mode == "digit":
            odd_lo, odd_hi = _digit_count_range(include_main, usable, slots, lambda number: number % 2 == 1)
        else:
            odd_lo, odd_hi = _count_range(include_main, available, slots, lambda number: number % 2 == 1)
        if odd_count is not None and not odd_lo <= odd_count <= odd_hi:
            raise ValueError("奇数个数无法满足")
        req_lo = 0 if odd_min is None else odd_min
        req_hi = need_main if odd_max is None else odd_max
        if odd_count is not None:
            req_lo = req_hi = odd_count
        if req_hi < odd_lo or req_lo > odd_hi:
            raise ValueError("奇数个数无法满足")

    sum_min = raw.get("sum_min")
    sum_max = raw.get("sum_max")
    if sum_min is not None:
        sum_min = int(sum_min)
    if sum_max is not None:
        sum_max = int(sum_max)
    if sum_min is not None and sum_max is not None and sum_min > sum_max:
        raise ValueError("和值下限不能大于上限")
    if sum_min is not None or sum_max is not None:
        if mode == "digit":
            hard_min, hard_max = _sum_bounds_digit(include_main, usable, slots)
        else:
            hard_min, hard_max = _sum_bounds_set(include_main, available, slots)
        if (sum_max is not None and sum_max < hard_min) or (sum_min is not None and sum_min > hard_max):
            raise ValueError("和值范围无法满足")

    span_min = raw.get("span_min")
    span_max = raw.get("span_max")
    if span_min is not None:
        span_min = int(span_min)
    if span_max is not None:
        span_max = int(span_max)
    if span_min is not None and span_max is not None and span_min > span_max:
        raise ValueError("跨度下限不能大于上限")
    if span_min is not None or span_max is not None:
        if mode == "digit":
            forced = 0
            if include_main:
                forced = max(_ints(include_main)) - min(_ints(include_main))
            hardest = max(_ints(usable)) - min(_ints(usable))
            if span_max is not None and span_max < forced:
                raise ValueError("跨度范围无法满足")
            if span_min is not None and span_min > hardest:
                raise ValueError("跨度范围无法满足")
        else:
            hardest_values = _ints(include_main) + _ints(available)
            if not hardest_values:
                raise ValueError("跨度范围无法满足")
            hardest = max(hardest_values) - min(hardest_values)
            soft = _min_span_set(include_main, available, slots)
            if soft is None or (span_max is not None and span_max < soft) or (span_min is not None and span_min > hardest):
                raise ValueError("跨度范围无法满足")

    zones = _zone_bounds(mode, main_lo, main_hi)
    zone_counts = raw.get("zone_counts")
    if zone_counts is not None:
        if len(zone_counts) != 3 or any(int(number) < 0 for number in zone_counts):
            raise ValueError("三区个数需要 3 个非负整数")
        zone_counts = [int(number) for number in zone_counts]
        if sum(zone_counts) != need_main:
            raise ValueError(f"三区个数之和必须等于 {need_main}")
        must_zones = [0, 0, 0]
        for number in include_main:
            must_zones[_zone_index(int(number), zones)] += 1
        if mode == "digit":
            avail_zones = [0, 0, 0]
            for number in usable:
                avail_zones[_zone_index(int(number), zones)] += 1
            for index, quota in enumerate(zone_counts):
                if must_zones[index] > quota or (quota - must_zones[index] > 0 and avail_zones[index] == 0):
                    raise ValueError("三区个数无法满足")
        else:
            avail_zones = [0, 0, 0]
            for number in available:
                avail_zones[_zone_index(int(number), zones)] += 1
            for index, quota in enumerate(zone_counts):
                if must_zones[index] > quota or quota - must_zones[index] > avail_zones[index]:
                    raise ValueError("三区个数无法满足")

    mid = (0 + 9) // 2 if mode == "digit" else (main_lo + main_hi) // 2
    big_count = raw.get("big_count")
    big_min = raw.get("big_min")
    big_max = raw.get("big_max")
    if big_count is not None:
        big_count = int(big_count)
    if big_min is not None:
        big_min = int(big_min)
    if big_max is not None:
        big_max = int(big_max)
    if big_min is not None and big_max is not None and big_min > big_max:
        raise ValueError("大号个数下限不能大于上限")
    if big_count is not None and not 0 <= big_count <= need_main:
        raise ValueError(f"大号个数超出 0–{need_main}")
    if big_min is not None and not 0 <= big_min <= need_main:
        raise ValueError(f"大号个数超出 0–{need_main}")
    if big_max is not None and not 0 <= big_max <= need_main:
        raise ValueError(f"大号个数超出 0–{need_main}")
    if any(value is not None for value in (big_count, big_min, big_max)):
        is_big = lambda number: number > mid
        if mode == "digit":
            big_lo, big_hi = _digit_count_range(include_main, usable, slots, is_big)
        else:
            big_lo, big_hi = _count_range(include_main, available, slots, is_big)
        if big_count is not None and not big_lo <= big_count <= big_hi:
            raise ValueError("大号个数无法满足")
        req_lo = 0 if big_min is None else big_min
        req_hi = need_main if big_max is None else big_max
        if big_count is not None:
            req_lo = req_hi = big_count
        if req_hi < big_lo or req_lo > big_hi:
            raise ValueError("大号个数无法满足")

    echo: dict = {}
    if include_main:
        echo["include_main"] = include_main
    if exclude_main:
        echo["exclude_main"] = exclude_main
    if include_special:
        echo["include_special"] = include_special
    if exclude_special:
        echo["exclude_special"] = exclude_special
    for key, value in (
        ("odd_count", odd_count),
        ("odd_min", odd_min),
        ("odd_max", odd_max),
        ("sum_min", sum_min),
        ("sum_max", sum_max),
        ("span_min", span_min),
        ("span_max", span_max),
        ("max_consecutive", max_consecutive),
        ("zone_counts", zone_counts),
        ("big_count", big_count),
        ("big_min", big_min),
        ("big_max", big_max),
    ):
        if value is not None:
            echo[key] = value
    return {
        "echo": echo,
        "mode": mode,
        "include_main": include_main,
        "exclude_main": exclude_main,
        "include_special": include_special,
        "exclude_special": exclude_special,
        "odd_count": odd_count,
        "odd_min": odd_min,
        "odd_max": odd_max,
        "sum_min": sum_min,
        "sum_max": sum_max,
        "span_min": span_min,
        "span_max": span_max,
        "max_consecutive": max_consecutive,
        "zone_counts": zone_counts,
        "big_count": big_count,
        "big_min": big_min,
        "big_max": big_max,
        "zones": zones,
        "mid": mid,
    }


def _measure(main: list[str], active: dict) -> dict:
    values = _ints(main)
    zones = [0, 0, 0]
    for number in values:
        zones[_zone_index(number, active["zones"])] += 1
    odd = sum(number % 2 for number in values)
    return {
        "odd": odd,
        "even": len(values) - odd,
        "total": sum(values),
        "span": (max(values) - min(values)) if values else 0,
        "big": sum(number > active["mid"] for number in values),
        "zones": zones,
        "run": _max_run(main),
    }


def _matches(main: list[str], special: list[str], active: dict) -> bool:
    if active["mode"] == "digit":
        if any(main.count(number) < 1 for number in active["include_main"]):
            return False
        if any(special.count(number) < 1 for number in active["include_special"]):
            return False
    else:
        if not set(active["include_main"]) <= set(main):
            return False
        if not set(active["include_special"]) <= set(special):
            return False
    if set(main) & set(active["exclude_main"]):
        return False
    if set(special) & set(active["exclude_special"]):
        return False
    stats = _measure(main, active)
    if active["odd_count"] is not None and stats["odd"] != active["odd_count"]:
        return False
    if active["odd_min"] is not None and stats["odd"] < active["odd_min"]:
        return False
    if active["odd_max"] is not None and stats["odd"] > active["odd_max"]:
        return False
    if active["sum_min"] is not None and stats["total"] < active["sum_min"]:
        return False
    if active["sum_max"] is not None and stats["total"] > active["sum_max"]:
        return False
    if active["span_min"] is not None and stats["span"] < active["span_min"]:
        return False
    if active["span_max"] is not None and stats["span"] > active["span_max"]:
        return False
    if active["max_consecutive"] is not None and stats["run"] > active["max_consecutive"]:
        return False
    if active["zone_counts"] is not None and stats["zones"] != active["zone_counts"]:
        return False
    if active["big_count"] is not None and stats["big"] != active["big_count"]:
        return False
    if active["big_min"] is not None and stats["big"] < active["big_min"]:
        return False
    if active["big_max"] is not None and stats["big"] > active["big_max"]:
        return False
    return True


def _summary(main: list[str], active: dict) -> str:
    stats = _measure(main, active)
    parts: list[str] = []
    if any(active[key] is not None for key in ("odd_count", "odd_min", "odd_max")):
        parts.append(f"奇{stats['odd']}偶{stats['even']}")
    if active["sum_min"] is not None or active["sum_max"] is not None:
        parts.append(f"和值 {stats['total']}")
    if active["span_min"] is not None or active["span_max"] is not None:
        parts.append(f"跨度 {stats['span']}")
    if any(active[key] is not None for key in ("big_count", "big_min", "big_max")):
        parts.append(f"{stats['big']}大{len(main) - stats['big']}小")
    if active["zone_counts"] is not None:
        parts.append("区位 " + ":".join(str(count) for count in stats["zones"]))
    if active["max_consecutive"] is not None:
        parts.append(f"连号≤{active['max_consecutive']}")
    if active["include_main"]:
        parts.append("含胆 " + "、".join(active["include_main"]))
    if active["exclude_main"]:
        parts.append("杀号 " + "、".join(active["exclude_main"]))
    if active["include_special"]:
        parts.append("特别号含 " + "、".join(active["include_special"]))
    if active["exclude_special"]:
        parts.append("特别号杀 " + "、".join(active["exclude_special"]))
    return " · ".join(parts)


def generate(
    db: Session,
    lottery_type: str,
    strategy: str = "hot",
    count: int = 1,
    constraints=None,
    max_attempts: int = MAX_ATTEMPTS,
    before_issue: str | None = None,
) -> dict:
    if (strategy or "").strip().lower() == "pulse":
        if constraints_requested(constraints):
            raise ValueError("机选条件只用于热号、冷号、混合和随机；脉动综合保持原有打分，请去掉条件或改用其他策略。")
        from .pulse_ensemble import generate_pulse

        return generate_pulse(db, lottery_type, count=count)
    t = normalize_type(lottery_type)
    stats = analyze(db, t, limit=50, before_issue=before_issue)
    main_freq = stats["main_freq"]
    spec_freq = stats["special_freq"]
    strategy = (strategy or "hot").lower()

    def weights_for(freq: list[dict], mode: str) -> list[float]:
        counts = [f["count"] for f in freq]
        if mode == "hot":
            return [c + 1 for c in counts]
        if mode == "cold":
            mx = max(counts) if counts else 1
            return [mx - c + 1 for c in counts]
        if mode == "hybrid":
            # 热号与冷号混合偏置
            return [((c + 1) * 0.6 + 1) for c in counts]
        return [1.0] * len(freq)

    need_main = {"ssq": 6, "dlt": 5, "fc3d": 3, "pl3": 3, "pl5": 5, "qxc": 6, "qlc": 7, "kl8": 20}.get(t, 6)
    need_spec = {"ssq": 1, "dlt": 2, "qxc": 1}.get(t, 0)

    # 数字彩：按位独立时仍用同一数字池，允许重复
    allow_dup = t in ("fc3d", "pl3", "pl5", "qxc")
    active = _prepare(t, constraints)

    def sample_one() -> dict:
        if allow_dup:
            pool = [f["n"] for f in main_freq] or [str(i) for i in range(10)]
            ws = weights_for(main_freq, mode) if main_freq else [1.0] * len(pool)
            if mode == "random":
                main = [random.choice(pool) for _ in range(need_main)]
            else:
                main = []
                for _i in range(need_main):
                    main.extend(_pick(pool, ws, 1))
            special = []
            if need_spec and spec_freq:
                sp_pool = [f["n"] for f in spec_freq]
                sp_ws = weights_for(spec_freq, mode)
                special = _pick(sp_pool, sp_ws, need_spec) if mode != "random" else random.sample(sp_pool, need_spec)
            elif need_spec:
                special = [str(random.randint(0, 14 if t == "qxc" else 9))]
        else:
            pool = [f["n"] for f in main_freq]
            ws = weights_for(main_freq, mode)
            if mode == "random":
                main = sorted(random.sample(pool, need_main), key=lambda x: int(x))
            else:
                main = _pick(pool, ws, need_main)
            special = []
            if need_spec and spec_freq:
                sp_pool = [f["n"] for f in spec_freq]
                sp_ws = weights_for(spec_freq, mode)
                special = (
                    sorted(random.sample(sp_pool, need_spec), key=lambda x: int(x))
                    if mode == "random"
                    else _pick(sp_pool, sp_ws, need_spec)
                )
        return {"main": main, "special": special}

    results = []
    mode = strategy if strategy in ("hot", "cold", "random", "hybrid") else "random"
    budget = max(0, int(max_attempts))
    for _ in range(count):
        if active is None:
            results.append(sample_one())
            continue
        found = None
        for _attempt in range(budget):
            candidate = sample_one()
            if _matches(candidate["main"], candidate["special"], active):
                found = candidate
                break
        if found is None:
            raise ValueError("在限定次数内无法生成满足机选条件的号码，请放宽条件。")
        found["constraint_summary"] = _summary(found["main"], active)
        results.append(found)

    payload = {
        "lottery_type": t,
        "strategy": mode,
        "recommendations": results,
        "disclaimer": DISCLAIMER,
        "entertainment_only": True,
        "data_status": stats.get("data_status", "seed"),
    }
    if active is not None:
        payload["constraints"] = active["echo"]
    return payload
