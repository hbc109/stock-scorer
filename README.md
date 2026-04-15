# Stock Scorer

A stock assessment tool that scores equities across four dimensions using Yahoo Finance data, with both a CLI and a web dashboard.

![Python](https://img.shields.io/badge/Python-3.8+-blue) ![Flask](https://img.shields.io/badge/Flask-web%20UI-green) ![yfinance](https://img.shields.io/badge/Data-Yahoo%20Finance-purple)

## Scoring Model

Each stock is evaluated on four categories, weighted into an overall score (0–100):

| Category | Weight | What it measures |
|---|---|---|
| **Growth Potential** | 30% | Revenue growth, EPS growth, forward EPS, PEG ratio, FCF growth |
| **Relative Strength** | 25% | Percentile rank vs sector peers on P/E, P/B, revenue growth, ROE, margins |
| **Market Strength** | 25% | 52-week position, volume trend, analyst recs, institutional %, short interest |
| **Narrative & Sentiment** | 20% | News headline sentiment, news volume, narrative stage classification |

### Ratings

| Score | Rating |
|---|---|
| 75–100 | STRONG BUY |
| 60–74 | BUY |
| 40–59 | HOLD |
| 25–39 | UNDERPERFORM |
| 0–24 | SELL |

### Narrative Stages

The scorer classifies each stock into a narrative lifecycle stage:

- **Under the Radar** — Low news coverage, neutral sentiment
- **Early** — Positive sentiment emerging, price below 60% of 52-week range
- **Momentum** — Broad positive coverage, price trending up
- **Peak Hype** — High volume + sentiment, price near 52-week highs
- **Declining** — Negative sentiment dominating

## Installation

```bash
pip install flask yfinance pandas
```

## Usage

### Command Line

```bash
# Single stock
python3 stock_scorer.py AAPL

# Multiple stocks (with comparison table)
python3 stock_scorer.py AAPL MSFT NVDA GOOG META

# Hong Kong stocks
python3 stock_scorer.py 0857.HK 0005.HK
```

### Web Dashboard

```bash
python3 stock_app.py
# Opens at http://localhost:5000
```

The web UI features:
- Dark theme dashboard
- Circular gauge for overall score
- Category breakdown bars
- Expandable detail panels for each scoring dimension
- Side-by-side comparison table (sortable) when analyzing multiple stocks
- ETF/fund detection with warning cards

## Architecture

```
stock_scorer.py    — Scoring engine (CLI + importable API)
  ├── calc_growth_score()      → Growth Potential (0–100)
  ├── calc_relative_score()    → Relative Strength vs Peers (0–100)
  ├── calc_market_score()      → Market Strength / Popularity (0–100)
  ├── calc_narrative_score()   → Narrative & Sentiment (0–100)
  └── assess_stock_data()      → Full assessment as dict (used by web UI)

stock_app.py       — Flask web UI (single-file, embedded HTML/CSS/JS)
  ├── GET /                    → Dashboard page
  └── POST /api/analyze        → Score up to 10 tickers, return JSON
```

## Notes

- Peer comparison fetches data for up to 5 sector peers per stock — this can be slow for large batches
- ETFs, mutual funds, indices, and other non-equity instruments are detected and skipped with a warning
- Hong Kong tickers are auto-normalized (e.g. `00857.HK` → `0857.HK`)
- All data comes from Yahoo Finance via the `yfinance` library
