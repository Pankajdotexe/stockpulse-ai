"""Data quality reporting utility for StockPulse AI.

Queries PostgreSQL ohlcv_daily and data_quality_log to generate a comprehensive
per-ticker data audit report covering counts, date spans, missing sessions,
anomalies, and schema health.
"""

from typing import Any

from sqlalchemy import text

from services.common.db import get_db_session
from services.common.logging import configure_logging, get_logger

logger = get_logger(__name__)


def generate_quality_report() -> None:
    """Generate and print terminal data quality audit table."""
    with get_db_session() as session:
        # 1. Query summary statistics from ohlcv_daily
        summary_sql = text(
            """
            SELECT
                ticker,
                COUNT(*) AS total_bars,
                MIN(date) AS start_date,
                MAX(date) AS end_date,
                ROUND(CAST((MAX(date) - MIN(date)) / 365.25 AS numeric), 2) AS history_years,
                COUNT(*) FILTER (WHERE volume = 0) AS zero_volume_count
            FROM ohlcv_daily
            GROUP BY ticker
            ORDER BY ticker;
            """
        )
        summary_rows = session.execute(summary_sql).mappings().all()

        if not summary_rows:
            print(
                "\n❌ No market data found in PostgreSQL database (table 'ohlcv_daily' is empty)."
            )
            print("Run 'make ingest' first to download historical data.\n")
            return

        # 2. Query check counts from data_quality_log
        log_sql = text(
            """
            SELECT
                ticker,
                check_name,
                status,
                details
            FROM data_quality_log
            WHERE id IN (
                SELECT MAX(id)
                FROM data_quality_log
                GROUP BY ticker, check_name
            );
            """
        )
        log_rows = session.execute(log_sql).mappings().all()

        # Build quality map
        check_map: dict[str, dict[str, Any]] = {}
        for row in log_rows:
            t = row["ticker"]
            if t not in check_map:
                check_map[t] = {}
            check_map[t][row["check_name"]] = {
                "status": row["status"],
                "details": row["details"] or {},
            }

        # 3. Print report
        title = " STOCKPULSE AI — DATABASE QUALITY AUDIT REPORT "
        width = 96
        print("\n" + "=" * width)
        print(title.center(width, "="))
        print("=" * width)
        header = (
            f"{'Ticker':<14} | {'Bars':<6} | {'Start Date':<10} | {'End Date':<10} | "
            f"{'Years':<6} | {'Missing':<8} | {'Outliers':<8} | {'Zero Vol':<8} | {'Status':<6}"
        )
        print(header)
        print("-" * width)

        anomalies_to_report: list[dict[str, Any]] = []

        for row in summary_rows:
            ticker = row["ticker"]
            t_checks = check_map.get(ticker, {})

            missing_info = t_checks.get("missing_trading_days", {})
            missing_count = missing_info.get("details", {}).get("missing_count", 0)

            outlier_info = t_checks.get("outlier_detection", {})
            outlier_count = outlier_info.get("details", {}).get("outlier_count", 0)
            sample_outliers = outlier_info.get("details", {}).get("sample_outliers", [])

            zero_vol = row["zero_volume_count"]
            is_valid = (
                t_checks.get("duplicate_check", {}).get("status") != "FAIL"
                and t_checks.get("pydantic_schema_validation", {}).get("status") != "FAIL"
            )
            status_str = "PASS" if is_valid else "FAIL"

            if sample_outliers:
                anomalies_to_report.append({"ticker": ticker, "outliers": sample_outliers})

            print(
                f"{ticker:<14} | {row['total_bars']:<6} | {str(row['start_date']):<10} | "
                f"{str(row['end_date']):<10} | {row['history_years']:<6} | "
                f"{missing_count:<8} | {outlier_count:<8} | {zero_vol:<8} | {status_str:<6}"
            )

        print("-" * width)

        if anomalies_to_report:
            print("\n📌 NOTABLE PRICE ANOMALIES & CIRCUIT BREAKER EVENTS (>20% or >3.5σ):")
            for item in anomalies_to_report[:5]:
                for out in item["outliers"][:2]:
                    print(
                        f"  • [{item['ticker']}] Date: {out.get('date')}, "
                        f"Return: {out.get('daily_return') * 100:.2f}%, "
                        f"Z-Score: {out.get('z_score')}, Flag: {out.get('flag')}"
                    )

        print("\n" + "=" * width + "\n")


def main() -> None:
    """CLI entry point for data quality report."""
    configure_logging(log_level="WARNING", json_format=False)
    generate_quality_report()


if __name__ == "__main__":
    main()
