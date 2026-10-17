"""预测/推荐策略 — 明确仅供娱乐。"""
from __future__ import annotations
import random
from sqlalchemy.orm import Session
from .analyze import analyze
from ..lotteries import normalize_type, fmt_num

DISCLAIMER = "仅供娱乐，不保证中奖；彩票有风险，请理性购彩，请勿沉迷。"


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


def generate(db: Session, lottery_type: str, strategy: str = "hot", count: int = 1) -> dict:
    if (strategy or "").strip().lower() == "pulse":
        from .pulse_ensemble import generate_pulse

        return generate_pulse(db, lottery_type, count=count)
    t = normalize_type(lottery_type)
    stats = analyze(db, t, limit=50)
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
    width = 2 if t in ("ssq", "dlt", "qlc", "kl8") else 0

    # 数字彩：按位独立时仍用同一数字池，允许重复
    allow_dup = t in ("fc3d", "pl3", "pl5", "qxc")

    results = []
    mode = strategy if strategy in ("hot", "cold", "random", "hybrid") else "random"
    for _ in range(count):
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
        results.append({"main": main, "special": special})

    return {
        "lottery_type": t,
        "strategy": mode,
        "recommendations": results,
        "disclaimer": DISCLAIMER,
        "entertainment_only": True,
        "data_status": stats.get("data_status", "seed"),
    }
