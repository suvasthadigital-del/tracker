"""
Scrapes live stock prices from Merolagani.com for NEPSE symbols.
Falls back gracefully if a symbol isn't found.
"""
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

def scrape_single(symbol: str) -> dict:
    url = f"https://merolagani.com/StockQuote.aspx?symbol={symbol.upper()}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        def get_text(selector):
            el = soup.select_one(selector)
            return el.get_text(strip=True) if el else None

        # LTP
        ltp_el = soup.select_one("#ctl00_ContentPlaceHolder1_LiveTrading1_lblLastTradedPrice")
        ltp = ltp_el.get_text(strip=True).replace(",", "") if ltp_el else None

        # Previous close
        prev_el = soup.select_one("#ctl00_ContentPlaceHolder1_LiveTrading1_lblPreviousClose")
        prev = prev_el.get_text(strip=True).replace(",", "") if prev_el else None

        # % change
        chng_el = soup.select_one("#ctl00_ContentPlaceHolder1_LiveTrading1_lblChange")
        chng = chng_el.get_text(strip=True).replace(",", "") if chng_el else None

        # Company name
        name_el = soup.select_one("#ctl00_ContentPlaceHolder1_LiveTrading1_lblCompanyName")
        name = name_el.get_text(strip=True) if name_el else symbol

        def safe_float(v):
            try:
                return float(str(v).replace(",", "").strip()) if v else None
            except Exception:
                return None

        ltp_f  = safe_float(ltp)
        prev_f = safe_float(prev)
        chng_f = safe_float(chng)

        return {
            "symbol":         symbol.upper(),
            "company_name":   name,
            "ltp":            ltp_f,
            "prev_close":     prev_f,
            "change_percent": chng_f,
            "day_change":     round(ltp_f - prev_f, 2) if ltp_f and prev_f else None,
            "error":          None,
        }

    except Exception as e:
        return {
            "symbol":         symbol.upper(),
            "company_name":   symbol,
            "ltp":            None,
            "prev_close":     None,
            "change_percent": None,
            "day_change":     None,
            "error":          str(e),
        }


def scrape_prices(symbols: list) -> dict:
    """
    Returns a dict keyed by symbol:
    { "NABIL": { ltp, prev_close, change_percent, day_change, ... }, ... }
    """
    result = {}
    for sym in symbols:
        result[sym.upper()] = scrape_single(sym)
    return result
