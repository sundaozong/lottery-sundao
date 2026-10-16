import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import PurchaseRecord
from ..schemas import RecordIn, RecordUpdate
from ..lotteries import LOTTERIES, load_bet
from ..services.prize import canonical_bet, play_name
from ..services.seed import ensure_seed

router = APIRouter(prefix="/api/records", tags=["records"])


def _ser(r: PurchaseRecord) -> dict:
    bet = load_bet(r.numbers)
    return {
        "id": r.id,
        "lottery_type": r.lottery_type,
        "name": LOTTERIES.get(r.lottery_type, {}).get("name", r.lottery_type),
        "issue": r.issue,
        "numbers": bet,
        "play_name": play_name(r.lottery_type, bet),
        "cost": r.cost,
        "prize": r.prize,
        "note": r.note,
        "purchased_at": r.purchased_at,
        "profit": round(r.prize - r.cost, 2),
    }


@router.get("")
def list_records(db: Session = Depends(get_db)):
    ensure_seed(db)
    rows = db.query(PurchaseRecord).order_by(PurchaseRecord.id.desc()).all()
    total_cost = sum(r.cost for r in rows)
    total_prize = sum(r.prize for r in rows)
    return {
        "items": [_ser(r) for r in rows],
        "summary": {
            "count": len(rows),
            "total_cost": round(total_cost, 2),
            "total_prize": round(total_prize, 2),
            "net": round(total_prize - total_cost, 2),
        },
    }


def _store_numbers(lottery_type: str, numbers) -> str:
    import json
    try:
        stored = canonical_bet(lottery_type, numbers)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return json.dumps(stored, ensure_ascii=False)


@router.post("")
def create_record(body: RecordIn, db: Session = Depends(get_db)):
    row = PurchaseRecord(
        lottery_type=body.lottery_type,
        issue=body.issue,
        numbers=_store_numbers(body.lottery_type, body.numbers),
        cost=body.cost,
        prize=body.prize,
        note=body.note,
        purchased_at=body.purchased_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _ser(row)


@router.put("/{rid}")
def update_record(rid: int, body: RecordUpdate, db: Session = Depends(get_db)):
    row = db.get(PurchaseRecord, rid)
    if not row:
        raise HTTPException(404, "记录不存在")
    data = body.model_dump(exclude_unset=True)
    if "numbers" in data and data["numbers"] is not None:
        lottery_type = data.get("lottery_type") or row.lottery_type
        data["numbers"] = _store_numbers(lottery_type, data["numbers"])
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return _ser(row)


@router.delete("/{rid}")
def delete_record(rid: int, db: Session = Depends(get_db)):
    row = db.get(PurchaseRecord, rid)
    if not row:
        raise HTTPException(404, "记录不存在")
    db.delete(row)
    db.commit()
    return {"ok": True}
