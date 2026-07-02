#!/usr/bin/env python3
"""Deterministic Telegram summary for the Equity Screener daily cron.

The dashboard build job should not only say "pushed dashboard". This module reads
the generated dashboard JSON, compares it with the prior committed run when
available, and emits a concise PM-style Telegram update with key takeaways and
new findings.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DATA_PATH = REPO / "data" / "dashboard_data.json"
DASHBOARD_URL = "https://zeusnightbolt.github.io/equity-screener/"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _git_show(ref_path: str) -> dict[str, Any] | None:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(REPO), "show", ref_path],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def _num(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return default
        return float(x)
    except Exception:
        return default


def _fmt_score(x: Any) -> str:
    return f"{_num(x):.1f}"


def _fmt_pct(x: Any) -> str:
    v = _num(x)
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.1f}%"


def _fmt_money(x: Any) -> str:
    v = _num(x)
    if v >= 1_000_000_000:
        return f"${v/1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"${v/1_000_000:.0f}M"
    return f"${v:.2f}"


def _ticker_set(rows: list[dict[str, Any]]) -> set[str]:
    return {str(r.get("ticker", "")).upper() for r in rows if r.get("ticker")}


def _by_ticker(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r.get("ticker", "")).upper(): r for r in rows if r.get("ticker")}


def _score_for_row(r: dict[str, Any]) -> tuple[str, float]:
    if r.get("combined_rank_score") is not None:
        return "C", _num(r.get("combined_rank_score"))
    return "O", _num(r.get("opportunity_score"))


def _strategy_label(r: dict[str, Any]) -> str:
    if r.get("primary_strategy"):
        return str(r.get("primary_strategy"))
    if r.get("alignment_status"):
        return str(r.get("alignment_status")).lower()
    if r.get("diversified_source"):
        return str(r.get("diversified_source"))
    return "setup"


def _top_line(rows: list[dict[str, Any]], n: int = 5) -> str:
    bits = []
    for r in rows[:n]:
        ticker = str(r.get("ticker", "?"))
        score_label, score = _score_for_row(r)
        bits.append(f"{ticker} {score_label}{score:.1f} ({_strategy_label(r)})")
    return ", ".join(bits) if bits else "None"


def _new_entries(curr: list[dict[str, Any]], prev: list[dict[str, Any]], n: int = 5) -> list[dict[str, Any]]:
    old = _ticker_set(prev)
    return [r for r in curr if str(r.get("ticker", "")).upper() not in old][:n]


def _row_score_value(row: dict[str, Any]) -> float:
    return _num(row.get("combined_rank_score") if row.get("combined_rank_score") is not None else row.get("opportunity_score"))


def _score_changes(curr: list[dict[str, Any]], prev: list[dict[str, Any]], n: int = 3) -> list[tuple[str, float, dict[str, Any]]]:
    c = _by_ticker(curr)
    p = _by_ticker(prev)
    changes = []
    for ticker, row in c.items():
        if ticker in p:
            delta = _row_score_value(row) - _row_score_value(p[ticker])
            if abs(delta) >= 3:
                changes.append((ticker, delta, row))
    changes.sort(key=lambda x: abs(x[1]), reverse=True)
    return changes[:n]


def _sector_leaders(rows: list[dict[str, Any]], n: int = 3) -> str:
    sectors = Counter(str(r.get("sector") or "Unknown") for r in rows[:20])
    return ", ".join(f"{sector}×{count}" for sector, count in sectors.most_common(n)) or "None"


def _penalty_watch(rows: list[dict[str, Any]], n: int = 3) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        penalty = _num(r.get("quality_penalty")) + _num(r.get("thin_volume_penalty")) + _num(r.get("broken_trend_penalty")) + _num(r.get("crash_penalty"))
        if penalty >= 10:
            rr = dict(r)
            rr["_penalty_total"] = penalty
            out.append(rr)
    out.sort(key=lambda r: _num(r.get("_penalty_total")), reverse=True)
    return out[:n]


def _latest_generated(d: dict[str, Any]) -> str:
    raw = str(d.get("generated_at") or "")
    if not raw:
        return "unknown"
    try:
        return datetime.fromisoformat(raw).strftime("%Y-%m-%d %H:%M %Z")
    except Exception:
        return raw[:19]


def build_summary(curr: dict[str, Any], prev: dict[str, Any] | None) -> str:
    diversified = curr.get("top_diversified") or []
    combined = curr.get("combined_top25") or curr.get("top") or []
    inflections = curr.get("inflections") or []
    llm = curr.get("llm_analysis") or []

    prev_div = (prev or {}).get("top_diversified") or []
    prev_combined = (prev or {}).get("combined_top25") or (prev or {}).get("top") or []
    prev_inflections = (prev or {}).get("inflections") or []

    lines = [
        DASHBOARD_URL,
        "",
        "## Equity Screener — Daily Takeaways",
        f"Generated: {_latest_generated(curr)} | 4h data: {curr.get('latest_4h_timestamp', 'unknown')}",
        f"Universe: {curr.get('universe_count', '?')} stocks ≥ ${_num(curr.get('price_filter')):.0f} | Displayed inflections: {len(inflections)} | LLM checks: {len(llm)}",
        "",
        "**Top setups**",
        f"- Diversified top 10: {_top_line(diversified, 5)}",
        f"- Combined top 5: {_top_line(combined, 5)}",
    ]

    new_div = _new_entries(diversified, prev_div, 5) if prev else []
    new_combined = _new_entries(combined, prev_combined, 5) if prev else []
    new_inflect = _new_entries(inflections, prev_inflections, 5) if prev else []
    changes = _score_changes(combined, prev_combined, 3) if prev else []

    lines += ["", "**New since last run**"]
    if new_div:
        lines.append("- New diversified names: " + ", ".join(f"{r.get('ticker')} {_fmt_score(r.get('opportunity_score'))}" for r in new_div))
    if new_combined:
        lines.append("- New combined-top names: " + ", ".join(f"{r.get('ticker')} C{_fmt_score(r.get('combined_rank_score'))}" for r in new_combined))
    if new_inflect:
        lines.append("- Fresh RSI inflections: " + ", ".join(f"{r.get('ticker')} RSI {_fmt_score(r.get('rsi0'))}, Δ1 {_fmt_score(r.get('rsi_delta_1'))}" for r in new_inflect[:5]))
    if not any([new_div, new_combined, new_inflect]):
        lines.append("- No material new names versus the prior committed run; update is mainly score/refresh maintenance.")

    if changes:
        lines += ["", "**Largest score moves**"]
        for ticker, delta, row in changes:
            sign = "+" if delta > 0 else ""
            score_label, score = _score_for_row(row)
            lines.append(f"- {ticker}: {sign}{delta:.1f} to {score_label}{score:.1f} ({_strategy_label(row)})")

    penalty = _penalty_watch(combined, 3)
    lines += ["", "**Risk / quality flags**"]
    if penalty:
        for r in penalty:
            lines.append(
                f"- {r.get('ticker')}: penalty {_fmt_score(r.get('_penalty_total'))}; raw {_fmt_score(r.get('raw_opportunity_score'))} → net {_fmt_score(r.get('opportunity_score'))}"
            )
    else:
        lines.append("- No top combined names carry a ≥10 quality/trend/liquidity penalty.")

    lines += ["", "**Regime read**", f"- Sector concentration in top 20: {_sector_leaders(combined, 4)}"]
    if diversified:
        leader = diversified[0]
        lines.append(
            f"- Best current diversified setup: {leader.get('ticker')} ({leader.get('sector')}) score {_fmt_score(leader.get('opportunity_score'))}, RSI {_fmt_score(leader.get('rsi0'))}, 1M {_fmt_pct(leader.get('ret_1m_pct'))}."
        )
    lines.append("- Treat this as an idea queue, not a trade instruction; use source/filing checks before sizing.")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--prev-ref", default="HEAD~1:data/dashboard_data.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if not args.data.exists():
        print(f"ERROR: missing dashboard data: {args.data}", file=sys.stderr)
        return 1
    curr = _load_json(args.data)
    prev = _git_show(args.prev_ref)
    summary = build_summary(curr, prev)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(summary)
    print(summary, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
