import numpy as np
import pandas as pd

from .scoring import pct_score
from .selection import cap_by_sector

def factor_basket_analysis(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty or "production_factor_basket" not in df.columns:
        return pd.DataFrame(), pd.DataFrame()
    work = df[df["production_factor_basket"].notna()].copy()
    if work.empty:
        return pd.DataFrame(), pd.DataFrame()
    g = work.groupby("production_factor_basket", dropna=True)
    baskets = g.agg(
        ticker_count=("ticker", "count"),
        avg_opportunity_score=("opportunity_score", "mean"),
        avg_factor_score=("production_factor_score", "mean"),
        avg_value_score=("composite_value_score", "mean"),
        avg_ret_1w_pct=("ret_1w_pct", "mean"),
        avg_ret_1m_pct=("ret_1m_pct", "mean"),
        avg_ret_3m_pct=("ret_3m_pct", "mean"),
        avg_ret_ytd_pct=("ret_ytd_pct", "mean"),
        avg_rsi=("rsi0", "mean"),
        avg_rsi_delta_1=("rsi_delta_1", "mean"),
        avg_rsi_accel=("rsi_accel", "mean"),
        inflection_count=("is_top_inflection", "sum"),
    ).reset_index().rename(columns={"production_factor_basket": "basket_name"})
    baskets = baskets[baskets["ticker_count"] >= 3].copy()
    if baskets.empty:
        return baskets, pd.DataFrame()
    baskets["lag_score"] = (
        np.maximum(0, -baskets["avg_ret_1m_pct"].fillna(0))
        + 0.50 * np.maximum(0, -baskets["avg_ret_3m_pct"].fillna(0))
        + 0.25 * np.maximum(0, -baskets["avg_ret_ytd_pct"].fillna(0))
    )
    baskets["inflection_score"] = (
        4.0 * np.maximum(0, baskets["avg_rsi_delta_1"].fillna(0))
        + 2.0 * np.maximum(0, baskets["avg_rsi_accel"].fillna(0))
        + 0.5 * np.maximum(0, baskets["avg_ret_1w_pct"].fillna(0))
        + 3.0 * baskets["inflection_count"].fillna(0) / baskets["ticker_count"].clip(lower=1)
    )
    baskets["is_lagged"] = (
        (baskets["avg_ret_1m_pct"].fillna(0) < 0)
        | (baskets["avg_ret_3m_pct"].fillna(0) < 0)
        | (baskets["avg_ret_ytd_pct"].fillna(0) < 0)
    )
    baskets["factor_reversal_score"] = (
        0.60 * pct_score(baskets["lag_score"], lower_is_better=False).fillna(50)
        + 0.40 * pct_score(baskets["inflection_score"], lower_is_better=False).fillna(50)
    )
    # The selected factor must be a true laggard; non-lagged baskets stay visible but cannot win.
    baskets["display_score"] = np.where(baskets["is_lagged"], baskets["factor_reversal_score"], baskets["factor_reversal_score"] * 0.25)
    baskets = baskets.sort_values(["display_score", "factor_reversal_score"], ascending=False).reset_index(drop=True)
    baskets["rank"] = baskets.index + 1
    target_basket = baskets[baskets["is_lagged"]].iloc[0]["basket_name"] if baskets["is_lagged"].any() else baskets.iloc[0]["basket_name"]
    opps = work[work["production_factor_basket"] == target_basket].copy()
    opps["factor_opportunity_score"] = (
        0.35 * opps["rsi_value_score"].fillna(50)
        + 0.25 * opps["composite_value_score"].fillna(50)
        + 0.20 * opps["production_factor_score"].fillna(opps["production_factor_score"].median()) * 10.0
        + 0.20 * opps["peer_lag_score"].fillna(50)
    ).clip(0, 100)
    opps = cap_by_sector(opps.sort_values("factor_opportunity_score", ascending=False), "factor_opportunity_score", 20, 4)
    return baskets, opps

def keyword_theme_analysis(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rank Polygon keyword/thematic baskets like AI Infrastructure, Cloud Software, Oil & Gas."""
    if df.empty or "primary_keyword_factor" not in df.columns:
        return pd.DataFrame(), pd.DataFrame()
    work = df[df["primary_keyword_factor"].notna()].copy()
    if work.empty:
        return pd.DataFrame(), pd.DataFrame()
    g = work.groupby("primary_keyword_factor", dropna=True)
    themes = g.agg(
        ticker_count=("ticker", "count"),
        avg_keyword_score=("primary_keyword_factor_score", "mean"),
        avg_opportunity_score=("opportunity_score", "mean"),
        avg_factor_score=("production_factor_score", "mean"),
        avg_value_score=("composite_value_score", "mean"),
        avg_ret_1w_pct=("ret_1w_pct", "mean"),
        avg_ret_1m_pct=("ret_1m_pct", "mean"),
        avg_ret_3m_pct=("ret_3m_pct", "mean"),
        avg_ret_ytd_pct=("ret_ytd_pct", "mean"),
        avg_rsi=("rsi0", "mean"),
        avg_rsi_delta_1=("rsi_delta_1", "mean"),
        avg_rsi_accel=("rsi_accel", "mean"),
        inflection_count=("is_top_inflection", "sum"),
    ).reset_index().rename(columns={"primary_keyword_factor": "theme_name"})
    themes = themes[themes["ticker_count"] >= 3].copy()
    if themes.empty:
        return themes, pd.DataFrame()
    themes["lag_score"] = (
        np.maximum(0, -themes["avg_ret_1m_pct"].fillna(0))
        + 0.50 * np.maximum(0, -themes["avg_ret_3m_pct"].fillna(0))
        + 0.25 * np.maximum(0, -themes["avg_ret_ytd_pct"].fillna(0))
    )
    themes["inflection_score"] = (
        4.0 * np.maximum(0, themes["avg_rsi_delta_1"].fillna(0))
        + 2.0 * np.maximum(0, themes["avg_rsi_accel"].fillna(0))
        + 0.5 * np.maximum(0, themes["avg_ret_1w_pct"].fillna(0))
        + 3.0 * themes["inflection_count"].fillna(0) / themes["ticker_count"].clip(lower=1)
    )
    themes["is_lagged"] = (
        (themes["avg_ret_1m_pct"].fillna(0) < 0)
        | (themes["avg_ret_3m_pct"].fillna(0) < 0)
        | (themes["avg_ret_ytd_pct"].fillna(0) < 0)
    )
    themes["theme_reversal_score"] = (
        0.50 * pct_score(themes["lag_score"], lower_is_better=False).fillna(50)
        + 0.30 * pct_score(themes["inflection_score"], lower_is_better=False).fillna(50)
        + 0.20 * pct_score(themes["avg_keyword_score"], lower_is_better=False).fillna(50)
    )
    themes["display_score"] = np.where(themes["is_lagged"], themes["theme_reversal_score"], themes["theme_reversal_score"] * 0.25)
    themes = themes.sort_values(["display_score", "theme_reversal_score"], ascending=False).reset_index(drop=True)
    themes["rank"] = themes.index + 1
    target_theme = themes[themes["is_lagged"]].iloc[0]["theme_name"] if themes["is_lagged"].any() else themes.iloc[0]["theme_name"]
    opps = work[work["primary_keyword_factor"] == target_theme].copy()
    keyword_fill = opps["primary_keyword_factor_score"].median() if opps["primary_keyword_factor_score"].notna().any() else 10.0
    opps["theme_opportunity_score"] = (
        0.30 * opps["rsi_value_score"].fillna(50)
        + 0.25 * opps["squeeze_laggard_score"].fillna(50)
        + 0.20 * opps["composite_value_score"].fillna(50)
        + 0.15 * opps["primary_keyword_factor_score"].fillna(keyword_fill).clip(0, 50) * 2.0
        + 0.10 * opps["peer_lag_score"].fillna(50)
    ).clip(0, 100)
    opps = cap_by_sector(opps.sort_values("theme_opportunity_score", ascending=False), "theme_opportunity_score", 20, 4)
    return themes, opps
