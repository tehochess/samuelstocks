"""
fetch_insider.py
Uses yfinance to pull insider trading data directly from Yahoo Finance.
Yahoo Finance is designed for programmatic server access — never blocked.
"""
import json, os, time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import yfinance as yf

DJIA_TICKERS = [
    "AAPL","AMGN","AXP","BA","CAT","CRM","CSCO","CVX","DIS","DOW",
    "GS","HD","HON","IBM","INTC","JNJ","JPM","KO","MCD","MMM",
    "MRK","MSFT","NKE","PG","TRV","UNH","V","VZ","WBA","WMT"
]

COMPANY_NAMES = {
    "AAPL":"Apple","AMGN":"Amgen","AXP":"American Express","BA":"Boeing",
    "CAT":"Caterpillar","CRM":"Salesforce","CSCO":"Cisco","CVX":"Chevron",
    "DIS":"Disney","DOW":"Dow Inc","GS":"Goldman Sachs","HD":"Home Depot",
    "HON":"Honeywell","IBM":"IBM","INTC":"Intel","JNJ":"Johnson & Johnson",
    "JPM":"JPMorgan Chase","KO":"Coca-Cola","MCD":"McDonald's","MMM":"3M",
    "MRK":"Merck","MSFT":"Microsoft","NKE":"Nike","PG":"Procter & Gamble",
    "TRV":"Travelers","UNH":"UnitedHealth","V":"Visa","VZ":"Verizon",
    "WBA":"Walgreens","WMT":"Walmart",
}

PST = ZoneInfo("America/Los_Angeles")

def fetch_ticker(ticker):
    company = COMPANY_NAMES.get(ticker, ticker)
    buys, sells = [], []

    try:
        stock = yf.Ticker(ticker)
        df = stock.insider_transactions

        if df is None or df.empty:
            print(f"  {ticker}: no data")
            return [], []

        print(f"  {ticker}: {len(df)} transactions")

        # Filter to last 30 days
        cutoff = datetime.now(PST).date() - timedelta(days=30)

        for _, row in df.iterrows():
            try:
                # Parse date
                start_date = row.get("startDate") or row.get("Start Date") or row.get("date")
                if start_date is None:
                    continue

                # Convert to date object
                if hasattr(start_date, 'date'):
                    trade_date = start_date.date()
                else:
                    try:
                        trade_date = datetime.strptime(str(start_date)[:10], "%Y-%m-%d").date()
                    except:
                        continue

                if trade_date < cutoff:
                    continue

                date_str = trade_date.strftime("%Y-%m-%d")

                # Get fields — yfinance column names vary slightly by version
                insider = str(row.get("filerName") or row.get("Filer Name") or row.get("insider") or "Unknown").strip()
                role    = str(row.get("filerRelation") or row.get("Filer Relation") or row.get("relationship") or "Insider").strip()
                shares  = int(abs(float(row.get("shares") or row.get("Shares") or 0)))
                value   = int(abs(float(row.get("value") or row.get("Value") or 0)))
                text    = str(row.get("transactionText") or row.get("Transaction") or row.get("text") or "").upper()

                if shares == 0:
                    continue

                print(f"    {date_str} | {role:20} | {insider:25} | {shares:>8,} | ${value:>10,} | {text[:30]}")

                # Determine buy vs sell from transaction text
                is_buy  = "PURCHASE" in text or "BUY" in text or "ACQUISITION" in text
                is_sell = "SALE" in text or "SELL" in text or "DISPOSED" in text

                if not is_buy and not is_sell:
                    # If unclear, skip — we only want clear signals
                    continue

                record = {
                    "ticker":      ticker,
                    "company":     company,
                    "insider":     insider,
                    "role":        role,
                    "date":        date_str,
                    "filing_url":  f"https://finance.yahoo.com/quote/{ticker}/insider-transactions/",
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
                print(f"    row error: {e}")
                continue

    except Exception as e:
        print(f"  {ticker}: ERROR - {e}")

    return buys, sells


def main():
    all_buys, all_sells = [], []

    for ticker in DJIA_TICKERS:
        buys, sells = fetch_ticker(ticker)
        all_buys.extend(buys)
        all_sells.extend(sells)
        time.sleep(0.5)

    def sort_key(x):
        r = (x.get("role") or "").upper()
        if "CEO" in r:   return (0, -x.get("value", 0))
        elif "CFO" in r: return (1, -x.get("value", 0))
        else:            return (2, -x.get("value", 0))

    all_buys.sort(key=sort_key)
    all_sells.sort(key=sort_key)

    now = datetime.now(PST)
    os.makedirs("data", exist_ok=True)
    with open("data/insider.json", "w") as f:
        json.dump({
            "updated":     now.strftime("%b %d, %Y %I:%M %p PST"),
            "updated_iso": now.isoformat(),
            "buys":  all_buys,
            "sells": all_sells,
        }, f, indent=2)

    print(f"\nDone: {len(all_buys)} buys, {len(all_sells)} sells -> data/insider.json")

if __name__ == "__main__":
    main()
