-- ==============================================================================
-- StockPulse AI - Comprehensive PostgreSQL Schema Architecture Plan
-- Database: PostgreSQL 16
-- Description: Full schema definitions across all phases (Phase 1 to Phase 4).
-- NOTE: Migrations will be executed incrementally via Alembic in future phases.
-- ==============================================================================

-- Create necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==============================================================================
-- PHASE 1: Data Ingestion & Data Quality Tables
-- ==============================================================================

-- 1. Pipeline Runs: Audit trail for ingestion, processing, and streaming pipelines
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pipeline_name VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL, -- 'STARTED', 'SUCCESS', 'FAILED', 'PARTIAL'
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    records_processed INT DEFAULT 0,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_pipeline_name ON pipeline_runs(pipeline_name);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at ON pipeline_runs(started_at DESC);

-- 2. Daily OHLCV Data: Cleaned, historical adjusted daily bars for NIFTY 50
CREATE TABLE IF NOT EXISTS ohlcv_daily (
    ticker VARCHAR(32) NOT NULL,
    date DATE NOT NULL,
    open NUMERIC(12, 4) NOT NULL,
    high NUMERIC(12, 4) NOT NULL,
    low NUMERIC(12, 4) NOT NULL,
    close NUMERIC(12, 4) NOT NULL,
    adj_close NUMERIC(12, 4) NOT NULL,
    volume BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_ohlcv_daily PRIMARY KEY (ticker, date),
    CONSTRAINT chk_positive_prices CHECK (
        open > 0 AND high > 0 AND low > 0 AND close > 0 AND adj_close > 0
    ),
    CONSTRAINT chk_high_low CHECK (high >= low),
    CONSTRAINT chk_positive_volume CHECK (volume >= 0)
);

CREATE INDEX IF NOT EXISTS idx_ohlcv_daily_ticker ON ohlcv_daily(ticker);
CREATE INDEX IF NOT EXISTS idx_ohlcv_daily_date ON ohlcv_daily(date DESC);

