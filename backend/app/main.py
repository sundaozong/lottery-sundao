"""孙导带你夜夜笙歌 · FastAPI 入口"""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from .database import Base, engine, SessionLocal
from .services.seed import ensure_seed
from .services.crawl import run_crawl
from .models import AppSetting
from .config import get_settings
from .routers import draws, analysis, predict, records, prize, settings_mail

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("yysg")
scheduler = BackgroundScheduler()


def _crawl_job():
    import asyncio
    db = SessionLocal()
    try:
        asyncio.run(run_crawl(db))
    except Exception as e:
        logger.warning("scheduled crawl failed: %s", e)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_seed(db)
        interval = 60
        row = db.get(AppSetting, "crawl_interval_minutes")
        if row and row.value.isdigit():
            interval = max(5, int(row.value))
        else:
            interval = max(5, get_settings().crawl_interval_minutes)
    finally:
        db.close()

    if not scheduler.running:
        scheduler.add_job(_crawl_job, "interval", minutes=interval, id="crawl", replace_existing=True)
        scheduler.start()
        logger.info("scheduler started, crawl every %s min", interval)
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="孙导带你夜夜笙歌",
    description="个人彩票观测站 API · 预测仅供娱乐",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(draws.router)
app.include_router(analysis.router)
app.include_router(predict.router)
app.include_router(records.router)
app.include_router(prize.router)
app.include_router(settings_mail.router)


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "name": "孙导带你夜夜笙歌",
        "disclaimer": "预测与分析仅供娱乐，不保证中奖；请理性购彩。",
    }
