"""
All portfolio calculations: P&L, CAGR, XIRR, aggregation.
"""
from datetime import date, datetime
from collections import defaultdict

try:
    from pyxirr import xirr as _xirr
    HAS_PYXIRR = True
except ImportError:
    HAS_PYXIRR = False


def _parse_date(d):
    if isinstance(d, date):
        return d
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(d, fmt).date()
        except Exception:
            pass
    return date.today()


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def compute_xirr(cash_flows: list) -> float | None:
    """
    cash_flows: list of (date, amount) tuples
    Buys are negative, current value is positive.
    """
    if not HAS_PYXIRR or len(cash_flows) < 2:
        return None
    try:
        dates   = [cf[0] for cf in cash_flows]
        amounts = [cf[1] for cf in cash_flows]
        result  = _xirr(dates, amounts)
        if result is None:
            return None
        return round(result * 100, 2)
    except Exception:
        return None


def compute_cagr(invested: float, current: float, buy_date: date) -> float | None:
    if invested <= 0 or current <= 0:
        return None
    days = (date.today() - buy_date).days
    if days < 1:
        return None
    years = days / 365.25
    try:
        cagr = ((current / invested) ** (1 / years) - 1) * 100
        return round(cagr, 2)
    except Exception:
        return None


def calculate_portfolio(holdings: list, prices: dict) -> dict:
    """
    Main calculation function.
    Returns a rich dict with per-holding detail and overall summary.
    """
    # ── Group by symbol for aggregated view ──────────────────────────────────
    by_symbol = defaultdict(list)
    for h in holdings:
        by_symbol[h["symbol"].upper()].append(h)

    holdings_detail   = []
    total_invested    = 0.0
    total_current_val = 0.0
    total_day_change  = 0.0
    xirr_cashflows    = []   # all cash flows for portfolio-level XIRR

    for h in holdings:
        sym       = h["symbol"].upper()
        qty       = _safe_float(h.get("quantity", 0))
        buy_price = _safe_float(h.get("buy_price", 0))
        buy_date  = _parse_date(h.get("buy_date", date.today()))

        price_data  = prices.get(sym, {})
        ltp         = _safe_float(price_data.get("ltp") or 0)
        prev_close  = _safe_float(price_data.get("prev_close") or 0)
        chng_pct    = price_data.get("change_percent")
        company_name = price_data.get("company_name") or h.get("company_name") or sym

        invested      = buy_price * qty
        current_value = ltp * qty if ltp else 0.0
        pnl_amount    = current_value - invested
        pnl_percent   = (pnl_amount / invested * 100) if invested > 0 else 0.0
        day_chg_amt   = (ltp - prev_close) * qty if ltp and prev_close else 0.0

        days_held = (date.today() - buy_date).days
        cagr      = compute_cagr(invested, current_value, buy_date) if ltp else None

        # Cash flow for XIRR: buy = negative on buy_date, current value = positive today
        if invested > 0:
            xirr_cashflows.append((buy_date, -invested))
        if current_value > 0:
            xirr_cashflows.append((date.today(), current_value))

        total_invested    += invested
        total_current_val += current_value
        total_day_change  += day_chg_amt

        holdings_detail.append({
            "id":             h["id"],
            "symbol":         sym,
            "company_name":   company_name,
            "tag":            h.get("tag", "Buy"),
            "quantity":       qty,
            "buy_price":      buy_price,
            "buy_date":       str(buy_date),
            "days_held":      days_held,
            "notes":          h.get("notes", ""),
            "ltp":            ltp,
            "prev_close":     prev_close,
            "change_percent": chng_pct,
            "invested":       round(invested, 2),
            "current_value":  round(current_value, 2),
            "pnl_amount":     round(pnl_amount, 2),
            "pnl_percent":    round(pnl_percent, 2),
            "day_change_amt": round(day_chg_amt, 2),
            "cagr":           cagr,
            "price_available": ltp > 0,
        })

    # ── Portfolio-level XIRR ─────────────────────────────────────────────────
    # Collapse same-day cash flows
    cf_map = defaultdict(float)
    for d, amt in xirr_cashflows:
        cf_map[d] += amt
    merged_cf = sorted(cf_map.items())
    portfolio_xirr = compute_xirr(merged_cf)

    # ── Aggregated by symbol ──────────────────────────────────────────────────
    agg = defaultdict(lambda: {"invested": 0, "current_value": 0, "qty": 0,
                               "pnl_amount": 0, "pnl_percent": 0,
                               "symbol": "", "company_name": "", "ltp": 0})
    for hd in holdings_detail:
        sym = hd["symbol"]
        agg[sym]["symbol"]       = sym
        agg[sym]["company_name"] = hd["company_name"]
        agg[sym]["ltp"]          = hd["ltp"]
        agg[sym]["invested"]     += hd["invested"]
        agg[sym]["current_value"] += hd["current_value"]
        agg[sym]["qty"]          += hd["quantity"]
        agg[sym]["pnl_amount"]   += hd["pnl_amount"]

    for sym in agg:
        inv = agg[sym]["invested"]
        cv  = agg[sym]["current_value"]
        agg[sym]["pnl_percent"] = round((cv - inv) / inv * 100, 2) if inv > 0 else 0.0
        agg[sym]["avg_buy_price"] = round(inv / agg[sym]["qty"], 2) if agg[sym]["qty"] > 0 else 0

    aggregated = sorted(agg.values(), key=lambda x: x["pnl_percent"], reverse=True)

    # ── Charts data ───────────────────────────────────────────────────────────
    pie_labels  = list(agg.keys())
    pie_values  = [round(agg[s]["current_value"], 2) for s in pie_labels]
    bar_labels  = [s for s in pie_labels]
    bar_pnl     = [round(agg[s]["pnl_amount"], 2) for s in pie_labels]

    # ── Top gainers / losers ──────────────────────────────────────────────────
    sorted_agg = sorted(agg.values(), key=lambda x: x["pnl_percent"])
    top_losers  = sorted_agg[:3]
    top_gainers = list(reversed(sorted_agg[-3:]))

    overall_pnl     = total_current_val - total_invested
    overall_pnl_pct = (overall_pnl / total_invested * 100) if total_invested > 0 else 0.0

    return {
        "holdings_detail":      holdings_detail,
        "aggregated":           aggregated,
        "total_invested":       round(total_invested, 2),
        "total_current_value":  round(total_current_val, 2),
        "overall_pnl":          round(overall_pnl, 2),
        "overall_pnl_percent":  round(overall_pnl_pct, 2),
        "total_day_change":     round(total_day_change, 2),
        "portfolio_xirr":       portfolio_xirr,
        "top_gainers":          top_gainers,
        "top_losers":           top_losers,
        "chart_pie_labels":     pie_labels,
        "chart_pie_values":     pie_values,
        "chart_bar_labels":     bar_labels,
        "chart_bar_pnl":        bar_pnl,
        "holdings_count":       len(holdings),
        "symbols_count":        len(agg),
    }
