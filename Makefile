.PHONY: help up down test lint format migrate

help:
	@echo "StockPulse AI - Development Commands"
	@echo "  make up       - Start PostgreSQL and Redpanda (lite profile)"
	@echo "  make down     - Stop docker containers"
	@echo "  make test     - Run pytest test suite"
	@echo "  make lint     - Run ruff linter check"
	@echo "  make format   - Run ruff code formatter"
	@echo "  make migrate  - Run alembic database migrations"

up:
	docker compose --profile lite up -d

down:
	docker compose --profile lite --profile tools down

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

migrate:
	alembic upgrade head
