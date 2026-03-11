import logging
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.routes import auth
from app.routes import marketplaces
from app.routes import products
from app.routes import taxonomy
from app.routes import orders
from app.routes import webhooks
from app.tasks.order_sync import sync_all_orders
from app.tasks.walmart_feed_sync import sync_walmart_feed_status

async def walmart_feed_worker():

    while True:

        try:
            sync_walmart_feed_status()
        except Exception as e:
            print("Walmart feed sync error:", e)

        # run every 30 seconds
        await asyncio.sleep(30)

logger = logging.getLogger(__name__)

MEDIA_DIR = Path("media")
MEDIA_DIR.mkdir(exist_ok=True)


settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.APP_DEBUG,
)
@app.on_event("startup")
async def start_workers():

    asyncio.create_task(walmart_feed_worker())

app.include_router(auth.router)
app.include_router(marketplaces.router)
app.include_router(products.router)
app.include_router(taxonomy.router)
app.include_router(orders.router)
app.include_router(webhooks.router)

# allow CORS origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

# ========================
# PERIODIC ORDER SYNC
# ========================

scheduler = BackgroundScheduler()
scheduler.add_job(
    sync_all_orders,
    "interval",
    minutes=settings.ORDER_SYNC_INTERVAL_MINUTES,
    id="order_sync",
    replace_existing=True,
)


@app.on_event("startup")
def start_scheduler():
    scheduler.start()
    logger.info(
        "Order sync scheduler started (every %d min)",
        settings.ORDER_SYNC_INTERVAL_MINUTES,
    )


@app.on_event("shutdown")
def stop_scheduler():
    scheduler.shutdown(wait=False)
    logger.info("Order sync scheduler stopped")


@app.get("/")
def health_check():
    return {"status": "ok"}
