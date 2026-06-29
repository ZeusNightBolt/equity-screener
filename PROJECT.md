---
name: equity-screener
status: active
created: 2026-06-24T12:05:23.190142
objective: Multi-sleeve equity screener: RSI inflection, squeeze laggards, value laggards, momentum pullbacks + EV Master Opportunities — deploys tabbed dashboard to GitHub Pages
tags: []
---

# Equity Screener — Project Reference

**Repo:** https://github.com/ZeusNightBolt/equity-screener  
**Local path:** `~/equity-screener`  
**Cron:** `4dbc25d5abb4` (daily 20:30 ET, builds + deploys dashboard)
**Live:** https://zeusnightbolt.github.io/equity-screener/

## Pipeline DAG

```
market-data-warehouse (~/market-data/)
├── cron f6150d6895cd: hourly-bars-weekday (9-16 ET, pulls Polygon hourly bars)
├── cron 5800f96cc1f7: daily-warehouse-refresh (9:30 ET weekdays)
│   ├── pull_hourly.py → hourly_bars
│   ├── build_higher_timeframes.py → daily_bars, weekly_bars
│   ├── create_indicator_views.py → SQL views
│   ├── refresh_latest_daily_indicators.py → technical_indicators (daily)
│   └── refresh_latest_intraday_indicators.py → technical_indicators (1h/4h)
│
└── DuckDB: technical_indicators (4h RSI), daily_bars,
    v_vti_sector_universe_5b, vti_daily_enriched_latest,
    v_vti_factor_production_scores_5b
         ↓
Equity Screener (~/equity-screener/)
├── cron 4dbc25d5abb4: daily-equity-screener-dashboard (20:30 ET daily)
├── scripts/build_dashboard.py
│   ├── query_candidates(): DuckDB → 128 tickers (mkt cap ≥$5B, price <$30)
│   ├── score_candidates(): multi-sleeve composite scoring
│   ├── build_diversified_top10(): blend 4 sleeves, cap 3/sector
│   ├── analyze_top_inflections(): LLM deep-dive on top 10
│   └── render_dashboard(): self-contained HTML + JSON data
├── docs/index.html (self-contained dashboard)
├── docs/dashboard_data.json (structured JSON)
└── git push → GitHub Pages
```

## Score Sleeves (4 sleeves)

### 1. RSI Value Score
RSI acceleration (inflection) × composite value. Best for mean-reversion setups.
- 65% RSI acceleration (70% percentile + 20% delta + grind bonus)
- 35% composite value (Dolt + Yahoo Finance grades + P/E/P/B/PEG)

### 2. Squeeze Laggard Score
Shorted names near lows, peer laggards during sector rallies.
- 35% short interest percentile + 30% near-52w-low + 25% peer lag + 10% RSI 25-55 zone
- Bonus: +10 if peer rally flag + short ≥5%

### 3. Value Laggard Score
Cheap stocks lagging their sector peers.
- 45% composite value + 35% peer lag + 20% near-52w-low

### 4. Momentum Pullback Score *(new June 2026)*
Strong 6mo uptrends that have pulled back 1-2 weeks and are coiling into SMAs.
- **Gate:** ret_6m >10%, ret_1w <0%, off 52w high >5%, RSI 30-65
- 30% 6-month return percentile + 25% pullback depth (5-40% off highs)
- 20% SMA proximity (SMA50/SMA200 tightness) + 15% RSI cooling zone
- 10% volume contraction during pullback

### Blending (top 10)
1. 4 slots: best all-around (opportunity_score)
2. 3 slots: squeeze laggards
3. 3 slots: value laggards → momentum pullbacks
4. Fill remaining: overall score

## Key Files

| File | Purpose |
|------|---------|
| `scripts/build_dashboard.py` | Single script: query → score → render → deploy |
| `run_daily.sh` | Cron entrypoint wrapper |
| `docs/index.html` | Self-contained dashboard (4-sleeve table) |
| `docs/dashboard_data.json` | Structured data for API consumers |
| `docs/factor-baskets.html` | Factor/theme basket inflection analysis |
| `data/` | LLM analysis cache + dashboard payload |

## Recent Fixes (June 2026)

| Date | Issue | Fix |
|------|-------|-----|
| 2026-06-22 | Dashboard stale at June 18 | Removed `current_date` filter from `v_daily_from_hourly`; re-enabled hourly cron |
| 2026-06-22 | Hourly pull missed multi-day gaps | Added stale-hourly detection to `pull_hourly.py` (>24h staleness check) |
| 2026-06-24 | Added momentum pullback sleeve | New 5-factor scoring gate, 4th sleeve in diversified top-10 |

## Upstream Dependencies (market-data-warehouse)

| Dependency | File | Status |
|-----------|------|--------|
| `current_date` filter removed | `build_higher_timeframes.py:68-74` | ✅ committed 4281d14 |
| Stale hourly detection | `pull_hourly.py:171-207` | ✅ committed 4281d14 |
| Hourly weekday cron | `f6150d6895cd` (9-16 ET weekdays) | ✅ enabled |
| Daily warehouse refresh | `5800f96cc1f7` (9:30 ET weekdays) | ✅ active |

## Dependencies

- DuckDB: `~/market-data/market_data.duckdb`
- Python: `/usr/bin/python3` with duckdb, pandas, numpy
- API keys (in `~/.hermes/.env`): DEEPSEEK_API_KEY or OPENROUTER_API_KEY (LLM analysis)
- Polygon API key: via market-data warehouse scripts (not dashboard)
