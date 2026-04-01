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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def fetch_openinsider(ticker):
    """Fetch insider trades from OpenInsider for a ticker."""
    url = f"http://openinsider.com/screener?s={ticker}&o=&pl=&ph=&ll=&lh=&fd=30&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=30&xp=1&xs=1&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=40&page=1"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"    {ticker}: HTTP {r.status_code}")
            return []
        return parse_openinsider(r.text, ticker)
    except Exception as e:
        print(f"    {ticker}: error - {e}")
        return []

def parse_openinsider(html, ticker):
    """Parse OpenInsider HTML table."""
    results = []
    company = COMPANY_NAMES.get(ticker, ticker)

    # Find the data table
    table_m = re.search(r'<table[^>]*class="[^"]*tinytable[^"]*"[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE)
    if not table_m:
        # Try alternate table finding
        table_m = re.search(r'<tbody>(.*?)</tbody>', html, re.DOTALL | re.IGNORECASE)
        if not table_m:
            print(f"    {ticker}: no table found")
            return []
        tbody = table_m.group(1)
    else:
        tbody_m = re.search(r'<tbody>(.*?)</tbody>', table_m.group(1), re.DOTALL | re.IGNORECASE)
        tbody = tbody_m.group(1) if tbody_m else table_m.group(1)

    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbody, re.DOTALL | re.IGNORECASE)
    print(f"    {ticker}: {len(rows)} rows found")

    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL | re.IGNORECASE)
        # Strip HTML tags from cells
        clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
        if len(clean) < 10:
            continue

        try:
            # OpenInsider columns:
            # 0=filing date, 1=trade date, 2=ticker, 3=company, 4=insider, 5=title,
            # 6=type, 7=price, 8=qty, 9=owned, 10=change, 11=value
            trade_date = clean[1] if len(clean) > 1 else ""
            insider_name = clean[4] if len(clean) > 4 else "Unknown"
            title = clean[5] if len(clean) > 5 else "Insider"
            trade_type = clean[6] if len(clean) > 6 else ""
            price_str = clean[7] if len(clean) > 7 else "0"
            qty_str = clean[8] if len(clean) > 8 else "0"
            owned_str = clean[9] if len(clean) > 9 else "0"
            value_str = clean[11] if len(clean) > 11 else "0"

            # Clean numbers
            def clean_num(s):
                try:
                    return float(re.sub(r'[^\d.-]', '', s) or '0')
                except:
                    return 0.0

            price = clean_num(price_str)
            qty = abs(int(clean_num(qty_str)))
            owned = abs(int(clean_num(owned_str)))
            value = abs(int(clean_num(value_str)))

            if qty == 0:
                continue

            # P = Purchase, S = Sale
            is_buy = "P" in trade_type or "Purchase" in trade_type
            is_sell = "S" in trade_type or "Sale" in trade_type

            if not is_buy and not is_sell:
                print(f"      skipping type: {trade_type}")
                continue

            filing_url = f"http://openinsider.com/screener?s={ticker}"

            print(f"      {trade_type} | {insider_name} | {qty:,} shares @ ${price} | {trade_date}")

            record = {
                "ticker": ticker,
                "company": company,
                "insider": insider_name,
                "role": title,
                "date": trade_date,
                "filing_url": filing_url,
            }

            if is_buy:
                record["shares"] = qty
                record["value"] = value or round(qty * price)
                results.append(("buy", record))
            else:
                record["shares_sold"] = qty
                record["shares_remaining"] = owned
                record["expiry"] = None
                record["value"] = value or round(qty * price)
                results.append(("sell", record))

        except Exception as e:
            print(f"      row parse error: {e}")
            continue

    return results

def main():
    buys = []
    sells = []

    for ticker in DJIA_TICKERS:
        print(f"  {ticker}...", flush=True)
        txns = fetch_openinsider(ticker)
        for kind, record in txns:
            if kind == "buy":
                buys.append(record)
            else:
                sells.append(record)
        time.sleep(1.5)  # be polite to OpenInsider

    def sort_key(x):
        r = (x.get("role") or "").upper()
        if "CEO" in r:
            return (0, -x.get("value", 0))
        elif "CFO" in r:
            return (1, -x.get("value", 0))
        else:
            return (2, -x.get("value", 0))

    buys.sort(key=sort_key)
    sells.sort(key=sort_key)

    now = datetime.now(PST)
    os.makedirs("data", exist_ok=True)
    with open("data/insider.json", "w") as f:
        json.dump({
            "updated": now.strftime("%b %d, %Y %I:%M %p PST"),
            "updated_iso": now.isoformat(),
            "buys": buys,
            "sells": sells
        }, f, indent=2)

    print(f"\nDone: {len(buys)} buys, {len(sells)} sells -> data/insider.json")

if __name__ == "__main__":
    main()
