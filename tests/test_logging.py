"""Unit tests for structlog logging configuration."""

import logging
from typing import Any

from services.common.logging import configure_logging, get_logger


def test_configure_logging_console() -> None:
    """Verify configure_logging initializes in console mode without error."""
    configure_logging(log_level="DEBUG", json_format=False)
    logger = get_logger("test.console")
    assert logger is not None
    # Logging a message should succeed without error
    logger.info("Test console log", key="value")


def test_configure_logging_json() -> None:
    """Verify configure_logging initializes in JSON format without error."""
    configure_logging(log_level="INFO", json_format=True)
    logger = get_logger("test.json")
    assert logger is not None
    logger.info("Test json log", metric=42, status="ok")


def test_get_logger_singleton_behavior() -> None:
    """Verify get_logger returns an object responding to standard logging methods."""
    logger: Any = get_logger("test.interface")
    assert hasattr(logger, "info")
    assert hasattr(logger, "debug")
    assert hasattr(logger, "warning")
    assert hasattr(logger, "error")


def test_root_logger_level_updated() -> None:
    """Verify that root logger level reflects the requested configuration."""
    configure_logging(log_level="WARNING", json_format=False)
    root = logging.getLogger()
    assert root.level == logging.WARNING

    # Reset back to INFO for subsequent tests
    configure_logging(log_level="INFO", json_format=False)
    assert root.level == logging.INFO
