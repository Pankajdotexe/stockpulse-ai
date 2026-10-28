# StockPulse AI 📈⚡

> **End-to-End NIFTY 50 Streaming Ingestion, Feature Engineering, and Directional ML Prediction Platform**

---

> [!CAUTION]
> **DISCLAIMER: FOR EDUCATIONAL PURPOSES ONLY — NOT FINANCIAL ADVICE**
>
> This software is an academic engineering and portfolio project built to demonstrate end-to-end data engineering, streaming systems, and applied machine learning practices. It is not intended for live financial trading, investment recommendations, or wealth management. Financial markets involve substantial risk of loss. The authors assume no liability for financial decisions made using this code.

---

## 1. Project Overview

StockPulse AI ingests daily market data for National Stock Exchange of India (**NSE NIFTY 50**) equities, streams it through a Kafka-compatible **Redpanda** message broker, computes standard technical indicators, and trains/evaluates machine learning models to predict **next-day price direction (UP/DOWN)**.

### Realistic & Honest ML Formulation
- **Direction over Raw Price**: We explicitly predict binary price direction ($\text{Close}_{t+1} > \text{Close}_t$), never raw closing price. Raw price prediction is a classic academic pitfall susceptible to trivial non-stationary lag overfitting.
- **Honest Baselines**: In liquid equity markets under the Efficient Market Hypothesis, next-day directional accuracy typically hovers near naive baselines (50.5%–53.5%). Results near baseline validated through rigorous walk-forward cross validation and zero lookahead bias are considered successful, credible engineering.

---

## 2. Tech Stack

- **Language & Runtime**: Python 3.11 (`>=3.11,<3.12`), Node.js 20 (`.nvmrc`)
- **Data Ingestion**: `yfinance` abstracted behind a clean adapter interface
- **Streaming Broker**: Redpanda (`v24.2.16`, C++ Kafka-compatible) via `confluent-kafka`
- **Database & Storage**: PostgreSQL 16 Alpine, Apache Parquet
- **Machine Learning**: `scikit-learn`, `xgboost`, `lightgbm`, `pandas`
- **Experiment Tracking**: MLflow (local SQLite backend `sqlite:///mlruns.db` + local artifact directory)
- **API Layer**: FastAPI, Pydantic v2, synchronous SQLAlchemy 2.0 with `psycopg` (v3)
- **Frontend Dashboard**: React 18, Vite, TypeScript, TradingView Lightweight Charts, Recharts
- **Tooling & CI**: Docker Compose (profile-based), GitHub Actions, `pytest`, `ruff` (linter + formatter), `alembic`

*Out of Scope: Spark, LSTM, TimescaleDB, Prometheus, Grafana, Airflow, Kubernetes, Redis.*

---

## 3. Resource & Machine Constraints

Optimized to run smoothly on a **MacBook M2 (Apple Silicon ARM64, 8 GB RAM)** with Docker Desktop constrained to **4 GB**:
- Every container has an explicit `mem_limit`. Total Docker budget is capped under **2.5 GB**.
- Real container memory limits: **Postgres 512M, Redpanda 1G, Console 256M** (~1.75 GB total).
- **Redpanda Broker**: configured with `--memory 512M --smp 1 --overprovisioned`.
- **Docker Compose Profiles**:
  - `lite` (default): Starts PostgreSQL (`512M`) + Redpanda (`1G` limit, `512M` cache) = ~1.5 GB total.
  - `tools`: Redpanda Console (`256M`), off by default.
- Heavy workloads (ML training, Vite development server, FastAPI) run on the host OS, avoiding Docker virtualization overhead.

---

## 4. Repository Structure

```text
stockpulse-ai/
├── .env.example                    # Template environment variables
├── .gitignore                      # Git ignore patterns
├── .nvmrc                          # Node.js version pin (20)
├── Makefile                        # Development automation commands
├── alembic.ini                     # Database migration configuration
├── docker-compose.yml              # Container orchestration (profiles: lite, tools)
├── pyproject.toml                  # Project dependencies & tool configurations
├── .github/
│   └── workflows/ci.yml            # GitHub Actions CI workflow (lint, format, test)
├── configs/
│   ├── tickers.yaml                # NIFTY 50 and 10-ticker dev universe
│   ├── features.yaml               # Technical indicators & target definition
│   └── model.yaml                  # Walk-forward CV & model hyperparameters
├── db/
│   ├── schema.sql                  # Commented relational schema for all phases
│   └── migrations/                 # Alembic environment and versions
├── docs/
│   ├── architecture.md             # System architecture & Mermaid flowcharts
│   ├── results.md                  # Experiment leaderboard & evaluation template
│   └── decisions/
│       └── survivorship_bias.md    # ADR: Survivorship bias in NIFTY 50 backtests
├── services/
│   ├── common/                     # Config (pydantic-settings) & logging (structlog)
│   ├── ingestion/                  # Market data ingestion & provider adapters
│   ├── streaming/                  # Kafka/Redpanda producers and consumers
│   ├── ml/                         # Features, training, evaluation, inference
│   └── api/                        # FastAPI routers, schemas, and database session
├── data/                           # Local parquet caches (gitignored)
├── monitoring/                     # Diagnostic & pipeline health scripts
├── notebooks/                      # Exploratory notebooks
└── tests/                          # Pytest test suite
```

---

## 5. Quickstart

### 5.1 Prerequisites
- Python 3.11 (`python3.11 --version`)
- Docker Desktop with Compose (`docker compose version`)
- Node.js 20 (`node -v`)

### 5.2 Environment Setup
```bash
# 1. Clone repository
git clone https://github.com/Pankajdotexe/stockpulse-ai.git
cd stockpulse-ai

# 2. Copy environment template
cp .env.example .env

# 3. Create virtual environment with Python 3.11
python3.11 -m venv .venv
source .venv/bin/activate

# 4. Install development dependencies
pip install --upgrade pip
pip install -e ".[dev]"
```

### 5.3 Development Workflow Commands
```bash
# Start background infrastructure (PostgreSQL 16 + Redpanda)
make up

# Run linters and formatters
make lint
make format

# Run test suite
make test

# Run database migrations
make migrate

# Stop infrastructure
make down
```

---

## 6. Implementation Roadmap

- **Phase 0: Project Scaffolding & Foundation** (Completed)
- **Phase 1: Data** (In Progress)
- **Phase 2: Features and ML**
- **Phase 3: Streaming**
- **Phase 4: Backend**
- **Phase 5: Frontend**
- **Phase 6: Polish**
