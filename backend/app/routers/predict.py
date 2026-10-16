from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas import PredictIn
from ..services.predict import generate, DISCLAIMER
from ..services.seed import ensure_seed

router = APIRouter(prefix="/api/predict", tags=["predict"])


@router.post("")
def predict(body: PredictIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    return generate(db, body.lottery_type, body.strategy, body.count)


@router.get("/disclaimer")
def disclaimer():
    return {"disclaimer": DISCLAIMER, "entertainment_only": True}
