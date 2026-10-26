# StockPulse AI - Model Performance & Results

> **Disclaimer**: This project is developed strictly for educational and portfolio demonstration purposes. It does not constitute financial advice.

---

## 1. Overview & Evaluation Philosophy

Predicting daily stock market price direction ($Close_{t+1} > Close_t$) is notoriously difficult due to the Weak-Form Efficient Market Hypothesis, high noise-to-signal ratios, and non-stationarity.

In this project, **honesty and methodological rigor are prioritized over inflated metrics**:
- **Naive Baseline Parity**: In liquid equities, daily directional accuracy often hovers between **50.5% and 53.5%**. Any claim of 70–80% daily directional accuracy almost certainly indicates lookahead bias, target leakage, or data snooping.
- **Strict Out-of-Sample Walk-Forward Validation**: Models are tested strictly on out-of-sample data following chronological training folds with an embargo period.
- **Multiple Metrics**: We evaluate probability calibration (Brier Score) and ranking ability (ROC-AUC, PR-AUC), not just raw accuracy.

---

## 2. Experimental Setup

- **Universe**: NIFTY 50 (or 10-ticker Dev subset)
- **Time Horizon**: 10 years of daily bars
- **Validation Scheme**: Walk-Forward Cross Validation
  - Minimum Training Window: 3 years
  - Step Size: 3 months
  - Embargo Window: 5 trading days
- **Target Variable**: $y_t = \mathbb{I}(Close_{t+1} > Close_t)$ (Binary 0 or 1)

---

## 3. Results Leaderboard (Template)

| Model Name | Out-of-Sample Accuracy | ROC-AUC | PR-AUC | F1-Score | Brier Score | vs Baseline $\Delta$ Acc |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Random Guess** | 50.00% | 0.5000 | 0.5000 | 0.5000 | 0.2500 | 0.00% |
| **Majority Class Baseline** | — | 0.5000 | — | — | — | Baseline |
| **Prev-Day Direction Baseline** | — | — | — | — | — | — |
| **Logistic Regression (L2)** | — | — | — | — | — | — |
| **Random Forest** | — | — | — | — | — | — |
| **XGBoost** | — | — | — | — | — | — |
| **LightGBM** | — | — | — | — | — | — |

*(Leaderboard to be populated upon completion of Phase 2 model training)*

---

## 4. Key Questions & Honest Analysis

### 4.1 Did Any Model Consistently Beat the Naive Baseline?
- *To be recorded after experiments.*
- Analysis of whether technical indicators provide a statistically significant edge over predicting the majority class or previous day's return sign.

### 4.2 Probability Calibration & Brier Score
- Financial predictions require well-calibrated probabilities rather than binary guesses.
- If a model predicts $P(\text{UP}) = 0.52$, does that correspond to an actual 52% empirical frequency?

### 4.3 Feature Importance Analysis
- Top 5 predictive features across walk-forward folds (e.g., Short-term RSI, MACD histogram, 1-day lagged return).
- Stability of feature importance over time (market regime shifts).

---

## 5. Leakage & Integrity Checklist

Before certifying any result, verify that none of the following common pitfalls occurred:
- [ ] **No Lookahead in Moving Averages**: Rolling indicators at index $t$ only include indices $\le t$.
- [ ] **Correct Target Alignment**: Target $Close_{t+1} / Close_t$ is aligned to features at $t$.
- [ ] **Train/Test Scaling Isolation**: Feature scalers (e.g., `RobustScaler`) fit strictly on the training fold, never on the full dataset.
- [ ] **Embargo Enforced**: 5-day trading embargo between training end and validation start to mitigate autocorrelation effects.
- [ ] **No Survivorship Assumption Overstatement**: Results clearly acknowledged under current constituent survivorship bias (see [survivorship_bias.md](file:///Users/pankajkumar/stockpulse-ai/docs/decisions/survivorship_bias.md)).
