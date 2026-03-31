"""
send_email.py
Reads data/insider.json and sends a nightly digest email to dad's Outlook account.
Triggered by GitHub Actions at midnight PST (08:00 UTC).
"""

import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from zoneinfo import ZoneInfo

PST = ZoneInfo("America/Los_Angeles")

# ── Config (set these as GitHub Actions secrets) ───────────────────────────────
SENDER_EMAIL    = os.environ["SENDER_GMAIL"]          # your Gmail address
SENDER_PASSWORD = os.environ["SENDER_GMAIL_APP_PASS"] # Gmail app password (not your real password)
RECIPIENT_EMAIL = os.environ["RECIPIENT_EMAIL"]        # dad's Outlook/Live address
SITE_URL        = os.environ.get("SITE_URL", "https://yourusername.github.io/samuelstocks")


def load_data():
    with open("data/insider.json") as f:
        return json.load(f)


def role_label(role):
    r = (role or "").upper()
    if "CEO" in r: return "🔵 CEO"
    if "CFO" in r: return "🟣 CFO"
    return role or "Insider"


def fmt_shares(n):
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def fmt_money(n):
    try:
        v = abs(float(n))
        if v >= 1_000_000:
            return f"${v/1_000_000:.2f}M"
        if v >= 1_000:
            return f"${v/1_000:.0f}K"
        return f"${v:.0f}"
    except Exception:
        return "—"


