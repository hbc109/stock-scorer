#!/usr/bin/env python3
"""
Stock Assessment Scorer
Evaluates stocks on: Growth Potential, Relative Strength vs Peers,
Market Strength/Popularity, and Narrative & Sentiment.
Usage: python3 stock_scorer.py AAPL [MSFT GOOG ...]
"""

import sys
import time
import yfinance as yf
import pandas as pd

# Yahoo Finance silently rate-limits yfinance — sometimes returning HTTP 429
# (Too Many Requests), sometimes 426 ("Upgrade Required"), sometimes a stub
# empty info dict. These helpers retry on those signals and surface a clear
# error if we still can't get usable data.
RATE_LIMIT_HINTS = ("upgrade required", "rate limit", "too many requests", "429", "426")


def _looks_like_rate_limit(err: BaseException) -> bool:
    return any(h in str(err).lower() for h in RATE_LIMIT_HINTS)


def safe_info(ticker, symbol: str = "?", retries: int = 3, base_delay: float = 1.5) -> dict:
    """Fetch ticker.info with retry on rate-limit / transient errors.
    Raises RuntimeError with a clear message after retries are exhausted.
    """
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            info = ticker.info
        except Exception as e:  # network / parser / yfinance internal
            last_err = e
            if attempt < retries and _looks_like_rate_limit(e):
                time.sleep(base_delay * attempt)
                continue
            if attempt < retries:
                time.sleep(base_delay * attempt)
                continue
            break
        # yfinance sometimes returns {} or just {"trailingPegRatio": None}
        # when rate-limited rather than raising.
        if info and len(info) > 5:
            return info
        last_err = RuntimeError(f"empty info dict (size={len(info) if info else 0})")
        if attempt < retries:
            time.sleep(base_delay * attempt)
    raise RuntimeError(
        f"Yahoo Finance is rate-limiting or unreachable for {symbol}. "
        f"Try again in a minute. (last error: {last_err})"
    )

# ── Sentiment keyword lists ──────────────────────────────────────────────

POSITIVE_WORDS = {
    "surge", "surges", "soar", "soars", "jump", "jumps", "rally", "rallies",
    "gain", "gains", "rise", "rises", "bull", "bullish", "upgrade", "upgrades",
    "beat", "beats", "record", "strong", "growth", "profit", "boom", "optimism",
    "breakout", "outperform", "buy", "positive", "upbeat", "momentum", "recover",
    "recovery", "high", "highs", "top", "tops", "win", "wins", "success",
}

NEGATIVE_WORDS = {
    "drop", "drops", "fall", "falls", "crash", "crashes", "plunge", "plunges",
    "decline", "declines", "loss", "losses", "bear", "bearish", "downgrade",
    "downgrades", "miss", "misses", "weak", "warning", "risk", "sell", "selloff",
    "fear", "fears", "slump", "slumps", "cut", "cuts", "layoff", "layoffs",
    "recession", "debt", "lawsuit", "fraud", "negative", "concern", "trouble",
    "low", "lows", "worst", "bankruptcy", "default",
}


def safe_get(info, key, default=None):
    """Safely get a value from info dict."""
    val = info.get(key, default)
    if val is None:
        return default
    return val


# ── 1. Growth Potential (0–100) ──────────────────────────────────────────

def score_growth_tier(pct):
    """Score a growth percentage on a 0-20 tier."""
    if pct is None:
        return 0
    if pct > 0.20:
        return 20
    if pct > 0.10:
        return 15
    if pct > 0.05:
        return 10
    if pct > 0:
        return 5
    return 0


