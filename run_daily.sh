#!/usr/bin/env bash
set -euo pipefail
cd /home/nima/rsi-value-opportunities

# ── Freshness guard: refuse to build if 4h RSI data is >30h stale ──
/usr/bin/python3 -c "
import duckdb, sys, datetime
db = duckdb.connect('/home/nima/market-data/market_data.duckdb', read_only=True)
ti_max = db.execute(\"SELECT max(to_timestamp(CAST(timestamp/1000 AS BIGINT))) FROM technical_indicators WHERE timeframe='4h'\").fetchone()
if ti_max[0] is None:
    print('FATAL: no 4h RSI data in technical_indicators')
    sys.exit(2)
age_hours = (datetime.datetime.now(datetime.timezone.utc) - ti_max[0].replace(tzinfo=datetime.timezone.utc)).total_seconds() / 3600
if age_hours > 30:
    print(f'REFUSING: 4h RSI data is {age_hours:.0f}h old (max={ti_max[0]}). Run refresh_latest_intraday_indicators.py first.')
    sys.exit(2)
print(f'OK: 4h RSI data is {age_hours:.0f}h old (max={ti_max[0]})')
db.close()
" || exit $?

/usr/bin/python3 scripts/build_dashboard.py --price-filter 75 --top-llm 10 --push
