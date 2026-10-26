# Architecture Decision Record: Handling Survivorship Bias in NIFTY 50 Universe

- **Status**: Accepted
- **Deciders**: StockPulse AI Engineering Team
- **Date**: 2026-10-26

---

## 1. Context & Problem Statement

When backtesting quantitative models or training machine learning systems on stock indices (such as the National Stock Exchange's **NIFTY 50**) over an extended historical period (e.g., 10 years), **survivorship bias** is a prominent structural risk.

The NIFTY 50 index is semi-annually rebalanced (typically in March and September). Over a 10-year span, dozens of companies enter and exit the index based on market capitalization and liquidity criteria.

If an ML pipeline trains and evaluates models on the *current* 50 constituent companies over the past 10 years:
1. **Selection Bias**: The dataset exclusively contains companies that survived, grew, and outperformed over the period (e.g., Bajaj Finance, Titan, TCS).
2. **Omission of Failed/Demoted Firms**: Firms that suffered catastrophic drawdowns, bankruptcy, or demotion (e.g., Reliance Communications, Jet Airways, Yes Bank, DHFL) are omitted.
3. **Optimistic Out-of-Sample Performance**: Any historical directional or return model will appear systematically more optimistic than it would have been if traded in real-time.

---

## 2. Constraints & Trade-Offs

1. **Academic / Free Portfolio Scope**:
   - Access to historical point-in-time (PIT) index constituent membership files for the Indian market requires institutional commercial subscriptions (e.g., NSE historical data subscriptions, Bloomberg Terminal, or CMIE Prowess IQ), costing thousands of dollars per annum.
   - For an individual CSE student portfolio project, using publicly accessible data sources (`yfinance`) is necessary for zero-cost reproducibility by reviewers and recruiters.

2. **Data Availability**:
   - Yahoo Finance provides adjusted historical bars for currently traded tickers, but does not provide point-in-time constituent rosters.

---

## 3. Decision

We make the following deliberate engineering decisions:

1. **Explicit Documentation & Disclaimer**:
   - We explicitly declare that the backtest universe represents **current NIFTY 50 constituents** applied historically, and therefore suffers from survivorship bias.
   - We highlight this transparently in `README.md`, `docs/results.md`, and system documentation.

2. **Config-Driven Universe Isolation**:
   - Ticker universes are decoupled from application code and isolated entirely in `configs/tickers.yaml`.
   - The file explicitly flags the constituents as `"TO BE VERIFIED against official NSE NIFTY 50 index constituents"`.
   - The architecture supports switching universes without modifying ingestion, streaming, or ML code.

3. **Production Mitigation Blueprint**:
   - We document how an enterprise-grade quantitative pipeline resolves this issue:
     - **PIT Constituent Table**: Maintain an `index_membership` table storing `(index_name, ticker, start_date, end_date)`.
     - **Dynamic Filtering**: During walk-forward cross validation at time $t$, query `index_membership` to select only the tickers that were active members of the index at time $t$.
     - **Delisted Security Handling**: Ingest and store historical delisted data to include distressed exits.

---

## 4. Interview Talking Points (Why This Matters)

Being transparent about survivorship bias demonstrates high engineering maturity:
- **Novice Mistake**: Believing a 60% directional accuracy on current constituents proves the algorithm works.
- **Senior/Quantitative Insight**: Understanding that part of that predictive power is an artifact of selecting past winners who were guaranteed not to fail. Addressing and quantifying this bias is a hallmark of real-world quantitative systems engineering.
