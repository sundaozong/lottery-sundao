from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import BetExpandIn
from ..services.bet_expand import expand_bets, expand_rules
from ..services.form_check import center_bands

router = APIRouter(prefix="/api", tags=["bet-expand"])


def _zone(body):
    if body is None:
        return None
    return body.model_dump()


@router.get("/bet-expand/rules")
def rules():
    return expand_rules()


@router.get("/bet-expand/bands")
def bands(lottery_type: str, limit: int = 80, db: Session = Depends(get_db)):
    try:
        return center_bands(db, lottery_type, limit)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/bet-expand")
def expand(body: BetExpandIn, db: Session = Depends(get_db)):
    band = None
    filter_meta = {"only_center": body.only_center, "applied": False, "sample_size": 0, "bands": {}}
    extra_notes: list[str] = []
    if body.only_center:
        try:
            info = center_bands(db, body.lottery_type, body.band_limit)
        except ValueError:
            info = None
        if info is not None:
            filter_meta["sample_size"] = info["sample_size"]
            filter_meta["bands"] = info["bands"]
            if info["ready"]:
                band = info["bands"]
                filter_meta["applied"] = True
            else:
                extra_notes.append("还没有历史可对照，未做常见带过滤")
    result = expand_bets(
        body.lottery_type,
        body.mode,
        pick=body.pick,
        main=_zone(body.main),
        special=_zone(body.special),
        positions=[item.model_dump() for item in body.positions] if body.positions is not None else None,
        offset=body.offset,
        limit=body.limit,
        band=band,
    )
    if extra_notes:
        result["notes"] = extra_notes + result["notes"]
    result["filter"] = filter_meta
    return result
