from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Service


def seed(db: Session) -> None:
    """Create the starting services once. Edit names, fees and descriptions here or in the DB."""
    if db.scalar(select(Service.id).limit(1)) is not None:
        return
    settings = get_settings()
    fee_paise = settings.default_fee_inr * 100
    for i in (1, 2, 3):
        db.add(
            Service(
                name=f"Service {i}",
                description=f"Description for Service {i}.",
                duration_minutes=settings.slot_duration_minutes,
                fee_paise=fee_paise,
                sort_order=i,
            )
        )
    db.commit()
