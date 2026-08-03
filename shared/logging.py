from __future__ import annotations

import json
import logging
import time
from typing import Any

ALLOWED_LOG_FIELDS = {
    "timestamp",
    "level",
    "service",
    "event",
    "request_id",
    "worker_id",
    "model_version",
    "attempt",
    "error_code",
    "duration_ms",
    "queue_depth",
    "batch_requests",
    "batch_items",
}


class StructuredLogger:
    def __init__(self, service_name: str) -> None:
        self.service_name = service_name
        self._logger = logging.getLogger(service_name)
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    def log(self, level: str, event: str, **kwargs: Any) -> None:
        record: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "level": level.upper(),
            "service": self.service_name,
            "event": event,
        }
        for k, v in kwargs.items():
            if k in ALLOWED_LOG_FIELDS and v is not None:
                record[k] = v

        msg = json.dumps(record)
        if level.upper() == "ERROR":
            self._logger.error(msg)
        elif level.upper() == "WARNING":
            self._logger.warning(msg)
        else:
            self._logger.info(msg)


def get_logger(service_name: str) -> StructuredLogger:
    return StructuredLogger(service_name)