def calc_growth_score(ticker):
    """Calculate growth potential score (0–100)."""
    info = ticker.info
    details = {}

    # Revenue growth YoY
    rev_growth = None
    try:
        fins = ticker.financials
        if fins is not None and not fins.empty and "Total Revenue" in fins.index:
            revs = fins.loc["Total Revenue"].dropna().sort_index()
            if len(revs) >= 2:
                rev_growth = (revs.iloc[-1] - revs.iloc[-2]) / abs(revs.iloc[-2])
    except Exception:
        pass
    rev_score = score_growth_tier(rev_growth)
    details["Revenue Growth YoY"] = (f"{rev_growth:.1%}" if rev_growth is not None else "N/A", rev_score)

    # EPS growth YoY (from income statement)
    eps_growth = None
    try:
        inc = ticker.income_stmt
        if inc is not None and not inc.empty and "Net Income" in inc.index:
            ni = inc.loc["Net Income"].dropna().sort_index()
            if len(ni) >= 2:
                eps_growth = (ni.iloc[-1] - ni.iloc[-2]) / abs(ni.iloc[-2])
    except Exception:
        pass
    # Fallback: trailing vs forward EPS
    if eps_growth is None:
        trailing = safe_get(info, "trailingEps")
        forward = safe_get(info, "forwardEps")
        if trailing and forward and trailing != 0:
            eps_growth = (forward - trailing) / abs(trailing)
    eps_score = score_growth_tier(eps_growth)
    details["EPS Growth"] = (f"{eps_growth:.1%}" if eps_growth is not None else "N/A", eps_score)

    # Forward EPS vs Trailing EPS
    fwd_eps_growth = None
    trailing_eps = safe_get(info, "trailingEps")
    forward_eps = safe_get(info, "forwardEps")
    if trailing_eps and forward_eps and trailing_eps != 0:
        fwd_eps_growth = (forward_eps - trailing_eps) / abs(trailing_eps)
    fwd_score = score_growth_tier(fwd_eps_growth)
    details["Forward vs Trailing EPS"] = (f"{fwd_eps_growth:.1%}" if fwd_eps_growth is not None else "N/A", fwd_score)

    # PEG Ratio
    peg = safe_get(info, "pegRatio")
    if peg is not None and peg > 0:
        if peg < 1:
            peg_score = 20
        elif peg < 1.5:
            peg_score = 15
        elif peg < 2:
            peg_score = 10
        else:
            peg_score = 5
    else:
        peg_score = 0
    details["PEG Ratio"] = (f"{peg:.2f}" if peg is not None else "N/A", peg_score)

    # Free Cash Flow growth
    fcf_growth = None
    try:
        cf = ticker.cashflow
        if cf is not None and not cf.empty and "Free Cash Flow" in cf.index:
            fcfs = cf.loc["Free Cash Flow"].dropna().sort_index()
            if len(fcfs) >= 2:
                fcf_growth = (fcfs.iloc[-1] - fcfs.iloc[-2]) / abs(fcfs.iloc[-2])
    except Exception:
        pass
    fcf_score = score_growth_tier(fcf_growth)
    details["FCF Growth YoY"] = (f"{fcf_growth:.1%}" if fcf_growth is not None else "N/A", fcf_score)

    total = rev_score + eps_score + fwd_score + peg_score + fcf_score
    return total, details


# ── 2. Relative Strength vs Peers (0–100) ───────────────────────────────

def get_peer_tickers(info, limit=10):
    """Get peer tickers from the same sector/industry."""
    # yfinance doesn't have a direct peer API, so we use a curated approach
    # Try to get from info if available
    sector = safe_get(info, "sector", "")
    industry = safe_get(info, "industry", "")

    # Common sector-based peer groups (fallback)
    SECTOR_PEERS = {
        "Technology": ["AAPL", "MSFT", "GOOG", "META", "NVDA", "AVGO", "CRM", "ADBE", "ORCL", "CSCO"],
        "Healthcare": ["JNJ", "UNH", "PFE", "ABBV", "MRK", "TMO", "ABT", "LLY", "BMY", "AMGN"],
        "Financial Services": ["JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW", "AXP", "USB"],
        "Consumer Cyclical": ["AMZN", "TSLA", "HD", "NKE", "MCD", "SBUX", "TGT", "LOW", "TJX", "BKNG"],
        "Communication Services": ["GOOG", "META", "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS", "SPOT", "SNAP"],
        "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "HES"],
        "Industrials": ["CAT", "HON", "UPS", "BA", "RTX", "DE", "LMT", "GE", "MMM", "UNP"],
        "Consumer Defensive": ["PG", "KO", "PEP", "WMT", "COST", "PM", "MO", "CL", "MDLZ", "KHC"],
        "Real Estate": ["AMT", "PLD", "CCI", "EQIX", "SPG", "O", "PSA", "DLR", "WELL", "AVB"],
        "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "XEL", "ED", "WEC"],
        "Basic Materials": ["LIN", "APD", "SHW", "ECL", "FCX", "NEM", "NUE", "DOW", "DD", "PPG"],
    }

    peers = SECTOR_PEERS.get(sector, [])
    return peers[:limit]


