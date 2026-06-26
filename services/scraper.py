"""
NEPSE price scraper using the official nepalstock.com API
via the `nepse-scraper` PyPI package.

Falls back gracefully per symbol if data is missing.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Lazy-load the scraper so import errors don't crash the app ────────────
def _get_scraper():
    try:
        from nepse_scraper import NepseScraper
        return NepseScraper(verify_ssl=False)
    except Exception as e:
        logger.error(f"Failed to initialise NepseScraper: {e}")
        return None


# ── Fetch all today prices once, then look up per symbol ─────────────────
def _fetch_all_today_prices(scraper) -> dict:
    """
    Returns dict keyed by symbol (uppercase):
    { "NABIL": { ltp, prev_close, change_percent, ... }, ... }
    """
    try:
        records = scraper.get_today_price()   # list of dicts
        if not records:
            return {}

        result = {}
        for r in records:
            sym = (r.get("symbol") or r.get("securitySymbol") or "").upper().strip()
            if not sym:
                continue

            def sf(k):
                v = r.get(k)
                try:
                    return float(v) if v not in (None, "", "N/A") else None
                except Exception:
                    return None

            ltp        = sf("lastTradedPrice") or sf("ltp") or sf("closingPrice")
            prev_close = sf("previousClose")   or sf("previousClosingPrice")
            open_price = sf("openPrice")
            high       = sf("highPrice")
            low        = sf("lowPrice")
            turnover   = sf("totalTurnover") or sf("turnover")
            volume     = sf("totalQuantity") or sf("quantity")

            day_change  = round(ltp - prev_close, 2) if ltp and prev_close else None
            change_pct  = round((day_change / prev_close) * 100, 2) if day_change and prev_close else None

            result[sym] = {
                "symbol":         sym,
                "company_name":   r.get("securityName") or r.get("companyName") or sym,
                "ltp":            ltp,
                "prev_close":     prev_close,
                "open_price":     open_price,
                "high":           high,
                "low":            low,
                "volume":         volume,
                "turnover":       turnover,
                "change_percent": change_pct,
                "day_change":     day_change,
                "error":          None,
                "source":         "nepalstock.com",
                "fetched_at":     datetime.now().isoformat(),
            }

        logger.info(f"Fetched today-price for {len(result)} symbols from nepalstock.com")
        return result

    except Exception as e:
        logger.error(f"Error fetching all today prices: {e}")
        return {}


def _fallback_entry(symbol: str, error: str) -> dict:
    return {
        "symbol":         symbol.upper(),
        "company_name":   symbol.upper(),
        "ltp":            None,
        "prev_close":     None,
        "change_percent": None,
        "day_change":     None,
        "error":          error,
        "source":         None,
        "fetched_at":     datetime.now().isoformat(),
    }


def scrape_prices(symbols: list) -> dict:
    """
    Public interface — same contract as before.
    Returns dict keyed by symbol:
    { "NABIL": { ltp, prev_close, change_percent, day_change, ... }, ... }
    """
    symbols_upper = [s.upper().strip() for s in symbols if s]
    result = {}

    scraper = _get_scraper()
    if scraper is None:
        for sym in symbols_upper:
            result[sym] = _fallback_entry(sym, "nepse-scraper package not available")
        return result

    # Fetch the full market data once (one API call for all symbols)
    all_prices = _fetch_all_today_prices(scraper)

    for sym in symbols_upper:
        if sym in all_prices:
            result[sym] = all_prices[sym]
        else:
            # Symbol not found in today's data (possibly delisted / no trade today)
            result[sym] = _fallback_entry(sym, "Symbol not found in today's NEPSE data")

    return result
