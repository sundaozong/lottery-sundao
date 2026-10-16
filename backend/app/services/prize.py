"""单式 / 复式奖金估算，以及各彩种对照表。

浮动奖用示意金额，固定奖按公开规则。未计大乐透追加、3D 和值等扩展玩法。
"""
from __future__ import annotations

import math
from typing import Any, Optional

from ..lotteries import normalize_type, parse_numbers

STAKE = 2
MAX_BETS = 2_000_000

SSQ_ROWS = [
    ((6, 1), "6红+1蓝", "一等奖", 5_000_000, True),
    ((6, 0), "6红+0蓝", "二等奖", 150_000, True),
    ((5, 1), "5红+1蓝", "三等奖", 3_000, False),
    ((5, 0), "5红+0蓝", "四等奖", 200, False),
    ((4, 1), "4红+1蓝", "四等奖", 200, False),
    ((4, 0), "4红+0蓝", "五等奖", 10, False),
    ((3, 1), "3红+1蓝", "五等奖", 10, False),
    ((2, 1), "2红+1蓝", "六等奖", 5, False),
    ((1, 1), "1红+1蓝", "六等奖", 5, False),
    ((0, 1), "0红+1蓝", "六等奖", 5, False),
]

DLT_ROWS = [
    ((5, 2), "5前+2后", "一等奖", 10_000_000, True),
    ((5, 1), "5前+1后", "二等奖", 500_000, True),
    ((5, 0), "5前+0后", "三等奖", 10_000, False),
    ((4, 2), "4前+2后", "四等奖", 3_000, False),
    ((4, 1), "4前+1后", "五等奖", 300, False),
    ((3, 2), "3前+2后", "六等奖", 200, False),
    ((4, 0), "4前+0后", "七等奖", 100, False),
    ((3, 1), "3前+1后", "八等奖", 15, False),
    ((2, 2), "2前+2后", "八等奖", 15, False),
    ((3, 0), "3前+0后", "九等奖", 5, False),
    ((2, 1), "2前+1后", "九等奖", 5, False),
    ((1, 2), "1前+2后", "九等奖", 5, False),
    ((0, 2), "0前+2后", "九等奖", 5, False),
]

DIGIT_ROWS = [
    ("直选", "按位全部相同", 1040, False),
    ("组三", "两位相同，顺序不限", 346, False),
    ("组六", "三位各不相同，顺序不限", 173, False),
]

# 命中个数 → (条件, 奖级, 金额, 是否浮动)
KL8_HITS = {
    10: [(10, "中10", "一等奖", 5_000_000, True), (9, "中9", "二等奖", 8000, False), (8, "中8", "三等奖", 800, False), (7, "中7", "四等奖", 80, False), (6, "中6", "五等奖", 5, False), (5, "中5", "六等奖", 3, False), (0, "中0", "七等奖", 2, False)],
    9: [(9, "中9", "一等奖", 300_000, False), (8, "中8", "二等奖", 2000, False), (7, "中7", "三等奖", 200, False), (6, "中6", "四等奖", 20, False), (5, "中5", "五等奖", 5, False), (4, "中4", "六等奖", 3, False), (0, "中0", "七等奖", 2, False)],
    8: [(8, "中8", "一等奖", 50_000, False), (7, "中7", "二等奖", 800, False), (6, "中6", "三等奖", 88, False), (5, "中5", "四等奖", 10, False), (4, "中4", "五等奖", 3, False), (0, "中0", "六等奖", 2, False)],
    7: [(7, "中7", "一等奖", 10_000, False), (6, "中6", "二等奖", 288, False), (5, "中5", "三等奖", 28, False), (4, "中4", "四等奖", 4, False), (0, "中0", "五等奖", 2, False)],
    6: [(6, "中6", "一等奖", 3000, False), (5, "中5", "二等奖", 30, False), (4, "中4", "三等奖", 10, False), (3, "中3", "四等奖", 3, False)],
    5: [(5, "中5", "一等奖", 1000, False), (4, "中4", "二等奖", 21, False), (3, "中3", "三等奖", 3, False)],
    4: [(4, "中4", "一等奖", 100, False), (3, "中3", "二等奖", 5, False), (2, "中2", "三等奖", 3, False)],
    3: [(3, "中3", "一等奖", 53, False), (2, "中2", "二等奖", 3, False)],
    2: [(2, "中2", "一等奖", 19, False)],
    1: [(1, "中1", "一等奖", 4.6, False)],
}

# (基本号命中, 是否含特别号) → 条件、奖级、示意金额、是否浮动
QLC_ROWS = [
    ((7, 0), "7个基本号", "一等奖", 500_000, True),
    ((6, 1), "6个基本号+特别号", "二等奖", 20_000, True),
    ((6, 0), "6个基本号", "三等奖", 2_000, True),
    ((5, 1), "5个基本号+特别号", "四等奖", 200, False),
    ((5, 0), "5个基本号", "五等奖", 50, False),
    ((4, 1), "4个基本号+特别号", "六等奖", 10, False),
    ((4, 0), "4个基本号", "七等奖", 5, False),
]

