"""Yahoo Finance adapter implementing MarketDataAdapter."""

import time
from datetime import date

import pandas as pd
import yfinance as yf

from services.common.logging import get_logger
from services.ingestion.adapters.base import (
    DateType,
    IngestionError,
    MarketDataAdapter,
    TickerNotFoundError,
)

logger = get_logger(__name__)


class YFinanceAdapter(MarketDataAdapter):
    """Yahoo Finance API adapter with auto_adjust, exponential backoff, and rate pacing."""

    def __init__(
        self,
        max_retries: int = 3,
        base_backoff_seconds: float = 1.0,
        per_ticker_delay_seconds: float = 0.5,
    ) -> None:
        """Initialize adapter with retry and throttling settings.

        Args:
            max_retries: Maximum number of download attempts before failing.
            base_backoff_seconds: Initial backoff duration for exponential retry.
            per_ticker_delay_seconds: Polite delay between ticker requests to avoid rate limits.
        """
        self.max_retries = max_retries
        self.base_backoff_seconds = base_backoff_seconds
        self.per_ticker_delay_seconds = per_ticker_delay_seconds

    def fetch_daily_bars(
        self,
        ticker: str,
        start_date: DateType,
        end_date: DateType | None = None,
    ) -> pd.DataFrame:
        """Download daily historical bars using auto_adjust=True for consistent adjusted OHLC.

        Args:
            ticker: Yahoo Finance symbol (e.g., 'RELIANCE.NS').
            start_date: Start date string ('YYYY-MM-DD') or date object.
            end_date: End date string ('YYYY-MM-DD') or date object.

        Returns:
            pd.DataFrame: Formatted dataframe with columns:
                ['ticker', 'date', 'open', 'high', 'low', 'close', 'adj_close', 'volume']

        Raises:
            TickerNotFoundError: If no data could be found for the ticker.
            IngestionError: If retries are exhausted.
        """
        start_str = start_date.isoformat() if isinstance(start_date, date) else str(start_date)
        end_str = (
            end_date.isoformat()
            if isinstance(end_date, date)
            else (str(end_date) if end_date else None)
        )

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "fetching_yfinance_bars",
                    ticker=ticker,
                    start=start_str,
                    end=end_str,
                    attempt=attempt,
                )

                yf_ticker = yf.Ticker(ticker)
                # auto_adjust=True adjusts Open, High, Low, Close consistently for splits/dividends
                df: pd.DataFrame = yf_ticker.history(
                    start=start_str,
                    end=end_str,
                    auto_adjust=True,
                    interval="1d",
                )

                if df.empty:
                    raise TickerNotFoundError(f"No price history returned for ticker '{ticker}'")

                # Format DataFrame to standard schema
                normalized_df = self._normalize_dataframe(df, ticker)

                # Polite per-ticker rate limit pacing
                if self.per_ticker_delay_seconds > 0:
                    time.sleep(self.per_ticker_delay_seconds)

                return normalized_df

            except TickerNotFoundError:
                raise
            except Exception as exc:
                last_error = exc
                wait_time = self.base_backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "yfinance_fetch_failed_retrying",
                    ticker=ticker,
                    attempt=attempt,
                    wait_seconds=wait_time,
                    error=str(exc),
                )
                time.sleep(wait_time)

        raise IngestionError(
            f"Failed to fetch data for {ticker} after {self.max_retries} retries: {last_error}"
        ) from last_error

    @staticmethod
    def _normalize_dataframe(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        df = df.copy()
        # Drop incomplete or non-trading rows where OHLC prices are NaN
        df = df.dropna(subset=["Open", "High", "Low", "Close"])

        # Handle timezone in DatetimeIndex (convert to IST date)
        if isinstance(df.index, pd.DatetimeIndex):
            if df.index.tz is not None:
                df.index = df.index.tz_convert("Asia/Kolkata")
            dates = [ts.date() for ts in df.index]
        else:
            dates = [pd.to_datetime(d).date() for d in df.index]

        result = pd.DataFrame(
            {
                "ticker": ticker,
                "date": dates,
                "open": df["Open"].astype(float),
                "high": df["High"].astype(float),
                "low": df["Low"].astype(float),
                "close": df["Close"].astype(float),
                # Under auto_adjust=True, Close is the split/dividend-adjusted close
                "adj_close": df["Close"].astype(float),
                "volume": df["Volume"].fillna(0).astype("int64"),
            }
        )

        # Reset index and sort chronologically
        result = result.sort_values(by="date").reset_index(drop=True)
        return result
