"""Historical market data ingestion pipeline for StockPulse AI.

Downloads 10 years of daily OHLCV bars for the configured ticker universe,
executes data quality validation gates, saves raw data as Parquet files in data/raw,
and idempotently upserts verified records into PostgreSQL ohlcv_daily.
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.common.config import get_active_tickers, get_settings, get_tickers_config
from services.common.db import get_db_session
from services.common.logging import configure_logging, get_logger
from services.ingestion.adapters.base import MarketDataAdapter
from services.ingestion.adapters.yfinance_adapter import YFinanceAdapter
from services.ingestion.data_quality import (
    TickerQualityReport,
    persist_quality_logs,
    run_full_data_quality_suite,
)

logger = get_logger(__name__)


def record_pipeline_run_start(session: Session, pipeline_name: str) -> UUID:
    """Record pipeline run start in the database."""
    run_id = uuid4()
    query = text(
        """
        INSERT INTO pipeline_runs (run_id, pipeline_name, status, started_at, records_processed, metadata)
        VALUES (:run_id, :pipeline_name, 'STARTED', NOW(), 0, CAST(:metadata AS jsonb))
        """
    )
    import json

    session.execute(
        query,
        {
            "run_id": run_id,
            "pipeline_name": pipeline_name,
            "metadata": json.dumps({"environment": get_settings().environment}),
        },
    )
    return run_id


def record_pipeline_run_finish(
    session: Session,
    run_id: UUID,
    status: str,
    records_processed: int,
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Update pipeline run status upon completion or failure."""
    import json

    query = text(
        """
        UPDATE pipeline_runs
        SET status = :status,
            completed_at = NOW(),
            records_processed = :records_processed,
            error_message = :error_message,
            metadata = metadata || CAST(:metadata AS jsonb)
        WHERE run_id = :run_id
        """
    )
    session.execute(
        query,
        {
            "run_id": run_id,
            "status": status,
            "records_processed": records_processed,
            "error_message": error_message,
            "metadata": json.dumps(metadata or {}),
        },
    )


def save_raw_parquet(df: pd.DataFrame, ticker: str, output_dir: Path) -> Path:
    """Save normalized historical bars into data/raw as Parquet."""
    output_dir.mkdir(parents=True, exist_ok=True)
    clean_symbol = ticker.replace("^", "").replace(".", "_")
    target_path = output_dir / f"{clean_symbol}.parquet"
    df.to_parquet(target_path, index=False)
    return target_path


def upsert_ohlcv_records(session: Session, records: list[dict[str, Any]]) -> int:
    """Idempotently upsert OHLCV daily records into PostgreSQL."""
    if not records:
        return 0

    upsert_sql = text(
        """
        INSERT INTO ohlcv_daily (ticker, date, open, high, low, close, adj_close, volume, updated_at)
        VALUES (:ticker, :date, :open, :high, :low, :close, :adj_close, :volume, NOW())
        ON CONFLICT (ticker, date) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            adj_close = EXCLUDED.adj_close,
            volume = EXCLUDED.volume,
            updated_at = NOW()
        """
    )

    session.execute(upsert_sql, records)
    return len(records)


def ingest_ticker_history(
    ticker: str,
    adapter: MarketDataAdapter,
    start_date: date,
    end_date: date,
    min_history_years: int,
    raw_data_dir: Path,
    session: Session,
    run_id: UUID,
) -> tuple[int, TickerQualityReport, bool]:
    """Ingest, validate, cache to parquet, and persist historical data for a single ticker.

    Returns:
        tuple of (records_count, quality_report, has_sufficient_history)
    """
    logger.info("ingesting_ticker", ticker=ticker, min_history_years=min_history_years)

    # 1. Fetch bars from adapter
    df = adapter.fetch_daily_bars(ticker=ticker, start_date=start_date, end_date=end_date)
    if df.empty:
        raise ValueError(f"No bars returned for {ticker}")

    # 2. Check history span against min_history_years
    min_date = df["date"].min()
    max_date = df["date"].max()
    actual_span_years = (max_date - min_date).days / 365.25
    has_sufficient_history = actual_span_years >= (min_history_years - 0.5)

    if not has_sufficient_history:
        logger.warning(
            "short_history_detected",
            ticker=ticker,
            span_years=round(actual_span_years, 2),
            required_years=min_history_years,
        )

    # 3. Execute full data quality validation suite
    validated_records, quality_report = run_full_data_quality_suite(df, ticker)

    # 4. Save raw parquet cache
    save_raw_parquet(df, ticker, raw_data_dir)

    # 5. Persist quality check findings to data_quality_log
    persist_quality_logs(session, run_id, quality_report)

    # 6. Idempotently write verified records into PostgreSQL
    written_count = upsert_ohlcv_records(session, validated_records)

    logger.info(
        "ticker_ingestion_complete",
        ticker=ticker,
        bars_written=written_count,
        span_years=round(actual_span_years, 2),
        is_valid=quality_report.is_valid,
    )

    return written_count, quality_report, has_sufficient_history