QXC_ROWS = [
    ("7位全中", "一等奖", 5_000_000, True),
    ("前6位全中", "二等奖", 100_000, True),
    ("前6位中5位+特别号", "三等奖", 3000, False),
    ("前6位中5位，或中4位+特别号", "四等奖", 500, False),
    ("前6位中4位，或中3位+特别号", "五等奖", 30, False),
    ("前6位中3位，或中0–2位+特别号", "六等奖", 5, False),
]

PLAY_NAMES = {
    "single": "单式",
    "compound": "复式",
    "direct": "直选单式",
    "direct_compound": "直选复式",
    "group3": "组三单式",
    "group3_compound": "组三复式",
    "group6": "组六单式",
    "group6_compound": "组六复式",
    "pick": "选号",
}

PICK_CN = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九", 10: "十"}


def comb(n: int, k: int) -> int:
    if k < 0 or n < 0 or k > n:
        return 0
    return math.comb(n, k)


def fmt_money(amount: float) -> str:
    if amount >= 10000 and abs(amount - round(amount)) < 1e-9 and int(amount) % 10000 == 0:
        wan = int(amount) // 10000
        return f"{wan}万"
    if abs(amount - round(amount)) < 1e-9:
        return f"{int(round(amount)):,}"
    return f"{amount:.1f}"


def money_label(amount: float, floating: bool) -> str:
    text = fmt_money(amount)
    return f"浮动（示意 {text}）" if floating else text


def _row(condition: str, level: str, amount: float, floating: bool) -> dict:
    return {
        "condition": condition,
        "level": level,
        "amount": amount,
        "floating": floating,
        "amount_label": money_label(amount, floating),
    }


def _balls(values: Any, width: int, lo: int, hi: int, label: str, allow_dup: bool = False) -> list[str]:
    if values is None:
        values = []
    if isinstance(values, str):
        values = [p for p in values.replace(",", " ").split() if p]
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = str(raw).strip()
        if not text.isdigit():
            raise ValueError(f"{label}号码无效：{text}")
        number = int(text)
        if number < lo or number > hi:
            raise ValueError(f"{label}超出 {lo}–{hi}：{text}")
        key = str(number).zfill(width) if width > 1 else str(number)
        if key in seen and not allow_dup:
            raise ValueError(f"{label}重复：{key}")
        seen.add(key)
        out.append(key)
    return out


def _split_positions(raw: Any, count: int) -> list[list[str]]:
    if not raw:
        return [[] for _ in range(count)]
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.split("|")]
        raw = parts
    positions = list(raw)[:count]
    while len(positions) < count:
        positions.append([])
    return positions


def _as_dict(bet_numbers: Any) -> dict:
    if isinstance(bet_numbers, dict):
        return dict(bet_numbers)
    parsed = parse_numbers(bet_numbers)
    return {"main": parsed["main"], "special": parsed["special"]}


def play_name(lottery_type: str, bet: dict, bets: int = 1) -> str:
    t = normalize_type(lottery_type)
    play = bet.get("play") or ""
    if t == "kl8":
        pick = int(bet.get("pick") or 10)
        kind = "复式" if bets > 1 else "单式"
        return f"选{PICK_CN.get(pick, pick)}{kind}"
    if not play:
        if t in ("fc3d", "pl3", "pl5"):
            return "直选"
        return "单式"
    if play in ("single", "compound") and t in ("ssq", "dlt", "qxc", "qlc"):
        return "复式" if play == "compound" or bets > 1 else "单式"
    return PLAY_NAMES.get(play, play)


def _table_for(t: str, pick: Optional[int] = None) -> list[dict]:
    if t == "ssq":
        return [_row(c, lv, amt, fl) for _, c, lv, amt, fl in SSQ_ROWS]
    if t == "dlt":
        return [_row(c, lv, amt, fl) for _, c, lv, amt, fl in DLT_ROWS]
    if t in ("fc3d", "pl3"):
        return [_row(cond, lv, amt, fl) for lv, cond, amt, fl in DIGIT_ROWS]
    if t == "pl5":
        return [_row("5位按位全中", "直选", 100_000, False)]
    if t == "qxc":
        return [_row(c, lv, amt, fl) for c, lv, amt, fl in QXC_ROWS]
    if t == "qlc":
        return [_row(c, lv, amt, fl) for _, c, lv, amt, fl in QLC_ROWS]
    if t == "kl8":
        n = int(pick or 10)
        rows = KL8_HITS.get(n) or []
        return [_row(c, lv, amt, fl) for _, c, lv, amt, fl in rows]
    return []


def _inputs_ball(key: str, label: str, placeholder: str) -> dict:
    return {"kind": "balls", "key": key, "label": label, "placeholder": placeholder}


def _inputs_pos(labels: list[str], placeholder: str) -> list[dict]:
    return [{"kind": "positions", "labels": labels, "placeholder": placeholder}]


