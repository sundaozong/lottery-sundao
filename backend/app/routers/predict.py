from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas import PredictIn
from ..services.predict import DISCLAIMER, constraints_requested, generate
from ..services.pulse_ensemble import generate_pulse
from ..services.seed import ensure_seed

router = APIRouter(prefix="/api/predict", tags=["predict"])


@router.post(
    "",
    summary="生成娱乐推荐",
    description=(
        "strategy 为 hot、cold、hybrid、random 时按历史频次抽样。"
        "strategy=pulse（脉动综合）生成一批候选票，调用重号、动量、邻号、跨度、连号簇、012路、和值、奇偶、质合、区位、尾数、AC值、和尾、大小、升平降、振幅、均值、中位数的现有打分函数，"
        "等权（或按 weights）合成总分后返回前 count 注。分数只对照近期形态，不代表预测能力。"
        "可选 constraints 为机选硬条件（胆码、杀号、奇偶、和值、跨度、连号、三区、大小），"
        "只在 hot、cold、hybrid、random 上拒绝采样；不传则与原来一致。脉动综合不套用机选条件。"
        "仅供娱乐，不构成投注建议。"
    ),
)
def predict(body: PredictIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    strategy = (body.strategy or "hot").strip().lower()
    try:
        if strategy == "pulse":
            if constraints_requested(body.constraints):
                raise ValueError("机选条件只用于热号、冷号、混合和随机；脉动综合保持原有打分，请去掉条件或改用其他策略。")
            return generate_pulse(db, body.lottery_type, count=body.count, weights=body.weights)
        return generate(db, body.lottery_type, strategy, body.count, constraints=body.constraints)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/disclaimer")
def disclaimer():
    return {"disclaimer": DISCLAIMER, "entertainment_only": True}
