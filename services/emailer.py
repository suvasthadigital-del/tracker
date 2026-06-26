"""
Daily portfolio summary email via SendGrid.
Reads SENDGRID_API_KEY and SENDGRID_FROM_EMAIL from environment.
"""
import os
from datetime import date

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    HAS_SENDGRID = True
except ImportError:
    HAS_SENDGRID = False


def _fmt(n, prefix="Rs. "):
    try:
        return f"{prefix}{n:,.2f}"
    except Exception:
        return str(n)


def build_email_html(portfolio: dict) -> str:
    today     = date.today().strftime("%B %d, %Y")
    pnl       = portfolio["overall_pnl"]
    pnl_pct   = portfolio["overall_pnl_percent"]
    pnl_color = "#16a34a" if pnl >= 0 else "#dc2626"
    pnl_sign  = "+" if pnl >= 0 else ""
    xirr      = portfolio.get("portfolio_xirr")
    xirr_str  = f"{xirr:+.2f}%" if xirr is not None else "N/A"

    rows = ""
    for h in portfolio.get("aggregated", []):
        color = "#16a34a" if h["pnl_amount"] >= 0 else "#dc2626"
        sign  = "+" if h["pnl_amount"] >= 0 else ""
        rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;font-weight:600">{h['symbol']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:right">{_fmt(h['ltp'],'')}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:right">{_fmt(h['current_value'])}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:right;color:{color}">{sign}{_fmt(h['pnl_amount'])} ({sign}{h['pnl_percent']}%)</td>
        </tr>"""

    gainers_html = ""
    for g in portfolio.get("top_gainers", []):
        gainers_html += f"<li><strong>{g['symbol']}</strong>: +{g['pnl_percent']}%</li>"

    losers_html = ""
    for l in portfolio.get("top_losers", []):
        losers_html += f"<li><strong>{l['symbol']}</strong>: {l['pnl_percent']}%</li>"

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:'Segoe UI',Arial,sans-serif">
  <div style="max-width:600px;margin:32px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08)">
    <div style="background:linear-gradient(135deg,#1e3a5f,#2563eb);padding:28px 32px">
      <h1 style="margin:0;color:#fff;font-size:20px;font-weight:700">NEPSE Portfolio Summary</h1>
      <p style="margin:4px 0 0;color:#93c5fd;font-size:14px">{today}</p>
    </div>
    <div style="padding:24px 32px">
      <div style="display:flex;gap:16px;margin-bottom:24px">
        <div style="flex:1;background:#f0fdf4;border-radius:8px;padding:16px;text-align:center">
          <div style="font-size:12px;color:#6b7280;margin-bottom:4px">Total Value</div>
          <div style="font-size:20px;font-weight:700;color:#111">{_fmt(portfolio['total_current_value'])}</div>
        </div>
        <div style="flex:1;background:#{'f0fdf4' if pnl>=0 else 'fef2f2'};border-radius:8px;padding:16px;text-align:center">
          <div style="font-size:12px;color:#6b7280;margin-bottom:4px">Overall P&L</div>
          <div style="font-size:20px;font-weight:700;color:{pnl_color}">{pnl_sign}{_fmt(pnl)} ({pnl_sign}{pnl_pct}%)</div>
        </div>
        <div style="flex:1;background:#eff6ff;border-radius:8px;padding:16px;text-align:center">
          <div style="font-size:12px;color:#6b7280;margin-bottom:4px">XIRR</div>
          <div style="font-size:20px;font-weight:700;color:#2563eb">{xirr_str}</div>
        </div>
      </div>
      <h3 style="margin:0 0 12px;color:#374151;font-size:14px;text-transform:uppercase;letter-spacing:.05em">Holdings</h3>
      <table style="width:100%;border-collapse:collapse;font-size:14px">
        <thead>
          <tr style="background:#f9fafb">
            <th style="padding:8px 12px;text-align:left;color:#6b7280;font-weight:600">Symbol</th>
            <th style="padding:8px 12px;text-align:right;color:#6b7280;font-weight:600">LTP</th>
            <th style="padding:8px 12px;text-align:right;color:#6b7280;font-weight:600">Value</th>
            <th style="padding:8px 12px;text-align:right;color:#6b7280;font-weight:600">P&L</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <div style="display:flex;gap:16px;margin-top:24px">
        <div style="flex:1;background:#f0fdf4;border-radius:8px;padding:16px">
          <div style="font-size:12px;color:#6b7280;margin-bottom:8px;font-weight:600">🏆 Top Gainers</div>
          <ul style="margin:0;padding-left:18px;color:#15803d;font-size:13px">{gainers_html}</ul>
        </div>
        <div style="flex:1;background:#fef2f2;border-radius:8px;padding:16px">
          <div style="font-size:12px;color:#6b7280;margin-bottom:8px;font-weight:600">📉 Top Losers</div>
          <ul style="margin:0;padding-left:18px;color:#dc2626;font-size:13px">{losers_html}</ul>
        </div>
      </div>
    </div>
    <div style="padding:16px 32px;background:#f9fafb;border-top:1px solid #f0f0f0;font-size:12px;color:#9ca3af;text-align:center">
      NEPSE Portfolio Tracker • Prices from Merolagani
    </div>
  </div>
</body>
</html>"""


def send_daily_summary(recipient: str, portfolio: dict):
    if not HAS_SENDGRID:
        print("SendGrid not installed.")
        return False
    api_key  = os.environ.get("SENDGRID_API_KEY")
    from_email = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@yourdomain.com")
    if not api_key or not recipient:
        print("SendGrid API key or recipient missing.")
        return False
    try:
        msg = Mail(
            from_email=from_email,
            to_emails=recipient,
            subject=f"📊 NEPSE Portfolio Summary — {date.today().strftime('%b %d, %Y')}",
            html_content=build_email_html(portfolio),
        )
        sg = SendGridAPIClient(api_key)
        sg.send(msg)
        print(f"Email sent to {recipient}")
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False