def build_html(d):
    updated = d.get("updated", "—")
    buys = d.get("buys", [])
    sells = d.get("sells", [])
    today = datetime.now(PST).strftime("%A, %B %d, %Y")

    # ── CEO/CFO highlights ─────────────────────────────────────────────────────
    ceo_cfo_buys = [b for b in buys if any(x in (b.get("role") or "").upper() for x in ["CEO", "CFO"])]

    highlight_rows = ""
    if ceo_cfo_buys:
        for b in ceo_cfo_buys[:5]:
            highlight_rows += f"""
            <tr>
              <td style="padding:10px 14px;border-bottom:1px solid #1e2a3a;font-family:monospace;color:#60a5fa;font-weight:bold;">{b['ticker']}</td>
              <td style="padding:10px 14px;border-bottom:1px solid #1e2a3a;">{b['company']}</td>
              <td style="padding:10px 14px;border-bottom:1px solid #1e2a3a;">{b['insider']}</td>
              <td style="padding:10px 14px;border-bottom:1px solid #1e2a3a;"><span style="background:#1e3a5f;color:#60a5fa;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:bold;">{role_label(b['role'])}</span></td>
              <td style="padding:10px 14px;border-bottom:1px solid #1e2a3a;color:#22c55e;font-family:monospace;font-weight:bold;">{fmt_shares(b['shares'])} shares</td>
              <td style="padding:10px 14px;border-bottom:1px solid #1e2a3a;font-family:monospace;">{fmt_money(b['value'])}</td>
              <td style="padding:10px 14px;border-bottom:1px solid #1e2a3a;color:#6b7a94;font-family:monospace;">{b['date']}</td>
            </tr>"""
    else:
        highlight_rows = '<tr><td colspan="7" style="padding:20px;text-align:center;color:#6b7a94;">No CEO/CFO buys this week.</td></tr>'

    # ── All buys ───────────────────────────────────────────────────────────────
    all_buy_rows = ""
    for b in buys[:20]:
        all_buy_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;font-family:monospace;color:#60a5fa;">{b['ticker']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;">{b.get('insider','—')}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;font-size:12px;">{b.get('role','—')}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;color:#22c55e;font-family:monospace;">{fmt_shares(b['shares'])}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;font-family:monospace;">{fmt_money(b['value'])}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;color:#6b7a94;font-size:12px;">{b['date']}</td>
        </tr>"""
    if not all_buy_rows:
        all_buy_rows = '<tr><td colspan="6" style="padding:16px;text-align:center;color:#6b7a94;">No insider buys recorded this week.</td></tr>'

    # ── All sells ──────────────────────────────────────────────────────────────
    all_sell_rows = ""
    for s in sells[:20]:
        expiry_str = s.get("expiry") or "—"
        all_sell_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;font-family:monospace;color:#60a5fa;">{s['ticker']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;">{s.get('insider','—')}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;font-size:12px;">{s.get('role','—')}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;color:#ef4444;font-family:monospace;">{fmt_shares(s.get('shares_sold',0))}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;font-family:monospace;">{fmt_shares(s.get('shares_remaining',0))}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;color:#6b7a94;font-size:12px;font-family:monospace;">{expiry_str}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;color:#6b7a94;font-size:12px;">{s['date']}</td>
        </tr>"""
    if not all_sell_rows:
        all_sell_rows = '<tr><td colspan="7" style="padding:16px;text-align:center;color:#6b7a94;">No insider sales recorded this week.</td></tr>'

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0a0e13;font-family:'IBM Plex Sans',Arial,sans-serif;color:#e8edf5;">
<div style="max-width:680px;margin:0 auto;padding:24px 16px;">

  <!-- Header -->
  <div style="border-bottom:1px solid #1e2a3a;padding-bottom:20px;margin-bottom:24px;">
    <div style="font-family:monospace;font-size:22px;font-weight:bold;letter-spacing:-0.02em;">
      samuel<span style="color:#3b82f6;">stocks</span>
    </div>
    <div style="color:#6b7a94;font-size:13px;margin-top:4px;">Nightly DJIA Insider Trading Digest · {today}</div>
  </div>

  <!-- Summary bar -->
  <div style="display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap;">
    <div style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;padding:14px 20px;flex:1;min-width:120px;">
      <div style="font-size:11px;color:#6b7a94;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;font-family:monospace;">Total filings</div>
      <div style="font-size:26px;font-weight:bold;font-family:monospace;">{len(buys)+len(sells)}</div>
    </div>
    <div style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;padding:14px 20px;flex:1;min-width:120px;">
      <div style="font-size:11px;color:#6b7a94;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;font-family:monospace;">Buys</div>
      <div style="font-size:26px;font-weight:bold;font-family:monospace;color:#22c55e;">{len(buys)}</div>
      <div style="font-size:11px;color:#6b7a94;margin-top:2px;">CEO/CFO: {len(ceo_cfo_buys)}</div>
    </div>
    <div style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;padding:14px 20px;flex:1;min-width:120px;">
      <div style="font-size:11px;color:#6b7a94;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;font-family:monospace;">Sells</div>
      <div style="font-size:26px;font-weight:bold;font-family:monospace;color:#ef4444;">{len(sells)}</div>
    </div>
  </div>

  <!-- CEO/CFO Spotlight -->
  <div style="margin-bottom:24px;">
    <div style="font-size:14px;font-weight:600;margin-bottom:12px;padding:10px 14px;background:#111720;border-left:3px solid #3b82f6;border-radius:0 6px 6px 0;">
      ⭐ CEO / CFO Buys — Pay attention to these
    </div>
    <div style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;overflow:hidden;">
      <table width="100%" cellspacing="0" cellpadding="0" style="font-size:13px;">
        <thead>
          <tr style="background:#0d1520;">
            <th style="padding:10px 14px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;letter-spacing:0.07em;font-weight:600;">Ticker</th>
            <th style="padding:10px 14px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;letter-spacing:0.07em;font-weight:600;">Company</th>
            <th style="padding:10px 14px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;letter-spacing:0.07em;font-weight:600;">Insider</th>
            <th style="padding:10px 14px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;letter-spacing:0.07em;font-weight:600;">Role</th>
            <th style="padding:10px 14px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;letter-spacing:0.07em;font-weight:600;">Shares</th>
            <th style="padding:10px 14px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;letter-spacing:0.07em;font-weight:600;">Value</th>
            <th style="padding:10px 14px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;letter-spacing:0.07em;font-weight:600;">Date</th>
          </tr>
        </thead>
        <tbody>{highlight_rows}</tbody>
      </table>
    </div>
  </div>

  <!-- All Buys -->
  <div style="margin-bottom:24px;">
    <div style="font-size:14px;font-weight:600;margin-bottom:12px;color:#22c55e;">All insider buys ({len(buys)} total)</div>
    <div style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;overflow:hidden;">
      <table width="100%" cellspacing="0" cellpadding="0" style="font-size:13px;">
        <thead>
          <tr style="background:#0d1520;">
            <th style="padding:8px 12px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;">Ticker</th>
            <th style="padding:8px 12px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;">Insider</th>
            <th style="padding:8px 12px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;">Role</th>
            <th style="padding:8px 12px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;">Shares</th>
            <th style="padding:8px 12px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;">Value</th>
            <th style="padding:8px 12px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;">Date</th>
          </tr>
        </thead>
        <tbody>{all_buy_rows}</tbody>
      </table>
    </div>
  </div>

  <!-- All Sells -->
  <div style="margin-bottom:24px;">
    <div style="font-size:14px;font-weight:600;margin-bottom:12px;color:#ef4444;">Insider sales ({len(sells)} total)</div>
    <div style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;overflow:hidden;">
      <table width="100%" cellspacing="0" cellpadding="0" style="font-size:13px;">
        <thead>
          <tr style="background:#0d1520;">
            <th style="padding:8px 12px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;">Ticker</th>
            <th style="padding:8px 12px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;">Insider</th>
            <th style="padding:8px 12px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;">Role</th>
            <th style="padding:8px 12px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;">Shares sold</th>
            <th style="padding:8px 12px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;">Shares left</th>
            <th style="padding:8px 12px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;">Option expiry</th>
            <th style="padding:8px 12px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;">Date</th>
          </tr>
        </thead>
        <tbody>{all_sell_rows}</tbody>
      </table>
    </div>
  </div>

  <!-- Footer -->
  <div style="border-top:1px solid #1e2a3a;padding-top:16px;text-align:center;">
    <a href="{SITE_URL}" style="display:inline-block;background:#1d4ed8;color:#fff;text-decoration:none;padding:10px 24px;border-radius:6px;font-size:13px;font-weight:500;margin-bottom:14px;">
      Open Full Dashboard →
    </a>
    <div style="font-size:11px;color:#6b7a94;line-height:1.6;">
      Data sourced from SEC EDGAR Form 4 filings. Updated nightly at midnight PST.<br>
      This is informational only — not financial advice. Always do your own research.
    </div>
  </div>

