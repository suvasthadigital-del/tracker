import os
import json
import uuid
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler
from services.scraper import scrape_prices
from services.calculator import calculate_portfolio
from services.emailer import send_daily_summary

app = Flask(__name__)

# ── Data paths ──────────────────────────────────────────────────────────────
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
HOLDINGS_FILE = os.path.join(DATA_DIR, "holdings.json")
PRICES_FILE   = os.path.join(DATA_DIR, "prices_cache.json")
HISTORY_FILE  = os.path.join(DATA_DIR, "portfolio_history.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

os.makedirs(DATA_DIR, exist_ok=True)

# ── JSON helpers ─────────────────────────────────────────────────────────────
def read_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default

def write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)

# ── Scheduled jobs ────────────────────────────────────────────────────────────
def daily_price_refresh():
    holdings = read_json(HOLDINGS_FILE, [])
    symbols  = list({h["symbol"] for h in holdings})
    if not symbols:
        return
    prices = scrape_prices(symbols)
    write_json(PRICES_FILE, {"updated_at": datetime.now().isoformat(), "prices": prices})
    # Save daily snapshot
    portfolio = calculate_portfolio(holdings, prices)
    history   = read_json(HISTORY_FILE, [])
    today_str = date.today().isoformat()
    history   = [h for h in history if h["date"] != today_str]
    history.append({"date": today_str, "total_value": portfolio["total_current_value"],
                    "total_invested": portfolio["total_invested"]})
    write_json(HISTORY_FILE, history)

def daily_email_job():
    settings = read_json(SETTINGS_FILE, {})
    if not settings.get("email_enabled"):
        return
    holdings = read_json(HOLDINGS_FILE, [])
    prices   = read_json(PRICES_FILE, {}).get("prices", {})
    portfolio = calculate_portfolio(holdings, prices)
    send_daily_summary(settings.get("email_recipient", ""), portfolio)

scheduler = BackgroundScheduler(timezone="Asia/Kathmandu")
scheduler.add_job(daily_price_refresh, "cron", hour=15, minute=30, id="price_refresh")
scheduler.add_job(daily_email_job,     "cron", hour=16, minute=0,  id="email_summary")
scheduler.start()

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def dashboard():
    holdings = read_json(HOLDINGS_FILE, [])
    prices   = read_json(PRICES_FILE, {}).get("prices", {})
    updated  = read_json(PRICES_FILE, {}).get("updated_at", None)
    portfolio = calculate_portfolio(holdings, prices)
    history  = read_json(HISTORY_FILE, [])
    return render_template("dashboard.html", portfolio=portfolio,
                           history=history, updated_at=updated)

@app.route("/holdings")
def holdings_page():
    holdings = read_json(HOLDINGS_FILE, [])
    prices   = read_json(PRICES_FILE, {}).get("prices", {})
    portfolio = calculate_portfolio(holdings, prices)
    return render_template("holdings.html", holdings=portfolio["holdings_detail"],
                           tags=["Buy","IPO","Bonus","Right","Merger","Gift","Others"])

@app.route("/settings", methods=["GET","POST"])
def settings():
    if request.method == "POST":
        data = request.get_json()
        write_json(SETTINGS_FILE, data)
        return jsonify({"ok": True})
    s = read_json(SETTINGS_FILE, {"email_recipient":"","email_enabled":False,"email_time":"16:00"})
    return render_template("settings.html", settings=s)

# ── API ───────────────────────────────────────────────────────────────────────
@app.route("/api/holdings", methods=["GET"])
def api_get_holdings():
    return jsonify(read_json(HOLDINGS_FILE, []))

@app.route("/api/holdings", methods=["POST"])
def api_add_holding():
    holdings = read_json(HOLDINGS_FILE, [])
    data = request.get_json()
    data["id"] = str(uuid.uuid4())
    data["created_at"] = datetime.now().isoformat()
    data["updated_at"] = datetime.now().isoformat()
    data["quantity"]   = float(data["quantity"])
    data["buy_price"]  = float(data["buy_price"])
    holdings.append(data)
    write_json(HOLDINGS_FILE, holdings)
    return jsonify(data), 201

@app.route("/api/holdings/<hid>", methods=["PUT"])
def api_update_holding(hid):
    holdings = read_json(HOLDINGS_FILE, [])
    data = request.get_json()
    for i, h in enumerate(holdings):
        if h["id"] == hid:
            data["id"]         = hid
            data["created_at"] = h.get("created_at")
            data["updated_at"] = datetime.now().isoformat()
            data["quantity"]   = float(data["quantity"])
            data["buy_price"]  = float(data["buy_price"])
            holdings[i]        = data
            write_json(HOLDINGS_FILE, holdings)
            return jsonify(data)
    return jsonify({"error": "Not found"}), 404

@app.route("/api/holdings/<hid>", methods=["DELETE"])
def api_delete_holding(hid):
    holdings = read_json(HOLDINGS_FILE, [])
    holdings = [h for h in holdings if h["id"] != hid]
    write_json(HOLDINGS_FILE, holdings)
    return jsonify({"ok": True})

@app.route("/api/refresh-prices", methods=["POST"])
def api_refresh_prices():
    holdings = read_json(HOLDINGS_FILE, [])
    symbols  = list({h["symbol"] for h in holdings})
    if not symbols:
        return jsonify({"error": "No holdings to refresh"}), 400
    prices = scrape_prices(symbols)
    write_json(PRICES_FILE, {"updated_at": datetime.now().isoformat(), "prices": prices})
    # Save daily snapshot
    portfolio = calculate_portfolio(holdings, prices)
    history   = read_json(HISTORY_FILE, [])
    today_str = date.today().isoformat()
    history   = [h for h in history if h["date"] != today_str]
    history.append({"date": today_str, "total_value": portfolio["total_current_value"],
                    "total_invested": portfolio["total_invested"]})
    write_json(HISTORY_FILE, history)
    return jsonify({"ok": True, "prices": prices, "updated_at": datetime.now().isoformat()})

@app.route("/api/portfolio")
def api_portfolio():
    holdings = read_json(HOLDINGS_FILE, [])
    prices   = read_json(PRICES_FILE, {}).get("prices", {})
    return jsonify(calculate_portfolio(holdings, prices))

@app.route("/api/send-test-email", methods=["POST"])
def api_send_test_email():
    settings = read_json(SETTINGS_FILE, {})
    recipient = settings.get("email_recipient", "")
    if not recipient:
        return jsonify({"error": "No recipient configured"}), 400
    holdings = read_json(HOLDINGS_FILE, [])
    prices   = read_json(PRICES_FILE, {}).get("prices", {})
    portfolio = calculate_portfolio(holdings, prices)
    ok = send_daily_summary(recipient, portfolio)
    if ok:
        return jsonify({"ok": True})
    return jsonify({"error": "Send failed — check SENDGRID_API_KEY env var"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