def calc_relative_score(ticker, symbol):
    """Calculate relative strength vs peers (0–100)."""
    info = ticker.info
    peers = get_peer_tickers(info)
    details = {}

    # Remove self from peers
    peers = [p for p in peers if p.upper() != symbol.upper()]
    if not peers:
        details["Peers"] = ("No peers found", 0)
        return 50, details  # neutral if no peers

    # Collect metrics for target and peers
    metrics_to_compare = {
        "P/E": "trailingPE",
        "P/B": "priceToBook",
        "Revenue Growth": "revenueGrowth",
        "ROE": "returnOnEquity",
        "Profit Margin": "profitMargins",
    }

    target_vals = {}
    for label, key in metrics_to_compare.items():
        target_vals[label] = safe_get(info, key)

    peer_data = {label: [] for label in metrics_to_compare}

    # Fetch peer data (limit to 5 peers for speed)
    sample_peers = peers[:5]
    details["Peers Compared"] = (", ".join(sample_peers), 0)

    for p in sample_peers:
        try:
            pi = yf.Ticker(p).info
            for label, key in metrics_to_compare.items():
                val = safe_get(pi, key)
                if val is not None:
                    peer_data[label].append(val)
        except Exception:
            continue

    # Calculate percentile rank for each metric
    percentile_scores = []
    for label in metrics_to_compare:
        tv = target_vals[label]
        pv = peer_data[label]
        if tv is None or not pv:
            details[label] = ("N/A", "-")
            continue

        all_vals = sorted(pv + [tv])
        # For P/E and P/B, lower is better (reverse rank)
        if label in ("P/E", "P/B"):
            rank = 1 - (all_vals.index(tv) / len(all_vals))
        else:
            rank = all_vals.index(tv) / max(len(all_vals) - 1, 1)

        pct = round(rank * 100)
        percentile_scores.append(pct)
        details[label] = (f"{tv:.2f} (pctl: {pct}%)", pct)

    if percentile_scores:
        total = round(sum(percentile_scores) / len(percentile_scores))
    else:
        total = 50

    return total, details


# ── 3. Market Strength / Popularity (0–100) ─────────────────────────────

def calc_market_score(ticker):
    """Calculate market strength/popularity score (0–100)."""
    info = ticker.info
    details = {}

    # 52-week price position (0–25)
    high52 = safe_get(info, "fiftyTwoWeekHigh")
    low52 = safe_get(info, "fiftyTwoWeekLow")
    price = safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice")
    if high52 and low52 and price and high52 != low52:
        pos = (price - low52) / (high52 - low52)
        pos_score = round(pos * 25)
        details["52wk Position"] = (f"{pos:.0%} (Price: {price:.2f})", pos_score)
    else:
        pos_score = 0
        details["52wk Position"] = ("N/A", 0)

    # Volume trend (0–20)
    avg_vol = safe_get(info, "averageVolume")
    avg_vol_10d = safe_get(info, "averageVolume10days")
    if avg_vol and avg_vol_10d and avg_vol > 0:
        vol_ratio = avg_vol_10d / avg_vol
        if vol_ratio > 1.5:
            vol_score = 20
        elif vol_ratio > 1.2:
            vol_score = 15
        elif vol_ratio > 1.0:
            vol_score = 10
        else:
            vol_score = 5
        details["Volume Trend"] = (f"{vol_ratio:.2f}x avg", vol_score)
    else:
        vol_score = 5
        details["Volume Trend"] = ("N/A", 5)

    # Analyst recommendation (0–25)
    rec = safe_get(info, "recommendationKey", "none")
    rec_scores = {"strong_buy": 25, "buy": 20, "hold": 10, "underperform": 5, "sell": 0}
    rec_score = rec_scores.get(rec, 10)
    details["Analyst Rec"] = (rec, rec_score)

    # Institutional holding (0–15)
    inst_pct = safe_get(info, "heldPercentInstitutions")
    if inst_pct is not None:
        if inst_pct > 0.60:
            inst_score = 15
        elif inst_pct > 0.40:
            inst_score = 10
        elif inst_pct > 0.20:
            inst_score = 5
        else:
            inst_score = 2
        details["Institutional %"] = (f"{inst_pct:.1%}", inst_score)
    else:
        inst_score = 5
        details["Institutional %"] = ("N/A", 5)

    # Short % of float (0–15) — lower is better
    short_pct = safe_get(info, "shortPercentOfFloat")
    if short_pct is not None:
        if short_pct < 0.05:
            short_score = 15
        elif short_pct < 0.10:
            short_score = 10
        else:
            short_score = 5
        details["Short % Float"] = (f"{short_pct:.1%}", short_score)
    else:
        short_score = 10
        details["Short % Float"] = ("N/A", 10)

    total = pos_score + vol_score + rec_score + inst_score + short_score
    return total, details


