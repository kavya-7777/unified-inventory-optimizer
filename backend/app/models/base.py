from datetime import datetime, timezone

from sqlalchemy import Float
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    type_annotation_map = {float: Float}


def utcnow() -> datetime:
    """Naive UTC timestamp, matching the timezone-less DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
