"""Configuration management module for StockPulse AI.

Provides centralized environment settings via pydantic-settings and loaders
for YAML configurations (tickers, features, and model hyperparameters).
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings loaded from environment and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    environment: str = Field(default="development", description="App environment")
    log_level: str = Field(default="INFO", description="Log level: DEBUG, INFO, WARNING, ERROR")
    app_name: str = Field(default="stockpulse-ai", description="Application name")

    # Database (PostgreSQL 16)
    postgres_user: str = Field(default="stockpulse")
    postgres_password: str = Field(default="stockpulse_dev_password")
    postgres_db: str = Field(default="stockpulse_db")
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    database_url: str = Field(
        default="postgresql+psycopg://stockpulse:stockpulse_dev_password@localhost:5432/stockpulse_db",
        description="Full SQLAlchemy database connection URL",
    )

    # Redpanda / Kafka Streaming
    redpanda_brokers: str = Field(default="localhost:9092")
    kafka_topic_ohlcv: str = Field(default="stockpulse.ohlcv.daily")
    kafka_consumer_group: str = Field(default="stockpulse-consumer-group")

    # MLflow
    mlflow_tracking_uri: str = Field(default="sqlite:///mlruns.db")
    mlflow_artifact_root: str = Field(default="./mlartifacts")

    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    # Active Universe
    active_universe: str = Field(default="dev", description="Universe key: dev or nifty50")

    # Directory Paths
    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent)
    config_dir: Path = Field(default_factory=lambda: Path("configs"))
    data_dir: Path = Field(default_factory=lambda: Path("data"))


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton instance."""
    return Settings()


def load_yaml_config(file_path: Path | str) -> dict[str, Any]:
    """Safely load and parse a YAML configuration file.

    Args:
        file_path: Path to the YAML file.

    Returns:
        Parsed configuration dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
        yaml.YAMLError: If the YAML content is invalid.
    """
    path = Path(file_path)
    if not path.is_absolute():
        # Check relative to base directory
        settings = get_settings()
        candidate = settings.base_dir / path
        if candidate.exists():
            path = candidate

    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    with open(path, encoding="utf-8") as f:
        content = yaml.safe_load(f)
        return content or {}


def get_tickers_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """Load the ticker universe configuration.

    Args:
        config_path: Optional custom path to tickers.yaml.

    Returns:
        Dictionary containing ticker configurations.
    """
    path = config_path or Path("configs/tickers.yaml")
    return load_yaml_config(path)


def get_active_tickers(config_path: Path | str | None = None) -> list[str]:
    """Retrieve the list of tickers for the currently configured active universe.

    Args:
        config_path: Optional custom path to tickers.yaml.

    Returns:
        List of stock ticker symbols (e.g. ['RELIANCE.NS', 'TCS.NS']).
    """
    settings = get_settings()
    data = get_tickers_config(config_path)
    universe_key = settings.active_universe or data.get("active_universe", "dev")

    universe_data = data.get(universe_key, {})
    tickers: list[str] = universe_data.get("tickers", [])
    if not tickers:
        raise ValueError(f"No tickers found for active universe '{universe_key}'")
    return tickers


def get_features_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """Load the feature engineering configuration.

    Args:
        config_path: Optional custom path to features.yaml.

    Returns:
        Dictionary containing technical indicator and target settings.
    """
    path = config_path or Path("configs/features.yaml")
    return load_yaml_config(path)


def get_model_config(config_path: Path | str | None = None) -> dict[str, Any]:
    """Load model training, validation, and baseline configuration.

    Args:
        config_path: Optional custom path to model.yaml.

    Returns:
        Dictionary containing model, metric, and validation parameters.
    """
    path = config_path or Path("configs/model.yaml")
    return load_yaml_config(path)
