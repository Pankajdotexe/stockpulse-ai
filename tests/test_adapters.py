"""Unit tests for market data adapters with mocked external APIs."""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from services.ingestion.adapters.base import IngestionError, TickerNotFoundError
from services.ingestion.adapters.yfinance_adapter import YFinanceAdapter


@pytest.fixture
def sample_yfinance_df() -> pd.DataFrame:
    """Provide a mock raw yfinance DataFrame."""
    dates = pd.date_range("2024-01-01", periods=3, freq="D", tz="Asia/Kolkata")
    return pd.DataFrame(
        {
            "Open": [100.0, 102.0, 101.0],
            "High": [105.0, 106.0, 104.0],
            "Low": [98.0, 100.0, 99.0],
            "Close": [103.0, 104.0, 102.0],
            "Volume": [1000000, 1500000, 1200000],
        },
        index=dates,
    )


def test_yfinance_adapter_success(sample_yfinance_df: pd.DataFrame) -> None:
    """Verify YFinanceAdapter successfully parses and normalizes raw history."""
    adapter = YFinanceAdapter(per_ticker_delay_seconds=0.0)

    with patch("yfinance.Ticker") as mock_ticker_cls:
        mock_instance = MagicMock()
        mock_instance.history.return_value = sample_yfinance_df
        mock_ticker_cls.return_value = mock_instance

        result = adapter.fetch_daily_bars(
            "RELIANCE.NS", start_date="2024-01-01", end_date="2024-01-03"
        )

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        expected_cols = ["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"]
        assert list(result.columns) == expected_cols
        assert result.iloc[0]["ticker"] == "RELIANCE.NS"
        assert result.iloc[0]["date"] == date(2024, 1, 1)
        assert result.iloc[0]["close"] == 103.0
        assert result.iloc[0]["adj_close"] == 103.0
        assert result.iloc[0]["volume"] == 1000000

        mock_instance.history.assert_called_once_with(
            start="2024-01-01",
            end="2024-01-03",
            auto_adjust=True,
            interval="1d",
        )


def test_yfinance_adapter_empty_history_raises_ticker_not_found() -> None:
    """Verify YFinanceAdapter raises TickerNotFoundError when empty dataframe is returned."""
    adapter = YFinanceAdapter(per_ticker_delay_seconds=0.0)

    with patch("yfinance.Ticker") as mock_ticker_cls:
        mock_instance = MagicMock()
        mock_instance.history.return_value = pd.DataFrame()
        mock_ticker_cls.return_value = mock_instance

        with pytest.raises(TickerNotFoundError):
            adapter.fetch_daily_bars("INVALID.NS", start_date="2024-01-01")


def test_yfinance_adapter_retries_on_network_error(sample_yfinance_df: pd.DataFrame) -> None:
    """Verify YFinanceAdapter retries transient network errors before succeeding."""
    adapter = YFinanceAdapter(
        max_retries=3, base_backoff_seconds=0.01, per_ticker_delay_seconds=0.0
    )

    with patch("yfinance.Ticker") as mock_ticker_cls:
        mock_instance = MagicMock()
        # Fail once with connection error, then succeed
        mock_instance.history.side_effect = [
            ConnectionError("Temporary network reset"),
            sample_yfinance_df,
        ]
        mock_ticker_cls.return_value = mock_instance

        result = adapter.fetch_daily_bars("TCS.NS", start_date="2024-01-01")
        assert len(result) == 3
        assert mock_instance.history.call_count == 2


def test_yfinance_adapter_exhausted_retries_raises_ingestion_error() -> None:
    """Verify IngestionError is raised when retries are exhausted."""
    adapter = YFinanceAdapter(
        max_retries=2, base_backoff_seconds=0.01, per_ticker_delay_seconds=0.0
    )

    with patch("yfinance.Ticker") as mock_ticker_cls:
        mock_instance = MagicMock()
        mock_instance.history.side_effect = TimeoutError("Connection timed out")
        mock_ticker_cls.return_value = mock_instance

        with pytest.raises(IngestionError):
            adapter.fetch_daily_bars("INFY.NS", start_date="2024-01-01")

        assert mock_instance.history.call_count == 2
