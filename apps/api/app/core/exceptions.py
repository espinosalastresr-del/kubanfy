"""Domain and HTTP-consistent error types.

API responses should be consistent across the application.
"""

from __future__ import annotations

from typing import Any


class KubanFyError(Exception):
    """Base application error."""

    code: str = "INTERNAL_ERROR"
    status_code: int = 500
    message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class AuthError(KubanFyError):
    code = "AUTH_ERROR"
    status_code = 401
    message = "Authentication required"


class ForbiddenError(KubanFyError):
    code = "FORBIDDEN"
    status_code = 403
    message = "You do not have permission to perform this action"


class NotFoundError(KubanFyError):
    code = "NOT_FOUND"
    status_code = 404
    message = "Resource not found"


class ValidationError(KubanFyError):
    code = "VALIDATION_ERROR"
    status_code = 422
    message = "Validation failed"


class ProviderUnavailableError(KubanFyError):
    code = "PROVIDER_UNAVAILABLE"
    status_code = 503
    message = "External provider is currently unavailable"


class ProviderRateLimitedError(KubanFyError):
    code = "PROVIDER_RATE_LIMITED"
    status_code = 429
    message = "External provider rate limit exceeded"


class SourceExpiredError(KubanFyError):
    code = "SOURCE_EXPIRED"
    status_code = 410
    message = "Audio source has expired"


class CacheMissError(KubanFyError):
    code = "CACHE_MISS"
    status_code = 404
    message = "Content not found in cache"


class StorageError(KubanFyError):
    code = "STORAGE_ERROR"
    status_code = 500
    message = "Storage operation failed"


class TranscodeError(KubanFyError):
    code = "TRANSCODE_ERROR"
    status_code = 500
    message = "Audio transcoding failed"


class EntitlementRequiredError(KubanFyError):
    code = "ENTITLEMENT_REQUIRED"
    status_code = 402
    message = "A valid entitlement is required for this action"


class PaymentPendingError(KubanFyError):
    code = "PAYMENT_PENDING"
    status_code = 402
    message = "Payment is pending verification"


class RightsError(KubanFyError):
    code = "RIGHTS_ERROR"
    status_code = 403
    message = "Content rights do not allow this operation"


class AbuseBlockedError(KubanFyError):
    code = "ABUSE_BLOCKED"
    status_code = 429
    message = "Request blocked due to abuse detection"


class ConflictError(KubanFyError):
    code = "CONFLICT"
    status_code = 409
    message = "Resource conflict"


class RateLimitError(KubanFyError):
    code = "RATE_LIMITED"
    status_code = 429
    message = "Too many requests"
