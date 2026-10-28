"""Abstract base interface for market data providers."""

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd

DateType = date | str


class IngestionError(Exception):
    """Base exception for market data ingestion failures."""

    pass


class TickerNotFoundError(IngestionError):
    """Raised when a requested ticker is invalid or returns no data."""

    pass


class RateLimitError(IngestionError):
    """Raised when data provider returns HTTP 429 / rate limit."""

    pass


class MarketDataAdapter(ABC):
    """Abstract interface decoupling market data vendors from downstream processing."""

    @abstractmethod
    def fetch_daily_bars(
        self,
        ticker: str,
        start_date: DateType,
        end_date: DateType | None = None,
    ) -> pd.DataFrame:
        """Fetch historical daily OHLCV bars for a ticker.

        Args:
            ticker: Stock symbol (e.g. 'RELIANCE.NS').
            start_date: Start date for historical bars (inclusive).
            end_date: End date for historical bars (inclusive or exclusive per provider).

        Returns:
            pd.DataFrame: Normalized dataframe with standard columns:
                ['ticker', 'date', 'open', 'high', 'low', 'close', 'adj_close', 'volume']
                where 'date' is of type datetime.date.
        """
        pass
