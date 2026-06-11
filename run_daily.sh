#!/usr/bin/env bash
set -euo pipefail
cd /home/nima/rsi-value-opportunities
/usr/bin/python3 scripts/build_dashboard.py --price-filter 30 --top-llm 10 --push
