import json, os, time
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
import yfinance as yf
import pandas as pd

DJIA_TICKERS = [
    "AAPL","AMGN","AXP","BA","CAT","CRM","CSCO","CVX","DIS","DOW",
    "GS","HD","HON","IBM","INTC","JNJ","JPM","KO","MCD","MMM",
    "MRK","MSFT","NKE","PG","TRV","UNH","V","VZ","WMT"
]

COMPANY_NAMES = {
    "AAPL":"Apple","AMGN":"Amgen","AXP":"American Express","BA":"Boeing",
    "CAT":"Caterpillar","CRM":"Salesforce","CSCO":"Cisco","CVX":"Chevron",
    "DIS":"Disney","DOW":"Dow Inc","GS":"Goldman Sachs","HD":"Home Depot",
    "HON":"Honeywell","IBM":"IBM","INTC":"Intel","JNJ":"Johnson & Johnson",
    "JPM":"JPMorgan Chase","KO":"Coca-Cola","MCD":"McDonald's","MMM":"3M",
    "MRK":"Merck","MSFT":"Microsoft","NKE":"Nike","PG":"Procter & Gamble",
    "TRV":"Travelers","UNH":"UnitedHealth","V":"Visa","VZ":"Verizon",
    "WMT":"Walmart",
}

PST   = ZoneInfo("America/Los_Angeles")
TODAY = date.today()

def safe_float(v):
    try:
        f = float(v)
        return 0.0 if pd.isna(f) else round(f, 4)
    except:
        return 0.0

def fetch_ticker(ticker):
    company = COMPANY_NAMES.get(ticker, ticker)
    dividend_row = None
    earnings_row = None

    try:
        stock = yf.Ticker(ticker)
        info  = stock.info

        # ── DIVIDEND ──────────────────────────────────────────────
        ex_ts = info.get("exDividendDate")
        ex_str = "N/A"
        ex_status = "none"   # "upcoming" | "recent" | "suspended" | "none"

        if ex_ts:
            ex_date_obj = datetime.fromtimestamp(ex_ts).date()
            ex_str      = ex_date_obj.strftime("%Y-%m-%d")
            days_ago    = (TODAY - ex_date_obj).days

            if ex_date_obj >= TODAY:
                ex_status = "upcoming"          # future — genuinely upcoming
            elif days_ago <= 90:
                ex_status = "recent"            # past but within 90 days — still useful context
            elif days_ago > 365:
                ex_str    = "Suspended"
                ex_status = "suspended"         # Boeing, Intel etc
            else:
                ex_status = "recent"            # 90–365 days ago — show but label correctly

        div_rate = safe_float(info.get("dividendRate", 0))
        price    = safe_float(info.get("currentPrice") or info.get("regularMarketPrice", 0))

        # Calculate yield directly — bypasses Yahoo's inconsistent dividendYield field
        if div_rate > 0 and price > 0:
            div_yield_pct = round((div_rate / price) * 100, 2)
        else:
            div_yield_pct = 0.0

        # Sanity check: no Dow 30 stock pays above 15% yield
        if div_yield_pct > 15:
            div_yield_pct = 0.0

        dividend_row = {
            "ticker":        ticker,
            "company":       company,
            "exDate":        ex_str,
            "exStatus":      ex_status,
            "dividendRate":  round(div_rate, 2),
            "dividendYield": div_yield_pct,
            "price":         round(price, 2),
        }
        print("  " + ticker + ": ex=" + ex_str + " [" + ex_status + "] rate=$" + str(round(div_rate,2)) + " yield=" + str(div_yield_pct) + "%")

        # ── EARNINGS ──────────────────────────────────────────────
        short_ratio = safe_float(info.get("shortRatio", 0))
        short_pct   = safe_float(info.get("shortPercentOfFloat", 0))

        earn_str = "N/A"
        try:
            cal = stock.calendar
            if cal is not None and not cal.empty:
                candidates = []
                if isinstance(cal, dict):
                    ed = cal.get("Earnings Date")
                    if ed:
                        candidates = ed if isinstance(ed, list) else [ed]
                else:
                    candidates = list(cal.columns)

                # Only keep FUTURE earnings dates
                future_dates = []
                for c in candidates:
                    try:
                        d = pd.Timestamp(c).date()
                        if d >= TODAY:
                            future_dates.append(d)
                    except:
                        pass

                if future_dates:
                    future_dates.sort()
                    earn_str = str(future_dates[0])
        except Exception as e:
            print("  " + ticker + ": calendar err - " + str(e))

        squeeze_flag = short_ratio >= 5.0
        short_pct_display = round(short_pct * 100, 1) if short_pct < 1 else round(short_pct, 1)

        earnings_row = {
            "ticker":       ticker,
            "company":      company,
            "earningsDate": earn_str,
            "shortRatio":   round(short_ratio, 1),
            "shortPct":     short_pct_display,
            "squeezeFlag":  squeeze_flag,
        }
        print("  " + ticker + ": earn=" + earn_str + " short_ratio=" + str(round(short_ratio,1)))

    except Exception as e:
        print("  " + ticker + ": ERROR - " + str(e))
        dividend_row = {"ticker": ticker, "company": company, "exDate": "N/A", "exStatus": "none", "dividendRate": 0, "dividendYield": 0, "price": 0}
        earnings_row = {"ticker": ticker, "company": company, "earningsDate": "N/A", "shortRatio": 0, "shortPct": 0, "squeezeFlag": False}

    return dividend_row, earnings_row


def main():
    dividends = []
    earnings  = []

    for ticker in DJIA_TICKERS:
        d, e = fetch_ticker(ticker)
        if d: dividends.append(d)
        if e: earnings.append(e)
        time.sleep(0.5)

    # Sort: upcoming first, then recent (by date desc), then suspended/none
    def div_sort(x):
        status = x.get("exStatus", "none")
        ex     = x.get("exDate", "")
        if status == "upcoming":   return ("0", ex)      # future dates first
        if status == "recent":     return ("1", ex)      # recent past next
        if status == "suspended":  return ("3", ex)      # suspended last
        return ("4", ex)
    dividends.sort(key=div_sort)

    # Check if any upcoming ex-dates exist at all
    has_upcoming = any(d.get("exStatus") == "upcoming" for d in dividends)

    earnings.sort(key=lambda x: -x["shortRatio"])

    now = datetime.now(PST)
    os.makedirs("data", exist_ok=True)
    with open("data/key_dates.json", "w") as f:
        json.dump({
            "updated":      now.strftime("%b %d, %Y %I:%M %p PST"),
            "updated_iso":  now.isoformat(),
            "hasUpcoming":  has_upcoming,   # tells email/website whether dates are future or recent
            "dividends":    dividends,
            "earnings":     earnings,
        }, f, indent=2)

    upcoming_count = sum(1 for d in dividends if d.get("exStatus") == "upcoming")
    recent_count   = sum(1 for d in dividends if d.get("exStatus") == "recent")
    print("Done: " + str(upcoming_count) + " upcoming, " + str(recent_count) + " recent, " + str(len(earnings)) + " earnings rows")


if __name__ == "__main__":
    main()
