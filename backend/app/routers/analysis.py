from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..services.analyze import analyze
from ..services.seed import ensure_seed
from ..lotteries import normalize_type

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/{lottery_type}")
def get_analysis(
    lottery_type: str,
    limit: int = Query(50, ge=5, le=200),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    return analyze(db, normalize_type(lottery_type), limit=limit)
