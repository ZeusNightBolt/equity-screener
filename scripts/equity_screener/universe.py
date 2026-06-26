"""Build the full broad universe with historical composite scores from DuckDB.

Produces a DataFrame with all VTI stocks (market_cap >= $5B, no price cap),
with today's opportunity_score, historical composite scores at 1w and 1m ago,
ret_ytd_pct, and sector classification for the heat-map tab.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import numpy as np
import pandas as pd

from .config import DB_PATH


def _business_days_back(n: int) -> int:
    """Timestamp in ms for N business days ago (approximate)."""
    d = dt.date.today()
    skipped = 0
    while skipped < n:
        d = d - dt.timedelta(days=1)
        if d.weekday() < 5:
            skipped += 1
    return int(dt.datetime.combine(d, dt.time.min, tzinfo=dt.timezone.utc).timestamp() * 1000)


def _date_to_ms(year: int, month: int, day: int) -> int:
    """Timestamp in ms for a given date at midnight UTC."""
    return int(dt.datetime(year, month, day, tzinfo=dt.timezone.utc).timestamp() * 1000)


def _snapshot_universe(snapshot_ts_ms: int) -> pd.DataFrame:
    """Build a minimal scoring DataFrame for the universe at a given timestamp.

    Queries DuckDB for: daily close, 4h RSI, and computed return fields.
    Returns columns compatible with score_candidates().
    """
    db = duckdb.connect(str(DB_PATH), read_only=True)
    q = f"""
    with rsi_snap as (
      select ticker, timestamp, rsi_14, close,
             row_number() over(partition by ticker order by abs(timestamp - {snapshot_ts_ms})) rn
      from technical_indicators
      where timeframe='4h' and rsi_14 is not null and close is not null
    ),
    rsi_piv as (
      select ticker,
        max(case when rn=1 then rsi_14 end) rsi0,
        max(case when rn=2 then rsi_14 end) rsi1,
        max(case when rn=3 then rsi_14 end) rsi2,
        max(case when rn=4 then rsi_14 end) rsi3,
        max(case when rn=5 then rsi_14 end) rsi4,
        max(case when rn=6 then rsi_14 end) rsi5
      from rsi_snap where rn<=6 group by ticker
    ),
    daily_snap as (
      select ticker, close as daily_close,
             row_number() over(partition by ticker order by abs(timestamp - {snapshot_ts_ms})) rn
      from daily_bars where close is not null
    ),
    daily_piv as (
      select ticker, max(case when rn=1 then daily_close end) snap_close
      from daily_snap where rn=1 group by ticker
    ),
    returns as (
      select ticker,
        max(case when rn=1 then close end) close_now,
        max(case when rn=2 then close end) close_1w,
        max(case when rn=3 then close end) close_1m,
        max(case when rn=4 then close end) close_3m,
        max(case when rn=5 then close end) close_6m,
        max(case when rn=6 then close end) close_ytd
      from (
        select ticker, close, timestamp,
               row_number() over(partition by ticker order by abs(timestamp - {snapshot_ts_ms})) rn
        from daily_bars where close is not null
      ) where rn <= 6 group by ticker
    ),
    ytd_start as (
      select ticker, close as ytd_start_close
      from (
        select ticker, close,
               row_number() over(partition by ticker order by abs(timestamp - {int(dt.datetime(2026,1,1,tzinfo=dt.timezone.utc).timestamp()*1000)})) rn
        from daily_bars
        where close is not null
      ) where rn = 1
    ),
    qtd_start as (
      select ticker, close as qtd_start_close
      from (
        select ticker, close,
               row_number() over(partition by ticker order by abs(timestamp - {int(dt.datetime(2026,4,1,tzinfo=dt.timezone.utc).timestamp()*1000)})) rn
        from daily_bars
        where close is not null
      ) where rn = 1
    ),
    base as (
      select distinct
        s.ticker, s.sector, s.company_name company, s.market_cap,
        coalesce(d.snap_close, r.close_now) display_close,
        r.close_now, r.close_1w, r.close_1m, r.close_3m, r.close_6m,
        y.ytd_start_close,
        q.qtd_start_close,
        p.rsi0, p.rsi1, p.rsi2, p.rsi3, p.rsi4, p.rsi5,
        (p.rsi0 - p.rsi1) rsi_delta_1,
        ((p.rsi1-p.rsi2)+(p.rsi2-p.rsi3)+(p.rsi3-p.rsi4))/3.0 prior_delta_3_avg,
        ((p.rsi0-p.rsi1) - (((p.rsi1-p.rsi2)+(p.rsi2-p.rsi3)+(p.rsi3-p.rsi4))/3.0)) rsi_accel
      from v_vti_sector_universe_5b s
      left join daily_piv d on s.ticker=d.ticker
      left join returns r on s.ticker=r.ticker
      left join rsi_piv p on s.ticker=p.ticker
      left join ytd_start y on s.ticker=y.ticker
      left join qtd_start q on s.ticker=q.ticker
      where s.market_cap >= 5000000000
        and s.sector is not null and s.sector <> ''
    )
    select * from base
    """
    df = db.execute(q).fetchdf()
    db.close()
    if df.empty:
        return df

    # Compute return columns from the price data
    for col, num, denom in [
        ("ret_1w_pct", "close_1w", "display_close"),
        ("ret_1m_pct", "close_1m", "display_close"),
        ("ret_3m_pct", "close_3m", "display_close"),
        ("ret_6m_pct", "close_6m", "display_close"),
    ]:
        df[col] = np.where(
            (df[num].notna() & df[denom].notna() & (df[num] > 0) & (df[denom] > 0)),
            100.0 * (df[denom] - df[num]) / df[num],
            np.nan,
        )

    df["ret_ytd_pct"] = np.where(
        (df["ytd_start_close"].notna() & df["display_close"].notna() & (df["ytd_start_close"] > 0)),
        100.0 * (df["display_close"] - df["ytd_start_close"]) / df["ytd_start_close"],
        np.nan,
    )
    df["ret_qtd_pct"] = np.where(
        (df["qtd_start_close"].notna() & df["display_close"].notna() & (df["qtd_start_close"] > 0)),
        100.0 * (df["display_close"] - df["qtd_start_close"]) / df["qtd_start_close"],
        np.nan,
    )

    df["short_pct_float"] = np.nan
    df["from_52w_low_pct"] = np.nan
    df["from_52w_high_pct"] = np.nan
    df["price_vs_sma20_pct"] = np.nan
    df["price_vs_sma50_pct"] = np.nan
    df["price_vs_sma200_pct"] = np.nan
    df["volume_vs_20d"] = np.nan
    df["dollar_volume_20d_polygon"] = np.nan
    df["yf_forward_pe"] = np.nan
    df["yf_trailing_pe"] = np.nan
    df["yf_price_to_book"] = np.nan
    df["yf_peg_ratio"] = np.nan
    df["value_grade"] = None
    df["growth_grade"] = None
    df["momentum_grade"] = None
    df["dolt_value_score"] = np.nan
    df["production_factor_score"] = np.nan
    df["production_factor_basket"] = ""
    df["production_theme"] = ""
    df["primary_keyword_factor"] = ""
    df["primary_keyword_factor_score"] = np.nan
    df["keyword_factor_baskets"] = "[]"
    df["sentiment_score"] = np.nan
    df["inflection_flag"] = 0
    df["four_h_timestamp"] = pd.Timestamp.utcnow()

    return df


def universe_snapshot() -> pd.DataFrame:
    """Build today's universe with historical composite score deltas.

    Returns DataFrame with columns:
    ticker, company, sector, market_cap, display_close,
    opportunity_score (today's full composite),
    composite_1w_ago (simplified historical composite at ~1w ago),
    composite_1m_ago (simplified historical composite at ~1m ago),
    ret_ytd_pct, score_delta_1w, score_delta_1m
    """
    from .scoring import score_candidates

    # Build today's snapshot and run scoring
    ts_today = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    ts_ytd = _date_to_ms(2026, 1, 2)

    df_today = _snapshot_universe(ts_today)
    if df_today.empty:
        return df_today

    scored_today = score_candidates(df_today)

    # Build historical snapshots
    df_1w = _snapshot_universe(_business_days_back(5))
    df_1m = _snapshot_universe(_business_days_back(21))
    df_ytd = _snapshot_universe(ts_ytd)

    scored_1w = score_candidates(df_1w) if not df_1w.empty else pd.DataFrame()
    scored_1m = score_candidates(df_1m) if not df_1m.empty else pd.DataFrame()
    scored_ytd = score_candidates(df_ytd) if not df_ytd.empty else pd.DataFrame()

    # Merge today's scores with historical
    out = scored_today[["ticker", "company", "sector", "market_cap", "display_close",
                         "opportunity_score", "ret_ytd_pct", "ret_qtd_pct", "primary_strategy"]].copy()

    # Add historical opportunity_scores
    for label, scored_df in [("composite_1w_ago", scored_1w), ("composite_1m_ago", scored_1m), ("composite_ytd_ago", scored_ytd)]:
        if not scored_df.empty:
            hist = scored_df[["ticker", "opportunity_score"]].rename(
                columns={"opportunity_score": label}
            )
            out = out.merge(hist, on="ticker", how="left")
        else:
            out[label] = np.nan

    # Compute deltas
    out["score_delta_1w"] = out["opportunity_score"] - out["composite_1w_ago"]
    out["score_delta_1m"] = out["opportunity_score"] - out["composite_1m_ago"]
    out["score_delta_ytd"] = out["opportunity_score"] - out["composite_ytd_ago"]

    # Sort by sector then YTD score delta desc (best improvement to worst deterioration)
    out = out.sort_values(["sector", "score_delta_ytd"], ascending=[True, False]).reset_index(drop=True)

    return out
