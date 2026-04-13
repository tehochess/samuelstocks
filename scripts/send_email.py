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

# ── Formatters ─────────────────────────────────────────────────
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

def pct_str(p):
    try:
        p = float(p)
        return f"+{p:.2f}%" if p > 0 else f"{p:.2f}%"
    except: return "-"

def pct_color(p):
    try: return "#22c55e" if float(p) >= 0 else "#ef4444"
    except: return "#6b7a94"

def role_badge(role):
    r = (role or "").upper()
    if "CEO" in r:
        return '<span style="background:#1e3a5f;color:#60a5fa;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold">CEO</span>'
    if "CFO" in r:
        return '<span style="background:#2e1a4f;color:#c084fc;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold">CFO</span>'
    return f'<span style="background:#1a1f2e;color:#6b7a94;padding:2px 8px;border-radius:4px;font-size:11px">{role or "Insider"}</span>'

def th(label):
    return f'<th style="padding:8px 12px;text-align:left;font-size:10px;color:#6b7a94;text-transform:uppercase;letter-spacing:.07em;background:#0a0e13;font-weight:600">{label}</th>'

def section_header(title, color="#3b82f6"):
    return f'''
  <div style="font-size:16px;font-weight:700;color:{color};font-family:monospace;
              padding:14px 0 10px 0;margin-top:32px;border-top:2px solid {color};
              letter-spacing:0.04em">{title}</div>'''

def divider():
    return '<div style="height:1px;background:#1e2a3a;margin:28px 0"></div>'

def row_bg(i):
    return "#0d1520" if i % 2 == 0 else "#111720"

def signal_color(sig_name):
    if not sig_name or sig_name == "—": return "#6b7a94"
    n = sig_name.lower()
    if "breakdown" in n or "peak" in n: return "#ef4444"
    if "strong bottom" in n or "momentum" in n: return "#22c55e"
    if "near bottom" in n or "possible" in n: return "#f59e0b"
    return "#6b7a94"

