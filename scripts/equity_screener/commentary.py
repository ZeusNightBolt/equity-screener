import datetime as dt
import html
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd

from .config import DATA_DIR
from .selection import build_diversified_top10

def call_llm(prompt: str) -> str:
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    if deepseek_key:
        url = "https://api.deepseek.com/chat/completions"
        headers = {"Authorization": f"Bearer {deepseek_key}", "Content-Type": "application/json"}
        model = "deepseek-chat"
    elif openrouter_key:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/ZeusNightBolt/equity-screener",
            "X-Title": "Equity Screener",
        }
        model = "deepseek/deepseek-chat-v3-0324"
    else:
        return "LLM unavailable: DEEPSEEK_API_KEY and OPENROUTER_API_KEY were not found."

    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a hedge-fund research assistant. Be concise, skeptical, and compliance-safe. Do not give investment advice. Analyze the long setup using only supplied data; clearly label unknowns.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 650,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        return f"LLM call failed: {type(exc).__name__}: {exc}"

def _clean_company_for_query(company: str | None) -> str:
    if not company:
        return ""
    text = re.sub(r"\b(Common Stock|Class [A-Z]|Inc\.?|Corporation|Corp\.?|Ltd\.?|PLC|Company|Co\.?)\b", " ", str(company), flags=re.I)
    return re.sub(r"\s+", " ", text).strip()

def _compact_text(text: str, max_chars: int = 1600) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"\s+", " ", text).strip()
    # Trim common boilerplate tails before they overwhelm actual commentary.
    for marker in ["Terms of Use", "Privacy Policy", "Cookie Policy", "All rights reserved"]:
        idx = text.lower().find(marker.lower())
        if idx > 700:
            text = text[:idx]
            break
    return text[:max_chars].strip()

def _is_bad_commentary_url(result_url: str) -> bool:
    parsed = urllib.parse.urlparse(result_url)
    domain = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()
    bad_domains = ("finviz.com", "barchart.com", "stockcharts.com", "google.com", "bing.com", "duckduckgo.com")
    bad_paths = ("/quote/", "/symbol/", "/market-data/quotes/", "/research-ratings", "/analysis/", "/analyst-ratings/", "expert-time")
    if any(bad in domain for bad in bad_domains):
        return True
    if domain == "finance.yahoo.com" and not (path.startswith("/news/") or path.startswith("/markets/") or path.startswith("/sectors/")):
        return True
    if domain == "seekingalpha.com" and (path.startswith("/symbol/") or path.endswith("/earnings")):
        return True
    return any(bad in path for bad in bad_paths)

def yahoo_finance_news_search(ticker: str, max_results: int = 8) -> list[dict]:
    url = "https://query1.finance.yahoo.com/v1/finance/search?" + urllib.parse.urlencode({
        "q": ticker,
        "quotesCount": 0,
        "newsCount": max_results,
    })
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return []
    out = []
    for news in payload.get("news", []):
        link = str(news.get("link") or "").strip()
        title = _compact_text(str(news.get("title") or ""), 180)
        if not link.startswith(("http://", "https://")) or _is_bad_commentary_url(link):
            continue
        title_l = title.lower()
        if ticker.lower() not in title_l and "$" + ticker.lower() not in title_l:
            # Keep Yahoo's broad ticker feed honest; unrelated sector articles are usually not ticker-specific commentary.
            continue
        out.append({
            "title": title,
            "url": link,
            "snippet": _compact_text(str(news.get("summary") or news.get("publisher") or ""), 700),
            "query": f"Yahoo Finance news API: {ticker}",
        })
    return out

def tavily_commentary_search(ticker: str, company: str | None, max_results: int = 8) -> list[dict]:
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return []
    company_q = _clean_company_for_query(company)
    query = (
        f'{ticker} {company_q} stock latest earnings analyst commentary outlook '
        '-site:finance.yahoo.com/quote -site:seekingalpha.com/symbol'
    )
    body = json.dumps({
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "advanced",
        "topic": "news",
        "include_answer": False,
    }).encode("utf-8")
    try:
        req = urllib.request.Request("https://api.tavily.com/search", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return []
    found = []
    for result in payload.get("results", []):
        result_url = str(result.get("url") or "").strip()
        if not result_url.startswith(("http://", "https://")) or _is_bad_commentary_url(result_url):
            continue
        found.append({
            "title": _compact_text(str(result.get("title") or ""), 180),
            "url": result_url,
            "snippet": _compact_text(str(result.get("content") or ""), 700),
            "query": query,
        })
    return found

def search_commentary_web(ticker: str, company: str | None, max_results: int = 8) -> list[dict]:
    """Search for external stock commentary URLs. Prefer ticker-specific Yahoo news, then Tavily, then self-hosted SearXNG."""
    found: list[dict] = []
    seen_urls: set[str] = set()
    for hit in yahoo_finance_news_search(ticker, max_results=max_results):
        if hit["url"] not in seen_urls:
            seen_urls.add(hit["url"])
            found.append(hit)
        if len(found) >= max_results:
            return found
    for hit in tavily_commentary_search(ticker, company, max_results=max_results):
        if hit["url"] not in seen_urls:
            seen_urls.add(hit["url"])
            found.append(hit)
        if len(found) >= max_results:
            return found

    searxng = os.environ.get("SEARXNG_URL", "http://localhost:8888").rstrip("/")
    company_q = _clean_company_for_query(company)
    queries = [
        f'"{ticker}" "{company_q}" stock news earnings analyst outlook -site:finance.yahoo.com/quote -site:seekingalpha.com/symbol',
        f'"{ticker}" "{company_q}" why shares stock earnings guidance',
        f'"{ticker}" "{company_q}" downgrade upgrade analyst stock outlook',
    ]
    for query in queries:
        params = urllib.parse.urlencode({"q": query, "format": "json", "language": "en-US"})
        url = f"{searxng}/search?{params}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception:
            continue
        for result in payload.get("results", []):
            result_url = str(result.get("url") or "").strip()
            if not result_url.startswith(("http://", "https://")) or result_url in seen_urls or _is_bad_commentary_url(result_url):
                continue
            seen_urls.add(result_url)
            found.append({
                "title": _compact_text(str(result.get("title") or ""), 180),
                "url": result_url,
                "snippet": _compact_text(str(result.get("content") or result.get("snippet") or ""), 700),
                "query": query,
            })
            if len(found) >= max_results:
                return found
    return found

def extract_commentary_source(source: dict, ticker: str, company: str | None) -> dict | None:
    """Fetch and extract readable text from a commentary URL. Falls back to search snippet if extraction fails."""
    url = source.get("url")
    if not url:
        return None
    text = ""
    title = source.get("title") or ""
    try:
        req = urllib.request.Request(str(url), headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 AppleWebKit/537.36 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read(1_500_000).decode("utf-8", errors="replace")
        try:
            from readability import Document
            from html2text import html2text
            doc = Document(raw)
            title = title or doc.short_title() or doc.title()
            text = html2text(doc.summary())
        except Exception:
            raw = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", raw)
            text = re.sub(r"(?s)<[^>]+>", " ", raw)
    except Exception:
        text = source.get("snippet") or ""
    excerpt = _compact_text(text, 1800)
    snippet = _compact_text(source.get("snippet") or "", 450)
    company_token = (_clean_company_for_query(company).split(" ") or [""])[0].lower()
    haystack = f"{title} {snippet} {excerpt}".lower()
    ticker_re = re.compile(rf"(?<![a-z0-9])\$?{re.escape(ticker.lower())}(?![a-z0-9])")
    if not ticker_re.search(haystack) and (company_token and company_token not in haystack):
        return None
    if len(excerpt) < 240 and len(snippet) < 120:
        return None
    return {
        "title": _compact_text(title, 180) or "Untitled source",
        "url": str(url),
        "excerpt": excerpt if len(excerpt) >= 240 else snippet,
        "search_snippet": snippet,
    }

def collect_web_commentary(row: pd.Series, max_sources: int = 3) -> list[dict]:
    ticker = str(row["ticker"])
    company = row.get("company")
    sources = []
    for hit in search_commentary_web(ticker, company, max_results=10):
        extracted = extract_commentary_source(hit, ticker, company)
        if extracted:
            sources.append(extracted)
        if len(sources) >= max_sources:
            break
    return sources

def analyze_top_inflections(df: pd.DataFrame, top_n: int, force_refresh: bool) -> list[dict]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = DATA_DIR / "llm_analysis.json"
    cache = {}
    if cache_path.exists() and not force_refresh:
        try:
            cache = {item["ticker"]: item for item in json.loads(cache_path.read_text())}
        except Exception:
            cache = {}

    candidates = build_diversified_top10(df, 3).head(top_n)
    analyses = []
    for _, row in candidates.iterrows():
        ticker = str(row["ticker"])
        cache_key = f"web-v4:{ticker}:{row['ts0']}:{round(float(row['opportunity_score']), 2)}:{row.get('primary_strategy')}"
        cached = cache.get(ticker)
        if cached and cached.get("cache_key") == cache_key and cached.get("sources"):
            analyses.append(cached)
            continue
        payload = {
            "ticker": ticker,
            "company": row.get("company"),
            "sector": row.get("sector"),
            "industry": row.get("industry"),
            "primary_strategy": row.get("primary_strategy"),
            "price": round(float(row.get("display_close")), 4),
            "market_cap_bn": round(float(row.get("market_cap")) / 1e9, 2),
            "opportunity_score": round(float(row.get("opportunity_score")), 1),
            "rsi_value_score": round(float(row.get("rsi_value_score")), 1),
            "squeeze_laggard_score": round(float(row.get("squeeze_laggard_score")), 1),
            "value_laggard_score": round(float(row.get("value_laggard_score")), 1),
            "composite_value_score": round(float(row.get("composite_value_score")), 1),
            "rsi_acceleration_score": round(float(row.get("rsi_acceleration_score")), 1),
            "rsi_current": round(float(row.get("rsi0")), 1),
            "rsi_delta_1": round(float(row.get("rsi_delta_1")), 1),
            "prior_rsi_delta_3_bar_avg": round(float(row.get("prior_delta_3_avg")), 1),
            "rsi_acceleration": round(float(row.get("rsi_accel")), 1),
            "short_pct_float": None if pd.isna(row.get("short_pct_float")) else round(float(row.get("short_pct_float")), 1),
            "from_52w_low_pct": None if pd.isna(row.get("from_52w_low_pct")) else round(float(row.get("from_52w_low_pct")), 1),
            "from_52w_high_pct": None if pd.isna(row.get("from_52w_high_pct")) else round(float(row.get("from_52w_high_pct")), 1),
            "ret_1m_pct": None if pd.isna(row.get("ret_1m_pct")) else round(float(row.get("ret_1m_pct")), 1),
            "sector_ret_1m_median": None if pd.isna(row.get("sector_ret_1m_median")) else round(float(row.get("sector_ret_1m_median")), 1),
            "peer_lag_1m_pct": None if pd.isna(row.get("peer_lag_1m_pct")) else round(float(row.get("peer_lag_1m_pct")), 1),
            "forward_pe": None if pd.isna(row.get("yf_forward_pe")) else round(float(row.get("yf_forward_pe")), 2),
            "trailing_pe": None if pd.isna(row.get("yf_trailing_pe")) else round(float(row.get("yf_trailing_pe")), 2),
            "price_to_book": None if pd.isna(row.get("yf_price_to_book")) else round(float(row.get("yf_price_to_book")), 2),
            "peg": None if pd.isna(row.get("yf_peg_ratio")) else round(float(row.get("yf_peg_ratio")), 2),
            "sentiment_score": None if pd.isna(row.get("sentiment_score")) else round(float(row.get("sentiment_score")), 2),
        }
        web_sources = [] if (cached and cached.get("cache_key") == cache_key and cached.get("sources")) else collect_web_commentary(row, max_sources=3)
        source_block = "\n\n".join(
            f"[{i}] {src['title']}\nURL: {src['url']}\nExcerpt: {src['excerpt']}"
            for i, src in enumerate(web_sources, 1)
        ) or "No reliable external commentary sources were extracted."
        prompt = (
            "Analyze this candidate as a possible LONG setup for a research dashboard, but do NOT merely restate the RSI/price chart. "
            "Use the web-extracted source excerpts as the primary qualitative input. The warehouse metrics are only context. "
            "Cite external commentary inline as [1], [2], etc. If the source excerpts do not support a claim, say it is unknown. "
            "Return exactly 5 bullets with labels: External commentary, Why it can work, What can break it, Confirming evidence to watch, Bottom line. "
            "Be specific, skeptical, and compliance-safe. No trade recommendation, no target price.\n\n"
            "Warehouse context:\n" + json.dumps(payload, indent=2) + "\n\n"
            "Web-extracted commentary sources:\n" + source_block
        )
        text = call_llm(prompt) if web_sources else (
            "- **External commentary**: No reliable external commentary source was extracted by the web-search pipeline for this run; avoid treating this as a catalyst-backed setup.\n"
            "- **Why it can work**: Unknown from external commentary. Only deterministic warehouse factors are available.\n"
            "- **What can break it**: Unknown from external commentary; fundamental or news-driven risks require manual source review.\n"
            "- **Confirming evidence to watch**: Fresh earnings commentary, management guidance, analyst notes, or company filings that validate the setup.\n"
            "- **Bottom line**: Source coverage failed, so this card should be read as quantitatively flagged but qualitatively unverified."
        )
        item = {
            "ticker": ticker,
            "cache_key": cache_key,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "input": payload,
            "sources": web_sources,
            "analysis": text,
        }
        analyses.append(item)
        time.sleep(0.5)
    cache_path.write_text(json.dumps(analyses, indent=2, default=str))
    return analyses
