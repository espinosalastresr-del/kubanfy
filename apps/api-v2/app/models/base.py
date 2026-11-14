from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

AUTH_SCHEMA = "auth_v2"


class Base(DeclarativeBase):
    metadata = MetaData(schema=AUTH_SCHEMA)