# ── 4. Narrative & Sentiment (0–100) ────────────────────────────────────

def analyze_headline_sentiment(title):
    """Score a headline: +1 positive, -1 negative, 0 neutral."""
    words = set(title.lower().split())
    pos = len(words & POSITIVE_WORDS)
    neg = len(words & NEGATIVE_WORDS)
    if pos > neg:
        return 1
    if neg > pos:
        return -1
    return 0


def calc_narrative_score(ticker):
    """Calculate narrative & sentiment score (0–100)."""
    info = ticker.info
    details = {}

    # Fetch news
    try:
        news = ticker.news
        if isinstance(news, list):
            articles = news
        else:
            articles = []
    except Exception:
        articles = []

    num_articles = len(articles)
    details["News Articles"] = (str(num_articles), 0)

    # Sentiment analysis
    sentiments = []
    for article in articles:
        title = article.get("title", "") or article.get("content", {}).get("title", "")
        if title:
            sentiments.append(analyze_headline_sentiment(title))

    if sentiments:
        avg_sentiment = sum(sentiments) / len(sentiments)
        pos_pct = sentiments.count(1) / len(sentiments)
        neg_pct = sentiments.count(-1) / len(sentiments)
    else:
        avg_sentiment = 0
        pos_pct = 0
        neg_pct = 0

    # Sentiment score (0–40)
    sent_score = round(max(0, min(40, (avg_sentiment + 1) * 20)))
    details["Sentiment"] = (f"Pos:{pos_pct:.0%} Neg:{neg_pct:.0%} (avg:{avg_sentiment:+.2f})", sent_score)

    # News volume score (0–30)
    if num_articles >= 15:
        vol_score = 30
    elif num_articles >= 10:
        vol_score = 25
    elif num_articles >= 5:
        vol_score = 15
    elif num_articles >= 1:
        vol_score = 10
    else:
        vol_score = 0
    details["News Volume"] = (f"{num_articles} articles", vol_score)

    # Narrative stage classification (0–30)
    # Combine: sentiment + price momentum + news volume
    price = safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice")
    high52 = safe_get(info, "fiftyTwoWeekHigh")
    low52 = safe_get(info, "fiftyTwoWeekLow")

    price_position = 0.5
    if price and high52 and low52 and high52 != low52:
        price_position = (price - low52) / (high52 - low52)

    # Determine narrative stage
    if num_articles < 3 and abs(avg_sentiment) < 0.2:
        stage = "Under the Radar"
        stage_score = 10
    elif avg_sentiment > 0.2 and num_articles < 8 and price_position < 0.6:
        stage = "Early"
        stage_score = 25
    elif avg_sentiment > 0.1 and num_articles >= 5 and 0.4 < price_position < 0.85:
        stage = "Momentum"
        stage_score = 30
    elif avg_sentiment > 0 and num_articles >= 8 and price_position > 0.8:
        stage = "Peak Hype"
        stage_score = 20
    elif avg_sentiment < 0:
        stage = "Declining"
        stage_score = 5
    else:
        stage = "Neutral"
        stage_score = 15

    details["Narrative Stage"] = (stage, stage_score)

    total = sent_score + vol_score + stage_score
    return min(total, 100), details


