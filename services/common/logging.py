"""Structured logging setup using structlog for StockPulse AI.

Provides standard structured logging with ISO timestamps, log levels,
and flexible console or JSON formatting suitable for local development
and containerized deployment.
"""

import logging
import sys
from typing import Any

import structlog


def configure_logging(
    log_level: str = "INFO",
    json_format: bool = False,
) -> None:
    """Configure structlog and standard library logging handlers.

    Args:
        log_level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_format: If True, outputs logs as JSON lines. If False, pretty colored console.
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Base logging processors
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_format:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())

    # Configure structlog
    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Standard library handler formatting
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)

    # Prevent noisy third-party logs
    for noisy in ("urllib3", "kafka", "yfinance", "peewee"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> Any:
    """Obtain a structured logger instance.

    Args:
        name: Name of the logger / component.

    Returns:
        A bound structlog logger.
    """
    return structlog.get_logger(name or "stockpulse")