# ── SECTION 1: Insider Trading ─────────────────────────────────
def build_insider_section(d):
    buys    = d.get("buys", [])
    sells   = d.get("sells", [])
    ceo_cfo = [b for b in buys if any(x in (b.get("role") or "").upper() for x in ["CEO","CFO"])]

    # Summary cards
    summary = f'''
  <table width="100%" cellspacing="0" cellpadding="0" style="margin-bottom:20px"><tr>
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
  </tr></table>'''

    # CEO/CFO buys
    if ceo_cfo:
        ceo_rows = ""
        for i, b in enumerate(ceo_cfo[:8]):
            ceo_rows += f'''<tr style="background:{row_bg(i)}">
              <td style="padding:10px 12px;font-family:monospace;color:#60a5fa;font-weight:bold;border-bottom:1px solid #1e2a3a">{b['ticker']}</td>
              <td style="padding:10px 12px;border-bottom:1px solid #1e2a3a">{b.get('company', b['ticker'])}</td>
              <td style="padding:10px 12px;border-bottom:1px solid #1e2a3a">{b.get('insider','-')}</td>
              <td style="padding:10px 12px;border-bottom:1px solid #1e2a3a">{role_badge(b.get('role'))}</td>
              <td style="padding:10px 12px;border-bottom:1px solid #1e2a3a;color:#22c55e;font-family:monospace;font-weight:bold">{fmt(b.get('shares',0))} shares</td>
              <td style="padding:10px 12px;border-bottom:1px solid #1e2a3a;font-family:monospace">{fmtM(b.get('value',0))}</td>
              <td style="padding:10px 12px;border-bottom:1px solid #1e2a3a;color:#6b7a94;font-size:12px">{b.get('date','-')}</td>
            </tr>'''
    else:
        ceo_rows = '<tr><td colspan="7" style="padding:20px;text-align:center;color:#6b7a94">No CEO/CFO open-market buys this period.</td></tr>'

    # All buys
    if buys:
        buy_rows = ""
        for i, b in enumerate(buys[:30]):
            buy_rows += f'''<tr style="background:{row_bg(i)}">
              <td style="padding:8px 12px;font-family:monospace;color:#60a5fa;border-bottom:1px solid #1e2a3a">{b['ticker']}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a">{b.get('insider','-')}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;font-size:12px;color:#a0aec0">{b.get('role','-')}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;color:#22c55e;font-family:monospace">{fmt(b.get('shares',0))}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;font-family:monospace">{fmtM(b.get('value',0))}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;color:#6b7a94;font-size:12px">{b.get('date','-')}</td>
            </tr>'''
    else:
        buy_rows = '<tr><td colspan="6" style="padding:16px;text-align:center;color:#6b7a94">No open-market buys recorded.</td></tr>'

    # Sells
    if sells:
        sell_rows = ""
        for i, s in enumerate(sells[:30]):
            sell_rows += f'''<tr style="background:{row_bg(i)}">
              <td style="padding:8px 12px;font-family:monospace;color:#60a5fa;border-bottom:1px solid #1e2a3a">{s['ticker']}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a">{s.get('insider','-')}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a">{role_badge(s.get('role'))}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;color:#ef4444;font-family:monospace">{fmt(s.get('shares_sold',0))}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;font-family:monospace">{fmt(s.get('shares_remaining',0))}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a;color:#6b7a94;font-size:12px">{s.get('date','-')}</td>
            </tr>'''
    else:
        sell_rows = '<tr><td colspan="6" style="padding:16px;text-align:center;color:#6b7a94">No insider sales recorded.</td></tr>'

    return summary + f'''
  <div style="margin-bottom:18px">
    <div style="font-size:13px;font-weight:600;margin-bottom:10px;padding:10px 14px;background:#111720;border-left:3px solid #3b82f6;border-radius:0 6px 6px 0">
      ⭐ CEO &amp; CFO Buys — pay closest attention to these
    </div>
    <div style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;overflow:hidden">
      <table width="100%" cellspacing="0" cellpadding="0" style="font-size:13px">
        <thead><tr>{th('Ticker')}{th('Company')}{th('Insider')}{th('Role')}{th('Shares')}{th('Value')}{th('Date')}</tr></thead>
        <tbody>{ceo_rows}</tbody>
      </table>
    </div>
  </div>

  <div style="margin-bottom:18px">
    <div style="font-size:13px;font-weight:600;margin-bottom:8px;color:#22c55e">All insider buys ({len(buys)} total)</div>
    <div style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;overflow:hidden">
      <table width="100%" cellspacing="0" cellpadding="0" style="font-size:13px">
        <thead><tr>{th('Ticker')}{th('Insider')}{th('Role')}{th('Shares')}{th('Value')}{th('Date')}</tr></thead>
        <tbody>{buy_rows}</tbody>
      </table>
    </div>
  </div>

  <div style="margin-bottom:18px">
    <div style="font-size:13px;font-weight:600;margin-bottom:8px;color:#ef4444">Insider sales ({len(sells)} total)</div>
    <div style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;overflow:hidden">
      <table width="100%" cellspacing="0" cellpadding="0" style="font-size:13px">
        <thead><tr>{th('Ticker')}{th('Insider')}{th('Role')}{th('Shares sold')}{th('Shares left')}{th('Date')}</tr></thead>
        <tbody>{sell_rows}</tbody>
      </table>
    </div>
  </div>'''

