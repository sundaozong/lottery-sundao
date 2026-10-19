from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import ReplayStrategyIn, ReplayTicketIn
from ..services.replay import replay_strategy, replay_ticket
from ..services.seed import ensure_seed

router = APIRouter(prefix="/api/replay", tags=["replay"])


@router.post("/ticket")
def ticket(body: ReplayTicketIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return replay_ticket(
            db,
            body.lottery_type,
            body.bet_numbers,
            window=body.window,
            multiple=body.multiple,
            play=body.play,
            pick=body.pick,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/strategy")
def strategy(body: ReplayStrategyIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    try:
        return replay_strategy(
            db,
            body.lottery_type,
            strategy=body.strategy,
            constraints=body.constraints,
            tickets=body.tickets,
            window=body.window,
            seed=body.seed,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
