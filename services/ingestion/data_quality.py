"""Data quality assurance and validation module for StockPulse AI.

Implements automated quality gates:
1. Duplicate (ticker, date) detection
2. Missing trading session detection against NSE official trading calendars (XNSE/XBOM)
3. Return outlier detection via z-score and absolute 20% circuit threshold
4. Zero/negative trading volume validation
5. Strict Pydantic schema validation before database writes
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID

import exchange_calendars as xcals
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from services.common.logging import get_logger

logger = get_logger(__name__)

# Register XNSE alias to XBOM in exchange_calendars
try:
    xcals.get_calendar("XNSE")
except Exception:
    try:
        xcals.register_calendar_alias("XNSE", "XBOM")
    except Exception as exc:
        logger.warning("failed_to_register_xnse_alias", error=str(exc))


class OHLCVRecord(BaseModel):
    """Pydantic validation schema for a single daily OHLCV candlestick bar."""

    ticker: str = Field(min_length=1, max_length=32)
    date: date
    open: float = Field(gt=0, description="Opening price must be strictly positive")
    high: float = Field(gt=0, description="High price must be strictly positive")
    low: float = Field(gt=0, description="Low price must be strictly positive")
    close: float = Field(gt=0, description="Close price must be strictly positive")
    adj_close: float = Field(gt=0, description="Adjusted close must be strictly positive")
    volume: int = Field(ge=0, description="Volume must be non-negative")

    @model_validator(mode="after")
    def validate_price_bounds(self) -> "OHLCVRecord":
        """Validate high is greater than or equal to low, open, and close."""
        if self.high < self.low:
            raise ValueError(
                f"High price ({self.high}) cannot be lower than Low price ({self.low})"
            )
        return self


@dataclass
class QualityCheckDetail:
    """Individual data quality issue detail."""

    check_name: str
    status: str  # 'PASS', 'WARN', 'FAIL'
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class TickerQualityReport:
    """Consolidated data quality report for a ticker."""

    ticker: str
    total_bars: int = 0
    duplicate_count: int = 0
    missing_days_count: int = 0
    missing_dates: list[str] = field(default_factory=list)
    outlier_count: int = 0
    outliers: list[dict[str, Any]] = field(default_factory=list)
    zero_volume_count: int = 0
    schema_errors_count: int = 0
    schema_errors: list[str] = field(default_factory=list)
    checks: list[QualityCheckDetail] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return True if no fatal errors (duplicates or schema violations) are present."""
        return self.duplicate_count == 0 and self.schema_errors_count == 0


def check_duplicates(df: pd.DataFrame, ticker: str) -> tuple[int, QualityCheckDetail]:
    """Verify there are no duplicate (ticker, date) pairs."""
    dupes = df.duplicated(subset=["ticker", "date"], keep=False)
    count = int(dupes.sum())

    if count > 0:
        dup_dates = [str(d) for d in df.loc[dupes, "date"].head(5)]
        detail = QualityCheckDetail(
            check_name="duplicate_check",
            status="FAIL",
            message=f"Found {count} duplicate (ticker, date) records",
            details={"duplicate_count": count, "sample_dates": dup_dates},
        )
    else:
        detail = QualityCheckDetail(
            check_name="duplicate_check",
            status="PASS",
            message="No duplicate (ticker, date) pairs detected",
        )
    return count, detail


def check_missing_trading_days(
    df: pd.DataFrame,
    ticker: str,
    calendar_name: str = "XNSE",
) -> tuple[int, list[str], QualityCheckDetail]:
    """Check for missing trading sessions using exchange_calendars."""
    if df.empty or len(df) < 2:
        return (
            0,
            [],
            QualityCheckDetail(
                check_name="missing_trading_days",
                status="PASS",
                message="Insufficient bars to evaluate missing trading sessions",
            ),
        )

    try:
        cal = xcals.get_calendar(calendar_name)
    except Exception:
        cal = xcals.get_calendar("XBOM")

    min_date = df["date"].min()
    max_date = df["date"].max()

    expected_sessions = cal.sessions_in_range(min_date, max_date)
    expected_dates = {s.date() for s in expected_sessions}
    actual_dates = set(df["date"])

    missing = sorted(expected_dates - actual_dates)
    count = len(missing)
    missing_strs = [d.isoformat() for d in missing]

    if count > 0:
        detail = QualityCheckDetail(
            check_name="missing_trading_days",
            status="WARN" if count < 20 else "FAIL",
            message=f"Found {count} missing expected trading days",
            details={"missing_count": count, "sample_missing": missing_strs[:10]},
        )
    else:
        detail = QualityCheckDetail(
            check_name="missing_trading_days",
            status="PASS",
            message="All scheduled exchange trading sessions accounted for",
        )

    return count, missing_strs, detail


