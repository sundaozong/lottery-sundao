from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas import EchoIn
from ..services.analyze import analyze
from ..services.echo import find_echoes
from ..services.shape import shape_stats
from ..services.seed import ensure_seed
from ..lotteries import normalize_type

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/{lottery_type}/shape")
def get_shape(
    lottery_type: str,
    limit: int = Query(50, ge=5, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    try:
        return shape_stats(db, normalize_type(lottery_type), limit=limit)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{lottery_type}/echo")
def post_echo(lottery_type: str, body: EchoIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return find_echoes(
            db,
            normalize_type(lottery_type),
            body.main,
            body.special,
            limit=body.limit,
            top=body.top,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{lottery_type}")
def get_analysis(
    lottery_type: str,
    limit: int = Query(50, ge=5, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    return analyze(db, normalize_type(lottery_type), limit=limit)
