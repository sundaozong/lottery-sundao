"""号码结伴：同一期里哪些主号经常一起出现。

乐透（双色球 / 大乐透 / 七乐彩 / 快乐八）把主号当成无序集合，统计两两共现。
数字彩（福彩3D / 排列三 / 排列五 / 七星彩）只比较不同位置上的数字。
蓝球 / 特别号单独轻量列出，不混进主号结伴。只读已有开奖，不改其他分析接口。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..lotteries import LOTTERIES, normalize_type, parse_numbers
from ..models import Draw

DISCLAIMER = "号码结伴只看近期开奖里哪些号码一起出现，仅供娱乐，不构成投注建议。"

ANCHOR_LIMIT = 6
COMPANION_LIMIT = 5
SEEDED_COMPANION_LIMIT = 12
PAIR_LIMIT = 10
SPECIAL_PAIR_LIMIT = 6

# main: (lo, hi)。special_label 为空表示不单列特别号。
PROFILES = {
    "ssq": {"mode": "set", "width": 2, "main": (1, 33), "special_label": "蓝球", "positions": []},
    "dlt": {"mode": "set", "width": 2, "main": (1, 35), "special_label": "后区", "positions": []},
    "qlc": {"mode": "set", "width": 2, "main": (1, 30), "special_label": "特别号", "positions": []},
    "kl8": {"mode": "set", "width": 2, "main": (1, 80), "special_label": None, "positions": []},
    "fc3d": {"mode": "digit", "width": 1, "main": (0, 9), "special_label": None, "positions": ["百", "十", "个"]},
    "pl3": {"mode": "digit", "width": 1, "main": (0, 9), "special_label": None, "positions": ["百", "十", "个"]},
    "pl5": {"mode": "digit", "width": 1, "main": (0, 9), "special_label": None, "positions": ["万", "千", "百", "十", "个"]},
    "qxc": {"mode": "digit", "width": 1, "main": (0, 9), "special_label": "特别号", "positions": ["1", "2", "3", "4", "5", "6"]},
}


def _fmt(number: int, width: int) -> str:
    return f"{number:0{width}d}" if width > 1 else str(number)


def _rate(count: int, base: int) -> float:
    if base <= 0:
        return 0.0
    return round(count / base, 4)


def _clean_seed(seed) -> str | None:
    if seed is None:
        return None
    text = str(seed).strip()
    return text or None


def _as_int(raw) -> int | None:
    if isinstance(raw, bool) or isinstance(raw, float):
        return None
    if isinstance(raw, int):
        return raw
    text = str(raw).strip()
    if text.isdigit():
        return int(text)
    return None


def _unique_ints(raw) -> list[int]:
    seen: list[int] = []
    found: set[int] = set()
    for item in raw or []:
        number = _as_int(item)
        if number is None or number in found:
            continue
        found.add(number)
        seen.append(number)
    return seen


def _parse_seed(seed: str, lo: int, hi: int, digit: bool) -> int:
    if not seed.isdigit():
        label = "结伴数字" if digit else "结伴号码"
        raise ValueError(f"{label}无效：{seed}")
    number = int(seed)
    if number < lo or number > hi:
        if digit:
            raise ValueError("结伴数字需在 0–9")
        raise ValueError(f"结伴号码超出 {lo}–{hi}：{seed}")
    return number


def _set_summary(draws: list[list], lottery_type: str, profile: dict, seed: str | None, specials: list | None) -> dict:
    lo, hi = profile["main"]
    width = profile["width"]
    parsed = _parse_seed(seed, lo, hi, digit=False) if seed is not None else None
    appearances: dict[int, int] = {}
    pair_counts: dict[tuple[int, int], int] = {}
    special_counts: dict[tuple[int, int], int] = {}
    spec_rows = specials or []

    for index, raw in enumerate(draws):
        nums = sorted(_unique_ints(raw))
        for number in nums:
            appearances[number] = appearances.get(number, 0) + 1
        for left_index, left in enumerate(nums):
            for right in nums[left_index + 1 :]:
                pair_counts[(left, right)] = pair_counts.get((left, right), 0) + 1
        if profile["special_label"] and index < len(spec_rows):
            for main in nums:
                for spec in _unique_ints(spec_rows[index]):
                    special_counts[(main, spec)] = special_counts.get((main, spec), 0) + 1

    companion_limit = SEEDED_COMPANION_LIMIT if parsed is not None else COMPANION_LIMIT

    def companions_of(anchor: int) -> list[dict]:
        rows = []
        base = appearances.get(anchor, 0)
        for (left, right), count in pair_counts.items():
            if left == anchor:
                other = right
            elif right == anchor:
                other = left
            else:
                continue
            rows.append({"n": _fmt(other, width), "count": count, "rate": _rate(count, base)})
        rows.sort(key=lambda item: (-item["count"], int(item["n"])))
        return rows[:companion_limit]

    if parsed is not None:
        anchors = [parsed]
    else:
        anchors = sorted(appearances, key=lambda number: (-appearances[number], number))[:ANCHOR_LIMIT]

    companions = [
        {"n": _fmt(anchor, width), "appearances": appearances.get(anchor, 0), "companions": companions_of(anchor)}
        for anchor in anchors
    ]
    top_pairs = [
        {"a": _fmt(left, width), "b": _fmt(right, width), "count": count, "rate": _rate(count, len(draws))}
        for (left, right), count in pair_counts.items()
    ]
    top_pairs.sort(key=lambda item: (-item["count"], int(item["a"]), int(item["b"])))

    special = None
    if profile["special_label"]:
        special_rows = [
            {
                "main": _fmt(main, width),
                "special": _fmt(spec, width),
                "count": count,
                "rate": _rate(count, len(draws)),
            }
            for (main, spec), count in special_counts.items()
        ]
        special_rows.sort(key=lambda item: (-item["count"], int(item["main"]), int(item["special"])))
        special = {"label": profile["special_label"], "top_pairs": special_rows[:SPECIAL_PAIR_LIMIT]}

    return {
        "lottery_type": lottery_type,
        "sample_size": len(draws),
        "mode": "set",
        "seed": _fmt(parsed, width) if parsed is not None else None,
        "companions": companions,
        "top_pairs": top_pairs[:PAIR_LIMIT],
        "special": special,
        "disclaimer": DISCLAIMER,
    }


def _label(labels: list[str], position: int) -> str:
    if 0 <= position < len(labels):
        return labels[position]
    return str(position + 1)


def _digit_summary(draws: list[list], lottery_type: str, profile: dict, seed: str | None, specials: list | None) -> dict:
    lo, hi = profile["main"]
    labels: list[str] = profile["positions"]
    parsed = _parse_seed(seed, lo, hi, digit=True) if seed is not None else None
    appearances: dict[tuple[int, int], int] = {}
    pair_counts: dict[tuple[int, int, int, int], int] = {}
    special_counts: dict[tuple[int, int, int], int] = {}
    spec_rows = specials or []
    position_count = len(labels)

    for index, raw in enumerate(draws):
        digits = [number for number in (_as_int(item) for item in raw) if number is not None]
        limit = min(len(digits), position_count) if position_count else len(digits)
        for position in range(limit):
            key = (position, digits[position])
            appearances[key] = appearances.get(key, 0) + 1
        for left in range(limit):
            for right in range(left + 1, limit):
                key = (left, digits[left], right, digits[right])
                pair_counts[key] = pair_counts.get(key, 0) + 1
        if profile["special_label"] and index < len(spec_rows):
            specs = _unique_ints(spec_rows[index])
            for position in range(limit):
                for spec in specs:
                    key = (position, digits[position], spec)
                    special_counts[key] = special_counts.get(key, 0) + 1

    companion_limit = SEEDED_COMPANION_LIMIT if parsed is not None else COMPANION_LIMIT

    def companions_of(position: int, digit: int) -> list[dict]:
        rows = []
        base = appearances.get((position, digit), 0)
        for (left_pos, left_digit, right_pos, right_digit), count in pair_counts.items():
            if left_pos == position and left_digit == digit:
                other_pos, other_digit = right_pos, right_digit
            elif right_pos == position and right_digit == digit:
                other_pos, other_digit = left_pos, left_digit
            else:
                continue
            rows.append(
                {
                    "n": str(other_digit),
                    "position": other_pos,
                    "position_label": _label(labels, other_pos),
                    "count": count,
                    "rate": _rate(count, base),
                }
            )
        rows.sort(key=lambda item: (-item["count"], item["position"], int(item["n"])))
        return rows[:companion_limit]

    if parsed is not None:
        positions = [position for position in range(position_count) if appearances.get((position, parsed), 0)]
        if positions:
            companions = [
                {
                    "n": str(parsed),
                    "position": position,
                    "position_label": _label(labels, position),
                    "appearances": appearances.get((position, parsed), 0),
                    "companions": companions_of(position, parsed),
                }
                for position in positions
            ]
        else:
            companions = [
                {"n": str(parsed), "position": None, "position_label": "", "appearances": 0, "companions": []}
            ]
    else:
        anchors = sorted(appearances, key=lambda key: (-appearances[key], key[0], key[1]))[:ANCHOR_LIMIT]
        companions = [
            {
                "n": str(digit),
                "position": position,
                "position_label": _label(labels, position),
                "appearances": appearances[(position, digit)],
                "companions": companions_of(position, digit),
            }
            for position, digit in anchors
        ]

    top_pairs = [
        {
            "a": str(left_digit),
            "pos_a": left_pos,
            "label_a": _label(labels, left_pos),
            "b": str(right_digit),
            "pos_b": right_pos,
            "label_b": _label(labels, right_pos),
            "count": count,
            "rate": _rate(count, len(draws)),
        }
        for (left_pos, left_digit, right_pos, right_digit), count in pair_counts.items()
    ]
    top_pairs.sort(key=lambda item: (-item["count"], item["pos_a"], int(item["a"]), item["pos_b"], int(item["b"])))

    special = None
    if profile["special_label"]:
        special_rows = [
            {
                "n": str(digit),
                "position": position,
                "position_label": _label(labels, position),
                "special": str(spec),
                "count": count,
                "rate": _rate(count, len(draws)),
            }
            for (position, digit, spec), count in special_counts.items()
        ]
        special_rows.sort(key=lambda item: (-item["count"], item["position"], int(item["n"]), int(item["special"])))
        special = {"label": profile["special_label"], "top_pairs": special_rows[:SPECIAL_PAIR_LIMIT]}

    return {
        "lottery_type": lottery_type,
        "sample_size": len(draws),
        "mode": "digit",
        "seed": str(parsed) if parsed is not None else None,
        "companions": companions,
        "top_pairs": top_pairs[:PAIR_LIMIT],
        "special": special,
        "disclaimer": DISCLAIMER,
    }


def summarize(draws: list[list], lottery_type: str, seed=None, specials: list | None = None) -> dict:
    """draws 已是每期主号。specials 与 draws 对齐，可省略。"""
    lottery = normalize_type(lottery_type)
    profile = PROFILES.get(lottery)
    if profile is None or lottery not in LOTTERIES:
        raise ValueError("未知彩种")
    cleaned = _clean_seed(seed)
    if profile["mode"] == "digit":
        return _digit_summary(draws, lottery, profile, cleaned, specials)
    return _set_summary(draws, lottery, profile, cleaned, specials)


def affinity_stats(db: Session, lottery_type: str, limit: int = 50, seed=None) -> dict:
    lottery = normalize_type(lottery_type)
    if lottery not in LOTTERIES:
        raise ValueError("未知彩种")
    rows = (
        db.query(Draw)
        .filter(Draw.lottery_type == lottery)
        .order_by(Draw.issue.desc())
        .limit(limit)
        .all()
    )
    draws: list[list[int]] = []
    specials: list[list[int]] = []
    for row in rows:
        parsed = parse_numbers(row.numbers)
        mains = _unique_ints(parsed["main"])
        if not mains:
            continue
        draws.append(mains)
        specials.append(_unique_ints(parsed["special"]))
    return summarize(draws, lottery, seed=seed, specials=specials)
