import json, os, re, time, requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def fetch_ticker(ticker):
    """
    Use OpenInsider screener with a 60-day window and sort by filing date descending.
    This reliably captures all recent transactions including S+OE (sale + option exercise).
    xp=1 includes purchases, xs=1 includes sales, sortcol=1 sorts by filing date desc.
    """
    url = (
        f"http://openinsider.com/screener?s={ticker}&o=&pl=&ph=&ll=&lh="
        f"&fd=60&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&xs=1"
        f"&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999"
        f"&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h="
        f"&sortcol=1&cnt=40&page=1"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"    {ticker}: HTTP {r.status_code}")
            return []
        return parse_page(r.text, ticker)
    except Exception as e:
        print(f"    {ticker}: error - {e}")
        return []

def parse_page(html, ticker):
    company = COMPANY_NAMES.get(ticker, ticker)
    results = []

    # Find the data table
    table_m = re.search(r'<tbody>(.*?)</tbody>', html, re.DOTALL | re.IGNORECASE)
    if not table_m:
        return []

    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_m.group(1), re.DOTALL | re.IGNORECASE)

    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL | re.IGNORECASE)
        clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]

        if len(clean) < 11:
            continue

        try:
            filing_date_str = clean[1] if len(clean) > 1 else ""
            trade_date_str  = clean[2] if len(clean) > 2 else ""
            insider_name    = clean[4] if len(clean) > 4 else "Unknown"
            title           = clean[5] if len(clean) > 5 else "Insider"
            trade_type      = clean[6] if len(clean) > 6 else ""
            price_str       = clean[7] if len(clean) > 7 else "0"
            qty_str         = clean[8] if len(clean) > 8 else "0"
            owned_str       = clean[9] if len(clean) > 9 else "0"
            value_str       = clean[11] if len(clean) > 11 else "0"

            def to_num(s):
                try: return float(re.sub(r'[^\d.-]', '', s) or '0')
                except: return 0.0

            price = to_num(price_str)
            qty   = abs(int(to_num(qty_str)))
            owned = abs(int(to_num(owned_str)))
            value = abs(int(to_num(value_str)))

            if qty == 0:
                continue

            tt = trade_type.upper()
            # Capture P=purchase, S=sale, S-Sale+OE=sale after option exercise
            is_buy  = tt.startswith("P") or tt == "P - PURCHASE"
            is_sell = tt.startswith("S") or "SALE" in tt

            if not is_buy and not is_sell:
                print(f"      skipping: {trade_type}")
                continue

            display_date = trade_date_str or filing_date_str
            filing_url   = f"http://openinsider.com/screener?s={ticker}"
            computed_val = value if value > 0 else round(qty * price)

            print(f"      {trade_type:20} | {title:20} | {insider_name:25} | {qty:>8,} | ${computed_val:>12,} | {display_date}")

            record = {
                "ticker": ticker, "company": company,
                "insider": insider_name, "role": title,
                "date": display_date, "filing_url": filing_url,
            }

            if is_buy:
                record["shares"] = qty
                record["value"]  = computed_val
                results.append(("buy", record))
            else:
                record["shares_sold"]      = qty
                record["shares_remaining"] = owned
                record["expiry"]           = None
                record["value"]            = computed_val
                results.append(("sell", record))

        except Exception as e:
            continue

    return results

def main():
    buys, sells = [], []

    for ticker in DJIA_TICKERS:
        print(f"  {ticker}...", flush=True)
        txns = fetch_ticker(ticker)
        print(f"    -> {len(txns)} transactions")
        for kind, record in txns:
            if kind == "buy": buys.append(record)
            else: sells.append(record)
        time.sleep(1.2)

    def sort_key(x):
        r = (x.get("role") or "").upper()
        if "CEO" in r:   return (0, -x.get("value", 0))
        elif "CFO" in r: return (1, -x.get("value", 0))
        else:            return (2, -x.get("value", 0))

    buys.sort(key=sort_key)
    sells.sort(key=sort_key)

    now = datetime.now(PST)
    os.makedirs("data", exist_ok=True)
    with open("data/insider.json", "w") as f:
        json.dump({
            "updated":     now.strftime("%b %d, %Y %I:%M %p PST"),
            "updated_iso": now.isoformat(),
            "buys": buys, "sells": sells,
        }, f, indent=2)

    print(f"\nDone: {len(buys)} buys, {len(sells)} sells -> data/insider.json")

if __name__ == "__main__":
    main()