def prize_rules() -> dict:
    ssq_single = [_inputs_ball("main", "红球", "03 12 18 22 27 31"), _inputs_ball("special", "蓝球", "09")]
    ssq_compound = [_inputs_ball("main", "红球", "01 03 12 18 22 27 31"), _inputs_ball("special", "蓝球", "09 16")]
    dlt_single = [_inputs_ball("main", "前区", "05 11 19 28 33"), _inputs_ball("special", "后区", "02 10")]
    dlt_compound = [_inputs_ball("main", "前区", "05 11 19 28 33 35"), _inputs_ball("special", "后区", "02 10 12")]
    digit_single = _inputs_pos(["百位", "十位", "个位"], "1")
    digit_compound = _inputs_pos(["百位", "十位", "个位"], "1 2")
    group_single = [_inputs_ball("main", "号码", "1 1 2")]
    group6_single = [_inputs_ball("main", "号码", "1 2 3")]
    group_compound = [_inputs_ball("main", "号码", "1 2 3 4")]
    pl5_single = _inputs_pos(["万位", "千位", "百位", "十位", "个位"], "1")
    pl5_compound = _inputs_pos(["万位", "千位", "百位", "十位", "个位"], "1 2")
    qxc_labels = ["第1位", "第2位", "第3位", "第4位", "第5位", "第6位", "特别号"]
    lotteries = {
        "ssq": {
            "note": "红球 1–33，蓝球 1–16。复式为红球 6–20 个、蓝球 1–16 个，且总注数大于 1。一、二等奖为浮动示意。",
            "plays": [
                {"id": "single", "name": "单式", "hint": "6 个红球 + 1 个蓝球", "inputs": ssq_single},
                {"id": "compound", "name": "复式", "hint": "红球多选或蓝球多选，2 元/注", "inputs": ssq_compound},
            ],
            "table": _table_for("ssq"),
        },
        "dlt": {
            "note": "前区 1–35 选 5，后区 1–12 选 2。未计追加。一、二等奖为浮动示意。",
            "plays": [
                {"id": "single", "name": "单式", "hint": "5 个前区 + 2 个后区", "inputs": dlt_single},
                {"id": "compound", "name": "复式", "hint": "前区 5–20 或后区 2–12，总注数大于 1", "inputs": dlt_compound},
            ],
            "table": _table_for("dlt"),
        },
        "fc3d": _digit_rules("直选 1040、组三 346、组六 173，单注 2 元。", digit_single, digit_compound, group_single, group6_single, group_compound),
        "pl3": _digit_rules("与福彩3D相同的固定奖：直选 1040、组三 346、组六 173。", digit_single, digit_compound, group_single, group6_single, group_compound),
        "pl5": {
            "note": "仅直选，5 位按位全中 10 万。复式为某一位或多位多选。",
            "plays": [
                {"id": "direct", "name": "直选单式", "hint": "万千百十个各 1 个数字", "inputs": pl5_single},
                {"id": "direct_compound", "name": "直选复式", "hint": "至少一位选 2 个及以上数字", "inputs": pl5_compound},
            ],
            "table": _table_for("pl5"),
        },
        "qlc": {
            "note": "从 01–30 选 7 个号码，开奖为 7 个基本号加 1 个特别号。复式选 8–16 个。一至三等奖为浮动示意，四至七等奖为固定奖。未计胆拖。",
            "plays": [
                {"id": "single", "name": "单式", "hint": "选 7 个号码", "inputs": [_inputs_ball("main", "号码", "03 08 12 18 21 25 29")]},
                {"id": "compound", "name": "复式", "hint": "选 8–16 个号码，每 7 个一组", "inputs": [_inputs_ball("main", "号码", "03 08 12 16 18 21 25 29")]},
            ],
            "table": _table_for("qlc"),
        },
        "qxc": {
            "note": "前 6 位 0–9，特别号 0–14。一、二等奖为浮动示意，其余为固定奖。",
            "plays": [
                {"id": "single", "name": "单式", "hint": "7 个位置各 1 个号码", "inputs": _inputs_pos(qxc_labels, "0")},
                {"id": "compound", "name": "复式", "hint": "至少一个位置多选", "inputs": _inputs_pos(qxc_labels, "0 1")},
            ],
            "table": _table_for("qxc"),
        },
        "kl8": {
            "note": "从 1–80 中选号，开奖 20 个。号码个数等于所选玩法为单式，多于玩法则为复式。选十中 10 为浮动示意。",
            "plays": [
                {
                    "id": "pick",
                    "name": "选号",
                    "hint": "先选「选几」，再填号码。多出的号码按复式计注",
                    "picks": list(range(1, 11)),
                    "inputs": [_inputs_ball("main", "号码", "01 05 12 18 22 27 31 35 40 44")],
                }
            ],
            "tables": {str(n): _table_for("kl8", n) for n in range(1, 11)},
        },
    }
    return {"stake": STAKE, "lotteries": lotteries}