def check_outliers(
    df: pd.DataFrame,
    ticker: str,
    z_threshold: float = 3.5,
    circuit_threshold: float = 0.20,
) -> tuple[int, list[dict[str, Any]], QualityCheckDetail]:
    """Detect return outliers via z-score and absolute 20% move threshold."""
    if len(df) < 5:
        return (
            0,
            [],
            QualityCheckDetail(
                check_name="outlier_detection",
                status="PASS",
                message="Insufficient data for statistical outlier checks",
            ),
        )

    df_sorted = df.sort_values(by="date").copy()
    returns = df_sorted["close"].pct_change()

    mean_ret = returns.mean()
    std_ret = returns.std(ddof=1)

    outliers: list[dict[str, Any]] = []

    if std_ret and not np.isnan(std_ret) and std_ret > 0:
        z_scores = (returns - mean_ret) / std_ret

        for idx, (ret, z) in enumerate(zip(returns, z_scores, strict=False)):
            if pd.isna(ret):
                continue
            abs_ret = abs(ret)
            abs_z = abs(z)

            is_z_outlier = bool(abs_z >= z_threshold)
            is_circuit_outlier = bool(abs_ret >= circuit_threshold)

            if is_z_outlier or is_circuit_outlier:
                row_date = df_sorted.iloc[idx]["date"]
                outliers.append(
                    {
                        "date": str(row_date),
                        "daily_return": round(float(ret), 4),
                        "z_score": round(float(z), 2) if not np.isnan(z) else 0.0,
                        "flag": "circuit_breaker (>20%)" if is_circuit_outlier else "z_score",
                    }
                )

    count = len(outliers)
    if count > 0:
        detail = QualityCheckDetail(
            check_name="outlier_detection",
            status="WARN",
            message=f"Detected {count} daily return anomaly flags",
            details={"outlier_count": count, "sample_outliers": outliers[:5]},
        )
    else:
        detail = QualityCheckDetail(
            check_name="outlier_detection",
            status="PASS",
            message="No daily return anomalies or circuit violations found",
        )

    return count, outliers, detail


def check_zero_volume(df: pd.DataFrame, ticker: str) -> tuple[int, QualityCheckDetail]:
    """Identify trading sessions with zero or negative volume."""
    zero_vol = df["volume"] <= 0
    count = int(zero_vol.sum())

    if count > 0:
        sample_dates = [str(d) for d in df.loc[zero_vol, "date"].head(5)]
        detail = QualityCheckDetail(
            check_name="zero_volume_check",
            status="WARN",
            message=f"Found {count} days with zero volume",
            details={"zero_volume_days": count, "sample_dates": sample_dates},
        )
    else:
        detail = QualityCheckDetail(
            check_name="zero_volume_check",
            status="PASS",
            message="All trading sessions have strictly positive volume",
        )

    return count, detail


def validate_schema(
    df: pd.DataFrame,
    ticker: str,
) -> tuple[int, list[str], list[dict[str, Any]], QualityCheckDetail]:
    """Validate each row against the Pydantic OHLCVRecord model."""
    errors: list[str] = []
    validated_records: list[dict[str, Any]] = []

    for idx, row in df.iterrows():
        try:
            record_dict = {
                "ticker": str(row["ticker"]),
                "date": row["date"]
                if isinstance(row["date"], date)
                else pd.to_datetime(row["date"]).date(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "adj_close": float(row["adj_close"]),
                "volume": int(row["volume"]),
            }
            validated = OHLCVRecord(**record_dict)
            validated_records.append(validated.model_dump())
        except Exception as exc:
            errors.append(f"Row {idx} ({row.get('date', 'unknown')}): {exc}")

    count = len(errors)
    if count > 0:
        detail = QualityCheckDetail(
            check_name="pydantic_schema_validation",
            status="FAIL",
            message=f"Schema validation failed on {count} records",
            details={"error_count": count, "sample_errors": errors[:5]},
        )
    else:
        detail = QualityCheckDetail(
            check_name="pydantic_schema_validation",
            status="PASS",
            message="All records passed strict Pydantic validation",
        )

    return count, errors, validated_records, detail


def run_full_data_quality_suite(
    df: pd.DataFrame,
    ticker: str,
) -> tuple[list[dict[str, Any]], TickerQualityReport]:
    """Run all data quality checks and return validated records alongside the quality report."""
    report = TickerQualityReport(ticker=ticker, total_bars=len(df))

    # 1. Duplicate check
    dup_count, dup_detail = check_duplicates(df, ticker)
    report.duplicate_count = dup_count
    report.checks.append(dup_detail)

    # 2. Missing trading days check
    missing_count, missing_dates, missing_detail = check_missing_trading_days(df, ticker)
    report.missing_days_count = missing_count
    report.missing_dates = missing_dates
    report.checks.append(missing_detail)

    # 3. Outlier check
    outlier_count, outliers, outlier_detail = check_outliers(df, ticker)
    report.outlier_count = outlier_count
    report.outliers = outliers
    report.checks.append(outlier_detail)

    # 4. Zero volume check
    zero_vol_count, zero_vol_detail = check_zero_volume(df, ticker)
    report.zero_volume_count = zero_vol_count
    report.checks.append(zero_vol_detail)

    # 5. Pydantic schema validation
    schema_err_count, schema_errors, validated_records, schema_detail = validate_schema(df, ticker)
    report.schema_errors_count = schema_err_count
    report.schema_errors = schema_errors
    report.checks.append(schema_detail)

    return validated_records, report


def persist_quality_logs(
    session: Session,
    run_id: UUID | None,
    report: TickerQualityReport,
) -> None:
    """Save data quality checks to PostgreSQL data_quality_log table."""
    insert_sql = text(
        """
        INSERT INTO data_quality_log (run_id, ticker, check_name, status, details, check_timestamp)
        VALUES (:run_id, :ticker, :check_name, :status, CAST(:details AS jsonb), NOW())
        """
    )
    import json

    for check in report.checks:
        session.execute(
            insert_sql,
            {
                "run_id": run_id,
                "ticker": report.ticker,
                "check_name": check.check_name,
                "status": check.status,
                "details": json.dumps(check.details),
            },
        )
