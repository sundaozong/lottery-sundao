"""邻号牵引：主号开出之后，±1 在随后几期里出现得勤不勤。

近 limit 期（5–200，默认 80）按期号从新到旧读取。空白主号的行会跳过，
不占窗口名额；limit 先限制查询条数，跳过发生在取出之后。
horizon 是随后看几期（1–10，默认 3）。只有后面刚好够 horizon 期的那次出现才算触发，
最近 horizon 期只当窗口，不再当作来源。

牵引率 = 邻号落在这些窗口里的次数 / (触发次数 × horizon)。
基线 = 该邻号自己的出现期数 / 样本期数，当作各期独立时的期望出现率。
lift = 牵引率 − 基线。一个号有两个邻号时，号码上的 pull_rate、baseline、lift
取两边的平均。触发次数为 0 时，rate 和 lift 留空，基线仍给出。

边界钳制，不环绕。现有数字彩只按位相等，没有 0↔9 环绕，所以这里同样钳住：
数字彩 0 只有 1、9 只有 8；乐透 1 没有更小的邻号，池子上限没有更大的邻号；
七星彩特别号 0 与 14 也钳住。乐透主号按集合，同一期重复只算一次。
蓝球 / 特别号单独统计，不进入主号牵引。数字彩按位置分开，顶层 numbers / pulled 留空。

给一注打分时，只看最近 horizon 期的主号。票面号码是这些号的 ±1 才算被牵引，
号码自己重开不算。多个来源取历史 lift 最大的一条；来源没有完整窗口时这条 lift 记 0。
score 是被牵引的个数，strength 是这些 lift 的和。特别号对照最近的特别号，不并进主号分。
只读本地开奖。
"""
from __future__ import annotations

from collections import Counter, defaultdict
from fractions import Fraction

from sqlalchemy.orm import Session

from ..lotteries import LOTTERIES, normalize_type, parse_numbers
from ..models import Draw
from .echo import PROFILES, normalize_query
from .repeat import POSITION_LABELS

DISCLAIMER = "邻号牵引看主号开出后，邻号在随后几期是否更常出现，仅供娱乐，不构成投注建议。"
EDGE = "clamp"


def _bounded(value, default: int, lo: int, hi: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(lo, min(number, hi))


def _profile(lottery_type: str) -> tuple[str, dict]:
    lottery = normalize_type(lottery_type)
    profile = PROFILES.get(lottery)
    if profile is None or lottery not in LOTTERIES:
        raise ValueError("未知彩种")
    return lottery, profile


def _fmt(number: int, width: int) -> str:
    return str(number).zfill(width) if width > 1 else str(number)


def _as_float(value: Fraction) -> float:
    return round(float(value), 4)


def _history_group(items: list, width: int) -> list[str]:
    out: list[str] = []
    for item in items or []:
        text = str(item).strip()
        if not text.isdigit():
            continue
        out.append(_fmt(int(text), width))
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


def _in_pool(items: list[str], lo: int, hi: int) -> list[str]:
    return [item for item in items if item.isdigit() and lo <= int(item) <= hi]


def _sides(number: str, lo: int, hi: int, width: int) -> list[tuple[str, str]]:
    value = int(number)
    found: list[tuple[str, str]] = []
    if value - 1 >= lo:
        found.append((_fmt(value - 1, width), "low"))
    if value + 1 <= hi:
        found.append((_fmt(value + 1, width), "high"))
    return found


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
                "issue": row.issue,
                "draw_date": row.draw_date or "",
                "main": main,
                "special": _unique(_history_group(parsed["special"], width)),
                "source": row.source or "seed",
            }
        )
    status = "mixed" if any(item["source"] == "crawl" for item in draws) else "seed"
    return draws, status


def _latest(draws: list[dict]) -> dict | None:
    if not draws:
        return None
    head = draws[0]
    return {
        "issue": head["issue"],
        "draw_date": head["draw_date"],
        "main": list(head["main"]),
        "special": list(head["special"]),
    }


def _collect(chrono: list[dict], key_fn, neighbor_fn, horizon: int):
    appearances: Counter = Counter()
    triggers: Counter = Counter()
    hits: dict[str, Counter] = defaultdict(Counter)
    for index, draw in enumerate(chrono):
        present = list(key_fn(draw))
        appearances.update(present)
        if index + horizon >= len(chrono):
            continue
        window = [set(key_fn(item)) for item in chrono[index + 1 : index + 1 + horizon]]
        for number in present:
            triggers[number] += 1
            for neighbor, _side in neighbor_fn(number):
                hits[number][neighbor] += sum(neighbor in group for group in window)
    return appearances, triggers, hits


