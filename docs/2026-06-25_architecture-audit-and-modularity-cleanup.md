---
type: reference
title: Equity Screener Architecture Audit and Modularity Cleanup
created: 2026-06-25
tags: [equity-screener, architecture, audit, modularity]
---

# Equity Screener Architecture Audit and Modularity Cleanup

## Summary

The active repo is now `~/equity-screener` on GitHub `ZeusNightBolt/equity-screener`. The codebase is intentionally small but the main build script is still monolithic. First cleanup focused on removing dead/bug code and centralizing sleeve metadata so future sleeves can be added with fewer drift-prone edits.

## Audit baseline

- Core script: `scripts/build_dashboard.py`
- Runtime wrapper: `run_daily.sh`
- Output: `docs/index.html`, `docs/factor-baskets.html`, `docs/dashboard_data.json`, `data/scored_candidates.csv`
- Baseline build command: `/usr/bin/python3 scripts/build_dashboard.py --price-filter 75 --no-llm`
- Verified universe on 2026-06-25 build: 358 names, 11 sectors.

## Fixed findings

1. `build_diversified_top10()` used cumulative quota values in a way that filled the top 10 before momentum/RS-breakout sleeves could contribute. It now uses `DIVERSIFIED_TOP_PLAN` with per-sleeve quotas.
2. `git_commit_push()` pushed `origin main` regardless of current branch. This could silently leave dashboard commits on a feature branch unpushed. It now pushes the current branch.
3. `score_candidates()` mutated the input DataFrame in place. It now returns a scored copy.
4. `record()` omitted `rel_strength_pullback_score` and treated `price_source` as numeric. Payload contract tests now cover both fields.
5. `diversified_top10` CSV flag used a different selection algorithm/index basis than the dashboard top-10 builder. It is now computed from `build_diversified_top10()` after final sorting.
6. `call_llm()` had narrow network exception handling. It now fails soft on any LLM exception and returns a diagnostic string.
7. Final dashboard candidates used stale warehouse fallback prices even when live Polygon snapshot data was available at build time. `final_candidate_tickers()` now selects only rendered opportunity rows and `enrich_latest_polygon_prices()` overlays latest snapshot prices while preserving `warehouse_display_close`.
8. Mobile cards omitted `rel_strength_pullback_score` while desktop/master views showed it. Mobile score rows now come from `SCORE_DISPLAY`.
9. Master comparison rows were hard-coded. They now iterate through `SCORE_DISPLAY[1:]`.
10. Dashboard copy said top 10 blended five sleeves; actual code uses six. Copy now says six.
11. RS Pullback tab copy described old gates; now matches relaxed gate logic.
12. Dead helpers `score_heatmap`, `render_mobile_card`, and `mobile_section` were removed.
13. Repeated score-column/label/color lists were centralized in module-level constants.

## Dynamic extension points

- `SCORE_COLUMNS`: canonical scoring contract.
- `DIVERSIFIED_TOP_PLAN`: per-sleeve quotas for diversified top 10 construction; selected rows carry `diversified_source` in the JSON payload.
- `SLEEVE_LABELS`: maps score column to human strategy label.
- `SCORE_DISPLAY`: drives mobile cards and master comparison rows.
- `COLOR_RGB`: heatmap/display colors.
- `GIT_TRACKED_OUTPUTS`: deploy commit file list.

## Next recommended module split

```text
scripts/build_dashboard.py        thin CLI/orchestrator
src/equity_screener/config.py     score/tab metadata
src/equity_screener/data.py       DuckDB query layer
src/equity_screener/scoring.py    sleeve scoring
src/equity_screener/render.py     HTML/JSON rendering
src/equity_screener/deploy.py     git commit/push
```

## Verification checklist

```bash
cd ~/equity-screener
/usr/bin/python3 -m py_compile scripts/build_dashboard.py
/usr/bin/python3 scripts/build_dashboard.py --price-filter 75 --no-llm
```

Then assert:

- `docs/dashboard_data.json` has non-empty sleeve arrays.
- `docs/index.html` contains `RS Pb` and `blends six sleeves`.
- `docs/index.html` does not contain `{{D_DATA}}` or stale `pullback < -3%` copy.

## Adversarial audit status

A devils-advocate task was dispatched on `agent-dispatch` as `t_2c329093`. Its completed summary flagged the quota bug in `build_diversified_top10()`, branch push behavior in `git_commit_push()`, input mutation in `score_candidates()`, and hidden optional commentary dependencies. The first three are fixed here; optional commentary dependency handling remains documented technical debt because failures already degrade to snippets/empty sources rather than breaking the build.
