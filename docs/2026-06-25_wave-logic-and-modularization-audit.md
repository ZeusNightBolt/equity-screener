# Wave logic + modularization audit — 2026-06-25

## Scope

Audited the June 25 wave-stage scoring additions and split the former `scripts/build_dashboard.py` monolith into focused modules under `scripts/equity_screener/`.

## Modularization result

`build_dashboard.py` is now a 26-line compatibility entrypoint. The package modules are:

| Module | Interface / purpose |
|---|---|
| `config.py` | Paths, score contracts, labels, colors, tracked output list. |
| `data.py` | Environment loading and DuckDB candidate query. |
| `scoring.py` | Continuous 0-100 factor scores, eligibility flags, wave-stage classifier. |
| `selection.py` | Sector caps, diversified top-10 construction, final ticker set. |
| `polygon_overlay.py` | Live Polygon snapshot overlay for final displayed candidates. |
| `commentary.py` | Web search/extract and LLM qualitative commentary. |
| `serialization.py` | JSON payload record contract and float cleaning. |
| `render_helpers.py` | Formatting, score bars, RSI cell, ticker links. |
| `baskets.py` | Factor basket and keyword/theme basket scoring. |
| `render.py` | Static HTML/data artifact rendering. |
| `git_ops.py` | Commit/push helper used by `--push`. |
| `main.py` | CLI orchestration. |

### Line-count verification

No implementation module is over 335 lines after the split; the entrypoint is 26 lines.

## Wave scoring audit

### Known — from local build output

Universe: 356 stocks under the $75 filter.

Post-audit score distributions:

| Factor | Mean | Median | Min | Max |
|---|---:|---:|---:|---:|
| Momentum leader | 49.0 | 53.3 | 6.4 | 80.3 |
| Momentum pullback | 52.8 | 51.6 | 22.9 | 77.6 |
| Relative strength pullback | 52.3 | 52.0 | 29.7 | 79.7 |
| RSI breakout | 54.1 | 55.5 | 14.4 | 82.4 |
| Wave setup | 61.4 | 61.8 | 38.4 | 81.9 |
| Distribution risk | 15.9 | 3.6 | 0.0 | 82.9 |
| Pullback presence | 58.1 | 56.5 | 5.0 | 100.0 |

Wave-stage counts after adding an ambiguity margin:

| Wave stage | Count |
|---|---:|
| Wave 2-4 / pullback | 88 |
| Wave 1 / accumulation | 86 |
| Wave 3-5 / breakout | 83 |
| Mixed / transition | 80 |
| Wave 3 / markup leader | 19 |

### Audit fixes applied

| Finding | Fix |
|---|---|
| `wave_setup_score` was upward-biased because it was the raw max of four stage scores. | Replaced raw max with `0.72 * top_stage + 0.28 * second_stage`, with a small ambiguity penalty when the top-stage margin is under 5 points. |
| Noisy `idxmax` stage labels when two stages were almost tied. | Added `wave_stage_margin`; labels become `Mixed / transition` when margin is under 3 points. |
| Pullback presence had a discontinuity around 0% one-week return. | Replaced binary negative-week logic with a continuous score: mild pullbacks get high scores, chase strength decays gradually. |
| Distribution/exhaustion risk was binary and weak. | Replaced with a continuous penalty based on 52-week price position, hot RSI, and positive one-week chase. |
| Grind-turn RSI bonus was a hard +12 jump. | Replaced with a continuous 0-12 bonus from current RSI delta, prior downside grind, and acceleration. |

### Estimated — model interpretation

The wave labels are deterministic stage proxies, not validated Elliott-wave counts. They use price-distribution location, RSI, returns, volume, and moving-average geometry as proxies:

- **Wave 1 / accumulation**: low-to-mid 52-week location plus RSI improvement/value support.
- **Wave 2-4 / pullback**: prior strength plus 1-week pullback, RSI reset, and SMA proximity.
- **Wave 3 / markup leader**: 3-6 month return strength, trend alignment, and volume confirmation.
- **Wave 3-5 / breakout**: RSI breakout, volume, sector tailwind, and higher price-distribution location.
- **Mixed / transition**: top two stage scores are too close to label confidently.

### Remaining limitations

1. **No forward-return validation yet.** This is a classifier, not a proven alpha signal.
2. **`wave_setup_score` remains a cross-stage score.** It is useful for finding different parts of the wave, but not directly comparable as one expected-return probability across all stages.
3. **Daily/4h timeframe mixing remains.** RSI comes from latest 4h technical indicators while 1w/1m/3m/6m returns are longer-horizon fields.
4. **Sector-neutral validation is still missing.** Scores use sector medians in parts of the model, but no formal sector-neutral backtest is included.

## Verification performed

- `/usr/bin/python3 -m py_compile scripts/build_dashboard.py scripts/equity_screener/*.py`
- `/usr/bin/python3 -m unittest -v test_build_dashboard.py` → 5/5 passing
- `/usr/bin/python3 scripts/build_dashboard.py --price-filter 75 --no-llm`
- Statistical audit of wave-stage counts, distributions, top wave names, and correlations.