def _measure(chrono: list[dict], key_fn, lo: int, hi: int, width: int, horizon: int, sample_size: int, extra: dict | None = None):
    neighbor_fn = lambda number: _sides(number, lo, hi, width)
    appearances, triggers, hits = _collect(chrono, key_fn, neighbor_fn, horizon)
    rows = []
    edges = []
    for number in sorted(appearances, key=lambda item: int(item)):
        if appearances[number] <= 0:
            continue
        trigger_count = int(triggers[number])
        neighbors = []
        rate_sum = Fraction(0)
        base_sum = Fraction(0)
        count = 0
        for neighbor, side in neighbor_fn(number):
            count += 1
            baseline = Fraction(int(appearances.get(neighbor, 0)), sample_size) if sample_size else Fraction(0)
            base_sum += baseline
            hit_count = int(hits[number][neighbor])
            if trigger_count == 0:
                rate = None
                lift = None
            else:
                rate_value = Fraction(hit_count, trigger_count * horizon)
                lift_value = rate_value - baseline
                rate_sum += rate_value
                rate = _as_float(rate_value)
                lift = _as_float(lift_value)
                edge = {
                    "source": number,
                    "number": neighbor,
                    "side": side,
                    "hits": hit_count,
                    "triggers": trigger_count,
                    "opportunities": trigger_count * horizon,
                    "rate": rate,
                    "baseline": _as_float(baseline),
                    "lift": lift,
                }
                if extra:
                    edge = {**extra, **edge}
                edges.append(edge)
            neighbors.append(
                {
                    "number": neighbor,
                    "side": side,
                    "hits": hit_count,
                    "rate": rate,
                    "baseline": _as_float(baseline),
                    "lift": lift,
                }
            )
        if trigger_count == 0 or count == 0:
            pull_rate = None
            lift = None
        else:
            pull_rate = _as_float(rate_sum / count)
            lift = _as_float(rate_sum / count - base_sum / count)
        rows.append(
            {
                "number": number,
                "appearances": int(appearances[number]),
                "triggers": trigger_count,
                "neighbors": neighbors,
                "pull_rate": pull_rate,
                "baseline": _as_float(base_sum / count) if count else 0.0,
                "lift": lift,
            }
        )
    edges.sort(key=lambda item: (-item["lift"], -item["rate"], int(item["number"]), int(item["source"])))
    return rows, edges


def _group_key(field: str, lo: int, hi: int):
    def key(draw: dict) -> list[str]:
        return _in_pool(draw[field], lo, hi)

    return key


def _position_key(index: int, lo: int, hi: int):
    def key(draw: dict) -> list[str]:
        main = draw["main"]
        if index >= len(main):
            return []
        return _in_pool([main[index]], lo, hi)

    return key


def _block(chrono, key_fn, bounds, width, horizon, sample_size, label=None, extra=None):
    lo, hi = bounds[0], bounds[1]
    rows, edges = _measure(chrono, key_fn, lo, hi, width, horizon, sample_size, extra)
    block = {"numbers": rows, "pulled": edges}
    if label is not None:
        block = {"label": label, **block}
    return block


def _positions(lottery: str, profile: dict, chrono: list[dict], horizon: int, sample_size: int) -> list[dict]:
    labels = POSITION_LABELS.get(lottery) or []
    lo, hi = profile["main"][0], profile["main"][1]
    positions = []
    for index, label in enumerate(labels):
        rows, edges = _measure(
            chrono,
            _position_key(index, lo, hi),
            lo,
            hi,
            profile["width"],
            horizon,
            sample_size,
            {"index": index, "label": label},
        )
        positions.append({"index": index, "label": label, "numbers": rows, "pulled": edges})
    return positions


def _special_block(profile: dict, chrono: list[dict], horizon: int, sample_size: int) -> dict | None:
    bounds = profile["special"]
    if bounds is None:
        return None
    return _block(
        chrono,
        _group_key("special", bounds[0], bounds[1]),
        bounds,
        profile["width"],
        horizon,
        sample_size,
        profile["special_label"],
    )


def neighbor_summary(db: Session, lottery_type: str, limit: int = 80, horizon: int = 3) -> dict:
    """主号开出后，邻号在随后 horizon 期的出现率，对照独立出现的基线。"""
    lottery, profile = _profile(lottery_type)
    limit_n = _bounded(limit, 80, 5, 200)
    horizon_n = _bounded(horizon, 3, 1, 10)
    draws, status = _load(db, lottery, profile, limit_n)
    chrono = list(reversed(draws))
    sample_size = len(draws)
    if profile["mode"] == "digit":
        numbers: list[dict] = []
        pulled: list[dict] = []
        positions = _positions(lottery, profile, chrono, horizon_n, sample_size)
    else:
        block = _block(
            chrono,
            _group_key("main", profile["main"][0], profile["main"][1]),
            profile["main"],
            profile["width"],
            horizon_n,
            sample_size,
        )
        numbers = block["numbers"]
        pulled = block["pulled"]
        positions = []
    return {
        "lottery_type": lottery,
        "mode": profile["mode"],
        "sample_size": sample_size,
        "horizon": horizon_n,
        "edge": EDGE,
        "numbers": numbers,
        "pulled": pulled,
        "positions": positions,
        "special": _special_block(profile, chrono, horizon_n, sample_size),
        "latest_draw": _latest(draws),
        "data_status": status,
        "disclaimer": DISCLAIMER,
    }


