"""彩种元数据与号码解析工具。"""
from __future__ import annotations
import json
from typing import Any

LOTTERIES = {
    "ssq": {
        "name": "双色球",
        "ball_color": "red",
        "special_color": "blue",
        "desc": "6红+1蓝",
    },
    "dlt": {
        "name": "大乐透",
        "ball_color": "red",
        "special_color": "blue",
        "desc": "5前+2后",
    },
    "fc3d": {
        "name": "福彩3D",
        "ball_color": "green",
        "special_color": "green",
        "desc": "3位数字",
    },
    "pl3": {
        "name": "排列三",
        "ball_color": "green",
        "special_color": "green",
        "desc": "3位数字",
    },
    "pl5": {
        "name": "排列五",
        "ball_color": "green",
        "special_color": "green",
        "desc": "5位数字",
    },
    "qxc": {
        "name": "七星彩",
        "ball_color": "purple",
        "special_color": "orange",
        "desc": "6位+1特别号",
    },
    "qlc": {
        "name": "七乐彩",
        "ball_color": "red",
        "special_color": "blue",
        "desc": "7个号+特别号",
    },
    "kl8": {
        "name": "快乐八",
        "ball_color": "orange",
        "special_color": "orange",
        "desc": "选20/80",
    },
}

TYPE_ALIASES = {"3d": "fc3d", "f3d": "fc3d"}


def normalize_type(t: str) -> str:
    t = (t or "").strip().lower()
    return TYPE_ALIASES.get(t, t)


def number_pools(lottery_type: str) -> tuple[list[str], list[str]]:
    """主号池、特别号池。与分析里的当前遗漏使用同一套号码。"""
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


def parse_numbers(raw: Any) -> dict:
    """统一为 {main: [...], special: [...]}，数字为两位数或单位数字符串。"""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            parts = raw.replace("+", "|").split("|")
            mains = [x.strip() for x in parts[0].replace(",", " ").split() if x.strip()]
            specs = []
            if len(parts) > 1:
                specs = [x.strip() for x in parts[1].replace(",", " ").split() if x.strip()]
            return {"main": mains, "special": specs}
    if isinstance(raw, dict):
        return {
            "main": [str(x).zfill(2) if str(x).isdigit() and int(x) > 9 or len(str(x)) >= 2 else str(x) for x in raw.get("main", raw.get("red", raw.get("front", [])))],
            "special": [str(x).zfill(2) if str(x).isdigit() and (len(str(x)) >= 2 or int(str(x)) > 9) else str(x) for x in raw.get("special", raw.get("blue", raw.get("back", [])))],
        }
    if isinstance(raw, list):
        return {"main": [str(x) for x in raw], "special": []}
    return {"main": [], "special": []}


def dump_numbers(obj: Any) -> str:
    if isinstance(obj, str):
        try:
            json.loads(obj)
            return obj
        except json.JSONDecodeError:
            return json.dumps(parse_numbers(obj), ensure_ascii=False)
    parsed = parse_numbers(obj)
    return json.dumps(parsed, ensure_ascii=False)


def load_bet(raw: Any) -> dict:
    """读出投注 JSON，保留玩法、定位和选几。旧数据只有 main/special。"""
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = None
    if not isinstance(data, dict):
        parsed = parse_numbers(raw)
        return {"main": parsed["main"], "special": parsed["special"], "positions": [], "play": "", "pick": None, "multiple": 1}
    parsed = parse_numbers(data)
    positions = []
    for pos in data.get("positions") or []:
        if isinstance(pos, list):
            positions.append([str(x) for x in pos])
        else:
            positions.append([p for p in str(pos).replace(",", " ").split() if p])
    pick = data.get("pick")
    return {
        "main": parsed["main"],
        "special": parsed["special"],
        "positions": positions,
        "play": data.get("play") or "",
        "pick": int(pick) if isinstance(pick, int) or (isinstance(pick, str) and pick.isdigit()) else pick,
        "multiple": int(data.get("multiple") or 1),
    }


def fmt_num(n: int | str, width: int = 2) -> str:
    s = str(n)
    if s.isdigit():
        return s.zfill(width) if width else s
    return s
