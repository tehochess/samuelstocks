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
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

def fetch_ticker(ticker):
    """
    Use the OpenInsider cluster page for a specific ticker.
    This gives us ALL recent filings sorted by filing date descending.
    Much more reliable than the screener URL.
    """
    # This URL fetches the dedicated ticker page — sorted by most recent first
    url = f"http://openinsider.com/{ticker}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"    {ticker}: HTTP {r.status_code}")
            return []
        return parse_ticker_page(r.text, ticker)
    except Exception as e:
        print(f"    {ticker}: request error - {e}")
        return []

def parse_ticker_page(html, ticker):
    """Parse the OpenInsider ticker page — extracts all recent transactions."""
    company = COMPANY_NAMES.get(ticker, ticker)
    results = []

    # Find all tables on the page — we want the one with transaction data
    # OpenInsider ticker pages have a table with class "tinytable"
    tables = re.findall(r'<table[^>]*class="[^"]*tinytable[^"]*"[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE)

    if not tables:
        # fallback: find any tbody
        tables = re.findall(r'<tbody>(.*?)</tbody>', html, re.DOTALL | re.IGNORECASE)

    if not tables:
        print(f"    {ticker}: no table found")
        return []

    # Use the largest table (most data)
    table = max(tables, key=len)
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table, re.DOTALL | re.IGNORECASE)

    # cutoff: only show last 30 days
    cutoff = datetime.now(PST).date() - timedelta(days=30)

    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL | re.IGNORECASE)
        clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]

        if len(clean) < 11:
            continue

        try:
            # OpenInsider ticker page columns:
            # 0=X, 1=filing date, 2=trade date, 3=ticker, 4=company,
            # 5=insider name, 6=title, 7=trade type, 8=price,
            # 9=qty, 10=owned, 11=delta own%, 12=value

            filing_date_str = clean[1] if len(clean) > 1 else ""
            trade_date_str  = clean[2] if len(clean) > 2 else ""
            insider_name    = clean[5] if len(clean) > 5 else "Unknown"
            title           = clean[6] if len(clean) > 6 else "Insider"
            trade_type      = clean[7] if len(clean) > 7 else ""
            price_str       = clean[8] if len(clean) > 8 else "0"
            qty_str         = clean[9] if len(clean) > 9 else "0"
            owned_str       = clean[10] if len(clean) > 10 else "0"
            value_str       = clean[12] if len(clean) > 12 else "0"

            # Parse filing date for cutoff check
            try:
                # Date format from OpenInsider: "2026-04-03 18:30:45" or "2026-04-03"
                date_part = filing_date_str.split(" ")[0]
                filing_date = datetime.strptime(date_part, "%Y-%m-%d").date()
                if filing_date < cutoff:
                    continue  # skip old filings
            except Exception:
                pass  # if we can't parse date, include it anyway

            # Clean numeric strings
            def to_num(s):
                try:
                    return float(re.sub(r'[^\d.-]', '', s) or '0')
                except:
                    return 0.0

            price = to_num(price_str)
            qty   = abs(int(to_num(qty_str)))
            owned = abs(int(to_num(owned_str)))
            value = abs(int(to_num(value_str)))

            if qty == 0:
                continue

            # Determine buy vs sell
            # P = Purchase, S = Sale, S+OE = Sale after option exercise
            # We capture both pure sales AND sale+OE as sells
            tt_upper = trade_type.upper()
            is_buy  = tt_upper.startswith("P") or "PURCHASE" in tt_upper
            is_sell = tt_upper.startswith("S") or "SALE" in tt_upper

            if not is_buy and not is_sell:
                continue

            # Use trade date for display, filing date as fallback
            display_date = trade_date_str or filing_date_str

            filing_url = f"http://openinsider.com/{ticker}"

            computed_value = value if value > 0 else round(qty * price)

            print(f"      {trade_type:15} | {title:20} | {insider_name:25} | {qty:>10,} shares | ${computed_value:>12,} | {display_date}")

            record = {
                "ticker":  ticker,
                "company": company,
                "insider": insider_name,
                "role":    title,
                "date":    display_date,
                "filing_url": filing_url,
            }

            if is_buy:
                record["shares"] = qty
                record["value"]  = computed_value
                results.append(("buy", record))
            else:
                record["shares_sold"]      = qty
                record["shares_remaining"] = owned
                record["expiry"]           = None
                record["value"]            = computed_value
                results.append(("sell", record))

        except Exception as e:
            continue

    return results

def main():
    buys  = []
    sells = []

    for ticker in DJIA_TICKERS:
        print(f"  {ticker}...", flush=True)
        txns = fetch_ticker(ticker)
        print(f"    -> {len(txns)} transactions")
        for kind, record in txns:
            if kind == "buy":
                buys.append(record)
            else:
                sells.append(record)
        time.sleep(1.2)  # polite delay between requests

    # Sort: CEO/CFO first, then by value descending
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
            "buys":  buys,
            "sells": sells,
        }, f, indent=2)

    print(f"\nDone: {len(buys)} buys, {len(sells)} sells -> data/insider.json")

if __name__ == "__main__":
    main()
