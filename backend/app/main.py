import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .booking_service import release_expired_holds
from .config import get_settings
from .database import SessionLocal, init_db
from .routers import admin, public, webhooks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("booking")


def _sweep() -> None:
    with SessionLocal() as db:
        release_expired_holds(db)


async def _hold_sweeper() -> None:
    """Every minute, free slots whose payment was not completed in time."""
    while True:
        try:
            await asyncio.to_thread(_sweep)
        except Exception:
            log.exception("Hold sweep failed")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    s = get_settings()
    log.info(
        "Payments: %s | Google Calendar: %s | Email: %s",
        "MOCK" if s.razorpay_mock else "Razorpay",
        "on" if s.google_enabled else "off",
        "Zoho SMTP" if s.smtp_enabled else "console",
    )
    task = asyncio.create_task(_hold_sweeper())
    yield
    task.cancel()


app = FastAPI(title="Consultation Booking API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(webhooks.router)


@app.get("/api/health")
def health():
    s = get_settings()
    return {"ok": True, "payments": "mock" if s.razorpay_mock else "razorpay", "calendar": s.google_enabled, "email": s.smtp_enabled}
