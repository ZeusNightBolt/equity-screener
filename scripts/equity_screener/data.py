import os
from pathlib import Path

import duckdb
import pandas as pd

from .config import DB_PATH

def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

def query_candidates(price_filter: float) -> pd.DataFrame:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    q = r"""
with rsi_hist as (
  select ticker, timestamp, rsi_14, close,
         row_number() over(partition by ticker order by timestamp desc) rn
  from technical_indicators
  where timeframe='4h' and rsi_14 is not null and close is not null
), piv as (
  select ticker,
    max(case when rn=1 then timestamp end) ts0,
    max(case when rn=1 then close end) close0,
    max(case when rn=1 then rsi_14 end) rsi0,
    max(case when rn=2 then rsi_14 end) rsi1,
    max(case when rn=3 then rsi_14 end) rsi2,
    max(case when rn=4 then rsi_14 end) rsi3,
    max(case when rn=5 then rsi_14 end) rsi4,
    max(case when rn=6 then rsi_14 end) rsi5,
    count(*) n
  from rsi_hist where rn<=6 group by ticker
), latest_daily_ts as (
  select max(timestamp) as max_ts from daily_bars
), latest_daily as (
  select ticker, timestamp as daily_ts, close as daily_close
  from (
    select ticker, timestamp, close,
           row_number() over(partition by ticker order by timestamp desc) rn
    from daily_bars
    where close is not null
  ) where rn = 1
), daily_52w as (
  select d.ticker, min(d.low) low_52w, max(d.high) high_52w
  from daily_bars d, latest_daily_ts l
  where d.timestamp >= l.max_ts - 31536000000
    and d.low is not null and d.high is not null
  group by d.ticker
), base as (
  select distinct
    s.sector,
    s.ticker,
    coalesce(s.company_name, s.holding_name) company,
    s.market_cap,
    s.exchange,
    s.industry,
    s.sic_description,
    s.sentiment_score,
    s.short_pct_float,
    coalesce(s.from_52w_high_pct, case when d.high_52w > 0 then ((case when ld.daily_ts > p.ts0 then ld.daily_close else p.close0 end / d.high_52w) - 1.0) * 100.0 end) from_52w_high_pct,
    coalesce(s.from_52w_low_pct, case when d.low_52w > 0 then ((case when ld.daily_ts > p.ts0 then ld.daily_close else p.close0 end / d.low_52w) - 1.0) * 100.0 end) from_52w_low_pct,
    s.price_vs_sma20_pct,
    s.price_vs_sma50_pct,
    s.price_vs_sma200_pct,
    s.volume_vs_20d,
    s.dollar_volume_20d_polygon,
    e.yf_forward_pe,
    e.yf_trailing_pe,
    e.yf_price_to_book,
    e.yf_peg_ratio,
    e.yf_dividend_yield,
    e.value_grade,
    e.growth_grade,
    e.momentum_grade,
    f.dolt_value_score,
    f.production_factor_score,
    f.production_factor_basket,
    f.production_theme,
    f.primary_keyword_factor,
    f.primary_keyword_factor_score,
    f.keyword_factor_baskets,
    f.quant_factor_score,
    f.ret_1w_pct,
    f.ret_1m_pct,
    f.ret_3m_pct,
    f.ret_6m_pct,
    f.ret_ytd_pct,
    p.ts0,
    to_timestamp(p.ts0/1000) four_h_timestamp,
    p.close0 four_h_close,
    ld.daily_ts latest_daily_ts,
    to_timestamp(ld.daily_ts/1000) latest_daily_timestamp,
    ld.daily_close latest_daily_close,
    case when ld.daily_ts > p.ts0 then ld.daily_close else p.close0 end display_close,
    case when ld.daily_ts > p.ts0 then 'daily_close_newer_than_4h' else '4h_close' end price_source,
    p.rsi0, p.rsi1, p.rsi2, p.rsi3, p.rsi4, p.rsi5,
    (p.rsi0-p.rsi1) rsi_delta_1,
    ((p.rsi1-p.rsi2)+(p.rsi2-p.rsi3)+(p.rsi3-p.rsi4))/3.0 prior_delta_3_avg,
    ((p.rsi0-p.rsi1) - (((p.rsi1-p.rsi2)+(p.rsi2-p.rsi3)+(p.rsi3-p.rsi4))/3.0)) rsi_accel,
    case when (p.rsi0-p.rsi1)>0 and (((p.rsi1-p.rsi2)+(p.rsi2-p.rsi3)+(p.rsi3-p.rsi4))/3.0)<0 then 1 else 0 end inflection_flag
  from v_vti_sector_universe_5b s
  join piv p on s.ticker=p.ticker
  left join vti_daily_enriched_latest e on s.ticker=e.ticker
  left join v_vti_factor_production_scores_5b f on s.ticker=f.ticker
  left join daily_52w d on s.ticker=d.ticker
  left join latest_daily ld on s.ticker=ld.ticker
  where s.market_cap >= 5000000000
    and case when ld.daily_ts > p.ts0 then ld.daily_close else p.close0 end < ?
    and s.sector is not null and s.sector <> ''
    and p.n >= 5
)
select * from base
"""
    df = con.execute(q, [price_filter]).fetchdf()
    con.close()
    return df