def _digit_rules(note, digit_single, digit_compound, group_single, group6_single, group_compound) -> dict:
    return {
        "note": note,
        "plays": [
            {"id": "direct", "name": "直选单式", "hint": "百、十、个各 1 个数字，顺序一致", "inputs": digit_single},
            {"id": "direct_compound", "name": "直选复式", "hint": "至少一位选多个数字", "inputs": digit_compound},
            {"id": "group3", "name": "组三单式", "hint": "3 个数字里恰好有两位相同，如 1 1 2", "inputs": group_single},
            {"id": "group3_compound", "name": "组三复式", "hint": "选 2 个及以上不同数字，注数 = n×(n−1)", "inputs": group_compound},
            {"id": "group6", "name": "组六单式", "hint": "3 个互不相同的数字", "inputs": group6_single},
            {"id": "group6_compound", "name": "组六复式", "hint": "选 4 个及以上不同数字，注数 = C(n,3)", "inputs": group_compound},
        ],
        "table": _table_for("fc3d"),
    }


def normalize_bet(lottery_type: str, bet_numbers: Any, play: Optional[str] = None, pick: Optional[int] = None, multiple: int = 1) -> dict:
    t = normalize_type(lottery_type)
    raw = _as_dict(bet_numbers)
    chosen = play or raw.get("play") or _infer_play(t, raw)
    pick_n = pick if pick is not None else raw.get("pick")
    mult = max(1, int(multiple or raw.get("multiple") or 1))
    if t == "ssq":
        return _norm_ssq_dlt(t, chosen, raw, mult, 6, 1, 33, 16, 20, 16, "红球", "蓝球")
    if t == "dlt":
        return _norm_ssq_dlt(t, chosen, raw, mult, 5, 2, 35, 12, 20, 12, "前区", "后区")
    if t in ("fc3d", "pl3"):
        return _norm_digit3(t, chosen, raw, mult)
    if t == "pl5":
        return _norm_positional(t, chosen, raw, mult, 5, 0, 9, "排列五")
    if t == "qxc":
        return _norm_qxc(chosen, raw, mult)
    if t == "qlc":
        return _norm_qlc(chosen, raw, mult)
    if t == "kl8":
        return _norm_kl8(raw, pick_n, mult)
    raise ValueError("未知彩种")


def _infer_play(t: str, raw: dict) -> str:
    if raw.get("positions"):
        sizes = [len(p) for p in raw["positions"] if isinstance(p, list)]
        if t in ("fc3d", "pl3", "pl5", "qxc") and any(n > 1 for n in sizes):
            return "direct_compound" if t != "qxc" else "compound"
        if t == "qxc":
            return "single"
        if t in ("fc3d", "pl3", "pl5"):
            return "direct"
    if t == "kl8":
        return "pick"
    if t in ("fc3d", "pl3"):
        return "direct"
    if t == "pl5":
        return "direct"
    if t == "qxc":
        return "single"
    if t == "qlc":
        mains = raw.get("main") or []
        return "compound" if isinstance(mains, list) and len(mains) > 7 else "single"
    return "single"


def _norm_ssq_dlt(t, play, raw, multiple, need_main, need_special, main_hi, special_hi, main_max, special_max, main_label, special_label) -> dict:
    if play not in ("single", "compound"):
        play = "single"
    main = _balls(raw.get("main"), 2, 1, main_hi, main_label)
    special = _balls(raw.get("special"), 2, 1, special_hi, special_label)
    if play == "single":
        if len(main) != need_main or len(special) != need_special:
            raise ValueError(f"单式需要 {need_main} 个{main_label} + {need_special} 个{special_label}")
    else:
        if not (need_main <= len(main) <= main_max):
            raise ValueError(f"复式{main_label}需要 {need_main}–{main_max} 个")
        if not (need_special <= len(special) <= special_max):
            raise ValueError(f"复式{special_label}需要 {need_special}–{special_max} 个")
        bets = comb(len(main), need_main) * comb(len(special), need_special)
        if bets < 2:
            raise ValueError("复式至少 2 注，注数不足时请改用单式")
        if bets > MAX_BETS:
            raise ValueError(f"注数 {bets} 超过上限 {MAX_BETS}，请减少号码")
    return {"play": play, "main": main, "special": special, "positions": [], "pick": None, "multiple": multiple}


def _position_sets(raw_positions, count, lo, hi, label, allow_multi: bool) -> list[list[str]]:
    positions = _split_positions(raw_positions, count)
    sets: list[list[str]] = []
    for i, pos in enumerate(positions):
        nums = _balls(pos, 1, lo, hi, f"{label}{i + 1}")
        if not nums:
            raise ValueError(f"第 {i + 1} 位至少选 1 个号码")
        if not allow_multi and len(nums) != 1:
            raise ValueError("单式每个位置只能选 1 个号码")
        sets.append(nums)
    return sets


