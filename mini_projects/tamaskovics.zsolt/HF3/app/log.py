from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict


class StructuredLogger(logging.Logger):
    """Logger that accepts arbitrary key=value fields and stores them as LogRecord extras."""

    def _log(
        self,
        level,
        msg,
        args,
        exc_info=None,
        extra=None,
        stack_info=False,
        stacklevel=1,
        **fields,
    ):
        if fields:
            merged = dict(extra or {})
            merged.update(fields)
            extra = merged
        super()._log(
            level,
            msg,
            args,
            exc_info=exc_info,
            extra=extra,
            stack_info=stack_info,
            stacklevel=stacklevel,
        )


# Ensure newly created loggers use StructuredLogger.
logging.setLoggerClass(StructuredLogger)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # merge extras
        for k, v in record.__dict__.items():
            if k.startswith("_"):
                continue
            if k in {"name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module",
                     "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs",
                     "relativeCreated", "thread", "threadName", "processName", "process"}:
                continue
            payload[k] = v
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(name)
    # In case a logger already exists with the default class, upgrade it.
    if not isinstance(logger, StructuredLogger):
        logger.__class__ = StructuredLogger  # type: ignore[attr-defined]
    if logger.handlers:
        return logger

    logger.setLevel(level.upper())
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger
