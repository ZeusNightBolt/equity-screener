import sys

import numpy as np
import pandas as pd

from .config import MARKET_DATA_DIR

def _load_polygon_client():
    if str(MARKET_DATA_DIR) not in sys.path:
        sys.path.insert(0, str(MARKET_DATA_DIR))
    from polygon_client import PolygonClient
    return PolygonClient(timeout=10, retries=2, max_workers=4)

def enrich_latest_polygon_prices(df: pd.DataFrame, tickers: list[str], client=None) -> pd.DataFrame:
    """Overlay latest Polygon snapshot prices for selected final candidates.

    This is side-effect free and intentionally runs after deterministic scoring:
    rankings remain warehouse-derived, while displayed prices are as fresh as
    Polygon's snapshot endpoint can provide at build time.
    """
    out = df.copy()
    out["warehouse_display_close"] = out.get("display_close", pd.Series(np.nan, index=out.index))
    out["latest_polygon_price"] = np.nan
    out["latest_polygon_price_source"] = None
    out["latest_polygon_price_timestamp"] = None
    out["latest_polygon_price_status"] = None
    if out.empty or not tickers:
        return out
    symbols = list(dict.fromkeys(str(t).upper() for t in tickers if str(t).strip()))
    if not symbols:
        return out
    try:
        price_client = client or _load_polygon_client()
        prices = price_client.latest_prices(symbols)
    except Exception as exc:
        print(f"WARN: Polygon latest-price enrichment skipped: {type(exc).__name__}: {exc}", file=sys.stderr)
        out.loc[out["ticker"].astype(str).str.upper().isin(symbols), "latest_polygon_price_status"] = "SKIPPED"
        return out
    for ticker, payload in prices.items():
        mask = out["ticker"].astype(str).str.upper() == ticker.upper()
        if not mask.any():
            continue
        status = payload.get("status") if isinstance(payload, dict) else "ERROR"
        out.loc[mask, "latest_polygon_price_status"] = status
        if not isinstance(payload, dict) or status != "OK" or payload.get("price") is None:
            continue
        price = float(payload["price"])
        source = str(payload.get("source") or "snapshot")
        out.loc[mask, "latest_polygon_price"] = price
        out.loc[mask, "latest_polygon_price_source"] = source
        out.loc[mask, "latest_polygon_price_timestamp"] = payload.get("timestamp")
        out.loc[mask, "display_close"] = price
        out.loc[mask, "price_source"] = f"polygon.{source}"
    return out