def _norm_positional(t, play, raw, multiple, count, lo, hi, label) -> dict:
    if play not in ("direct", "direct_compound"):
        play = "direct"
    positions = raw.get("positions")
    if not positions:
        raw_main = raw.get("main") or []
        if isinstance(raw_main, str):
            raw_main = [part for part in raw_main.replace(",", " ").split() if part]
        if len(raw_main) != count:
            raise ValueError(f"{label}需要 {count} 位号码")
        positions = [[n] for n in raw_main]
    sets = _position_sets(positions, count, lo, hi, label, play == "direct_compound")
    bets = 1
    for nums in sets:
        bets *= len(nums)
    if play == "direct_compound" and bets < 2:
        raise ValueError("直选复式至少一位要多选")
    if bets > MAX_BETS:
        raise ValueError(f"注数 {bets} 超过上限 {MAX_BETS}")
    flat = [n for pos in sets for n in pos]
    return {"play": play, "main": flat, "special": [], "positions": sets, "pick": None, "multiple": multiple}


def _norm_qlc(play, raw, multiple) -> dict:
    if play not in ("single", "compound"):
        play = "single"
    nums = _balls(raw.get("main"), 2, 1, 30, "号码")
    if play == "single":
        if len(nums) != 7:
            raise ValueError("单式需要 7 个号码")
    else:
        if not (8 <= len(nums) <= 16):
            raise ValueError("复式需要 8–16 个号码")
        if comb(len(nums), 7) > MAX_BETS:
            raise ValueError(f"注数超过上限 {MAX_BETS}")
    return {"play": play, "main": nums, "special": [], "positions": [], "pick": None, "multiple": multiple}


def _score_qlc(bet, draw_numbers):
    draw_main, draw_special = _draw_pair(draw_numbers, 2, 1, 30, "基本号", "特别号", 1, 30)
    if len(draw_main) < 7 or len(draw_special) < 1:
        raise ValueError("七乐彩开奖号码不完整")
    draw_main, draw_special = draw_main[:7], draw_special[:1]
    selected = set(bet["main"])
    basic_hit = len(selected & set(draw_main))
    special_hit = len(selected & (set(draw_special) - set(draw_main)))
    miss = len(bet["main"]) - basic_hit - special_hit
    bets = comb(len(bet["main"]), 7)
    _check_bets(bets)
    breakdown = []
    for (need_h, need_s), condition, level, unit, floating in QLC_ROWS:
        rest = 7 - need_h - need_s
        count = comb(basic_hit, need_h) * comb(special_hit, need_s) * comb(miss, rest)
        if count:
            breakdown.append({
                "condition": condition,
                "level": level,
                "count": count,
                "unit": unit,
                "floating": floating,
                "amount": count * unit,
            })
    return bets, breakdown, basic_hit, special_hit, {"main": draw_main, "special": draw_special}


def _norm_qxc(play, raw, multiple) -> dict:
    if play not in ("single", "compound"):
        play = "single"
    positions = raw.get("positions")
    if not positions:
        main = [str(x) for x in (raw.get("main") or [])]
        special = [str(x) for x in (raw.get("special") or [])]
        joined = main + special
        if len(joined) != 7:
            raise ValueError("七星彩需要 6 位 + 1 个特别号")
        positions = [[n] for n in joined]
    sets = []
    for i, pos in enumerate(_split_positions(positions, 7)):
        hi = 14 if i == 6 else 9
        label = "特别号" if i == 6 else f"第{i + 1}位"
        nums = _balls(pos, 1, 0, hi, label)
        if not nums:
            raise ValueError(f"{label}至少选 1 个号码")
        if play == "single" and len(nums) != 1:
            raise ValueError("单式每个位置只能选 1 个号码")
        sets.append(nums)
    bets = 1
    for nums in sets:
        bets *= len(nums)
    if play == "compound" and bets < 2:
        raise ValueError("复式至少一个位置要多选")
    if bets > MAX_BETS:
        raise ValueError(f"注数 {bets} 超过上限 {MAX_BETS}")
    return {
        "play": play,
        "main": [n for pos in sets[:6] for n in pos],
        "special": sets[6][:],
        "positions": sets,
        "pick": None,
        "multiple": multiple,
    }


def _norm_digit3(t, play, raw, multiple) -> dict:
    plays = {"direct", "direct_compound", "group3", "group3_compound", "group6", "group6_compound"}
    if play not in plays:
        play = "direct"
    if play in ("direct", "direct_compound"):
        return _norm_positional(t, play, raw, multiple, 3, 0, 9, "福彩3D" if t == "fc3d" else "排列三")
    nums = _balls(raw.get("main"), 1, 0, 9, "号码", allow_dup=(play == "group3"))
    distinct = list(dict.fromkeys(nums))
    if play == "group3":
        if len(nums) != 3 or len(set(nums)) != 2:
            raise ValueError("组三单式需要 3 个数字，且恰好两位相同")
    elif play == "group3_compound":
        if len(nums) != len(distinct):
            raise ValueError("组三复式请填互不相同的数字")
        if len(nums) < 2:
            raise ValueError("组三复式至少选 2 个数字")
        if len(nums) * (len(nums) - 1) > MAX_BETS:
            raise ValueError("注数超过上限")
    elif play == "group6":
        if len(nums) != 3 or len(set(nums)) != 3:
            raise ValueError("组六单式需要 3 个互不相同的数字")
    elif play == "group6_compound":
        if len(nums) != len(distinct):
            raise ValueError("组六复式请填互不相同的数字")
        if len(nums) < 4:
            raise ValueError("组六复式至少选 4 个数字")
        if comb(len(nums), 3) > MAX_BETS:
            raise ValueError("注数超过上限")
    return {"play": play, "main": nums, "special": [], "positions": [], "pick": None, "multiple": multiple}


