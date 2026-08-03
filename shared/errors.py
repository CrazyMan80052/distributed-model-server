from __future__ import annotations

from typing import Any


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message}


class InvalidRequestError(AppError):
    def __init__(self, message: str = "Invalid request.") -> None:
        super().__init__("INVALID_REQUEST", message, 400)


class UnsupportedModelError(AppError):
    def __init__(self, message: str = "Unsupported model version.") -> None:
        super().__init__("UNSUPPORTED_MODEL", message, 400)


class RequestTooLargeError(AppError):
    def __init__(self, message: str = "Request body or payload limit exceeded.") -> None:
        super().__init__("REQUEST_TOO_LARGE", message, 413)


class GatewayAtCapacityError(AppError):
    def __init__(self, message: str = "All healthy workers are saturated.") -> None:
        super().__init__("GATEWAY_AT_CAPACITY", message, 429)


class WorkerQueueFullError(AppError):
    def __init__(self, message: str = "Worker queue full.") -> None:
        super().__init__("WORKER_QUEUE_FULL", message, 429)


class NoHealthyWorkerError(AppError):
    def __init__(self, message: str = "No compatible worker is available.") -> None:
        super().__init__("NO_HEALTHY_WORKER", message, 503)


class WorkerUnavailableError(AppError):
    def __init__(self, message: str = "Worker unavailable.") -> None:
        super().__init__("WORKER_UNAVAILABLE", message, 503)


class ServiceDrainingError(AppError):
    def __init__(self, message: str = "Service is shutting down.") -> None:
        super().__init__("SERVICE_DRAINING", message, 503)


class DeadlineExceededError(AppError):
    def __init__(self, message: str = "Deadline exceeded.") -> None:
        super().__init__("DEADLINE_EXCEEDED", message, 504)


class InternalServerError(AppError):
    def __init__(self, message: str = "An unexpected internal error occurred.") -> None:
        super().__init__("INTERNAL_ERROR", message, 500)
