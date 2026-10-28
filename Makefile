VENV ?= .venv
PYTHON ?= $(shell which python3.11 2>/dev/null || which python3)
BIN = $(VENV)/bin

ifeq ($(wildcard $(BIN)/python),)
    PY = python
    ALEMBIC_BIN = alembic
    PYTEST_BIN = pytest
    RUFF_BIN = ruff
else
    PY = $(BIN)/python
    ALEMBIC_BIN = $(BIN)/alembic
    PYTEST_BIN = $(BIN)/pytest
    RUFF_BIN = $(BIN)/ruff
endif

.PHONY: help up down test lint format migrate ingest quality-report

help:
	@echo "StockPulse AI - Development Commands"
	@echo "  make up             - Start PostgreSQL and Redpanda (lite profile)"
	@echo "  make down           - Stop docker containers"
	@echo "  make test           - Run pytest test suite"
	@echo "  make lint           - Run ruff linter check"
	@echo "  make format         - Run ruff code formatter"
	@echo "  make migrate        - Run alembic database migrations"
	@echo "  make ingest         - Download 10-year historical data & load to DB"
	@echo "  make quality-report - Print data quality audit table from DB"

up:
	docker compose --profile lite up -d

down:
	docker compose --profile lite --profile tools down

test:
	$(PYTEST_BIN)

lint:
	$(RUFF_BIN) check .

format:
	$(RUFF_BIN) format .

migrate:
	$(ALEMBIC_BIN) upgrade head

ingest:
	$(PY) -m services.ingestion.historical_loader

quality-report:
	$(PY) -m services.ingestion.quality_report
