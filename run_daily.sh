#!/usr/bin/env bash
# Equity Screener — daily build + deploy
# 1. Refreshes warehouse data (latest hourly + indicators)
# 2. Builds dashboard
# 3. Pushes to GitHub Pages
set -euo pipefail
export PYTHONPATH="/home/nima/equity-screener/scripts${PYTHONPATH:+:$PYTHONPATH}"

LOG_DIR="/home/nima/market-data/logs"
mkdir -p "$LOG_DIR"
RUN_ID="$(date +%Y%m%dT%H%M%S%z)"
LOG_FILE="$LOG_DIR/equity_screener_${RUN_ID}.log"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "═══════════════════════════════════════"
echo "  EQUITY SCREENER RUN"
echo "  Run: $RUN_ID"
echo "  $(date -Is)"
echo "═══════════════════════════════════════"

run_quick_refresh() {
    local attempt="$1"
    echo ""
    echo "── Step 1.${attempt}: Warehouse quick refresh ──"
    if /usr/bin/bash /home/nima/market-data/scripts/quick_refresh.sh; then
        echo "   ✅ Warehouse refresh complete (${attempt})"
        return 0
    else
        local rc=$?
        echo "   ⚠️  Warehouse refresh failed (${attempt}, exit $rc) — freshness guard will decide whether build can continue"
        return "$rc"
    fi
}

# Step 1: Refresh warehouse data (latest 1h/4h data points)
run_quick_refresh "initial" || true

# Step 2: Freshness guard. If 4h pricing data is >50h stale, retry the
# warehouse refresh once before accepting weekend data or refusing the build.
echo ""
echo "── Step 2: Data freshness check ──"
set +e
/usr/bin/python3 -m equity_screener.freshness
fresh_rc=$?
set -e
if [[ "$fresh_rc" -eq 75 ]]; then
    echo "   ↻ 4h pricing data exceeded 50h; re-attempting market-data warehouse refresh"
    run_quick_refresh "stale-retry" || true
    /usr/bin/python3 -m equity_screener.freshness --refresh-retried || exit $?
elif [[ "$fresh_rc" -ne 0 ]]; then
    exit "$fresh_rc"
fi

# Step 3: Build + deploy dashboard
echo ""
echo "── Step 3: Build + deploy dashboard ──"
cd /home/nima/equity-screener
/usr/bin/python3 scripts/build_dashboard.py --price-filter 75 --top-llm 10 --push

echo ""
echo "═══════════════════════════════════════"
echo "  EQUITY SCREENER COMPLETE"
echo "  $(date -Is)"
echo "  Log: $LOG_FILE"
echo "═══════════════════════════════════════"
