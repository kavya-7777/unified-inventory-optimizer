from datetime import datetime, timezone

from sqlalchemy import DateTime, Double, String
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import DeclarativeBase

# MySQL needs a length on every VARCHAR, stores FLOAT as single precision (about 7 digits)
# and DATETIME to whole seconds by default. These defaults keep full precision everywhere.
ShortString = String(255)
PreciseDateTime = DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


class Base(DeclarativeBase):
    type_annotation_map = {
        float: Double(),
        str: ShortString,
        datetime: PreciseDateTime,
    }


def utcnow() -> datetime:
    """Naive UTC timestamp, matching the timezone-less DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
