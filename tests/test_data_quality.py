"""Unit tests for data quality checks using hand-crafted DataFrames."""

from datetime import date

import pandas as pd
import pytest

from services.ingestion.data_quality import (
    OHLCVRecord,
    check_duplicates,
    check_missing_trading_days,
    check_outliers,
    check_zero_volume,
    run_full_data_quality_suite,
    validate_schema,
)


@pytest.fixture
def clean_daily_df() -> pd.DataFrame:
    """Provide a clean hand-crafted DataFrame without quality issues."""
    return pd.DataFrame(
        {
            "ticker": ["RELIANCE.NS"] * 5,
            # Jan 1 (Mon) to Jan 5 (Fri) 2024 - 5 consecutive trading days
            "date": [
                date(2024, 1, 1),
                date(2024, 1, 2),
                date(2024, 1, 3),
                date(2024, 1, 4),
                date(2024, 1, 5),
            ],
            "open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "high": [105.0, 106.0, 107.0, 108.0, 109.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "close": [102.0, 103.0, 104.0, 105.0, 106.0],
            "adj_close": [102.0, 103.0, 104.0, 105.0, 106.0],
            "volume": [1000, 1200, 1100, 1300, 1500],
        }
    )


def test_duplicate_check_clean(clean_daily_df: pd.DataFrame) -> None:
    """Verify check_duplicates passes on unique dates."""
    count, detail = check_duplicates(clean_daily_df, "RELIANCE.NS")
    assert count == 0
    assert detail.status == "PASS"


def test_duplicate_check_detects_duplicates(clean_daily_df: pd.DataFrame) -> None:
    """Verify check_duplicates flags duplicate (ticker, date) rows."""
    dupe_row = clean_daily_df.iloc[[0]].copy()
    dirty_df = pd.concat([clean_daily_df, dupe_row], ignore_index=True)

    count, detail = check_duplicates(dirty_df, "RELIANCE.NS")
    assert count == 2  # The original and the dupe
    assert detail.status == "FAIL"
    assert "duplicate" in detail.message.lower()


def test_missing_trading_days_clean(clean_daily_df: pd.DataFrame) -> None:
    """Verify missing trading days check on complete session range."""
    # Jan 1 to Jan 5, 2024 are all trading days on NSE
    count, missing, detail = check_missing_trading_days(clean_daily_df, "RELIANCE.NS")
    assert count == 0
    assert len(missing) == 0
    assert detail.status == "PASS"


def test_missing_trading_days_detected(clean_daily_df: pd.DataFrame) -> None:
    """Verify missing trading days detected when a session is omitted."""
    # Drop Jan 3 (Wednesday)
    incomplete_df = clean_daily_df[clean_daily_df["date"] != date(2024, 1, 3)].copy()

    count, missing, detail = check_missing_trading_days(incomplete_df, "RELIANCE.NS")
    assert count == 1
    assert "2024-01-03" in missing
    assert detail.status == "WARN"


def test_outlier_check_detects_circuit_breaker() -> None:
    """Verify check_outliers flags price return moves exceeding 20%."""
    df = pd.DataFrame(
        {
            "ticker": ["TCS.NS"] * 6,
            "date": [date(2024, 1, i) for i in range(1, 7)],
            "open": [100.0] * 6,
            "high": [150.0] * 6,
            "low": [90.0] * 6,
            # Day 4 has a 25% surge (100 -> 125)
            "close": [100.0, 101.0, 100.0, 125.0, 126.0, 125.0],
            "adj_close": [100.0, 101.0, 100.0, 125.0, 126.0, 125.0],
            "volume": [1000] * 6,
        }
    )

    count, outliers, detail = check_outliers(df, "TCS.NS")
    assert count >= 1
    assert any(o.get("flag") == "circuit_breaker (>20%)" for o in outliers)
    assert detail.status == "WARN"


def test_zero_volume_check(clean_daily_df: pd.DataFrame) -> None:
    """Verify zero volume rows are detected."""
    # Clean check
    count, detail = check_zero_volume(clean_daily_df, "RELIANCE.NS")
    assert count == 0
    assert detail.status == "PASS"

    # Set one row volume to 0
    dirty_df = clean_daily_df.copy()
    dirty_df.loc[2, "volume"] = 0
    count_dirty, detail_dirty = check_zero_volume(dirty_df, "RELIANCE.NS")
    assert count_dirty == 1
    assert detail_dirty.status == "WARN"


def test_pydantic_schema_validation_success(clean_daily_df: pd.DataFrame) -> None:
    """Verify valid dataframe passes Pydantic schema validation."""
    count, errors, records, detail = validate_schema(clean_daily_df, "RELIANCE.NS")
    assert count == 0
    assert len(errors) == 0
    assert len(records) == 5
    assert detail.status == "PASS"


def test_pydantic_schema_validation_invalid_prices(clean_daily_df: pd.DataFrame) -> None:
    """Verify Pydantic rejects High < Low or negative prices."""
    dirty_df = clean_daily_df.copy()
    # High (90) < Low (99)
    dirty_df.loc[0, "high"] = 90.0
    # Negative close
    dirty_df.loc[1, "close"] = -10.0

    count, errors, records, detail = validate_schema(dirty_df, "RELIANCE.NS")
    assert count == 2
    assert detail.status == "FAIL"


def test_ohlcv_record_direct_validation() -> None:
    """Verify OHLCVRecord model validators directly."""
    # Valid record
    rec = OHLCVRecord(
        ticker="INFY.NS",
        date=date(2024, 1, 1),
        open=1500.0,
        high=1520.0,
        low=1490.0,
        close=1510.0,
        adj_close=1510.0,
        volume=500000,
    )
    assert rec.ticker == "INFY.NS"

    # High < Low should raise ValidationError
    with pytest.raises(ValueError):
        OHLCVRecord(
            ticker="INFY.NS",
            date=date(2024, 1, 1),
            open=1500.0,
            high=1480.0,  # Invalid: less than low 1490
            low=1490.0,
            close=1510.0,
            adj_close=1510.0,
            volume=500000,
        )


def test_run_full_data_quality_suite(clean_daily_df: pd.DataFrame) -> None:
    """Verify run_full_data_quality_suite executes all checks and builds complete report."""
    records, report = run_full_data_quality_suite(clean_daily_df, "RELIANCE.NS")
    assert len(records) == 5
    assert report.ticker == "RELIANCE.NS"
    assert report.total_bars == 5
    assert report.is_valid is True
    assert len(report.checks) == 5
