"""应用默认设置；不再写入示例开奖/购彩测试数据。"""
from __future__ import annotations

import json
from sqlalchemy.orm import Session

from ..lotteries import LOTTERIES
from ..models import AppSetting


def ensure_seed(db: Session) -> dict:
    """仅保证设置键存在，不插入任何开奖或购彩样例。"""
    defaults = {
        "crawl_interval_minutes": "60",
        "subscribed_types": json.dumps(list(LOTTERIES.keys())),
        "mail_enabled": "false",
        "mail_to": "",
    }
    for k, v in defaults.items():
        if not db.get(AppSetting, k):
            db.add(AppSetting(key=k, value=v))
    db.commit()
    return {"seed_draws_added": 0, "types": list(LOTTERIES.keys())}
