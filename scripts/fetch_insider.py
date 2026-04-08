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

def col(row, *names, default=None):
    """Get first matching column from a pandas Series."""
    for n in names:
        if n in row.index:
            v = row[n]
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                return v
    return default

def safe_int(v):
    try:
        f = float(v)
        return 0 if pd.isna(f) else int(f)
    except:
        return 0

def fetch_ticker(ticker):
    company = COMPANY_NAMES.get(ticker, ticker)
    buys, sells = [], []
    cutoff = datetime.now(PST).date() - timedelta(days=30)

    try:
        df = yf.Ticker(ticker).insider_transactions
        if df is None or df.empty:
            print(f"  {ticker}: no data")
            return [], []

        # Print columns so we always know what yfinance returns
        print(f"  {ticker}: {len(df)} rows | cols={list(df.columns)}")

        for _, row in df.iterrows():
            try:
                # DATE
                raw = col(row, "startDate","Start Date","date","Date",
                          "transactionDate","filingDate")
                if raw is None: continue
                d = pd.Timestamp(raw).date() if hasattr(raw,'date') is False \
                    else raw.date() if hasattr(raw,'date') else \
                    datetime.strptime(str(raw)[:10],"%Y-%m-%d").date()
                if d < cutoff: continue
                date_str = d.strftime("%Y-%m-%d")

                # NAME — use pandas .loc not .get
                insider = str(col(row,
                    "filerName","Filer Name","name","Name",
                    "insider","Insider","holderName","Holder Name",
                    default="Unknown")).strip()

                # ROLE
                role = str(col(row,
                    "filerRelation","Filer Relation","relationship",
                    "Relationship","title","Title","position","relation",
                    default="Insider")).strip()

                # SHARES — positive=buy, negative=sell in yfinance
                raw_sh = col(row,"shares","Shares","sharesTraded",
                             "Shares Traded",default=None)
                if raw_sh is None: continue
                sh_float = float(raw_sh) if not pd.isna(float(raw_sh)) else 0
                sh_abs = abs(int(sh_float))
                if sh_abs == 0: continue

                # VALUE
                value = abs(safe_int(col(row,"value","Value",
                            "transactionValue",default=0)))

                # BUY vs SELL — sign of shares is the reliable signal
                if sh_float > 0:
                    is_buy, is_sell = True, False
                elif sh_float < 0:
                    is_buy, is_sell = False, True
                else:
                    # fallback: check text
                    txt = str(col(row,"transactionText","Transaction Text",
                                  "text","Text","transaction","Transaction",
                                  default="")).upper()
                    is_buy  = any(x in txt for x in ["PURCHASE","BUY","ACQUI"])
                    is_sell = any(x in txt for x in ["SALE","SELL","DISPO"])
                    if not is_buy and not is_sell: continue

                print(f"    {date_str} | {'BUY' if is_buy else 'SELL'} | {role:20} | {insider:25} | {sh_abs:>8,} | ${value:>10,}")

                record = {
                    "ticker": ticker, "company": company,
                    "insider": insider, "role": role,
                    "date": date_str,
                    "filing_url": f"https://finance.yahoo.com/quote/{ticker}/insider-transactions/",
                }
                if is_buy:
                    record["shares"] = sh_abs
                    record["value"]  = value
                    buys.append(record)
                else:
                    record["shares_sold"]      = sh_abs
                    record["shares_remaining"] = 0
                    record["expiry"]           = None
                    record["value"]            = value
                    sells.append(record)

            except Exception as e:
                continue

    except Exception as e:
        print(f"  {ticker}: ERROR - {e}")

    print(f"  {ticker}: -> {len(buys)} buys, {len(sells)} sells")
    return buys, sells

def main():
    all_buys, all_sells = [], []
    for ticker in DJIA_TICKERS:
        b, s = fetch_ticker(ticker)
        all_buys.extend(b)
        all_sells.extend(s)
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
            "buys": all_buys, "sells": all_sells,
        }, f, indent=2)
    print(f"\nDone: {len(all_buys)} buys, {len(all_sells)} sells -> data/insider.json")

if __name__ == "__main__":
    main()
