from fastapi import APIRouter, Depends
from app.api.authorization import require_permissions
from app.models import User

router = APIRouter(prefix="/admin", tags=["administration"])

@router.get("/access")
async def admin_access(user: User = Depends(require_permissions("admin.dashboard.access"))):
    roles = sorted({assignment.role.name for assignment in user.role_assignments})
    permissions = sorted({rp.permission.code for assignment in user.role_assignments for rp in assignment.role.permissions})
    return {"admin": True, "user_id": str(user.id), "roles": roles, "permissions": permissions}
