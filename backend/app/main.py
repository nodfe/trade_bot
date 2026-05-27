from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.logging import logger as _  # noqa: F401 - init logging
from app.modules.bot.router import router as bot_router
from app.modules.bot.service import BotService
from app.modules.market_data.router import router as market_router
from app.modules.watchlist.router import router as watchlist_router

_bot_service: BotService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bot_service
    logger.info("Starting trade_bot backend...")
    _bot_service = BotService()
    if _bot_service.adapters:
        await _bot_service.start()
    else:
        logger.info("Bot service has no active adapters; skipping startup")
    yield
    if _bot_service.adapters:
        await _bot_service.stop()
    logger.info("Shutting down trade_bot backend...")


app = FastAPI(
    title="A股量化分析系统",
    description="A股行情数据、量化分析、回测、Bot 交互 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market_router, prefix="/api/v1")
app.include_router(bot_router, prefix="/api/v1")
app.include_router(watchlist_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
