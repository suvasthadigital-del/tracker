# 📊 NEPSE Portfolio Tracker

A personal portfolio tracker for NEPSE (Nepal Stock Exchange) with live price scraping, P&L calculations, XIRR, and daily email summaries.

## Features

- **Dashboard** — total P&L, XIRR, CAGR, charts (pie, bar, line history)
- **Holdings** — add/edit/delete stocks with tags: Buy, IPO, Bonus, Right, Merger, Gift, Others
- **Live Prices** — scraped from Merolagani.com (auto-refresh daily at 3:30 PM NPT)
- **Calculations** — P&L, weighted avg buy price, CAGR per holding, XIRR for full portfolio
- **Daily Email** — SendGrid summary at 4:00 PM NPT (after market close)
- **Persistent Storage** — JSON files on Render.com persistent disk (no data loss on redeploy)

---

## 🚀 Deploy to Render.com (Free)

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/nepse-portfolio.git
git push -u origin main
```

### Step 2 — Create Render Web Service

1. Go to [render.com](https://render.com) → **New** → **Web Service**
2. Connect your GitHub repository
3. Render will auto-detect `render.yaml` — click **Apply**
4. This creates:
   - A Python web service
   - A **1 GB persistent disk** mounted at `/var/data` (your JSON files live here safely)

### Step 3 — Set Environment Variables (Render Dashboard)

Under your service → **Environment**:

| Key | Value |
|-----|-------|
| `SENDGRID_API_KEY` | Your SendGrid API key |
| `SENDGRID_FROM_EMAIL` | Verified sender email in SendGrid |

> **SendGrid free tier:** 100 emails/day — more than enough for daily summaries.

### Step 4 — Done!

Visit your Render URL (e.g. `https://nepse-portfolio.onrender.com`). 

---

## 🖥️ Run Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

Visit `http://localhost:5000`

---

## 📁 Project Structure

```
nepse-portfolio/
├── app.py                  # Flask app + routes + scheduler
├── services/
│   ├── scraper.py          # Merolagani price scraper
│   ├── calculator.py       # P&L, XIRR, CAGR calculations
│   └── emailer.py          # SendGrid daily email
├── templates/
│   ├── base.html           # Nav + design system
│   ├── dashboard.html      # Dashboard with charts
│   ├── holdings.html       # Holdings table + add/edit/delete
│   └── settings.html       # Email config + manual actions
├── data/                   # JSON data files (auto-created)
│   ├── holdings.json
│   ├── prices_cache.json
│   ├── portfolio_history.json
│   └── settings.json
├── render.yaml             # Render.com deployment config
└── requirements.txt
```

---

## ⚠️ Notes

- **Merolagani scraping** — works as of mid-2025. If they change their HTML, update the CSS selectors in `services/scraper.py`.
- **Free Render tier** — the service sleeps after 15 min of inactivity (spins up in ~30s on next visit). The scheduler still fires correctly when the service is awake. For guaranteed daily emails, consider upgrading to Render's $7/mo Starter plan.
- **No login** — this is a single-user app accessible by URL. If you want to secure it, add a `SECRET_KEY` env var and Flask session-based password.

---

## 📐 Calculations Reference

| Metric | Method |
|--------|--------|
| Invested | `buy_price × quantity` |
| P&L | `current_value − invested` |
| P&L % | `(P&L / invested) × 100` |
| CAGR | `((current/invested)^(1/years)) − 1` |
| XIRR | Newton-Raphson on dated cash flows (`pyxirr`) |
| Avg Buy Price | Weighted average across entries per symbol |
