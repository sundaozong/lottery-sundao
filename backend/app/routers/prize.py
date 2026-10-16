from fastapi import APIRouter, HTTPException
from ..schemas import PrizeCalcIn
from ..services.prize import calculate, prize_rules

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
