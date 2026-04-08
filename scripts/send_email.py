import json, os, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from zoneinfo import ZoneInfo

PST        = ZoneInfo("America/Los_Angeles")
SENDER     = os.environ["SENDER_GMAIL"]
PASSWORD   = os.environ["SENDER_GMAIL_APP_PASS"]
RECIPIENTS = ["he.samuel900@gmail.com"]
SITE_URL   = os.environ.get("SITE_URL", "https://tehochess.github.io/samuelstocks")

def fmt(n):
    try: return f"{int(n):,}"
    except: return "-"

def fmtM(n):
    try:
        v = abs(float(n))
        if v >= 1e6: return f"${v/1e6:.2f}M"
        if v >= 1e3: return f"${v/1e3:.0f}K"
        return f"${v:.0f}"
    except: return "-"

def role_label(role):
    r = (role or "").upper()
    if "CEO" in r: return "CEO"
    if "CFO" in r: return "CFO"
    return role or "Insider"

def role_badge(role):
    r = (role or "").upper()
    if "CEO" in r:
        return '<span style="background:#1e3a5f;color:#60a5fa;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold">CEO</span>'
    if "CFO" in r:
        return '<span style="background:#2e1a4f;color:#c084fc;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold">CFO</span>'
    return f'<span style="background:#1a1f2e;color:#6b7a94;padding:2px 8px;border-radius:4px;font-size:11px">{role or "Insider"}</span>'

def th(label):
    return f'<th style="padding:8px 12px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;letter-spacing:.07em;background:#0a0e13;font-weight:600">{label}</th>'

