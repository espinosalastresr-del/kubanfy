from fastapi import Depends, HTTPException, status
from app.api.deps import CurrentIdentity
from app.models import User

def require_roles(*allowed_roles: str):
    async def guard(identity: CurrentIdentity) -> User:
        user, _session = identity
        current = {assignment.role.name for assignment in user.role_assignments}
        if not current.intersection(allowed_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes el rol necesario.")
        return user
    return guard

def require_permissions(*required: str):
    async def guard(identity: CurrentIdentity) -> User:
        user, _session = identity
        granted = {
            rp.permission.code
            for assignment in user.role_assignments
            for rp in assignment.role.permissions
        }
        if not set(required).issubset(granted):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para esta operación.")
        return user
    return guard
