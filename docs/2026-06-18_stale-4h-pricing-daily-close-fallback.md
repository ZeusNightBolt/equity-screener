---
title: Stale 4h Pricing — Daily Close Fallback
type: decision
project: equity-screener
date: 2026-06-18
created: 2026-06-18T09:26:03.583637
tags: []
status: accepted
---

# Stale 4h Pricing — Daily Close Fallback

## Context

<!-- What situation prompted this decision? -->

## Decision

## Context

On 2026-06-16, CELH showed a daily close of $30.01 but 4h technical indicators stopped at 08:00 ET with a close of $28.75. The RSI dashboard was displaying stale 4h pricing because the DuckDB warehouse hadn't pulled current-day hourly bars for that ticker.

## Decision

Modified `scripts/build_dashboard.py` to join `latest_daily` (latest daily close per ticker) and use `display_close` which selects the daily close when it's newer than the latest 4h bar:

```sql
case when ld.daily_ts > p.ts0 then ld.daily_close else p.close0 end display_close
```

The `price_source` column exposes which source was used: `daily_close_newer_than_4h` or `4h_close`.

The price filter in the WHERE clause also uses this fallback logic so tickers aren't incorrectly included/excluded based on stale 4h data.

## Root cause in warehouse

`pull_hourly.py` used `RECENT_GAP_DAYS=3` for gap detection, missing same-day gaps. Patched to `RECENT_GAP_HOURS=1` on 2026-06-17.

## Tags

dashboard, pricing, staleness, hourly-gap, celh, defensive-fallback

## Rationale

<!-- Why this option over alternatives? -->

## Alternatives Considered

<!-- What else was evaluated? -->

## Consequences

<!-- What are the implications? Trade-offs? -->
