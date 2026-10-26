"""Unit tests for configuration loaders and settings."""

from pathlib import Path

import pytest

from services.common.config import (
    Settings,
    get_active_tickers,
    get_features_config,
    get_model_config,
    get_settings,
    get_tickers_config,
    load_yaml_config,
)


def test_settings_initialization(test_settings: Settings) -> None:
    """Verify that default settings initialize correctly."""
    assert get_settings() is test_settings
    assert test_settings.app_name == "stockpulse-ai"
    assert test_settings.environment in ("development", "production", "test")
    assert test_settings.postgres_port == 5432
    assert "postgresql" in test_settings.database_url
    assert test_settings.redpanda_brokers == "localhost:9092"
    assert test_settings.active_universe == "dev"


def test_tickers_config_structure() -> None:
    """Verify tickers.yaml contains expected universe structure and constraints."""
    config = get_tickers_config()
    assert "active_universe" in config
    assert config["min_history_years"] == 10

    # Test dev universe
    dev_universe = config.get("dev", {})
    dev_tickers = dev_universe.get("tickers", [])
    assert len(dev_tickers) == 10
    assert all(ticker.endswith(".NS") for ticker in dev_tickers)
    assert "RELIANCE.NS" in dev_tickers
    assert "TCS.NS" in dev_tickers

    # Test nifty50 universe
    nifty50_universe = config.get("nifty50", {})
    nifty50_tickers = nifty50_universe.get("tickers", [])
    assert len(nifty50_tickers) == 50
    assert all(ticker.endswith(".NS") for ticker in nifty50_tickers)


def test_get_active_tickers() -> None:
    """Verify get_active_tickers returns the configured active universe."""
    tickers = get_active_tickers()
    assert isinstance(tickers, list)
    assert len(tickers) == 10
    assert "RELIANCE.NS" in tickers


def test_features_config_structure() -> None:
    """Verify features.yaml contains target definition and technical indicators."""
    features = get_features_config()
    assert "target" in features
    assert features["target"]["name"] == "target_direction"
    assert features["target"]["type"] == "binary_classification"
    assert features["target"]["horizon_days"] == 1

    indicators = features.get("indicators", {})
    assert "moving_averages" in indicators
    assert "momentum" in indicators
    assert "volatility" in indicators


def test_model_config_structure() -> None:
    """Verify model.yaml defines walk-forward parameters and baselines."""
    model_cfg = get_model_config()
    validation = model_cfg.get("validation", {})
    assert validation.get("scheme") == "walk_forward"
    assert validation.get("min_train_years") == 3
    assert validation.get("embargo_days") == 5
    assert validation.get("step_months") == 3

    baselines = model_cfg.get("baselines", [])
    baseline_names = [b["name"] for b in baselines]
    assert "majority_class" in baseline_names
    assert "previous_day_direction" in baseline_names

    models = model_cfg.get("models", {})
    assert "logistic_regression" in models
    assert "random_forest" in models
    assert "xgboost" in models
    assert "lightgbm" in models


def test_missing_config_raises_file_not_found(tmp_path: Path) -> None:
    """Verify load_yaml_config raises FileNotFoundError for nonexistent files."""
    missing_file = tmp_path / "nonexistent.yaml"
    with pytest.raises(FileNotFoundError):
        load_yaml_config(missing_file)