def build_email(d):
    buys  = d.get("buys", [])
    sells = d.get("sells", [])
    today = datetime.now(PST).strftime("%A, %B %d, %Y")
    ceo_cfo = [b for b in buys if any(x in (b.get("role") or "").upper() for x in ["CEO","CFO"])]

    def row_bg(i):
        return "#0d1520" if i % 2 == 0 else "#111720"

    if ceo_cfo:
        ceo_rows = ""
        for i, b in enumerate(ceo_cfo[:8]):
            ceo_rows += f"""<tr style="background:{row_bg(i)}">
              <td style="padding:10px 12px;font-family:monospace;color:#60a5fa;font-weight:bold;border-bottom:1px solid #1e2a3a">{b['ticker']}</td>
              <td style="padding:10px 12px;border-bottom:1px solid #1e2a3a">{b.get('company', b['ticker'])}</td>
              <td style="padding:10px 12px;border-bottom:1px solid #1e2a3a">{b.get('insider','-')}</td>
              <td style="padding:10px 12px;border-bottom:1px solid #1e2a3a">{role_badge(b.get('role'))}</td>
              <td style="padding:10px 12px;border-bottom:1px solid #1e2a3a;color:#22c55e;font-family:monospace;font-weight:bold">{fmt(b.get('shares',0))} shares</td>
              <td style="padding:10px 12px;border-bottom:1px solid #1e2a3a;font-family:monospace">{fmtM(b.get('value',0))}</td>
              <td style="padding:10px 12px;border-bottom:1px solid #1e2a3a;color:#6b7a94;font-size:12px">{b.get('date','-')}</td>
            </tr>"""
    else:
        ceo_rows = '<tr><td colspan="7" style="padding:20px;text-align:center;color:#6b7a94">No CEO/CFO open-market buys this period.</td></tr>'

    if buys:
        buy_rows = ""
        for i, b in enumerate(buys[:30]):
            buy_rows += f"""<tr style="background:{row_bg(i)}">
              <td style="padding:8px 12px;font-family:monospace;color:#60a5fa;border-bottom:1px solid #1e2a3a">{b['ticker']}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a">{b.get('insider','-')}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;font-size:12px;color:#a0aec0">{b.get('role','-')}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;color:#22c55e;font-family:monospace">{fmt(b.get('shares',0))}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;font-family:monospace">{fmtM(b.get('value',0))}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;color:#6b7a94;font-size:12px">{b.get('date','-')}</td>
            </tr>"""
    else:
        buy_rows = '<tr><td colspan="6" style="padding:16px;text-align:center;color:#6b7a94">No open-market buys recorded.</td></tr>'

    if sells:
        sell_rows = ""
        for i, s in enumerate(sells[:30]):
            sell_rows += f"""<tr style="background:{row_bg(i)}">
              <td style="padding:8px 12px;font-family:monospace;color:#60a5fa;border-bottom:1px solid #1e2a3a">{s['ticker']}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a">{s.get('insider','-')}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a">{role_badge(s.get('role'))}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;color:#ef4444;font-family:monospace">{fmt(s.get('shares_sold',0))}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;font-family:monospace">{fmt(s.get('shares_remaining',0))}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;color:#6b7a94;font-size:12px">{s.get('date','-')}</td>
            </tr>"""
    else:
        sell_rows = '<tr><td colspan="6" style="padding:16px;text-align:center;color:#6b7a94">No insider sales recorded.</td></tr>'

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0a0e13;font-family:Arial,sans-serif;color:#e8edf5">
<div style="max-width:700px;margin:0 auto;padding:24px 16px">

  <div style="border-bottom:1px solid #1e2a3a;padding-bottom:18px;margin-bottom:22px">
    <div style="font-family:monospace;font-size:22px;font-weight:bold">samuel<span style="color:#3b82f6">stocks</span></div>
    <div style="color:#6b7a94;font-size:13px;margin-top:4px">Nightly DJIA Insider Trading Digest &mdash; {today}</div>
  </div>

  <table width="100%" cellspacing="0" cellpadding="0" style="margin-bottom:22px"><tr>
    <td style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;padding:14px 18px">
      <div style="font-size:10px;color:#6b7a94;text-transform:uppercase;font-family:monospace;margin-bottom:4px">Total filings</div>
      <div style="font-size:26px;font-weight:bold;font-family:monospace">{len(buys)+len(sells)}</div>
    </td>
    <td width="10"></td>
    <td style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;padding:14px 18px">
      <div style="font-size:10px;color:#6b7a94;text-transform:uppercase;font-family:monospace;margin-bottom:4px">Buys</div>
      <div style="font-size:26px;font-weight:bold;font-family:monospace;color:#22c55e">{len(buys)}</div>
      <div style="font-size:11px;color:#6b7a94;margin-top:2px">CEO/CFO: {len(ceo_cfo)}</div>
    </td>
    <td width="10"></td>
    <td style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;padding:14px 18px">
      <div style="font-size:10px;color:#6b7a94;text-transform:uppercase;font-family:monospace;margin-bottom:4px">Sells</div>
      <div style="font-size:26px;font-weight:bold;font-family:monospace;color:#ef4444">{len(sells)}</div>
    </td>
  </tr></table>

  <div style="margin-bottom:22px">
    <div style="font-size:13px;font-weight:600;margin-bottom:10px;padding:10px 14px;background:#111720;border-left:3px solid #3b82f6;border-radius:0 6px 6px 0">
      &#11088; CEO &amp; CFO Buys &mdash; pay closest attention to these
    </div>
    <div style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;overflow:hidden">
      <table width="100%" cellspacing="0" cellpadding="0" style="font-size:13px">
        <thead><tr>{th('Ticker')}{th('Company')}{th('Insider')}{th('Role')}{th('Shares')}{th('Value')}{th('Date')}</tr></thead>
        <tbody>{ceo_rows}</tbody>
      </table>
    </div>
  </div>

  <div style="margin-bottom:22px">
    <div style="font-size:13px;font-weight:600;margin-bottom:10px;color:#22c55e">All insider buys ({len(buys)} total)</div>
    <div style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;overflow:hidden">
      <table width="100%" cellspacing="0" cellpadding="0" style="font-size:13px">
        <thead><tr>{th('Ticker')}{th('Insider')}{th('Role')}{th('Shares')}{th('Value')}{th('Date')}</tr></thead>
        <tbody>{buy_rows}</tbody>
      </table>
    </div>
  </div>

  <div style="margin-bottom:22px">
    <div style="font-size:13px;font-weight:600;margin-bottom:10px;color:#ef4444">Insider sales ({len(sells)} total)</div>
    <div style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;overflow:hidden">
      <table width="100%" cellspacing="0" cellpadding="0" style="font-size:13px">
        <thead><tr>{th('Ticker')}{th('Insider')}{th('Role')}{th('Shares sold')}{th('Shares left')}{th('Date')}</tr></thead>
        <tbody>{sell_rows}</tbody>
      </table>
    </div>
  </div>

  <div style="text-align:center;padding-top:16px;border-top:1px solid #1e2a3a">
    <a href="{SITE_URL}" style="display:inline-block;background:#1d4ed8;color:#fff;text-decoration:none;padding:10px 28px;border-radius:6px;font-size:13px;font-weight:500;margin-bottom:14px">Open Full Dashboard</a>
    <div style="font-size:11px;color:#6b7a94;line-height:1.7">
      Data sourced from SEC EDGAR Form 4 filings via OpenInsider.<br>
      Updated nightly at midnight PST. Informational only &mdash; not financial advice.
    </div>
  </div>

</div></body></html>"""

def send():
    d = json.load(open("data/insider.json"))
    today = datetime.now(PST).strftime("%B %d, %Y")
    buys  = d.get("buys", [])
    sells = d.get("sells", [])
    subject = f"Samuel Stocks - Insider Digest {today} ({len(buys)} buys, {len(sells)} sells)"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER
    msg["To"]      = ", ".join(RECIPIENTS)
    plain = f"Samuel Stocks Insider Digest - {today}\nBuys: {len(buys)} | Sells: {len(sells)}\nFull dashboard: {SITE_URL}"
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(build_email(d), "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(SENDER, PASSWORD)
        s.sendmail(SENDER, RECIPIENTS, msg.as_string())
    print(f"Email sent to: {', '.join(RECIPIENTS)}")

if __name__ == "__main__":
    send()