# ── SECTION 2: Key Dates ───────────────────────────────────────
def build_key_dates_section(kd):
    dividends = kd.get("dividends", [])
    earnings  = kd.get("earnings",  [])

    squeeze_candidates = [e for e in earnings if e.get("squeezeFlag")]

    # Dividend rows — only show upcoming (not suspended/N/A), max 15
    upcoming = [d for d in dividends if d.get("exStatus") == "upcoming"]
    recent   = [d for d in dividends if d.get("exStatus") == "recent"]
    # Show upcoming first; if none, show recent (correctly labeled)
    if upcoming:
        active_divs  = upcoming[:15]
        div_label    = "Upcoming ex-dividend dates"
    else:
        active_divs  = recent[:15]
        div_label    = "Recent ex-dividend dates (no future dates announced yet)"
    if active_divs:
        div_rows = ""
        for i, d in enumerate(active_divs):
            yld = f"{d.get('dividendYield',0):.2f}%" if d.get('dividendYield',0) > 0 else "—"
            rate = f"${d.get('dividendRate',0):.2f}" if d.get('dividendRate',0) > 0 else "—"
            div_rows += f'''<tr style="background:{row_bg(i)}">
              <td style="padding:8px 12px;font-family:monospace;color:#60a5fa;border-bottom:1px solid #1e2a3a">{d['ticker']}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a">{d.get('company','—')}</td>
              <td style="padding:8px 12px;font-family:monospace;color:#60a5fa;font-weight:600;border-bottom:1px solid #1e2a3a">{d.get('exDate','—')}</td>
              <td style="padding:8px 12px;font-family:monospace;color:#22c55e;border-bottom:1px solid #1e2a3a">{rate}</td>
              <td style="padding:8px 12px;font-family:monospace;border-bottom:1px solid #1e2a3a">{yld}</td>
              <td style="padding:8px 12px;font-family:monospace;color:#6b7a94;border-bottom:1px solid #1e2a3a">${d.get('price',0):.2f}</td>
            </tr>'''
    else:
        div_rows = '<tr><td colspan="6" style="padding:16px;text-align:center;color:#6b7a94">No upcoming ex-dividend dates.</td></tr>'

    # Earnings rows — all, squeeze flagged first
    if earnings:
        earn_rows = ""
        for i, e in enumerate(earnings[:20]):
            squeeze = "🔥 YES" if e.get("squeezeFlag") else "—"
            sq_color = "#fb923c" if e.get("squeezeFlag") else "#6b7a94"
            earn_rows += f'''<tr style="background:{row_bg(i)}">
              <td style="padding:8px 12px;font-family:monospace;color:#60a5fa;border-bottom:1px solid #1e2a3a">{e['ticker']}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a">{e.get('company','—')}</td>
              <td style="padding:8px 12px;font-family:monospace;color:#60a5fa;border-bottom:1px solid #1e2a3a">{e.get('earningsDate','N/A')}</td>
              <td style="padding:8px 12px;font-family:monospace;border-bottom:1px solid #1e2a3a">{e.get('shortRatio',0):.1f}</td>
              <td style="padding:8px 12px;font-family:monospace;color:{sq_color};font-weight:bold;border-bottom:1px solid #1e2a3a">{squeeze}</td>
            </tr>'''
    else:
        earn_rows = '<tr><td colspan="5" style="padding:16px;text-align:center;color:#6b7a94">No earnings data.</td></tr>'

    squeeze_note = ""
    if squeeze_candidates:
        names = ", ".join([e['ticker'] for e in squeeze_candidates])
        squeeze_note = f'<div style="background:#2d1a0e;border:1px solid #92400e;border-radius:6px;padding:10px 14px;margin-bottom:14px;font-size:13px;color:#fbbf24">🔥 Short squeeze candidates: <strong>{names}</strong> — short ratio ≥ 5, watch earnings dates closely</div>'

    return squeeze_note + f'''
  <div style="margin-bottom:18px">
    <div style="font-size:13px;font-weight:600;margin-bottom:8px;color:#f59e0b">{div_label}</div>
    <div style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;overflow:hidden">
      <table width="100%" cellspacing="0" cellpadding="0" style="font-size:13px">
        <thead><tr>{th('Ticker')}{th('Company')}{th('Ex-Date')}{th('Annual Div')}{th('Yield')}{th('Price')}</tr></thead>
        <tbody>{div_rows}</tbody>
      </table>
    </div>
  </div>

  <div style="margin-bottom:18px">
    <div style="font-size:13px;font-weight:600;margin-bottom:8px;color:#e8edf5">Earnings dates — short squeeze candidates flagged</div>
    <div style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;overflow:hidden">
      <table width="100%" cellspacing="0" cellpadding="0" style="font-size:13px">
        <thead><tr>{th('Ticker')}{th('Company')}{th('Earnings Date')}{th('Short Ratio')}{th('Squeeze?')}</tr></thead>
        <tbody>{earn_rows}</tbody>
      </table>
    </div>
  </div>'''

