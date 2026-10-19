from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import BasketVerifyIn
from ..services.basket_verify import verify_basket
from ..services.seed import ensure_seed

router = APIRouter(prefix="/api/basket", tags=["basket"])


@router.post("/verify")
def basket_verify(body: BasketVerifyIn, db: Session = Depends(get_db)):
    """对照当前彩种选号篮与某一期本地开奖。不写购彩记录，也不改 prize。"""
    ensure_seed(db)
    try:
        return verify_basket(
            db,
            body.lottery_type,
            issue=body.issue,
            tickets=body.tickets,
            multiple=body.multiple,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