def run_historical_loader(
    tickers: list[str] | None = None,
    min_history_years: int | None = None,
    adapter: MarketDataAdapter | None = None,
) -> dict[str, Any]:
    """Run end-to-end historical ingestion pipeline for active ticker universe."""
    settings = get_settings()
    ticker_cfg = get_tickers_config()

    active_tickers = tickers or get_active_tickers()
    min_years = min_history_years or ticker_cfg.get("min_history_years", 10)
    data_adapter = adapter or YFinanceAdapter()

    end_date = date.today()
    start_date = end_date - timedelta(days=int(min_years * 365.25) + 30)
    raw_dir = settings.base_dir / settings.data_dir / "raw"

    logger.info(
        "starting_historical_loader",
        universe_size=len(active_tickers),
        min_history_years=min_years,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )

    total_records = 0
    reports: dict[str, TickerQualityReport] = {}
    failed_tickers: list[str] = []
    short_history_tickers: list[str] = []

    with get_db_session() as session:
        run_id = record_pipeline_run_start(session, "historical_ohlcv_loader")

        try:
            for symbol in active_tickers:
                try:
                    count, report, has_history = ingest_ticker_history(
                        ticker=symbol,
                        adapter=data_adapter,
                        start_date=start_date,
                        end_date=end_date,
                        min_history_years=min_years,
                        raw_data_dir=raw_dir,
                        session=session,
                        run_id=run_id,
                    )
                    total_records += count
                    reports[symbol] = report
                    if not has_history:
                        short_history_tickers.append(symbol)
                except Exception as exc:
                    logger.error("ticker_ingestion_failed", ticker=symbol, error=str(exc))
                    failed_tickers.append(symbol)

            status = (
                "SUCCESS" if not failed_tickers else ("PARTIAL" if total_records > 0 else "FAILED")
            )
            metadata = {
                "active_universe": settings.active_universe,
                "failed_tickers": failed_tickers,
                "short_history_tickers": short_history_tickers,
                "successful_tickers_count": len(reports),
            }
            record_pipeline_run_finish(
                session=session,
                run_id=run_id,
                status=status,
                records_processed=total_records,
                error_message=f"Failed tickers: {failed_tickers}" if failed_tickers else None,
                metadata=metadata,
            )

        except Exception as exc:
            record_pipeline_run_finish(
                session=session,
                run_id=run_id,
                status="FAILED",
                records_processed=total_records,
                error_message=str(exc),
            )
            raise

    return {
        "run_id": str(run_id),
        "total_records": total_records,
        "successful_count": len(reports),
        "failed_tickers": failed_tickers,
        "short_history_tickers": short_history_tickers,
        "reports": reports,
    }


def print_quality_summary_table(reports: dict[str, TickerQualityReport]) -> None:
    """Print clean terminal summary of data quality metrics."""
    header = (
        f"{'Ticker':<14} | {'Bars':<6} | {'Duplicates':<10} | {'Missing Days':<12} | "
        f"{'Outliers':<8} | {'Zero Vol':<8} | {'Status':<6}"
    )
    separator = "-" * len(header)
    print("\n" + separator)
    print(" STOCKPULSE AI — DATA QUALITY AUDIT REPORT")
    print(separator)
    print(header)
    print(separator)

    for ticker, rep in sorted(reports.items()):
        status_str = "PASS" if rep.is_valid else "FAIL"
        print(
            f"{ticker:<14} | {rep.total_bars:<6} | {rep.duplicate_count:<10} | "
            f"{rep.missing_days_count:<12} | {rep.outlier_count:<8} | "
            f"{rep.zero_volume_count:<8} | {status_str:<6}"
        )

    print(separator + "\n")


def main() -> None:
    """CLI entry point for historical ingestion."""
    parser = argparse.ArgumentParser(description="StockPulse AI Historical Data Ingestion")
    parser.add_argument("--tickers", nargs="*", help="Specific tickers to ingest")
    parser.add_argument("--min-years", type=int, default=None, help="Minimum history years")
    parser.add_argument(
        "--report-only", action="store_true", help="Print quality report without loading"
    )
    args = parser.parse_args()

    configure_logging(log_level="INFO", json_format=False)
    results = run_historical_loader(tickers=args.tickers, min_history_years=args.min_years)
    print_quality_summary_table(results["reports"])

    if results["failed_tickers"]:
        print(f"⚠️ Warning: Failed tickers: {results['failed_tickers']}")
        print(
            f"ℹ️ Notice: Short history tickers (< required span): {results['short_history_tickers']}"
        )
    # Exit with code 0 if records were processed, but report any failed tickers
    sys.exit(0 if results["total_records"] > 0 else 1)


if __name__ == "__main__":
    main()
