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

def safe_int(v):
    try:
        f = float(v)
        return 0 if pd.isna(f) else int(f)
    except Exception:
        return 0

def fetch_ticker(ticker):
    company = COMPANY_NAMES.get(ticker, ticker)
    buys = []
    sells = []
    cutoff = datetime.now(PST).date() - timedelta(days=30)

    try:
        df = yf.Ticker(ticker).insider_transactions
        if df is None or df.empty:
            print("  " + ticker + ": no data")
            return [], []

        print("  " + ticker + ": " + str(len(df)) + " rows")

        # Debug first row — print ALL column values
        if len(df) > 0:
            first = df.iloc[0]
            for col in df.columns:
                print("  COL [" + col + "] = '" + str(first[col]) + "'")

        for _, row in df.iterrows():
            try:
                # DATE
                raw = row["Start Date"] if "Start Date" in row.index else None
                if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                    continue
                d = pd.Timestamp(raw).date()
                if d < cutoff:
                    continue
                date_str = d.strftime("%Y-%m-%d")

                insider = str(row["Insider"] if "Insider" in row.index else "Unknown").strip()
                role = str(row["Position"] if "Position" in row.index else "Insider").strip()
                shares = abs(safe_int(row["Shares"] if "Shares" in row.index else 0))
                if shares == 0:
                    continue
                value = abs(safe_int(row["Value"] if "Value" in row.index else 0))

                # Check ALL text columns for buy/sell signal
                text_col = str(row["Text"] if "Text" in row.index else "").strip().upper()
                url_col = str(row["URL"] if "URL" in row.index else "").strip().upper()
                ownership = str(row["Ownership"] if "Ownership" in row.index else "").strip().upper()

                combined = text_col + " " + url_col + " " + ownership

                is_buy = "PURCHASE" in combined or "ACQUI" in combined or "BUY" in combined
                is_sell = "SALE" in combined or "SELL" in combined or "DISPO" in combined

                # Last resort: if Ownership is "D" (direct) with shares > 0, likely a buy
                # Use the URL which often contains transaction type
                if not is_buy and not is_sell:
                    # Just classify everything as a buy for now and log
                    print("    NO_SIGNAL: " + insider + " | text='" + text_col + "' url='" + url_col[:50] + "' own='" + ownership + "'")
                    continue

                direction = "BUY" if is_buy else "SELL"
                print("    " + date_str + " | " + direction + " | " + insider + " | " + str(shares) + " | " + str(value))

                record = {
                    "ticker": ticker,
                    "company": company,
                    "insider": insider,
                    "role": role,
                    "date": date_str,
                    "filing_url": "https://finance.yahoo.com/quote/" + ticker + "/insider-transactions/",
                }
                if is_buy:
                    record["shares"] = shares
                    record["value"] = value
                    buys.append(record)
                else:
                    record["shares_sold"] = shares
                    record["shares_remaining"] = 0
                    record["expiry"] = None
                    record["value"] = value
                    sells.append(record)

            except Exception as e:
                print("    row error: " + str(e))
                continue

    except Exception as e:
        print("  " + ticker + ": ERROR - " + str(e))

    print("  " + ticker + ": -> " + str(len(buys)) + " buys, " + str(len(sells)) + " sells")
    return buys, sells


def main():
    all_buys = []
    all_sells = []

    for ticker in DJIA_TICKERS:
        b, s = fetch_ticker(ticker)
        all_buys.extend(b)
        all_sells.extend(s)
        time.sleep(0.5)

    def sort_key(x):
        r = (x.get("role") or "").upper()
        if "CEO" in r:
            return (0, -x.get("value", 0))
        elif "CFO" in r:
            return (1, -x.get("value", 0))
        else:
            return (2, -x.get("value", 0))

    all_buys.sort(key=sort_key)
    all_sells.sort(key=sort_key)

    now = datetime.now(PST)
    os.makedirs("data", exist_ok=True)
    with open("data/insider.json", "w") as f:
        json.dump({
            "updated": now.strftime("%b %d, %Y %I:%M %p PST"),
            "updated_iso": now.isoformat(),
            "buys": all_buys,
            "sells": all_sells,
        }, f, indent=2)

    print("Done: " + str(len(all_buys)) + " buys, " + str(len(all_sells)) + " sells")


if __name__ == "__main__":
    main()
