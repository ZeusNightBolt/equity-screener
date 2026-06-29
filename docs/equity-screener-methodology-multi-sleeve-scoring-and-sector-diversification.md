---
title: Equity Screener Methodology: Multi-Sleeve Scoring and Sector Diversification
type: reference
project: equity-screener
created: 2026-06-18T09:25:55.516142
tags: []
source: <!-- URL or citation -->
---

# Equity Screener Methodology: Multi-Sleeve Scoring and Sector Diversification

The RSI dashboard scores $5B+ market-cap stocks from the VTI universe using intraday 4h technical data from the DuckDB warehouse. Three scoring sleeves produce a sector-diversified top 10, capped at 3 names per sector.

## Query Flow

1. **technical_indicators** (timeframe=4h): latest 6 RSI periods per ticker
2. **v_vti_sector_universe_5b**: sector, market-cap, short float, price vs SMAs, sentiment
3. **vti_daily_enriched_latest**: forward PE, trailing PE, P/B, PEG, value/growth/momentum grades
4. **v_vti_factor_production_scores_5b**: Dolt value score, production factor scores, returns, keyword factor baskets
5. **daily_bars**: 52-week high/low computation (latest 1 year from max daily timestamp)

Price filter: latest available close (4h or daily, whichever is newer) < $30 (configurable).

## Sleeve Construction

### Sleeve 1: Opportunity (4 slots, best all-around)
- **RSI acceleration score** (70%): percentile rank of RSI acceleration over all candidates, with +15 bonus for inflection flags
- **Composite value score** (30%): weighted blend of warehouse value score (Dolt or Yahoo grade), forward PE, trailing PE, P/B, PEG
- Final: 65% RSI acceleration + 35% composite value

### Sleeve 2: Squeeze-laggard (3 slots, contrarian)
- **Short score** (35%): higher short float → higher score
- **Near-low score** (30%): closer to 52w low → higher score
- **Peer-lag score** (25%): wider gap vs sector 1m/3m median returns → higher score
- **RSI zone bonus** (10%): RSI in 25-55 zone →70, outside →40

### Sleeve 3: Value-laggard (3 slots)
- Sector peer-lag >5% and sector median 1m return >3% flagged as "rally laggard"
- Scored by value-grade + factor production scores

### Sleeve 4: Momentum Pullback (3 slots, new June 2026)
- **Gate:** ret_6m >10%, ret_1w <0%, off 52w high >5%, RSI 30-65
- **Momentum strength** (30%): percentile rank of 6-month return
- **Pullback depth** (25%): scored where 5-40% below 52w high (meaningful dip, not broken trend)
- **SMA proximity** (20%): weighted closeness to SMA50/SMA200 (tight coil = higher score)
- **RSI cooling** (15%): tent function peaking at RSI 45-50, decaying toward 30 and 65
- **Volume contraction** (10%): sub-1.0 volume vs 20-day average (drying up during pullback)
- Continuation setup: not a reversal, targets strong trends that temporarily sold off

## Sector Cap

Per-sector cap of 3 entries in the top 10 ensures diversification. If a sector hits 3, the next-highest-scoring ticker from a different sector claims the remaining slots.

## Factor Basket Inflection

Separate analysis identifies lagged factor baskets and keyword themes using `ticker_keyword_factor_membership` and `keyword_factor_baskets` tables. Lagged baskets ranked by reversal potential; target basket is the highest-scored one with `is_lagged=true`.

## Key Takeaways

<!-- The most important points to remember -->

## Relevance

<!-- Why is this worth keeping? How does it apply to our work? -->
