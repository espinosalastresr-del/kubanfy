"""Rights split and royalty ledger operations.

All money movement is append-only and idempotent; no balance is stored as a
mutable counter, so a future settlement worker can rebuild balances from the
ledger.
"""
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.artist_member import ArtistMember, ArtistMemberRole
from app.models.music import Artist, Release, Track
from app.models.rights import CollaboratorSplit, RoyaltyAccount, RoyaltyLedgerEntry, RoyaltySettlement
from app.services.rbac import RbacService

EDIT_ROLES={ArtistMemberRole.OWNER,ArtistMemberRole.MANAGER}

class RightsRoyaltyService:
    def __init__(self, session: AsyncSession): self.session=session

    async def _authorized(self,user_id:UUID,artist_id:UUID)->None:
        member=await self.session.scalar(select(ArtistMember).where(ArtistMember.artist_id==artist_id,ArtistMember.user_id==user_id))
        if member is None or member.role not in EDIT_ROLES: raise NotFoundError("Artist not found")
        artist=await self.session.get(Artist,artist_id)
        if artist is None or artist.status!="active": raise NotFoundError("Artist not found")

    async def set_splits(self, *, user_id:UUID, artist_id:UUID, scope_type:str, scope_id:UUID, splits:list[dict])->list[CollaboratorSplit]:
        await self._authorized(user_id,artist_id)
        scope_type=scope_type.lower()
        if scope_type not in ("track","release"): raise ValidationError("scope_type must be track or release")
        if scope_type=="track":
            obj=await self.session.scalar(select(Track).where(Track.id == scope_id).with_for_update())
            if obj is None or obj.release_id is None: raise NotFoundError("Track not found")
            release=await self.session.get(Release,obj.release_id)
            if release is None or release.artist_id!=artist_id: raise NotFoundError("Track not found")
        else:
            obj=await self.session.scalar(select(Release).where(Release.id == scope_id).with_for_update())
            if obj is None or obj.artist_id!=artist_id: raise NotFoundError("Release not found")
        if not splits: raise ValidationError("At least one collaborator split is required")
        total=sum(int(x.get("share_bps",0)) for x in splits)
        if total!=10000: raise ValidationError("Collaborator shares must total exactly 10000 basis points")
        if any(int(x.get("share_bps",0))<=0 for x in splits): raise ValidationError("Shares must be positive")
        artists=[UUID(str(x["artist_id"])) for x in splits]
        if len(artists)!=len(set(artists)): raise ValidationError("Duplicate collaborator artist")
        for aid in artists:
            a=await self.session.get(Artist,aid)
            if a is None or a.status!="active": raise ValidationError("Invalid collaborator artist")
        current=await self.session.scalar(select(func.max(CollaboratorSplit.generation)).where(CollaboratorSplit.scope_type==scope_type,CollaboratorSplit.scope_id==scope_id))
        generation=(current or 0)+1
        await self.session.execute(update(CollaboratorSplit).where(CollaboratorSplit.scope_type==scope_type,CollaboratorSplit.scope_id==scope_id,CollaboratorSplit.active.is_(True)).values(active=False))
        created=[]
        for item in splits:
            created.append(CollaboratorSplit(scope_type=scope_type,scope_id=scope_id,artist_id=UUID(str(item["artist_id"])),role=str(item.get("role","artist")),share_bps=int(item["share_bps"]),generation=generation,active=True,created_by_user_id=user_id))
        self.session.add_all(created)
        await self.session.flush()
        return created

    async def get_splits(self, *, user_id:UUID, artist_id:UUID, scope_type:str, scope_id:UUID)->list[CollaboratorSplit]:
        await self._authorized(user_id, artist_id)
        scope_type = scope_type.lower()
        if scope_type not in ("track", "release"):
            raise ValidationError("scope_type must be track or release")
        if scope_type == "track":
            obj = await self.session.get(Track, scope_id)
            if obj is None or obj.release_id is None:
                raise NotFoundError("Track not found")
            release = await self.session.get(Release, obj.release_id)
            if release is None or release.artist_id != artist_id:
                raise NotFoundError("Track not found")
        else:
            obj = await self.session.get(Release, scope_id)
            if obj is None or obj.artist_id != artist_id:
                raise NotFoundError("Release not found")
        result = await self.session.scalars(
            select(CollaboratorSplit).where(
                CollaboratorSplit.scope_type == scope_type,
                CollaboratorSplit.scope_id == scope_id,
                CollaboratorSplit.active.is_(True),
            ).order_by(CollaboratorSplit.created_at)
        )
        return list(result.all())

    async def ensure_account(self, artist_id:UUID, currency:str="CUP")->RoyaltyAccount:
        account=await self.session.scalar(select(RoyaltyAccount).where(RoyaltyAccount.artist_id==artist_id))
        if account is not None:
            if account.currency != currency.upper():
                raise ConflictError("Currency mismatch for royalty account")
            return account
        account=RoyaltyAccount(artist_id=artist_id,currency=currency.upper(),status="active")
        self.session.add(account)
        try:
            async with self.session.begin_nested():
                await self.session.flush()
        except Exception:
            account=await self.session.scalar(select(RoyaltyAccount).where(RoyaltyAccount.artist_id==artist_id))
            if account is None:
                raise
        return account

    async def append_ledger(self, *, user_id:UUID, artist_id:UUID, amount_cents:int, source_type:str, idempotency_key:str, direction:str="credit", source_id:UUID|None=None, currency:str="CUP", metadata:dict|None=None)->RoyaltyLedgerEntry:
        if not await RbacService(self.session).user_has_permission(user_id, "royalties.write"):
            await self._authorized(user_id, artist_id)
        if direction not in ("credit", "debit"): raise ValidationError("Invalid ledger direction")
        if amount_cents<0: raise ValidationError("Ledger amount cannot be negative")
        existing=await self.session.scalar(select(RoyaltyLedgerEntry).where(RoyaltyLedgerEntry.idempotency_key==idempotency_key))
        if existing is not None: return existing
        account=await self.ensure_account(artist_id,currency)
        if account.currency!=currency.upper(): raise ConflictError("Currency mismatch for royalty account")
        entry=RoyaltyLedgerEntry(account_id=account.id,amount_cents=amount_cents,currency=currency.upper(),direction=direction,source_type=source_type,source_id=source_id,idempotency_key=idempotency_key,entry_metadata=metadata or {})
        self.session.add(entry)
        try:
            async with self.session.begin_nested():
                await self.session.flush()
        except Exception:
            existing=await self.session.scalar(select(RoyaltyLedgerEntry).where(RoyaltyLedgerEntry.idempotency_key==idempotency_key))
            if existing is None:
                raise
            return existing
        return entry

    async def create_settlement(self, *, artist_id:UUID, period_start:datetime, period_end:datetime, gross_cents:int, net_cents:int, idempotency_key:str, currency:str="CUP")->RoyaltySettlement:
        if period_end<=period_start or gross_cents<0 or net_cents<0 or net_cents>gross_cents: raise ValidationError("Invalid settlement period or amounts")
        existing=await self.session.scalar(select(RoyaltySettlement).where(RoyaltySettlement.idempotency_key==idempotency_key))
        if existing is not None: return existing
        account=await self.ensure_account(artist_id,currency)
        settlement=RoyaltySettlement(account_id=account.id,period_start=period_start,period_end=period_end,gross_cents=gross_cents,net_cents=net_cents,currency=currency.upper(),status="pending",idempotency_key=idempotency_key)
        self.session.add(settlement)
        try:
            async with self.session.begin_nested():
                await self.session.flush()
        except Exception:
            existing=await self.session.scalar(select(RoyaltySettlement).where(RoyaltySettlement.idempotency_key==idempotency_key))
            if existing is None:
                raise
            return existing
        return settlement


    async def _settlement_authorized(self, user_id: UUID, settlement: RoyaltySettlement) -> None:
        account = await self.session.get(RoyaltyAccount, settlement.account_id)
        if account is None:
            raise NotFoundError("Royalty account not found")
        if not await RbacService(self.session).user_has_permission(user_id, "royalties.write"):
            await self._authorized(user_id, account.artist_id)

    async def approve_settlement(self, *, user_id: UUID, artist_id: UUID, settlement_id: UUID) -> RoyaltySettlement:
        settlement = await self.session.scalar(
            select(RoyaltySettlement).where(RoyaltySettlement.id == settlement_id).with_for_update()
        )
        if settlement is None:
            raise NotFoundError("Settlement not found")
        account = await self.session.get(RoyaltyAccount, settlement.account_id)
        if account is None or account.artist_id != artist_id:
            raise NotFoundError("Settlement not found")
        await self._settlement_authorized(user_id, settlement)
        if settlement.status == "approved":
            return settlement
        if settlement.status != "pending":
            raise ConflictError(f"Settlement cannot be approved from status {settlement.status}")
        settlement.status = "approved"
        await self.session.flush()
        return settlement

    async def reject_settlement(self, *, user_id: UUID, artist_id: UUID, settlement_id: UUID) -> RoyaltySettlement:
        settlement = await self.session.scalar(
            select(RoyaltySettlement).where(RoyaltySettlement.id == settlement_id).with_for_update()
        )
        if settlement is None:
            raise NotFoundError("Settlement not found")
        account = await self.session.get(RoyaltyAccount, settlement.account_id)
        if account is None or account.artist_id != artist_id:
            raise NotFoundError("Settlement not found")
        await self._settlement_authorized(user_id, settlement)
        if settlement.status == "rejected":
            return settlement
        if settlement.status in ("paid",):
            raise ConflictError("Paid settlement cannot be rejected")
        settlement.status = "rejected"
        await self.session.flush()
        return settlement

    async def mark_settlement_paid(self, *, user_id: UUID, artist_id: UUID, settlement_id: UUID) -> RoyaltySettlement:
        settlement = await self.session.scalar(
            select(RoyaltySettlement).where(RoyaltySettlement.id == settlement_id).with_for_update()
        )
        if settlement is None:
            raise NotFoundError("Settlement not found")
        account = await self.session.get(RoyaltyAccount, settlement.account_id)
        if account is None or account.artist_id != artist_id:
            raise NotFoundError("Settlement not found")
        if not await RbacService(self.session).user_has_permission(user_id, "royalties.write"):
            raise NotFoundError("Settlement not found")
        if settlement.status == "paid":
            return settlement
        if settlement.status != "approved":
            raise ConflictError("Only approved settlements can be marked paid")
        if settlement.net_cents > 0:
            await self.append_ledger(
                user_id=user_id,
                artist_id=(await self.session.get(RoyaltyAccount, settlement.account_id)).artist_id,
                amount_cents=settlement.net_cents,
                source_type="royalty_settlement",
                source_id=settlement.id,
                idempotency_key=f"settlement:{settlement.id}:payout",
                direction="debit",
                currency=settlement.currency,
                metadata={"settlement_id": str(settlement.id)},
            )
        settlement.status = "paid"
        await self.session.flush()
        return settlement