-- 3. Data Quality Log: Verification logs (null checks, outliers, price sanity, continuity)
CREATE TABLE IF NOT EXISTS data_quality_log (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID REFERENCES pipeline_runs(run_id) ON DELETE SET NULL,
    ticker VARCHAR(32) NOT NULL,
    check_name VARCHAR(64) NOT NULL, -- e.g., 'null_check', 'spread_sanity', 'volume_positive'
    status VARCHAR(16) NOT NULL,     -- 'PASS', 'FAIL', 'WARN'
    details JSONB DEFAULT '{}'::jsonb,
    check_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_data_quality_log_ticker ON data_quality_log(ticker);
CREATE INDEX IF NOT EXISTS idx_data_quality_log_check_timestamp ON data_quality_log(check_timestamp DESC);


-- ==============================================================================
-- PHASE 2: Feature Store & Machine Learning Experimentation Tables
-- ==============================================================================

-- 4. Daily Feature Store: Computed technical indicators and binary target direction
CREATE TABLE IF NOT EXISTS features_daily (
    ticker VARCHAR(32) NOT NULL,
    date DATE NOT NULL,
    sma_5 NUMERIC(12, 4),
    sma_20 NUMERIC(12, 4),
    sma_50 NUMERIC(12, 4),
    ema_12 NUMERIC(12, 4),
    ema_26 NUMERIC(12, 4),
    rsi_14 NUMERIC(8, 4),
    macd NUMERIC(12, 4),
    macd_signal NUMERIC(12, 4),
    macd_hist NUMERIC(12, 4),
    bb_upper NUMERIC(12, 4),
    bb_middle NUMERIC(12, 4),
    bb_lower NUMERIC(12, 4),
    atr_14 NUMERIC(12, 4),
    obv BIGINT,
    return_1d NUMERIC(8, 6),
    return_2d NUMERIC(8, 6),
    return_3d NUMERIC(8, 6),
    return_5d NUMERIC(8, 6),
    -- Binary target: 1 if close[t+1] > close[t], else 0 (NULL for the most recent day)
    target_direction SMALLINT CHECK (target_direction IN (0, 1) OR target_direction IS NULL),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_features_daily PRIMARY KEY (ticker, date),
    CONSTRAINT fk_features_ohlcv FOREIGN KEY (ticker, date)
        REFERENCES ohlcv_daily(ticker, date) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_features_daily_ticker ON features_daily(ticker);
CREATE INDEX IF NOT EXISTS idx_features_daily_date ON features_daily(date DESC);

-- 5. Model Runs: Registry of trained model configurations and walk-forward CV setups
CREATE TABLE IF NOT EXISTS model_runs (
    model_run_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_name VARCHAR(64) NOT NULL, -- 'logistic_regression', 'random_forest', 'xgboost', 'lightgbm'
    model_version VARCHAR(32) NOT NULL DEFAULT 'v1',
    hyperparameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    feature_set_version VARCHAR(32) NOT NULL,
    train_start_date DATE NOT NULL,
    train_end_date DATE NOT NULL,
    embargo_days INT NOT NULL DEFAULT 5,
    cv_folds INT NOT NULL DEFAULT 5,
    mlflow_run_id VARCHAR(64),
    status VARCHAR(32) NOT NULL DEFAULT 'TRAINED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_model_runs_model_name ON model_runs(model_name);
CREATE INDEX IF NOT EXISTS idx_model_runs_created_at ON model_runs(created_at DESC);

-- 6. Model Metrics: Evaluation scores per CV fold and out-of-sample test splits
CREATE TABLE IF NOT EXISTS model_metrics (
    id BIGSERIAL PRIMARY KEY,
    model_run_id UUID NOT NULL REFERENCES model_runs(model_run_id) ON DELETE CASCADE,
    fold_index INT NOT NULL DEFAULT 0, -- 0 for overall / out-of-sample summary
    split_type VARCHAR(16) NOT NULL,   -- 'TRAIN', 'VAL', 'TEST'
    metric_name VARCHAR(32) NOT NULL,  -- 'accuracy', 'roc_auc', 'pr_auc', 'f1', 'precision', 'recall', 'brier_score'
    metric_value NUMERIC(10, 6) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_model_metrics_run_metric ON model_metrics(model_run_id, metric_name);


-- ==============================================================================
-- PHASE 3: Streaming & Pipeline Metrics Tables
-- ==============================================================================

-- 7. Pipeline Performance Metrics: Ingestion latency, throughput, consumer lag
CREATE TABLE IF NOT EXISTS pipeline_metrics (
    id BIGSERIAL PRIMARY KEY,
    component VARCHAR(32) NOT NULL,    -- 'ingestion', 'redpanda_consumer', 'feature_pipeline'
    metric_name VARCHAR(64) NOT NULL,  -- 'records_ingested_total', 'consumer_lag', 'pipeline_latency_ms'
    metric_type VARCHAR(16) NOT NULL,  -- 'COUNTER', 'GAUGE', 'HISTOGRAM'
    metric_value DOUBLE PRECISION NOT NULL,
    tags JSONB DEFAULT '{}'::jsonb,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_metrics_component ON pipeline_metrics(component);
CREATE INDEX IF NOT EXISTS idx_pipeline_metrics_recorded_at ON pipeline_metrics(recorded_at DESC);


-- ==============================================================================
-- PHASE 4: Predictions & Inference Serving Tables
-- ==============================================================================

-- 8. Daily Predictions: Next-day direction forecasts with probabilities and verification
CREATE TABLE IF NOT EXISTS predictions (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(32) NOT NULL,
    target_date DATE NOT NULL,         -- Date the prediction targets (t+1)
    model_run_id UUID NOT NULL REFERENCES model_runs(model_run_id) ON DELETE CASCADE,
    predicted_direction SMALLINT NOT NULL CHECK (predicted_direction IN (0, 1)),
    probability_up NUMERIC(5, 4) NOT NULL CHECK (probability_up >= 0.0 AND probability_up <= 1.0),
    actual_direction SMALLINT CHECK (actual_direction IN (0, 1) OR actual_direction IS NULL),
    is_correct BOOLEAN GENERATED ALWAYS AS (
        CASE
            WHEN actual_direction IS NULL THEN NULL
            WHEN predicted_direction = actual_direction THEN TRUE
            ELSE FALSE
        END
    ) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ticker_target_model UNIQUE (ticker, target_date, model_run_id)
);

CREATE INDEX IF NOT EXISTS idx_predictions_ticker_date ON predictions(ticker, target_date DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_model_run ON predictions(model_run_id);
