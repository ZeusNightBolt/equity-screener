from __future__ import annotations

import pandas as pd

AVOID_TOKENS = ("avoid", "broken momentum")


def _is_avoid_basket(value: object) -> bool:
    text = str(value or "").lower()
    return any(token in text for token in AVOID_TOKENS)


def top10_factor_alignment(top10: pd.DataFrame) -> pd.DataFrame:
    """Classify top-10 opportunity names against their production factor basket.

    A top-10 ticker inside a Broken Momentum / Avoid basket is a divergence: the
    opportunity model likes it, but the factor-basket takeaway is cautionary.
    Other top-10 names are confirmations when their factor basket is not avoid-coded.
    """
    if top10.empty:
        return top10.copy()

    out = top10.copy()
    statuses: list[str] = []
    takeaways: list[str] = []
    severities: list[int] = []

    for _, row in out.iterrows():
        ticker = str(row.get("ticker", "")).strip().upper()
        basket = str(row.get("production_factor_basket", "") or "Unknown factor basket")
        strategy = str(row.get("primary_strategy", "") or "top-10 opportunity")
        opp = row.get("opportunity_score")
        opp_txt = "unknown" if pd.isna(opp) else f"{float(opp):.0f}"

        if _is_avoid_basket(basket):
            statuses.append("DIVERGENCE")
            severities.append(3)
            takeaways.append(
                f"{ticker} top-10 opportunity score {opp_txt} conflicts with {basket}; treat as a risk/reversal candidate, not clean momentum confirmation."
            )
        else:
            statuses.append("CONFIRMATION")
            severities.append(1)
            takeaways.append(
                f"{ticker} top-10 opportunity score {opp_txt} confirms the {basket} factor takeaway via {strategy}."
            )

    out["alignment_status"] = statuses
    out["alignment_severity"] = severities
    out["alignment_takeaway"] = takeaways
    return out.sort_values(["alignment_severity", "opportunity_score"], ascending=[False, False]).reset_index(drop=True)