def _norm_kl8(raw, pick_n, multiple) -> dict:
    try:
        pick = int(pick_n or 10)
    except (TypeError, ValueError):
        pick = 10
    if pick < 1 or pick > 10:
        raise ValueError("快乐八玩法为选一到选十")
    nums = _balls(raw.get("main"), 2, 1, 80, "号码")
    if len(nums) < pick:
        raise ValueError(f"选{PICK_CN.get(pick, pick)}至少需要 {pick} 个号码")
    if len(nums) > 80:
        raise ValueError("最多 80 个号码")
    bets = comb(len(nums), pick)
    if bets > MAX_BETS:
        raise ValueError(f"注数 {bets} 超过上限 {MAX_BETS}，请减少号码")
    return {"play": "pick", "main": nums, "special": [], "positions": [], "pick": pick, "multiple": multiple}


def _draw_pair(draw_numbers: Any, width: int, lo: int, hi: int, main_label: str, special_label: str, special_lo: int, special_hi: int, allow_dup: bool = False) -> tuple[list[str], list[str]]:
    parsed = parse_numbers(draw_numbers or {})
    if not parsed["main"] and not parsed["special"]:
        return [], []
    main = _balls(parsed["main"], width, lo, hi, "开奖" + main_label, allow_dup=allow_dup)
    special = _balls(parsed["special"], width, special_lo, special_hi, "开奖" + special_label, allow_dup=allow_dup)
    return main, special


def _check_bets(bets: int) -> None:
    if bets > MAX_BETS:
        raise ValueError(f"注数 {bets} 超过上限 {MAX_BETS}")


def _prize_pool(rows: list[tuple], hits: tuple[int, int]) -> list[dict]:
    breakdown = []
    for key, condition, level, unit, floating in rows:
        if key == hits:
            breakdown.append({
                "condition": condition,
                "level": level,
                "count": 1,
                "unit": unit,
                "floating": floating,
                "amount": unit,
            })
    return breakdown


def _compound_pool(rows, main_hit, main_miss, special_hit, special_miss, need_main, need_special) -> list[dict]:
    breakdown = []
    for (need_h, need_s), condition, level, unit, floating in rows:
        count = (
            comb(main_hit, need_h)
            * comb(main_miss, need_main - need_h)
            * comb(special_hit, need_s)
            * comb(special_miss, need_special - need_s)
        )
        if count:
            breakdown.append({
                "condition": condition,
                "level": level,
                "count": count,
                "unit": unit,
                "floating": floating,
                "amount": count * unit,
            })
    return breakdown


def _score(bet: dict, draw_numbers: Any) -> tuple[int, list[dict], int, int, Optional[dict]]:
    t = bet["lottery_type"]
    play = bet["play"]
    if draw_numbers is None:
        bets = _bet_count(bet)
        return bets, [], 0, 0, None

    if t == "ssq":
        draw_main, draw_special = _draw_pair(draw_numbers, 2, 1, 33, "红球", "蓝球", 1, 16)
        if len(draw_main) < 6 or len(draw_special) < 1:
            raise ValueError("双色球开奖号码不完整")
        return _score_set(bet, draw_main, draw_special, SSQ_ROWS, 6, 1)
    if t == "dlt":
        draw_main, draw_special = _draw_pair(draw_numbers, 2, 1, 35, "前区", "后区", 1, 12)
        if len(draw_main) < 5 or len(draw_special) < 2:
            raise ValueError("大乐透开奖号码不完整")
        return _score_set(bet, draw_main, draw_special, DLT_ROWS, 5, 2)
    if t == "kl8":
        draw_main, _ = _draw_pair(draw_numbers, 2, 1, 80, "号码", "号码", 1, 80)
        if len(draw_main) < 20:
            raise ValueError("快乐八开奖号码不完整")
        return _score_kl8(bet, draw_main)
    if t in ("fc3d", "pl3"):
        draw_main, _ = _draw_pair(draw_numbers, 1, 0, 9, "号码", "号码", 0, 9, allow_dup=True)
        if len(draw_main) < 3:
            raise ValueError("开奖号码需要 3 位")
        return _score_digit3(bet, draw_main[:3])
    if t == "pl5":
        draw_main, _ = _draw_pair(draw_numbers, 1, 0, 9, "号码", "号码", 0, 9, allow_dup=True)
        if len(draw_main) < 5:
            raise ValueError("排列五开奖号码需要 5 位")
        return _score_direct(bet, draw_main[:5], 100_000, "5位按位全中", "直选")
    if t == "qxc":
        return _score_qxc(bet, draw_numbers)
    if t == "qlc":
        return _score_qlc(bet, draw_numbers)
    raise ValueError("未知彩种")