# ── SECTION 3: Price Movement ──────────────────────────────────
def build_price_movement_section(pm):
    downs = pm.get("downStreaks", [])
    ups   = pm.get("upStreaks",   [])

    def mov_rows(stocks, direction):
        if not stocks:
            return f'<tr><td colspan="7" style="padding:16px;text-align:center;color:#6b7a94">No stocks {direction} 3 consecutive days.</td></tr>'
        rows = ""
        for i, s in enumerate(stocks):
            sig       = s.get("signal", {})
            sig_name  = sig.get("name", "—")
            sig_color = signal_color(sig_name)
            sig_icon  = sig.get("icon", "")
            total_col = "#ef4444" if s.get("allDown") else "#22c55e"
            rsi       = s.get("rsi")
            rsi_str   = f"{rsi}" if rsi else "—"
            rsi_col   = "#22c55e" if rsi and rsi < 30 else ("#ef4444" if rsi and rsi > 70 else "#6b7a94")
            vs200     = s.get("vs200dPct")
            vs200_str = (("▲ " if vs200>=0 else "▼ ") + f"{abs(vs200):.1f}%") if vs200 is not None else "—"
            vs200_col = "#22c55e" if vs200 and vs200 >= 0 else "#ef4444"
            vol       = s.get("volSignal","normal")
            vol_str   = ("↑ Heavy" if vol=="heavy" else ("↓ Light" if vol=="light" else "Normal"))
            vol_col   = "#ef4444" if vol=="heavy" else ("#f59e0b" if vol=="light" else "#6b7a94")
            rows += f'''<tr style="background:{row_bg(i)}">
              <td style="padding:8px 12px;font-family:monospace;color:#60a5fa;font-weight:bold;border-bottom:1px solid #1e2a3a">{s['ticker']}</td>
              <td style="padding:8px 12px;border-bottom:1px solid #1e2a3a">{s.get('company','—')}</td>
              <td style="padding:8px 12px;font-family:monospace;color:#a0aec0;border-bottom:1px solid #1e2a3a">${s.get('price',0):.2f}</td>
              <td style="padding:8px 12px;font-family:monospace;color:{total_col};font-weight:bold;border-bottom:1px solid #1e2a3a">{pct_str(s.get('totalMove',0))}</td>
              <td style="padding:8px 12px;font-family:monospace;color:{rsi_col};border-bottom:1px solid #1e2a3a">{rsi_str}</td>
              <td style="padding:8px 12px;font-family:monospace;color:{vs200_col};border-bottom:1px solid #1e2a3a">{vs200_str}</td>
              <td style="padding:8px 12px;font-family:monospace;color:{vol_col};border-bottom:1px solid #1e2a3a">{vol_str}</td>
              <td style="padding:8px 12px;font-weight:bold;color:{sig_color};border-bottom:1px solid #1e2a3a">{sig_icon} {sig_name}</td>
            </tr>'''
        return rows

    down_rows = mov_rows(downs, "down")
    up_rows   = mov_rows(ups,   "up")

    # Alert banner for high-conviction signals
    alerts = []
    for s in downs:
        sig = s.get("signal", {})
        if sig.get("strength", 0) >= 2:
            alerts.append(f"{s['ticker']} ({sig.get('icon','')} {sig.get('name','')})")
    for s in ups:
        sig = s.get("signal", {})
        if sig.get("strength", 0) >= 2:
            alerts.append(f"{s['ticker']} ({sig.get('icon','')} {sig.get('name','')})")

    alert_banner = ""
    if alerts:
        alert_banner = f'<div style="background:#1c1a0a;border:1px solid #92400e;border-radius:6px;padding:10px 14px;margin-bottom:14px;font-size:13px;color:#fbbf24">⚠️ High-conviction signals today: <strong>{", ".join(alerts)}</strong></div>'

    return alert_banner + f'''
  <div style="margin-bottom:18px">
    <div style="font-size:13px;font-weight:600;margin-bottom:8px;color:#ef4444">📉 Down 3 consecutive days ({len(downs)} stocks)</div>
    <div style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;overflow:hidden">
      <table width="100%" cellspacing="0" cellpadding="0" style="font-size:13px">
        <thead><tr>{th('Ticker')}{th('Company')}{th('Price')}{th('3d Move')}{th('RSI')}{th('vs 200d MA')}{th('Volume')}{th('Signal')}</tr></thead>
        <tbody>{down_rows}</tbody>
      </table>
    </div>
  </div>

  <div style="margin-bottom:18px">
    <div style="font-size:13px;font-weight:600;margin-bottom:8px;color:#22c55e">📈 Up 3 consecutive days ({len(ups)} stocks)</div>
    <div style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;overflow:hidden">
      <table width="100%" cellspacing="0" cellpadding="0" style="font-size:13px">
        <thead><tr>{th('Ticker')}{th('Company')}{th('Price')}{th('3d Move')}{th('RSI')}{th('vs 200d MA')}{th('Volume')}{th('Signal')}</tr></thead>
        <tbody>{up_rows}</tbody>
      </table>
    </div>
  </div>'''

