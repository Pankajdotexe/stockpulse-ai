"""Pytest fixtures for StockPulse AI tests."""

import pytest

from services.common.config import Settings, get_settings


@pytest.fixture
def test_settings() -> Settings:
    """Provide a fresh instance of Settings."""
    return get_settings()
