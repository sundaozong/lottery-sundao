"""开奖爬取：福彩 CWL + 体彩 sporttery，默认近 300 期；失败不致命。"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

from ..lotteries import LOTTERIES, dump_numbers
from ..models import Draw

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 300
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 福彩公开 JSON
CWL_NAME = {
    "ssq": "ssq",
    "qlc": "qlc",
    "fc3d": "3d",
    "kl8": "kl8",
}

# 体彩 webapi gameNo
SPORTTERY_GAME = {
    "dlt": "85",
    "pl3": "35",
    "pl5": "350133",
    "qxc": "04",
}


def _upsert_draw(
    db: Session,
    lottery_type: str,
    issue: str,
    numbers: Any,
    draw_date: str,
    source: str,
) -> bool:
    row = db.query(Draw).filter_by(lottery_type=lottery_type, issue=issue).first()
    payload = dump_numbers(numbers)
    if row:
        if source == "crawl":
            row.numbers = payload
            row.draw_date = draw_date or row.draw_date
            row.source = source
        return False
    db.add(
        Draw(
            lottery_type=lottery_type,
            issue=issue,
            numbers=payload,
            draw_date=draw_date,
            source=source,
        )
    )
    return True


def _parse_cwl_result(name: str, data: dict) -> list[dict]:
    out = []
    for item in data.get("result", []) or []:
        code = str(item.get("code") or item.get("issue") or "")
        date = str(item.get("date") or item.get("drawTime") or "")[:10]
        if name in ("ssq", "qlc"):
            red = (item.get("red") or "").replace(",", " ").split()
            blue = (item.get("blue") or "").split()
            nums = {
                "main": [x.zfill(2) for x in red],
                "special": [x.zfill(2) for x in blue],
            }
        elif name in ("3d", "fc3d"):
            digits = list(
                str(item.get("red") or item.get("number") or "")
                .replace(",", "")
                .replace(" ", "")
            )
            nums = {"main": digits[:3], "special": []}
        elif name == "kl8":
            red = (item.get("red") or "").replace(",", " ").split()
            nums = {"main": [x.zfill(2) for x in red[:20]], "special": []}
        else:
            continue
        if code:
            out.append({"issue": code, "numbers": nums, "draw_date": date})
    return out


def _parse_sporttery_item(lottery_type: str, item: dict) -> Optional[dict]:
    code = str(item.get("lotteryDrawNum") or "").strip()
    date = str(item.get("lotteryDrawTime") or "")[:10]
    raw = str(item.get("lotteryDrawResult") or "").strip()
    parts = [p for p in raw.replace(",", " ").split() if p]
    if not code or not parts:
        return None
    if lottery_type == "dlt":
        nums = {
            "main": [x.zfill(2) for x in parts[:5]],
            "special": [x.zfill(2) for x in parts[5:7]],
        }
    elif lottery_type == "pl3":
        nums = {"main": list(parts[0]) if len(parts) == 1 else parts[:3], "special": []}
        if len(parts) >= 3:
            nums = {"main": [str(x) for x in parts[:3]], "special": []}
    elif lottery_type == "pl5":
        if len(parts) == 1 and len(parts[0]) == 5:
            nums = {"main": list(parts[0]), "special": []}
        else:
            nums = {"main": [str(x) for x in parts[:5]], "special": []}
    elif lottery_type == "qxc":
        nums = {
            "main": [str(x) for x in parts[:6]],
            "special": [str(x) for x in parts[6:7]],
        }
    else:
        return None
    return {"issue": code, "numbers": nums, "draw_date": date}


async def crawl_cwl(
    client: httpx.AsyncClient, lottery_type: str, limit: int
) -> tuple[list[dict], Optional[str]]:
    name = CWL_NAME.get(lottery_type)
    if not name:
        return [], f"{lottery_type}: 非福彩源"
    url = (
        "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"
        f"?name={name}&issueCount={limit}"
    )
    try:
        r = await client.get(
            url,
            headers={"User-Agent": UA},
            timeout=60.0,
        )
        if r.status_code != 200:
            return [], f"{lottery_type}: HTTP {r.status_code}"
        data = r.json()
        parsed = _parse_cwl_result(name, data)[:limit]
        if not parsed:
            return [], f"{lottery_type}: 响应无有效期次"
        return parsed, None
    except Exception as e:
        logger.warning("crawl cwl %s failed: %s", lottery_type, e)
        return [], f"{lottery_type}: {type(e).__name__}: {e}"


async def crawl_sporttery(
    client: httpx.AsyncClient, lottery_type: str, limit: int
) -> tuple[list[dict], Optional[str]]:
    game_no = SPORTTERY_GAME.get(lottery_type)
    if not game_no:
        return [], f"{lottery_type}: 非体彩源"
    page_size = 100
    pages_needed = (limit + page_size - 1) // page_size
    out: list[dict] = []
    try:
        for page in range(1, pages_needed + 1):
            url = (
                "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry"
                f"?gameNo={game_no}&provinceId=0&pageSize={page_size}&isVerify=1&pageNo={page}"
            )
            r = await client.get(
                url,
                headers={"User-Agent": UA, "Referer": "https://www.sporttery.cn/"},
                timeout=30.0,
            )
            if r.status_code != 200:
                return out, f"{lottery_type}: HTTP {r.status_code} (page {page})"
            data = r.json()
            if not data.get("success") and str(data.get("errorCode")) not in ("0", "0.0"):
                return out, f"{lottery_type}: {data.get('errorMessage') or data.get('errorCode')}"
            value = data.get("value") or {}
            rows = value.get("list") or []
            if not rows:
                break
            for item in rows:
                parsed = _parse_sporttery_item(lottery_type, item)
                if parsed:
                    out.append(parsed)
                if len(out) >= limit:
                    return out[:limit], None
            await asyncio.sleep(0.25)
        if not out:
            return [], f"{lottery_type}: 响应无有效期次"
        return out[:limit], None
    except Exception as e:
        logger.warning("crawl sporttery %s failed: %s", lottery_type, e)
        return out, f"{lottery_type}: {type(e).__name__}: {e}"


async def crawl_one(
    client: httpx.AsyncClient, lottery_type: str, limit: int = DEFAULT_LIMIT
) -> tuple[list[dict], Optional[str]]:
    if lottery_type in CWL_NAME:
        return await crawl_cwl(client, lottery_type, limit)
    if lottery_type in SPORTTERY_GAME:
        return await crawl_sporttery(client, lottery_type, limit)
    return [], f"{lottery_type}: 暂无配置公开源"


async def run_crawl(
    db: Session,
    types: Optional[list[str]] = None,
    limit: int = DEFAULT_LIMIT,
) -> dict:
    types = types or list(LOTTERIES.keys())
    added = 0
    updated = 0
    errors: list[str] = []
    crawled_types: list[str] = []
    counts: dict[str, int] = {}

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for t in types:
            rows, err = await crawl_one(client, t, limit)
            if err:
                errors.append(err)
            n_new = 0
            for row in rows:
                if _upsert_draw(
                    db, t, row["issue"], row["numbers"], row["draw_date"], "crawl"
                ):
                    added += 1
                    n_new += 1
                else:
                    updated += 1
            if rows:
                crawled_types.append(t)
                counts[t] = len(rows)
            db.commit()

    return {
        "ok": True,
        "added": added,
        "updated": updated,
        "limit": limit,
        "counts": counts,
        "crawled_types": sorted(set(crawled_types)),
        "errors": errors,
        "message": "爬取完成；失败彩种见 errors" if errors else "爬取成功",
        "at": datetime.utcnow().isoformat() + "Z",
        "disclaimer": "开奖数据尽力而为；请以官方公布为准。",
    }