# ── Report Generation ────────────────────────────────────────────────────

def print_section(title, score, details):
    """Print a scoring section."""
    print(f"\n  {'─' * 50}")
    print(f"  {title}: {score}/100")
    print(f"  {'─' * 50}")
    for label, (value, pts) in details.items():
        pts_str = f"({pts}pts)" if isinstance(pts, int) else ""
        print(f"    {label:<25} {str(value):<25} {pts_str}")


def get_rating(score):
    """Convert overall score to a rating."""
    if score >= 75:
        return "STRONG BUY"
    if score >= 60:
        return "BUY"
    if score >= 40:
        return "HOLD"
    if score >= 25:
        return "UNDERPERFORM"
    return "SELL"


def assess_stock(symbol):
    """Run full assessment on a single stock."""
    symbol = normalize_ticker(symbol)
    print(f"\n{'═' * 60}")
    print(f"  STOCK ASSESSMENT: {symbol.upper()}")
    print(f"{'═' * 60}")

    ticker = yf.Ticker(symbol)
    info = safe_info(ticker, symbol)

    if is_etf_or_fund(info):
        quote_type = safe_get(info, "quoteType", "ETF")
        name = safe_get(info, "shortName", symbol)
        print(f"  {name}")
        print(f"\n  ⚠ WARNING: {symbol.upper()} is a {quote_type}, not an individual stock.")
        print(f"  Fundamental scoring is not applicable. Skipping.\n")
        return None

    name = safe_get(info, "shortName", symbol)
    sector = safe_get(info, "sector", "N/A")
    industry = safe_get(info, "industry", "N/A")
    price = safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice", 0)
    mcap = safe_get(info, "marketCap", 0)

    print(f"  {name}")
    print(f"  Sector: {sector} | Industry: {industry}")
    print(f"  Price: ${price:.2f} | Market Cap: ${mcap / 1e9:.1f}B" if mcap else f"  Price: ${price:.2f}")

    # Calculate all scores
    growth_score, growth_details = calc_growth_score(ticker)
    relative_score, relative_details = calc_relative_score(ticker, symbol)
    market_score, market_details = calc_market_score(ticker)
    narrative_score, narrative_details = calc_narrative_score(ticker)

    print_section("GROWTH POTENTIAL", growth_score, growth_details)
    print_section("RELATIVE STRENGTH", relative_score, relative_details)
    print_section("MARKET STRENGTH", market_score, market_details)
    print_section("NARRATIVE & SENTIMENT", narrative_score, narrative_details)

    # Overall score (weighted)
    overall = round(
        growth_score * 0.30
        + relative_score * 0.25
        + market_score * 0.25
        + narrative_score * 0.20
    )
    rating = get_rating(overall)

    print(f"\n  {'═' * 50}")
    print(f"  OVERALL SCORE: {overall}/100  →  {rating}")
    print(f"  {'═' * 50}")
    print(f"    Growth:    {growth_score:3}/100 (×0.30 = {growth_score * 0.30:.0f})")
    print(f"    Relative:  {relative_score:3}/100 (×0.25 = {relative_score * 0.25:.0f})")
    print(f"    Market:    {market_score:3}/100 (×0.25 = {market_score * 0.25:.0f})")
    print(f"    Narrative: {narrative_score:3}/100 (×0.20 = {narrative_score * 0.20:.0f})")
    print()

    return {
        "symbol": symbol.upper(),
        "name": name,
        "growth": growth_score,
        "relative": relative_score,
        "market": market_score,
        "narrative": narrative_score,
        "overall": overall,
        "rating": rating,
    }


NON_STOCK_TYPES = {"ETF", "MUTUALFUND", "INDEX", "CURRENCY", "CRYPTOCURRENCY", "FUTURE"}