# ── Master email builder ───────────────────────────────────────
def build_email(insider, key_dates, price_movement):
    buys  = insider.get("buys", [])
    sells = insider.get("sells", [])
    today = datetime.now(PST).strftime("%A, %B %d, %Y")
    kd_updated = key_dates.get("updated", "—")
    pm_updated = price_movement.get("updated", "—")

    insider_html    = build_insider_section(insider)
    key_dates_html  = build_key_dates_section(key_dates)
    price_mov_html  = build_price_movement_section(price_movement)

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0a0e13;font-family:Arial,sans-serif;color:#e8edf5">
<div style="max-width:760px;margin:0 auto;padding:24px 16px">

  <!-- Header -->
  <div style="border-bottom:1px solid #1e2a3a;padding-bottom:18px;margin-bottom:22px">
    <div style="font-family:monospace;font-size:22px;font-weight:bold">samuel<span style="color:#3b82f6">stocks</span></div>
    <div style="color:#6b7a94;font-size:13px;margin-top:4px">Nightly DJIA Digest &mdash; {today}</div>
  </div>

  <!-- Quick nav -->
  <div style="background:#111720;border:1px solid #1e2a3a;border-radius:8px;padding:12px 16px;margin-bottom:24px;font-size:12px;color:#6b7a94">
    Jump to:
    <a href="#insider"  style="color:#3b82f6;text-decoration:none;margin-left:10px">① Insider Trading</a>
    <a href="#keydates" style="color:#3b82f6;text-decoration:none;margin-left:10px">② Key Dates</a>
    <a href="#movement" style="color:#3b82f6;text-decoration:none;margin-left:10px">③ Price Movement</a>
  </div>

  <!-- ① INSIDER TRADING -->
  <div id="insider">
    {section_header("① INSIDER TRADING", "#3b82f6")}
    {insider_html}
  </div>

  {divider()}

  <!-- ② KEY DATES -->
  <div id="keydates">
    {section_header("② KEY DATES", "#f59e0b")}
    <div style="font-size:11px;color:#6b7a94;margin-bottom:12px">Data as of {kd_updated}</div>
    {key_dates_html}
  </div>

  {divider()}

  <!-- ③ PRICE MOVEMENT -->
  <div id="movement">
    {section_header("③ PRICE MOVEMENT", "#22c55e")}
    <div style="font-size:11px;color:#6b7a94;margin-bottom:12px">Data as of {pm_updated}</div>
    {price_mov_html}
  </div>

  {divider()}

  <!-- Footer -->
  <div style="text-align:center;padding-top:8px">
    <a href="{SITE_URL}" style="display:inline-block;background:#1d4ed8;color:#fff;text-decoration:none;padding:10px 28px;border-radius:6px;font-size:13px;font-weight:500;margin-bottom:14px">Open Full Dashboard</a>
    <div style="font-size:11px;color:#6b7a94;line-height:1.7">
      Insider data: SEC EDGAR Form 4 &nbsp;|&nbsp; Prices &amp; technicals: Yahoo Finance<br>
      Updated nightly at midnight PST &nbsp;|&nbsp; Informational only — not financial advice.
    </div>
  </div>

</div></body></html>"""

# ── Send ───────────────────────────────────────────────────────
def send():
    insider       = json.load(open("data/insider.json"))
    key_dates     = json.load(open("data/key_dates.json"))
    price_movement= json.load(open("data/price_movement.json"))

    today  = datetime.now(PST).strftime("%B %d, %Y")
    buys   = insider.get("buys", [])
    sells  = insider.get("sells", [])
    downs  = price_movement.get("downStreaks", [])
    ups    = price_movement.get("upStreaks",   [])

    subject = f"Samuel Stocks — {today} | {len(buys)}B {len(sells)}S insider | {len(downs)} down {len(ups)} up streaks"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER
    msg["To"]      = ", ".join(RECIPIENTS)

    plain = (f"Samuel Stocks Nightly Digest — {today}\n\n"
             f"INSIDER TRADING: {len(buys)} buys, {len(sells)} sells\n"
             f"KEY DATES: {len(key_dates.get('dividends',[]))} dividend entries\n"
             f"PRICE MOVEMENT: {len(downs)} down streaks, {len(ups)} up streaks\n\n"
             f"Full dashboard: {SITE_URL}")

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(build_email(insider, key_dates, price_movement), "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(SENDER, PASSWORD)
        s.sendmail(SENDER, RECIPIENTS, msg.as_string())

    print(f"Email sent to: {', '.join(RECIPIENTS)}")

if __name__ == "__main__":
    send()
