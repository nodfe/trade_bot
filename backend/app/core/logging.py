"""Loguru configuration.

Two sinks share the same logger:

- **Dev (default)**: human-readable colored format including ``request_id``
  if the current log call ran inside ``RequestIdMiddleware``'s
  ``logger.contextualize`` block.
- **Prod / structured**: when ``LOG_JSON=1`` is set, emit JSON with
  ``serialize=True`` so logs can be ingested by structured log pipelines
  without further parsing.

This is the project's ``structured logs`` baseline referenced in
``docs/engineering-harness.md``.
"""

import os
import sys

from loguru import logger

logger.remove()

_log_level = os.getenv("LOG_LEVEL", "DEBUG").upper()

if os.getenv("LOG_JSON", "0") in {"1", "true", "True"}:
    logger.add(sys.stderr, level=_log_level, serialize=True, backtrace=True, diagnose=False)
else:
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "req=<yellow>{extra[request_id]}</yellow> - "
            "<level>{message}</level>"
        ),
        level=_log_level,
        backtrace=True,
        diagnose=False,
    )

# Default value for ``request_id`` so log calls outside an HTTP request
# (Celery tasks, startup) don't break the format string.
logger.configure(extra={"request_id": "-"})
