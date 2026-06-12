# RSI Value Opportunities Dashboard

Daily dashboard for low-priced, $5B+ market-cap stocks ranked by:

- Composite value score from local Polygon/DuckDB warehouse enrichment fields.
- 4-hour RSI acceleration, weighted highest when RSI inflects from a prior grind lower into a sharp rise.
- Price filter: latest 4-hour close below `$50`.

The dashboard is generated locally from `~/market-data/market_data.duckdb` and deployed as a static GitHub Pages site from `docs/`.

## Run

```bash
/usr/bin/python3 scripts/build_dashboard.py --price-filter 50 --top-llm 10
```

Environment:

- `DEEPSEEK_API_KEY` in `~/.hermes/.env` for direct DeepSeek API calls.
- `OPENROUTER_API_KEY` optional fallback if direct DeepSeek is unavailable.

No API keys or warehouse data are committed.

## Compliance notes

This is a research dashboard, not investment advice. LLM analysis is clearly labeled qualitative and must not be treated as a source of truth. Numeric inputs come from the local Polygon warehouse and local enrichment fields; LLM output is downstream commentary only.
