"""Payment service — manual bank transfer and cash verification.

Flow: PaymentOrder → (admin verify) → EntitlementService.grant
Payment providers never mutate subscriptions/entitlements directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.entitlement import EntitlementScope, EntitlementSource, Plan, PlanPrice
from app.models.payment import PaymentMethod, PaymentOrder, PaymentStatus
from app.services.entitlement import EntitlementService

logger = get_logger(__name__)


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    async def create_order(self, order: PaymentOrder) -> PaymentOrder:
        ...


class ManualTransferProvider(PaymentProvider):
    name = "manual_transfer"

    async def create_order(self, order: PaymentOrder) -> PaymentOrder:
        order.method = PaymentMethod.BANK_TRANSFER
        order.status = PaymentStatus.PENDING
        return order


class CashProvider(PaymentProvider):
    name = "cash"

    async def create_order(self, order: PaymentOrder) -> PaymentOrder:
        order.method = PaymentMethod.CASH
        order.status = PaymentStatus.PENDING
        return order


class PaymentService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self._providers: dict[str, PaymentProvider] = {
            "bank_transfer": ManualTransferProvider(),
            "cash": CashProvider(),
        }

    async def create_order(
        self,
        user_id: UUID,
        *,
        amount_cents: int,
        currency: str = "CUP",
        method: str = "bank_transfer",
        plan_code: str | None = "premium",
        reference: str | None = None,
        idempotency_key: str | None = None,
    ) -> PaymentOrder:
        if not self.settings.feature_monetization:
            # Still allow creating orders in pending state for ops testing,
            # but document that monetization flag gates fulfillment.
            pass

        if amount_cents <= 0:
            raise ValidationError("amount_cents must be positive")

        if self.settings.feature_monetization:
            if not plan_code:
                raise ValidationError("plan_code is required when monetization is enabled")
            plan = await self.session.scalar(
                select(Plan).where(
                    Plan.code == plan_code,
                    Plan.is_active.is_(True),
                )
            )
            if plan is None:
                raise ValidationError("Unknown or inactive plan")
            price = await self.session.scalar(
                select(PlanPrice).where(
                    PlanPrice.plan_id == plan.id,
                    PlanPrice.currency == currency.upper(),
                    PlanPrice.amount_cents == amount_cents,
                    PlanPrice.is_active.is_(True),
                )
            )
            if price is None:
                raise ValidationError("Payment amount does not match an active plan price")

        if idempotency_key:
            existing = await self.session.scalar(
                select(PaymentOrder).where(PaymentOrder.idempotency_key == idempotency_key)
            )
            if existing:
                return existing

        provider = self._providers.get(method)
        if provider is None:
            raise ValidationError(f"Unsupported payment method: {method}")

        order = PaymentOrder(
            user_id=user_id,
            amount_cents=amount_cents,
            currency=currency.upper(),
            plan_code=plan_code,
            reference=reference,
            idempotency_key=idempotency_key,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            status=PaymentStatus.PENDING,
        )
        order = await provider.create_order(order)
        self.session.add(order)
        await self.session.flush()
        logger.info(
            "payment_order_created",
            order_id=str(order.id),
            user_id=str(user_id),
            method=method,
            amount=amount_cents,
        )
        return order

    async def submit_for_review(
        self, order_id: UUID, user_id: UUID, *, proof_storage_key: str | None = None
    ) -> PaymentOrder:
        order = await self._get_owned(order_id, user_id)
        if order.status not in (PaymentStatus.PENDING, PaymentStatus.REJECTED):
            raise ConflictError(f"Cannot submit order in status {order.status.value}")
        if proof_storage_key:
            order.proof_storage_key = proof_storage_key
        order.status = PaymentStatus.UNDER_REVIEW
        await self.session.flush()
        return order

    async def approve(
        self,
        order_id: UUID,
        admin_user_id: UUID,
        *,
        grant_premium: bool = True,
    ) -> PaymentOrder:
        # Serialize approval for this order so concurrent admin retries cannot
        # both fulfill the same payment.
        order = await self.session.scalar(
            select(PaymentOrder)
            .where(PaymentOrder.id == order_id)
            .with_for_update()
        )
        if order is None:
            raise NotFoundError("Payment order not found")
        # Approval is idempotent: a retried admin request must not grant
        # another premium entitlement.
        if order.status == PaymentStatus.APPROVED:
            return order
        if order.status not in (PaymentStatus.UNDER_REVIEW, PaymentStatus.PENDING):
            raise ConflictError(f"Cannot approve order in status {order.status.value}")

        order.status = PaymentStatus.APPROVED
        order.verified_by = admin_user_id
        order.verified_at = datetime.now(UTC)
        await self.session.flush()

        if grant_premium and order.plan_code:
            ent_svc = EntitlementService(self.session)
            await ent_svc.grant_payment_entitlement(
                user_id=order.user_id,
                payment_order_id=order.id,
                scope_type=EntitlementScope.USER_PREMIUM,
                source=EntitlementSource.MANUAL,
                expires_at=datetime.now(UTC) + timedelta(days=30),
                metadata={"plan_code": order.plan_code},
            )

        logger.info("payment_approved", order_id=str(order_id), by=str(admin_user_id))
        return order

    async def reject(
        self, order_id: UUID, admin_user_id: UUID, *, reason: str | None = None
    ) -> PaymentOrder:
        order = await self.session.scalar(select(PaymentOrder).where(PaymentOrder.id == order_id).with_for_update())
        if order is None:
            raise NotFoundError("Payment order not found")
        order.status = PaymentStatus.REJECTED
        order.verified_by = admin_user_id
        order.verified_at = datetime.now(UTC)
        order.rejection_reason = (reason or "")[:500]
        await self.session.flush()
        logger.info("payment_rejected", order_id=str(order_id), by=str(admin_user_id))
        return order

    async def list_for_user(self, user_id: UUID) -> list[PaymentOrder]:
        result = await self.session.execute(
            select(PaymentOrder)
            .where(PaymentOrder.user_id == user_id)
            .order_by(PaymentOrder.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_pending_review(self, *, limit: int = 50) -> list[PaymentOrder]:
        result = await self.session.execute(
            select(PaymentOrder)
            .where(PaymentOrder.status == PaymentStatus.UNDER_REVIEW)
            .order_by(PaymentOrder.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _get_owned(self, order_id: UUID, user_id: UUID) -> PaymentOrder:
        order = await self.session.get(PaymentOrder, order_id)
        if order is None:
            raise NotFoundError("Payment order not found")
        if order.user_id != user_id:
            raise ForbiddenError("Not your payment order")
        return order
