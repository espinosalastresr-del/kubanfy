"""Admin control plane — protected by RBAC permissions."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import DbSession, require_permissions
from app.models.admin import ModerationReportType, ModerationStatus
from app.models.entitlement import PlanCode
from app.models.user import User
from app.services.admin import AdminService
from app.services.rbac import RbacService

router = APIRouter(prefix="/admin", tags=["admin"])


class FlagUpdate(BaseModel):
    enabled: bool


class SettingUpdate(BaseModel):
    value: dict[str, Any]
    description: str | None = None


class ReportCreate(BaseModel):
    target_type: str = Field(pattern="^(track|artist|user|release)$")
    target_id: UUID
    report_type: str
    description: str | None = None


class ReportResolve(BaseModel):
    status: str = Field(pattern="^(resolved|rejected|reviewing)$")
    notes: str | None = None
    takedown_track: bool = False


class SuspendRequest(BaseModel):
    reason: str | None = None


class UserPlanUpdate(BaseModel):
    plan_code: PlanCode
    expires_at: datetime | None = None
    reason: str = Field(min_length=3, max_length=500)


# --- Feature flags ---


@router.get("/feature-flags")
async def list_flags(
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("feature_flags.read"))],
) -> list[dict[str, Any]]:
    svc = AdminService(session)
    await svc.ensure_default_flags()
    flags = await svc.list_flags()
    return [{"key": f.key, "enabled": f.enabled, "description": f.description} for f in flags]


@router.put("/feature-flags/{key}")
async def set_flag(
    key: str,
    body: FlagUpdate,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("feature_flags.write"))],
) -> dict[str, Any]:
    flag = await AdminService(session).set_flag(key, body.enabled, user.id)
    return {"key": flag.key, "enabled": flag.enabled}


# --- Settings ---


@router.put("/settings/{key}")
async def set_setting(
    key: str,
    body: SettingUpdate,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("settings.write"))],
) -> dict[str, Any]:
    s = await AdminService(session).set_setting(
        key, body.value, user.id, description=body.description
    )
    return {"key": s.key, "value": s.value}


@router.get("/settings/{key}")
async def get_setting(
    key: str,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("settings.read"))],
) -> dict[str, Any]:
    s = await AdminService(session).get_setting(key)
    if s is None:
        return {"key": key, "value": None}
    return {"key": s.key, "value": s.value}


# --- Moderation ---


@router.post("/moderation/reports", status_code=201)
async def create_report(
    body: ReportCreate,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("tracks.read"))],
) -> dict[str, Any]:
    # Authenticated users can report; permission is light. Public report can use separate endpoint.
    report = await AdminService(session).create_report(
        reporter_user_id=user.id,
        target_type=body.target_type,
        target_id=body.target_id,
        report_type=ModerationReportType(body.report_type),
        description=body.description,
    )
    return {"id": report.id, "status": report.status.value}


@router.get("/moderation/reports")
async def list_reports(
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("tracks.takedown"))],
    status: str | None = None,
) -> list[dict[str, Any]]:
    st = ModerationStatus(status) if status else None
    reports = await AdminService(session).list_reports(status=st)
    return [
        {
            "id": r.id,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "report_type": r.report_type.value,
            "status": r.status.value,
            "description": r.description,
            "created_at": r.created_at.isoformat(),
        }
        for r in reports
    ]


@router.post("/moderation/reports/{report_id}/resolve")
async def resolve_report(
    report_id: UUID,
    body: ReportResolve,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("tracks.takedown"))],
) -> dict[str, Any]:
    report = await AdminService(session).resolve_report(
        report_id,
        user.id,
        status=ModerationStatus(body.status),
        notes=body.notes,
        takedown_track=body.takedown_track,
    )
    return {"id": report.id, "status": report.status.value}


# --- Users ---


@router.get("/plan-access")
async def plan_access(
    user: Annotated[User, Depends(require_permissions("users.write"))],
) -> dict[str, bool]:
    return {"allowed": True}


@router.get("/users")
async def list_users(
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("users.read"))],
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    return await AdminService(session).list_users(search=q, limit=limit, offset=offset)


@router.put("/users/{user_id}/plan")
async def update_user_plan(
    user_id: UUID,
    body: UserPlanUpdate,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("users.write"))],
) -> dict[str, Any]:
    return await AdminService(session).set_user_plan(
        user_id,
        user.id,
        plan_code=body.plan_code,
        expires_at=body.expires_at,
        reason=body.reason,
    )


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: UUID,
    body: SuspendRequest,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("users.suspend"))],
) -> dict[str, str]:
    u = await AdminService(session).suspend_user(user_id, user.id, reason=body.reason)
    return {"id": str(u.id), "status": u.status.value}


@router.post("/users/{user_id}/unsuspend")
async def unsuspend_user(
    user_id: UUID,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("users.suspend"))],
) -> dict[str, str]:
    u = await AdminService(session).unsuspend_user(user_id, user.id)
    return {"id": str(u.id), "status": u.status.value}


# --- Audit ---


@router.get("/audit-logs")
async def audit_logs(
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("audit_logs.read"))],
    limit: int = 50,
) -> list[dict[str, Any]]:
    logs = await AdminService(session).list_audit_logs(limit=min(limit, 200))
    return [
        {
            "id": log.id,
            "actor_id": log.actor_id,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "result": log.result,
            "reason": log.reason,
            "before": log.before,
            "after": log.after,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


# --- RBAC bootstrap ---


@router.post("/rbac/ensure-defaults")
async def ensure_rbac(
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("settings.write"))],
) -> dict[str, str]:
    await RbacService(session).ensure_default_rbac()
    await AdminService(session).ensure_default_flags()
    return {"status": "ok"}
