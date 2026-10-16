from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas import BacktestIn, PrizeCalcIn
from ..services.backtest import backtest_ticket
from ..services.prize import calculate, prize_rules
from ..services.seed import ensure_seed

router = APIRouter(prefix="/api/prize", tags=["prize"])


@router.get("/rules")
def rules():
    return prize_rules()


@router.post("/calc")
def calc(body: PrizeCalcIn):
    try:
        return calculate(
            body.lottery_type,
            body.bet_numbers,
            body.draw_numbers,
            body.multiple,
            play=body.play,
            pick=body.pick,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/backtest")
def backtest(body: BacktestIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return backtest_ticket(
            db,
            body.lottery_type,
            body.bet_numbers,
            limit=body.limit,
            multiple=body.multiple,
            play=body.play,
            pick=body.pick,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
