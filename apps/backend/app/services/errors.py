from __future__ import annotations


class ServiceError(RuntimeError):
    """Base error for service-layer failures that map to HTTP responses."""

    status_code: int = 400

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.__class__.__name__
        super().__init__(self.message)


class AssistantConfigurationError(ServiceError):
    status_code = 400


class ThreadNotFoundError(ServiceError):
    status_code = 404


class ThreadForbiddenError(ServiceError):
    status_code = 403


class RateLimitExceededError(ServiceError):
    status_code = 429


class QuotaExceededError(ServiceError):
    status_code = 402


class UsageServiceUnavailable(ServiceError):
    status_code = 503


class AuthenticationError(ServiceError):
    status_code = 401


