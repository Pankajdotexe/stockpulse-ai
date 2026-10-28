"""Unit tests for historical data loading routines and raw parquet caching."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from services.ingestion.adapters.base import MarketDataAdapter
from services.ingestion.historical_loader import (
    ingest_ticker_history,
    save_raw_parquet,
)


class DummyAdapter(MarketDataAdapter):
    """Deterministic dummy adapter for testing loader logic."""

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df

    def fetch_daily_bars(
        self,
        ticker: str,
        start_date: date | str,
        end_date: date | str | None = None,
    ) -> pd.DataFrame:
        df = self.df.copy()
        df["ticker"] = ticker
        return df


@pytest.fixture
def mock_bars_df() -> pd.DataFrame:
    """Generate mock normalized bars."""
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    return pd.DataFrame(
        {
            "ticker": ["SBIN.NS"] * 10,
            "date": [d.date() for d in dates],
            "open": [500.0 + i for i in range(10)],
            "high": [510.0 + i for i in range(10)],
            "low": [495.0 + i for i in range(10)],
            "close": [505.0 + i for i in range(10)],
            "adj_close": [505.0 + i for i in range(10)],
            "volume": [2000000 + i * 1000 for i in range(10)],
        }
    )


def test_save_raw_parquet(tmp_path: Path, mock_bars_df: pd.DataFrame) -> None:
    """Verify save_raw_parquet creates valid readable parquet files."""
    saved_path = save_raw_parquet(mock_bars_df, "SBIN.NS", tmp_path)

    assert saved_path.exists()
    assert saved_path.suffix == ".parquet"
    assert "SBIN_NS" in saved_path.name

    # Read back and verify
    read_df = pd.read_parquet(saved_path)
    assert len(read_df) == 10
    assert list(read_df.columns) == list(mock_bars_df.columns)


def test_ingest_ticker_history_pipeline(tmp_path: Path, mock_bars_df: pd.DataFrame) -> None:
    """Verify ingest_ticker_history runs adapter, quality suite, and saves parquet."""
    adapter = DummyAdapter(mock_bars_df)
    mock_session = MagicMock()
    run_id = MagicMock()

    count, report, has_history = ingest_ticker_history(
        ticker="SBIN.NS",
        adapter=adapter,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 10),
        min_history_years=10,
        raw_data_dir=tmp_path,
        session=mock_session,
        run_id=run_id,
    )

    assert count == 10
    assert report.is_valid is True
    # 10 days is shorter than 10 years, so has_history should be False
    assert has_history is False
    assert (tmp_path / "SBIN_NS.parquet").exists()
    assert mock_session.execute.call_count >= 1
