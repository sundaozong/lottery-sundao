"""冷热频次、遗漏、热力数据。"""
from __future__ import annotations
import json
from collections import Counter
from sqlalchemy.orm import Session
from ..models import Draw
from ..lotteries import parse_numbers, normalize_type


def _pool(lottery_type: str) -> tuple[list[str], list[str]]:
    t = normalize_type(lottery_type)
    if t == "ssq":
        return [f"{i:02d}" for i in range(1, 34)], [f"{i:02d}" for i in range(1, 17)]
    if t == "dlt":
        return [f"{i:02d}" for i in range(1, 36)], [f"{i:02d}" for i in range(1, 13)]
    if t in ("fc3d", "pl3"):
        return [str(i) for i in range(10)], []
    if t == "pl5":
        return [str(i) for i in range(10)], []
    if t == "qxc":
        return [str(i) for i in range(10)], [str(i) for i in range(15)]
    if t == "qlc":
        nums = [f"{i:02d}" for i in range(1, 31)]
        return nums, nums
    if t == "kl8":
        return [f"{i:02d}" for i in range(1, 81)], []
    return [], []


def analyze(db: Session, lottery_type: str, limit: int = 50) -> dict:
    t = normalize_type(lottery_type)
    rows = (
        db.query(Draw)
        .filter(Draw.lottery_type == t)
        .order_by(Draw.issue.desc())
        .limit(limit)
        .all()
    )
    main_pool, spec_pool = _pool(t)
    main_cnt: Counter = Counter()
    spec_cnt: Counter = Counter()
    history: list[dict] = []
    for r in reversed(rows):
        nums = parse_numbers(r.numbers)
        main_cnt.update(nums["main"])
        spec_cnt.update(nums["special"])
        history.append({"issue": r.issue, "numbers": nums, "source": r.source})

    def freq_list(pool: list[str], cnt: Counter) -> list[dict]:
        mx = max((cnt.get(n, 0) for n in pool), default=1) or 1
        return [
            {"n": n, "count": cnt.get(n, 0), "level": min(5, max(0, round(cnt.get(n, 0) / mx * 5)))}
            for n in pool
        ]

    # 遗漏：从最新往前数，该号多久未出现
    miss_main = {n: len(rows) for n in main_pool}
    miss_spec = {n: len(rows) for n in spec_pool}
    for idx, r in enumerate(rows):  # rows 已按期号降序，idx=0 最新
        nums = parse_numbers(r.numbers)
        for n in nums["main"]:
            if n in miss_main and miss_main[n] == len(rows):
                miss_main[n] = idx
        for n in nums["special"]:
            if n in miss_spec and miss_spec[n] == len(rows):
                miss_spec[n] = idx

    hot_main = sorted(freq_list(main_pool, main_cnt), key=lambda x: -x["count"])[:10]
    cold_main = sorted(freq_list(main_pool, main_cnt), key=lambda x: x["count"])[:10]

    return {
        "lottery_type": t,
        "sample_size": len(rows),
        "main_freq": freq_list(main_pool, main_cnt),
        "special_freq": freq_list(spec_pool, spec_cnt) if spec_pool else [],
        "main_omit": [{"n": n, "omit": miss_main[n]} for n in main_pool],
        "special_omit": [{"n": n, "omit": miss_spec[n]} for n in spec_pool] if spec_pool else [],
        "hot_main": hot_main,
        "cold_main": cold_main,
        "heatmap": freq_list(main_pool, main_cnt),
        "history": list(reversed(history))[:20],
        "data_status": "mixed" if any(h.get("source") == "crawl" for h in history) else "seed",
        "disclaimer": "分析基于本地样本，仅供娱乐参考，不构成投注建议。",
    }