def _bet_count(bet: dict) -> int:
    play = bet["play"]
    if play in ("single", "compound") and bet["lottery_type"] in ("ssq", "dlt"):
        need = (6, 1) if bet["lottery_type"] == "ssq" else (5, 2)
        return comb(len(bet["main"]), need[0]) * comb(len(bet["special"]), need[1])
    if bet["lottery_type"] == "qlc":
        return comb(len(bet["main"]), 7)
    if play in ("direct", "direct_compound") or (bet["lottery_type"] == "qxc" and bet.get("positions")):
        bets = 1
        for pos in bet["positions"]:
            bets *= max(1, len(pos))
        return bets
    if play == "group3":
        return 1
    if play == "group3_compound":
        n = len(bet["main"])
        return n * (n - 1)
    if play == "group6":
        return 1
    if play == "group6_compound":
        return comb(len(bet["main"]), 3)
    if play == "pick":
        return comb(len(bet["main"]), int(bet["pick"]))
    if bet["lottery_type"] == "qxc":
        bets = 1
        for pos in bet["positions"]:
            bets *= max(1, len(pos))
        return bets
    return 1


def _score_set(bet, draw_main, draw_special, rows, need_main, need_special):
    main_hit = len(set(bet["main"]) & set(draw_main))
    special_hit = len(set(bet["special"]) & set(draw_special))
    bets = comb(len(bet["main"]), need_main) * comb(len(bet["special"]), need_special)
    _check_bets(bets)
    if bet["play"] == "single":
        breakdown = _prize_pool(rows, (main_hit, special_hit))
    else:
        breakdown = _compound_pool(
            rows,
            main_hit,
            len(bet["main"]) - main_hit,
            special_hit,
            len(bet["special"]) - special_hit,
            need_main,
            need_special,
        )
    draw = {"main": draw_main, "special": draw_special}
    return bets, breakdown, main_hit, special_hit, draw


def _score_kl8(bet, draw_main):
    pick = int(bet["pick"])
    selected = set(bet["main"])
    drawn = set(draw_main)
    hit = len(selected & drawn)
    miss = len(selected) - hit
    bets = comb(len(selected), pick)
    _check_bets(bets)
    breakdown = []
    for need, condition, level, unit, floating in KL8_HITS[pick]:
        count = comb(hit, need) * comb(miss, pick - need)
        if count:
            breakdown.append({
                "condition": condition,
                "level": level,
                "count": count,
                "unit": unit,
                "floating": floating,
                "amount": count * unit,
            })
    return bets, breakdown, hit, 0, {"main": draw_main, "special": []}


def _score_digit3(bet, draw_main):
    play = bet["play"]
    draw = {"main": draw_main, "special": []}
    if play in ("direct", "direct_compound"):
        return _score_direct(bet, draw_main, 1040, "按位全部相同", "直选")
    distinct = set(draw_main)
    if play == "group3":
        win = len(distinct) == 2 and sorted(bet["main"]) == sorted(draw_main)
        bets = 1
        breakdown = [_hit("两位相同，顺序不限", "组三", 346, win)]
        return bets, [b for b in breakdown if b], 3 if win else 0, 0, draw
    if play == "group3_compound":
        nums = set(bet["main"])
        bets = len(nums) * (len(nums) - 1)
        win = len(distinct) == 2 and distinct <= nums
        return bets, [b for b in [_hit("两位相同，顺序不限", "组三", 346, win)] if b], 3 if win else 0, 0, draw
    if play == "group6":
        win = len(distinct) == 3 and set(bet["main"]) == distinct
        return 1, [b for b in [_hit("三位各不相同，顺序不限", "组六", 173, win)] if b], 3 if win else 0, 0, draw
    nums = set(bet["main"])
    bets = comb(len(nums), 3)
    win = len(distinct) == 3 and distinct <= nums
    return bets, [b for b in [_hit("三位各不相同，顺序不限", "组六", 173, win)] if b], 3 if win else 0, 0, draw


def _hit(condition, level, unit, win: bool):
    if not win:
        return None
    return {"condition": condition, "level": level, "count": 1, "unit": unit, "floating": False, "amount": unit}


def _score_direct(bet, draw_main, unit, condition, level):
    bets = 1
    matched = 0
    for pos, digit in zip(bet["positions"], draw_main):
        bets *= len(pos)
        if digit in pos:
            matched += 1
    _check_bets(bets)
    win = matched == len(draw_main)
    breakdown = [b for b in [_hit(condition, level, unit, win)] if b]
    return bets, breakdown, matched, 0, {"main": draw_main, "special": []}


def _qxc_level(front_hits: int, special: bool):
    if front_hits == 6 and special:
        return QXC_ROWS[0]
    if front_hits == 6:
        return QXC_ROWS[1]
    if front_hits == 5 and special:
        return QXC_ROWS[2]
    if front_hits == 5 or (front_hits == 4 and special):
        return QXC_ROWS[3]
    if front_hits == 4 or (front_hits == 3 and special):
        return QXC_ROWS[4]
    if front_hits == 3 or (special and front_hits <= 2):
        return QXC_ROWS[5]
    return None