def normalize_ticker(symbol):
    """Normalize ticker format. E.g. 00857.HK → 0857.HK for Yahoo Finance."""
    symbol = symbol.strip().upper()
    if "." in symbol:
        code, exchange = symbol.rsplit(".", 1)
        if exchange == "HK":
            # HK tickers: Yahoo uses 4-digit max (e.g. 0857.HK not 00857.HK)
            code = code.lstrip("0") or "0"
            code = code.zfill(4)
            symbol = f"{code}.{exchange}"
    return symbol


def is_etf_or_fund(info):
    """Check if the ticker is an ETF, fund, or other non-stock instrument."""
    quote_type = safe_get(info, "quoteType", "")
    return (quote_type or "").upper() in NON_STOCK_TYPES


def assess_stock_data(symbol):
    """Return assessment data as a dict (no printing). Used by web UI."""
    symbol = normalize_ticker(symbol)
    ticker = yf.Ticker(symbol)
    info = safe_info(ticker, symbol)

    name = safe_get(info, "shortName", symbol)
    sector = safe_get(info, "sector", "N/A")
    industry = safe_get(info, "industry", "N/A")
    price = safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice", 0)
    mcap = safe_get(info, "marketCap", 0)
    quote_type = safe_get(info, "quoteType", "EQUITY")

    if is_etf_or_fund(info):
        return {
            "symbol": symbol.upper(),
            "name": name,
            "sector": sector,
            "industry": industry,
            "price": round(price, 2) if price else 0,
            "marketCap": mcap,
            "quoteType": quote_type,
            "warning": f"{symbol.upper()} is a {quote_type}, not an individual stock. "
                       "Fundamental scoring is not applicable.",
            "scores": None,
            "rating": None,
            "details": None,
        }

    growth_score, growth_details = calc_growth_score(ticker)
    relative_score, relative_details = calc_relative_score(ticker, symbol)
    market_score, market_details = calc_market_score(ticker)
    narrative_score, narrative_details = calc_narrative_score(ticker)

    overall = round(
        growth_score * 0.30
        + relative_score * 0.25
        + market_score * 0.25
        + narrative_score * 0.20
    )
    rating = get_rating(overall)

    def details_to_list(details):
        return [
            {"metric": k, "value": str(v), "points": p}
            for k, (v, p) in details.items()
        ]

    return {
        "symbol": symbol.upper(),
        "name": name,
        "sector": sector,
        "industry": industry,
        "price": round(price, 2) if price else 0,
        "marketCap": mcap,
        "quoteType": quote_type,
        "warning": None,
        "scores": {
            "growth": growth_score,
            "relative": relative_score,
            "market": market_score,
            "narrative": narrative_score,
            "overall": overall,
        },
        "rating": rating,
        "details": {
            "growth": details_to_list(growth_details),
            "relative": details_to_list(relative_details),
            "market": details_to_list(market_details),
            "narrative": details_to_list(narrative_details),
        },
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 stock_scorer.py TICKER [TICKER2 ...]")
        print("Example: python3 stock_scorer.py AAPL MSFT GOOG")
        sys.exit(1)

    symbols = sys.argv[1:]
    results = []

    for sym in symbols:
        try:
            result = assess_stock(sym)
            if result is not None:
                results.append(result)
        except Exception as e:
            print(f"\nError assessing {sym}: {e}")

    # Summary comparison if multiple stocks
    if len(results) > 1:
        print(f"\n{'═' * 60}")
        print("  COMPARISON SUMMARY")
        print(f"{'═' * 60}")
        print(f"  {'Ticker':<8} {'Growth':>8} {'Relative':>10} {'Market':>8} {'Narr.':>8} {'Overall':>9}  Rating")
        print(f"  {'─' * 58}")
        for r in sorted(results, key=lambda x: x["overall"], reverse=True):
            print(
                f"  {r['symbol']:<8} {r['growth']:>8} {r['relative']:>10} "
                f"{r['market']:>8} {r['narrative']:>8} {r['overall']:>9}  {r['rating']}"
            )
        print()


if __name__ == "__main__":
    main()