def _empty_ticket() -> dict:
    return {
        "items": [],
        "pulled": [],
        "idle": [],
        "pulled_count": 0,
        "idle_count": 0,
        "strength": 0.0,
        "score": 0,
    }


def _lookup_lift(rows: list[dict], source: str, number: str) -> float:
    row = next((item for item in rows if item["number"] == source), None)
    if row is None:
        return 0.0
    for neighbor in row["neighbors"]:
        if neighbor["number"] == number:
            if neighbor["lift"] is None:
                return 0.0
            return neighbor["lift"]
    return 0.0


def _adjacent(left: str, right: str, lo: int, hi: int) -> bool:
    if not left.isdigit() or not right.isdigit():
        return False
    a = int(left)
    b = int(right)
    if not (lo <= a <= hi and lo <= b <= hi):
        return False
    return abs(a - b) == 1


def _score_numbers(numbers: list[str], recent: list[list[str]], rows: list[dict], lo: int, hi: int) -> list[dict]:
    items = []
    for number in numbers:
        sources: list[str] = []
        seen: set[str] = set()
        hits = 0
        for present in recent:
            found = [source for source in present if _adjacent(number, source, lo, hi)]
            if not found:
                continue
            hits += 1
            for source in found:
                if source in seen:
                    continue
                seen.add(source)
                sources.append(source)
        sources.sort(key=lambda item: int(item))
        pulled = bool(sources)
        lift = max((_lookup_lift(rows, source, number) for source in sources), default=0.0) if pulled else 0.0
        items.append(
            {
                "number": number,
                "pulled": pulled,
                "sources": sources,
                "hits": hits,
                "lift": lift,
            }
        )
    return items


def _finish(items: list[dict], digit: bool) -> dict:
    pulled_items = [item for item in items if item["pulled"]]
    idle_items = [item for item in items if not item["pulled"]]
    if digit:
        pulled = [{"index": item["index"], "label": item["label"], "number": item["number"]} for item in pulled_items]
        idle = [{"index": item["index"], "label": item["label"], "number": item["number"]} for item in idle_items]
    else:
        pulled = [item["number"] for item in pulled_items]
        idle = [item["number"] for item in idle_items]
    return {
        "items": items,
        "pulled": pulled,
        "idle": idle,
        "pulled_count": len(pulled_items),
        "idle_count": len(idle_items),
        "strength": round(sum(item["lift"] for item in pulled_items), 4),
        "score": len(pulled_items),
    }


def _score_main(lottery: str, profile: dict, query: dict, summary: dict, recent: list[dict]) -> dict:
    lo, hi = profile["main"][0], profile["main"][1]
    if profile["mode"] == "digit":
        labels = POSITION_LABELS.get(lottery) or []
        items = []
        for index, label in enumerate(labels):
            number = query["main"][index] if index < len(query["main"]) else ""
            if not number:
                continue
            present = []
            for draw in recent:
                main = draw["main"]
                if index < len(main):
                    present.append(_in_pool([main[index]], lo, hi))
                else:
                    present.append([])
            rows = summary["positions"][index]["numbers"]
            scored = _score_numbers([number], present, rows, lo, hi)[0]
            items.append({"index": index, "label": label, **scored})
        return _finish(items, digit=True)
    present = [_in_pool(draw["main"], lo, hi) for draw in recent]
    return _finish(_score_numbers(query["main"], present, summary["numbers"], lo, hi), digit=False)


def _score_special(profile: dict, query: dict, summary: dict, recent: list[dict]) -> dict:
    special = summary.get("special")
    if not query["special"] or not special:
        return _empty_ticket()
    bounds = profile["special"]
    lo, hi = bounds[0], bounds[1]
    present = [_in_pool(draw["special"], lo, hi) for draw in recent]
    return _finish(_score_numbers(query["special"], present, special["numbers"], lo, hi), digit=False)


def score_neighbor(db: Session, lottery_type: str, main, special=None, limit: int = 80, horizon: int = 3) -> dict:
    """看一注的号码挨着最近开出的主号有多近，特别号单独对照。"""
    query = normalize_query(lottery_type, main, special)
    summary = neighbor_summary(db, query["lottery_type"], limit=limit, horizon=horizon)
    profile = PROFILES[query["lottery_type"]]
    horizon_n = summary["horizon"]
    lottery, _ = _profile(query["lottery_type"])
    draws, _status = _load(db, lottery, profile, _bounded(limit, 80, 5, 200))
    recent = draws[:horizon_n]
    return {
        **summary,
        "query": {"main": query["main"], "special": query["special"]},
        "ticket": _score_main(query["lottery_type"], profile, query, summary, recent),
        "special_ticket": _score_special(profile, query, summary, recent),
    }
