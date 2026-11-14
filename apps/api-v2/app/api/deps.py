from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models import User, UserSession
from app.services.auth import find_active_session

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_identity(request: Request, db: DbSession) -> tuple[User, UserSession]:
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida.")
    identity = await find_active_session(db, token)
    if identity is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="La sesión no es válida o ha vencido.")
    return identity


CurrentIdentity = Annotated[tuple[User, UserSession], Depends(get_current_identity)]
