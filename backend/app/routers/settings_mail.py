import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AppSetting, Draw
from ..schemas import SettingsIn, MailTestIn, MailPredictIn
from ..config import get_settings
from ..lotteries import LOTTERIES, parse_numbers
from ..services.mail import smtp_configured, send_mail, send_draw_digest
from ..services.seed import ensure_seed

router = APIRouter(prefix="/api", tags=["settings"])


def _get(db: Session, key: str, default: str = "") -> str:
    row = db.get(AppSetting, key)
    return row.value if row else default


def _set(db: Session, key: str, value: str):
    row = db.get(AppSetting, key)
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))


@router.get("/settings")
def get_app_settings(db: Session = Depends(get_db)):
    ensure_seed(db)
    cfg = get_settings()
    try:
        subscribed = json.loads(_get(db, "subscribed_types", "[]"))
    except json.JSONDecodeError:
        subscribed = list(LOTTERIES.keys())
    return {
        "crawl_interval_minutes": int(_get(db, "crawl_interval_minutes", str(cfg.crawl_interval_minutes)) or 60),
        "subscribed_types": subscribed,
        "mail_enabled": _get(db, "mail_enabled", "false").lower() == "true",
        "mail_to": _get(db, "mail_to", cfg.mail_to),
        "smtp_configured": smtp_configured(),
        "lotteries": list(LOTTERIES.keys()),
    }


@router.put("/settings")
def update_settings(body: SettingsIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    if body.crawl_interval_minutes is not None:
        _set(db, "crawl_interval_minutes", str(body.crawl_interval_minutes))
    if body.subscribed_types is not None:
        _set(db, "subscribed_types", json.dumps(body.subscribed_types, ensure_ascii=False))
    if body.mail_enabled is not None:
        _set(db, "mail_enabled", "true" if body.mail_enabled else "false")
    if body.mail_to is not None:
        _set(db, "mail_to", body.mail_to)
    db.commit()
    return get_app_settings(db)


@router.post("/mail/test")
def mail_test(body: MailTestIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    to = body.to or _get(db, "mail_to", get_settings().mail_to)
    return send_mail(
        to,
        "测试邮件 · 孙导带你夜夜笙歌",
        "这是一封来自「孙导带你夜夜笙歌」的测试邮件。\n若收到说明 SMTP 配置可用。\n\n仅供个人观测，请理性购彩。",
    )


@router.post("/mail/digest")
def mail_digest(db: Session = Depends(get_db)):
    ensure_seed(db)
    to = _get(db, "mail_to", get_settings().mail_to)
    draws = []
    for t, meta in LOTTERIES.items():
        row = db.query(Draw).filter(Draw.lottery_type == t).order_by(Draw.issue.desc()).first()
        if row:
            nums = parse_numbers(row.numbers)
            text = " ".join(nums["main"])
            if nums["special"]:
                text += " + " + " ".join(nums["special"])
            draws.append({"name": meta["name"], "lottery_type": t, "issue": row.issue, "numbers_text": text})
    return send_draw_digest(to, draws)



@router.post("/mail/predict")
def mail_predict(body: MailPredictIn, db: Session = Depends(get_db)):
    ensure_seed(db)
    to = body.to or _get(db, "mail_to", get_settings().mail_to)
    meta = LOTTERIES.get(body.lottery_type, {})
    name = meta.get("name", body.lottery_type)
    lines = [
        "【孙导带你夜夜笙歌】娱乐推荐",
        "",
        f"彩种：{name}",
        f"策略：{body.strategy or '—'}",
        "",
        "推荐号码（仅供娱乐，不保证中奖）：",
    ]
    for i, rec in enumerate(body.recommendations or [], 1):
        if isinstance(rec, dict):
            main = " ".join(str(x) for x in (rec.get("main") or []))
            special = " ".join(str(x) for x in (rec.get("special") or []))
            text_line = main + (f" + {special}" if special else "")
            score = rec.get("score")
            if isinstance(score, (int, float)) and not isinstance(score, bool):
                text_line += f"  综合 {float(score):.2f}"
        else:
            text_line = str(rec)
        lines.append(f"  方案 {i}: {text_line}")
    lines += ["", "本邮件仅供娱乐参考，请理性购彩，以官方开奖为准。"]
    return send_mail(to, f"娱乐推荐 · {name} · 孙导带你夜夜笙歌", "\n".join(lines))
