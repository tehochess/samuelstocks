import json, os, time
from datetime import datetime, timedelta
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

PST = ZoneInfo("America/Los_Angeles")

def safe_float(v):
    try:
        f = float(v)
        return 0.0 if pd.isna(f) else round(f, 2)
    except:
        return 0.0

def fetch_ticker(ticker):
    company = COMPANY_NAMES.get(ticker, ticker)
    dividend_row = None
    earnings_row = None

    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # --- DIVIDEND ---
        ex_ts = info.get("exDividendDate")
        if ex_ts:
            ex_str = datetime.fromtimestamp(ex_ts).strftime("%Y-%m-%d")
        else:
            ex_str = "N/A"

        div_rate = safe_float(info.get("dividendRate", 0))
        div_yield_raw = safe_float(info.get("dividendYield", 0))
        # Yahoo Finance returns yield as a decimal (e.g. 0.0589 = 5.89%)
        # If it's already > 1, it came in as a percentage, don't multiply
        if div_yield_raw > 1:
            div_yield_pct = round(div_yield_raw, 2)
        else:
            div_yield_pct = round(div_yield_raw * 100, 2)
        price = safe_float(info.get("currentPrice") or info.get("regularMarketPrice", 0))

        dividend_row = {
            "ticker": ticker,
            "company": company,
            "exDate": ex_str,
            "dividendRate": div_rate,
            "dividendYield": div_yield_pct,
            "price": price,
        }
        print("  " + ticker + ": ex=" + ex_str + " rate=$" + str(div_rate))

        # --- EARNINGS ---
        short_ratio = safe_float(info.get("shortRatio", 0))
        short_pct = safe_float(info.get("shortPercentOfFloat", 0))

        earn_str = "N/A"
        try:
            cal = stock.calendar
            if cal is not None and not cal.empty:
                if isinstance(cal, dict):
                    ed = cal.get("Earnings Date")
                    if ed:
                        earn_str = str(ed[0])[:10] if isinstance(ed, list) else str(ed)[:10]
                else:
                    earn_str = str(cal.columns[0])[:10]
        except Exception as e:
            print("  " + ticker + ": calendar err - " + str(e))

        squeeze_flag = short_ratio >= 5.0

        earnings_row = {
            "ticker": ticker,
            "company": company,
            "earningsDate": earn_str,
            "shortRatio": short_ratio,
            "shortPct": round(short_pct * 100, 2) if short_pct else 0,
            "squeezeFlag": squeeze_flag,
        }
        print("  " + ticker + ": earn=" + earn_str + " short_ratio=" + str(short_ratio))

    except Exception as e:
        print("  " + ticker + ": ERROR - " + str(e))
        dividend_row = {"ticker": ticker, "company": company, "exDate": "N/A", "dividendRate": 0, "dividendYield": 0, "price": 0}
        earnings_row = {"ticker": ticker, "company": company, "earningsDate": "N/A", "shortRatio": 0, "shortPct": 0, "squeezeFlag": False}

    return dividend_row, earnings_row


def main():
    dividends = []
    earnings = []

    for ticker in DJIA_TICKERS:
        d, e = fetch_ticker(ticker)
        if d:
            dividends.append(d)
        if e:
            earnings.append(e)
        time.sleep(0.5)

    # Sort dividends by ex-date soonest first (N/A goes to bottom)
    dividends.sort(key=lambda x: x["exDate"] if x["exDate"] != "N/A" else "9999")

    # Sort earnings by short ratio descending (squeeze candidates first)
    earnings.sort(key=lambda x: -x["shortRatio"])

    now = datetime.now(PST)
    os.makedirs("data", exist_ok=True)
    with open("data/key_dates.json", "w") as f:
        json.dump({
            "updated": now.strftime("%b %d, %Y %I:%M %p PST"),
            "updated_iso": now.isoformat(),
            "dividends": dividends,
            "earnings": earnings,
        }, f, indent=2)

    print("Done: " + str(len(dividends)) + " dividend rows, " + str(len(earnings)) + " earnings rows")


if __name__ == "__main__":
    main()
