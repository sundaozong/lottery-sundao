import json
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from ..database import get_db
from ..lotteries import LOTTERIES, load_bet, normalize_type
from ..models import Draw, PurchaseRecord
from ..schemas import RecordIn, RecordUpdate, RecordVerifyIn
from ..services.ledger import monthly_summary, parse_day, records_csv, rhythm
from ..services.prize import calculate, canonical_bet, play_name
from ..services.seed import ensure_seed

VERIFY_DISCLAIMER = "奖金为示意金额，浮动奖未按当期奖池计算。请以官方开奖与兑奖规则为准。"

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


def _all_rows(db: Session) -> list[PurchaseRecord]:
    return db.query(PurchaseRecord).order_by(PurchaseRecord.id.desc()).all()


@router.get("/monthly")
def records_monthly(db: Session = Depends(get_db)):
    ensure_seed(db)
    return monthly_summary(_all_rows(db))


@router.get("/rhythm")
def records_rhythm(
    on: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    ensure_seed(db)
    today = date.today()
    if on is not None:
        parsed = parse_day(on)
        if parsed is None:
            raise HTTPException(400, "日期无效")
        today = parsed
    return rhythm(_all_rows(db), today)


@router.get("/export")
def export_records(db: Session = Depends(get_db)):
    ensure_seed(db)
    payload = records_csv(_all_rows(db)).encode("utf-8-sig")
    return Response(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=records.csv; filename*=UTF-8''%E8%B4%AD%E4%B9%B0%E8%AE%B0%E5%BD%95.csv"
        },
    )


def _same_money(left, right) -> bool:
    return round(float(left or 0), 2) == round(float(right or 0), 2)


def _verify_item(row: PurchaseRecord, status: str, new_prize, **extra) -> dict:
    item = {
        "id": row.id,
        "lottery_type": row.lottery_type,
        "issue": row.issue or "",
        "old_prize": row.prize,
        "new_prize": new_prize,
        "status": status,
    }
    item.update(extra)
    return item


def _draw_index(db: Session) -> dict[tuple[str, str], Draw]:
    index: dict[tuple[str, str], Draw] = {}
    for draw in db.query(Draw).all():
        index[(normalize_type(draw.lottery_type), (draw.issue or "").strip())] = draw
    return index


@router.post("/verify")
def verify_records(body: RecordVerifyIn | None = None, db: Session = Depends(get_db)):
    """按彩种 + 期号对照本地开奖，重算奖金。默认只预览，apply 时只改 prize。"""
    if body is None:
        body = RecordVerifyIn()
    ensure_seed(db)
    query = db.query(PurchaseRecord)
    if body.record_ids is not None:
        if not body.record_ids:
            rows: list[PurchaseRecord] = []
        else:
            rows = (
                query.filter(PurchaseRecord.id.in_(body.record_ids))
                .order_by(PurchaseRecord.id.asc())
                .all()
            )
    else:
        rows = query.order_by(PurchaseRecord.id.asc()).all()

    draws = _draw_index(db) if rows else {}
    items: list[dict] = []
    wrote = False
    for row in rows:
        issue = (row.issue or "").strip()
        if not issue:
            items.append(_verify_item(row, "no_issue", None))
            continue
        draw = draws.get((normalize_type(row.lottery_type), issue))
        if draw is None:
            items.append(_verify_item(row, "no_draw", None))
            continue
        bet = load_bet(row.numbers)
        try:
            result = calculate(
                row.lottery_type,
                bet,
                draw.numbers,
                multiple=int(bet.get("multiple") or 1),
                play=bet.get("play") or None,
                pick=bet.get("pick"),
            )
        except Exception as exc:
            message = str(exc).strip() or "无法计算奖金"
            items.append(_verify_item(row, "error", None, message=message))
            continue
        amount = round(float(result.get("amount") or 0), 2)
        detail = {
            "level": result.get("level") or "",
            "main_hit": result.get("main_hit"),
            "special_hit": result.get("special_hit"),
        }
        if _same_money(row.prize, amount):
            items.append(_verify_item(row, "unchanged", amount, **detail))
            continue
        if not body.apply:
            items.append(_verify_item(row, "preview", amount, **detail))
            continue
        items.append(_verify_item(row, "updated", amount, **detail))
        row.prize = amount
        wrote = True

    if wrote:
        db.commit()

    counts = {"updated": 0, "preview": 0, "unchanged": 0, "no_issue": 0, "no_draw": 0, "error": 0}
    for item in items:
        if item["status"] in counts:
            counts[item["status"]] += 1
    return {
        "apply": body.apply,
        "disclaimer": VERIFY_DISCLAIMER,
        "summary": {"total": len(items), **counts},
        "items": items,
    }


def _store_numbers(lottery_type: str, numbers) -> str:
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
