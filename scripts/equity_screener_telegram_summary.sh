#!/usr/bin/env bash
set -euo pipefail
cd /home/nima/equity-screener
exec /usr/bin/python3 scripts/equity_screener/telegram_summary.py "$@"