def _score_qxc(bet, draw_numbers):
    parsed = parse_numbers(draw_numbers or {})
    positions = bet["positions"]
    if parsed["main"] and not parsed.get("special") and len(parsed["main"]) >= 7:
        draw_pos = [str(int(x)) for x in parsed["main"][:7]]
    else:
        front = _balls(parsed["main"], 1, 0, 9, "开奖前区", allow_dup=True)
        special = _balls(parsed["special"], 1, 0, 14, "开奖特别号")
        if len(front) < 6 or len(special) < 1:
            raise ValueError("七星彩开奖号码不完整")
        draw_pos = front[:6] + special[:1]
    bets = 1
    matched = []
    for pos, digit in zip(positions, draw_pos):
        bets *= len(pos)
        matched.append(digit in pos)
    _check_bets(bets)
    buckets: dict[str, dict] = {}
    for mask in range(1 << 7):
        count = 1
        for i in range(7):
            size = len(positions[i])
            hit = 1 if matched[i] else 0
            if mask & (1 << i):
                count *= hit
            else:
                count *= size - hit
            if count == 0:
                break
        if not count:
            continue
        front_hits = bin(mask & 0b111111).count("1")
        special = bool(mask & (1 << 6))
        level = _qxc_level(front_hits, special)
        if not level:
            continue
        condition, name, unit, floating = level
        slot = buckets.get(name)
        if not slot:
            buckets[name] = {
                "condition": condition,
                "level": name,
                "count": count,
                "unit": unit,
                "floating": floating,
                "amount": count * unit,
            }
        else:
            slot["count"] += count
            slot["amount"] += count * unit
    order = [row[1] for row in QXC_ROWS]
    breakdown = [buckets[name] for name in order if name in buckets]
    front_hit = sum(1 for flag in matched[:6] if flag)
    special_hit = 1 if matched[6] else 0
    draw = {"main": draw_pos[:6], "special": draw_pos[6:], "positions": [[n] for n in draw_pos]}
    return bets, breakdown, front_hit, special_hit, draw


def _level_text(breakdown: list[dict], opened: bool) -> str:
    if not opened:
        return "未开奖"
    if not breakdown:
        return "未中奖"
    names = []
    for row in breakdown:
        if row["level"] not in names:
            names.append(row["level"])
    if len(names) == 1:
        return names[0]
    return f"{names[0]}等"


def calculate(lottery_type: str, bet_numbers: Any, draw_numbers: Any = None, multiple: int = 1, play: Optional[str] = None, pick: Optional[int] = None) -> dict:
    t = normalize_type(lottery_type)
    bet = normalize_bet(t, bet_numbers, play=play, pick=pick, multiple=multiple)
    bet["lottery_type"] = t
    opened = draw_numbers is not None and _has_draw(draw_numbers)
    bets, breakdown, main_hit, special_hit, draw = _score(bet, draw_numbers if opened else None)
    mult = bet["multiple"]
    for row in breakdown:
        row["amount"] = round(row["amount"] * mult, 2)
        row["amount_label"] = money_label(row["amount"], row["floating"])
    amount = round(sum(row["amount"] for row in breakdown), 2)
    cost = round(bets * STAKE * mult, 2)
    table_pick = bet.get("pick") if t == "kl8" else None
    floating = any(row["floating"] for row in breakdown)
    note = "固定奖按公开规则，浮动奖为示意金额；大乐透未计追加。请以官方兑奖为准。"
    if floating:
        note = "含浮动奖示意金额。" + note
    return {
        "ok": True,
        "lottery_type": t,
        "play": bet["play"],
        "play_name": play_name(t, bet, bets),
        "pick": bet.get("pick"),
        "bets": bets,
        "stake": STAKE,
        "multiple": mult,
        "cost": cost,
        "level": _level_text(breakdown, opened),
        "amount": amount if opened else 0,
        "opened": opened,
        "main_hit": main_hit,
        "special_hit": special_hit,
        "breakdown": breakdown,
        "bet": {k: bet[k] for k in ("play", "main", "special", "positions", "pick", "multiple")},
        "draw": draw or {"main": [], "special": []},
        "table": _table_for(t, table_pick),
        "note": note,
    }


def _has_draw(draw_numbers: Any) -> bool:
    if draw_numbers is None:
        return False
    if isinstance(draw_numbers, dict):
        return bool(draw_numbers.get("main") or draw_numbers.get("special") or draw_numbers.get("positions"))
    parsed = parse_numbers(draw_numbers)
    return bool(parsed["main"] or parsed["special"])


def canonical_bet(lottery_type: str, bet_numbers: Any) -> dict:
    bet = normalize_bet(lottery_type, bet_numbers, multiple=int((_as_dict(bet_numbers).get("multiple") or 1)))
    stored = {
        "play": bet["play"],
        "main": bet["main"],
        "special": bet["special"],
        "multiple": bet["multiple"],
    }
    if bet.get("positions"):
        stored["positions"] = bet["positions"]
    if bet.get("pick"):
        stored["pick"] = bet["pick"]
    return stored
