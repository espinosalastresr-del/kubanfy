"""Anti-abuse controls: rate limits, concurrent sessions, download velocity.

Does not block on a single weak signal. Combines IP/user/device limits.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.core.exceptions import AbuseBlockedError, RateLimitError
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger(__name__)


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_seconds: int


class AntiAbuseService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def check_rate_limit(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int = 60,
    ) -> RateLimitResult:
        """Sliding window counter via Redis with configurable failure semantics."""
        try:
            redis = get_redis()
        except RuntimeError as exc:
            if not self.settings.rate_limit_fail_open:
                logger.error("rate_limit_redis_unavailable", error=str(exc))
                return RateLimitResult(allowed=False, remaining=0, reset_seconds=window_seconds)
            return RateLimitResult(allowed=True, remaining=limit, reset_seconds=window_seconds)

        redis_key = f"rl:{key}"
        try:
            pipe = redis.pipeline()
            pipe.incr(redis_key)
            pipe.ttl(redis_key)
            count, ttl = await pipe.execute()
            if ttl < 0:
                await redis.expire(redis_key, window_seconds)
                ttl = window_seconds
            remaining = max(0, limit - int(count))
            if int(count) > limit:
                logger.warning("rate_limit_exceeded", key=key, count=count, limit=limit)
                return RateLimitResult(allowed=False, remaining=0, reset_seconds=max(ttl, 1))
            return RateLimitResult(allowed=True, remaining=remaining, reset_seconds=max(ttl, 1))
        except Exception as exc:
            logger.warning("rate_limit_redis_error", error=str(exc))
            if not self.settings.rate_limit_fail_open:
                return RateLimitResult(allowed=False, remaining=0, reset_seconds=window_seconds)
            return RateLimitResult(allowed=True, remaining=limit, reset_seconds=window_seconds)

    async def enforce_rate_limit(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int = 60,
    ) -> None:
        result = await self.check_rate_limit(key, limit=limit, window_seconds=window_seconds)
        if not result.allowed:
            raise RateLimitError(
                "Too many requests",
                details={"retry_after": result.reset_seconds},
            )

    async def check_login(self, ip: str | None, email: str) -> None:
        if ip:
            await self.enforce_rate_limit(
                f"login:ip:{ip}",
                limit=self.settings.rate_limit_login,
            )
        await self.enforce_rate_limit(
            f"login:email:{email.lower()}",
            limit=self.settings.rate_limit_login,
        )

    async def check_register(self, ip: str | None) -> None:
        if ip:
            await self.enforce_rate_limit(
                f"register:ip:{ip}",
                limit=self.settings.rate_limit_register,
            )

    async def check_download(self, user_id: str, ip: str | None = None) -> None:
        await self.enforce_rate_limit(
            f"download:user:{user_id}",
            limit=self.settings.rate_limit_download,
        )
        if ip:
            await self.enforce_rate_limit(
                f"download:ip:{ip}",
                limit=self.settings.rate_limit_download * 2,
            )

    async def check_search(self, ip: str | None, user_id: str | None = None) -> None:
        if user_id:
            await self.enforce_rate_limit(
                f"search:user:{user_id}",
                limit=self.settings.rate_limit_search,
            )
        elif ip:
            await self.enforce_rate_limit(
                f"search:ip:{ip}",
                limit=self.settings.rate_limit_search,
            )

    async def check_analytics(self, ip: str | None, user_id: str | None = None) -> None:
        if user_id:
            await self.enforce_rate_limit(
                f"analytics:user:{user_id}", limit=self.settings.rate_limit_analytics
            )
        elif ip:
            await self.enforce_rate_limit(
                f"analytics:ip:{ip}", limit=self.settings.rate_limit_analytics
            )

    async def check_playback(self, token: str, ip: str | None = None) -> None:
        await self.enforce_rate_limit(
            f"playback:token:{token}", limit=self.settings.rate_limit_playback
        )
        if ip:
            await self.enforce_rate_limit(
                f"playback:ip:{ip}", limit=self.settings.rate_limit_playback * 2
            )

    async def check_share(self, ip: str | None) -> None:
        if ip:
            await self.enforce_rate_limit(
                f"share:ip:{ip}", limit=self.settings.rate_limit_share
            )

    async def flag_suspicious(
        self,
        *,
        user_id: str | None,
        reason: str,
        score: float = 1.0,
    ) -> None:
        """Accumulate suspicion score; only block when threshold exceeded."""
        if not user_id:
            return
        try:
            redis = get_redis()
            key = f"abuse:score:{user_id}"
            new_score = await redis.incrbyfloat(key, score)
            await redis.expire(key, 3600)
            if new_score >= 20.0:
                logger.warning("abuse_threshold", user_id=user_id, score=new_score, reason=reason)
                raise AbuseBlockedError(
                    "Account temporarily restricted due to unusual activity",
                    details={"reason": reason},
                )
        except AbuseBlockedError:
            raise
        except Exception as exc:
            logger.debug("abuse_score_unavailable", error=str(exc))