</div>
</body>
</html>"""
    return html


def build_plaintext(d):
    buys = d.get("buys", [])
    sells = d.get("sells", [])
    ceo_cfo = [b for b in buys if any(x in (b.get("role") or "").upper() for x in ["CEO", "CFO"])]
    today = datetime.now(PST).strftime("%B %d, %Y")

    lines = [
        f"SAMUELSTOCKS — Insider Trading Digest {today}",
        "=" * 50,
        f"Total filings: {len(buys)+len(sells)} | Buys: {len(buys)} | Sells: {len(sells)}",
        f"CEO/CFO buys: {len(ceo_cfo)}",
        "",
        "⭐ CEO/CFO BUYS (most important):",
        "-" * 40,
    ]
    if ceo_cfo:
        for b in ceo_cfo:
            lines.append(f"  {b['ticker']} | {b['company']} | {b['insider']} ({b['role']}) | {fmt_shares(b['shares'])} shares | {fmt_money(b['value'])} | {b['date']}")
    else:
        lines.append("  None this week.")

    lines += ["", "ALL BUYS:", "-" * 40]
    for b in buys[:15]:
        lines.append(f"  {b['ticker']} | {b.get('insider','?')} | {b.get('role','?')} | {fmt_shares(b['shares'])} shares | {b['date']}")

    lines += ["", "ALL SELLS:", "-" * 40]
    for s in sells[:15]:
        lines.append(f"  {s['ticker']} | {s.get('insider','?')} | Sold: {fmt_shares(s.get('shares_sold',0))} | Remaining: {fmt_shares(s.get('shares_remaining',0))} | {s['date']}")

    lines += ["", f"Full dashboard: {SITE_URL}"]
    return "\n".join(lines)


def fmt_shares(n):
    try: return f"{int(n):,}"
    except: return str(n)

def fmt_money(n):
    try:
        v = abs(float(n))
        if v >= 1_000_000: return f"${v/1_000_000:.2f}M"
        if v >= 1_000: return f"${v/1_000:.0f}K"
        return f"${v:.0f}"
    except: return "—"


def send():
    print("Loading insider data...")
    d = load_data()

    buys = d.get("buys", [])
    sells = d.get("sells", [])
    today = datetime.now(PST).strftime("%B %d, %Y")

    subject = f"📊 Insider Trading Digest — {today} ({len(buys)} buys, {len(sells)} sells)"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL

    msg.attach(MIMEText(build_plaintext(d), "plain"))
    msg.attach(MIMEText(build_html(d), "html"))

    print(f"Sending email to {RECIPIENT_EMAIL}...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())

    print("Email sent successfully.")


if __name__ == "__main__":
    send()
