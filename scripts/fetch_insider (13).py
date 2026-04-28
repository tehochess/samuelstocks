import json, os, time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import yfinance as yf
import pandas as pd
from tickers import SP100_TICKERS, COMPANY_NAMES   # ← only change from original

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

        if len(df) > 0:
            first = df.iloc[0]
            for col in df.columns:
                print("  COL [" + col + "] = '" + str(first[col]) + "'")

        for _, row in df.iterrows():
            try:
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

                text_col  = str(row["Text"]      if "Text"      in row.index else "").strip().upper()
                url_col   = str(row["URL"]       if "URL"       in row.index else "").strip().upper()
                ownership = str(row["Ownership"] if "Ownership" in row.index else "").strip().upper()

                combined = text_col + " " + url_col + " " + ownership

                is_buy  = "PURCHASE" in combined or "ACQUI" in combined or "BUY"  in combined
                is_sell = "SALE"     in combined or "SELL"  in combined or "DISPO" in combined

                if not is_buy and not is_sell:
                    print("    NO_SIGNAL: " + insider + " | text='" + text_col + "' url='" + url_col[:50] + "' own='" + ownership + "'")
                    continue

                direction = "BUY" if is_buy else "SELL"
                print("    " + date_str + " | " + direction + " | " + insider + " | " + str(shares) + " | " + str(value))

                record = {
                    "ticker":     ticker,
                    "company":    company,
                    "insider":    insider,
                    "role":       role,
                    "date":       date_str,
                    "filing_url": "https://finance.yahoo.com/quote/" + ticker + "/insider-transactions/",
                }
                if is_buy:
                    record["shares"] = shares
                    record["value"]  = value
                    buys.append(record)
                else:
                    record["shares_sold"]      = shares
                    record["shares_remaining"] = 0
                    record["expiry"]           = None
                    record["value"]            = value
                    sells.append(record)

            except Exception as e:
                print("    row error: " + str(e))
                continue

    except Exception as e:
        print("  " + ticker + ": ERROR - " + str(e))

    print("  " + ticker + ": -> " + str(len(buys)) + " buys, " + str(len(sells)) + " sells")
    return buys, sells


def main():
    all_buys  = []
    all_sells = []

    for ticker in SP100_TICKERS:          # ← was DJIA_TICKERS
        b, s = fetch_ticker(ticker)
        all_buys.extend(b)
        all_sells.extend(s)
        time.sleep(0.5)

    def sort_key(x):
        r = (x.get("role") or "").upper()
        if "CEO" in r: return (0, -x.get("value", 0))
        if "CFO" in r: return (1, -x.get("value", 0))
        return             (2, -x.get("value", 0))

    all_buys.sort(key=sort_key)
    all_sells.sort(key=sort_key)

    now = datetime.now(PST)
    os.makedirs("data", exist_ok=True)
    with open("data/insider.json", "w") as f:
        json.dump({
            "updated":     now.strftime("%b %d, %Y %I:%M %p PST"),
            "updated_iso": now.isoformat(),
            "buys":        all_buys,
            "sells":       all_sells,
        }, f, indent=2)

    print("Done: " + str(len(all_buys)) + " buys, " + str(len(all_sells)) + " sells")


if __name__ == "__main__":
    main()
