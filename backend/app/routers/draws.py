from typing import Optional
import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Draw
from ..lotteries import LOTTERIES, parse_numbers, normalize_type
from ..services.crawl import run_crawl
from ..services.seed import ensure_seed

router = APIRouter(prefix="/api/draws", tags=["draws"])


def _serialize(row: Draw) -> dict:
    return {
        "id": row.id,
        "lottery_type": row.lottery_type,
        "name": LOTTERIES.get(row.lottery_type, {}).get("name", row.lottery_type),
        "issue": row.issue,
        "numbers": parse_numbers(row.numbers),
        "draw_date": row.draw_date,
        "source": row.source,
    }


@router.get("/meta")
def lottery_meta():
    return {
        "lotteries": [
            {"type": k, **v} for k, v in LOTTERIES.items()
        ]
    }


@router.get("/latest")
def latest_draws(db: Session = Depends(get_db)):
    ensure_seed(db)
    out = []
    for t in LOTTERIES:
        row = db.query(Draw).filter(Draw.lottery_type == t).order_by(Draw.issue.desc()).first()
        if row:
            out.append(_serialize(row))
    return {"items": out, "disclaimer": "数据可能为种子或爬取结果，请以官方为准。"}


@router.get("")
def list_draws(
    lottery_type: Optional[str] = None,
    limit: int = Query(30, ge=1, le=500),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    q = db.query(Draw)
    if lottery_type:
        q = q.filter(Draw.lottery_type == normalize_type(lottery_type))
    rows = q.order_by(Draw.issue.desc()).limit(limit).all()
    return {"items": [_serialize(r) for r in rows], "total": len(rows)}


@router.post("/crawl")
async def crawl_draws(
    lottery_type: Optional[str] = None,
    limit: int = Query(300, ge=1, le=500),
    db: Session = Depends(get_db),
):
    types = [normalize_type(lottery_type)] if lottery_type else None
    return await run_crawl(db, types, limit=limit)
