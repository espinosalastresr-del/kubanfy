"""SQLAlchemy models.

Import all models here so Alembic and metadata see them.
"""

from app.models.user import User

__all__ = ["User"]
