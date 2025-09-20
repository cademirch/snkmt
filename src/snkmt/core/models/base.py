from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import JSON
from typing import Any


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON}
