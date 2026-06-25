# Equity Screener

Daily GitHub Pages dashboard for low-priced, $5B+ market-cap stocks ranked by six deterministic sleeves plus an EV master score.

## What it does

- Queries the local Polygon/DuckDB warehouse at `~/market-data/market_data.duckdb`.
- Scores candidates across RSI inflection/value, squeeze laggard, value laggard, momentum pullback, relative-strength pullback, and RSI breakout sleeves.
- Builds static HTML/JSON outputs in `docs/` for GitHub Pages.
- Optionally adds web/LLM commentary for the diversified top names.

## Run

```bash
/usr/bin/python3 scripts/build_dashboard.py --price-filter 75 --no-llm
```

Production cron uses:

```bash
/usr/bin/bash run_daily.sh
```

## Key docs

- Architecture and audit: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Dashboard: [`docs/index.html`](docs/index.html)
- Data payload: [`docs/dashboard_data.json`](docs/dashboard_data.json)

## Environment

- `DEEPSEEK_API_KEY` in `~/.hermes/.env` for direct DeepSeek API calls.
- `OPENROUTER_API_KEY` optional fallback if direct DeepSeek is unavailable.
- `TAVILY_API_KEY` optional for commentary search.
- `SEARXNG_URL` optional; defaults to `http://localhost:8888`.

No API keys or warehouse data are committed.

## Compliance notes

This is a research dashboard, not investment advice. LLM analysis is clearly labeled qualitative and must not be treated as a source of truth. Numeric inputs come from the local Polygon warehouse and local enrichment fields; LLM output is downstream commentary only.
