"""
fetch_insider.py — Triple-source insider trading fetcher
=========================================================
Source priority:
  1. SEC EDGAR EFTS API  — official US government, structured JSON, most reliable
  2. SEC EDGAR submissions — official backup, direct filing data
  3. OpenInsider screener  — final fallback if both SEC sources fail

This means we are NEVER at the mercy of a single source.
If one fails, the next takes over automatically.
"""

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

# Hardcoded CIK map — never fails, no network needed
CIKS = {
    "AAPL":"0000320193","AMGN":"0000820081","AXP":"0000004962","BA":"0000012927",
    "CAT":"0000018230","CRM":"0001108524","CSCO":"0000858877","CVX":"0000093410",
    "DIS":"0001001039","DOW":"0001751788","GS":"0000886982","HD":"0000354950",
    "HON":"0000773840","IBM":"0000051143","INTC":"0000050863","JNJ":"0000200406",
    "JPM":"0000019617","KO":"0000021344","MCD":"0000063908","MMM":"0000066740",
    "MRK":"0000310158","MSFT":"0000789019","NKE":"0000320187","PG":"0000080424",
    "TRV":"0000086312","UNH":"0000731766","V":"0001403161","VZ":"0000732712",
    "WBA":"0001141788","WMT":"0000104169",
}

PST = ZoneInfo("America/Los_Angeles")

SEC_HEADERS = {
    "User-Agent": "samuelstocks-dashboard tehochess@github.com",
    "Accept-Encoding": "gzip, deflate",
    "Host": "efts.sec.gov",
}

SEC_HEADERS2 = {
    "User-Agent": "samuelstocks-dashboard tehochess@github.com",
    "Accept-Encoding": "gzip, deflate",
}

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def safe_get(url, headers, timeout=20, retries=2):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200 and len(r.text) > 100:
                return r
            print(f"      attempt {attempt+1}: HTTP {r.status_code}, len={len(r.text)}")
        except Exception as e:
            print(f"      attempt {attempt+1}: {e}")
        if attempt < retries - 1:
            time.sleep(3)
    return None

# =============================================================================
# SOURCE 1: SEC EDGAR EFTS (full-text search API)
# Official SEC API. Returns structured JSON. No HTML parsing needed.
# =============================================================================
def fetch_via_efts(ticker, days=30):
    """
    SEC's EFTS API: https://efts.sec.gov/LATEST/search-index
    Searches the full text of all Form 4 filings for a ticker.
    Returns JSON with filing metadata.
    """
    cutoff = (datetime.now(PST) - timedelta(days=days)).strftime("%Y-%m-%d")
    url = (
        f"https://efts.sec.gov/LATEST/search-index"
        f"?q=%22{ticker}%22"
        f"&dateRange=custom&startdt={cutoff}"
        f"&forms=4"
        f"&hits.hits._source=period_of_report,entity_name,file_date,period_of_report"
        f"&hits.hits.total.value=true"
    )
    r = safe_get(url, SEC_HEADERS, timeout=15)
    if not r:
        return None

    try:
        data = r.json()
        hits = data.get("hits", {}).get("hits", [])
        print(f"      EFTS: {len(hits)} filings found")
        return hits
    except Exception as e:
        print(f"      EFTS parse error: {e}")
        return None

def parse_efts_filing(hit, ticker):
    """Parse a single EFTS hit and fetch the actual filing XML."""
    try:
        src = hit.get("_source", {})
        accession = hit.get("_id", "").replace(":", "-")
        cik = CIKS.get(ticker, "").lstrip("0")
        if not cik or not accession:
            return []

        file_date = src.get("file_date", "")
        acc_clean = accession.replace("-", "")
        xml_url   = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_clean}/{accession}.xml"
        pub_url   = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_clean}/{accession}-index.htm"

        r = safe_get(xml_url, SEC_HEADERS2, timeout=15)
        if not r or "ownershipDocument" not in r.text:
            return []

        return parse_form4_xml(r.text, ticker, COMPANY_NAMES.get(ticker, ticker), file_date, pub_url)
    except Exception as e:
        print(f"      filing parse error: {e}")
        return []

# =============================================================================
# SOURCE 2: SEC EDGAR submissions API
# Official SEC API. Returns all recent filings for a company CIK.
# =============================================================================
def fetch_via_submissions(ticker, days=30):
    """
    SEC submissions API: https://data.sec.gov/submissions/CIK{cik}.json
    Returns all recent filings for a company. We filter for Form 4s.
    """
    cik = CIKS.get(ticker)
    if not cik:
        return None

    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    r = safe_get(url, SEC_HEADERS2, timeout=15)
    if not r:
        return None

    try:
        data = r.json()
        filings = data.get("filings", {}).get("recent", {})
        cutoff  = (datetime.now(PST) - timedelta(days=days)).date()
        results = []

        forms   = filings.get("form", [])
        dates   = filings.get("filingDate", [])
        accnums = filings.get("accessionNumber", [])

        for i, form in enumerate(forms):
            if form != "4":
                continue
            try:
                d = datetime.strptime(dates[i], "%Y-%m-%d").date()
                if d >= cutoff:
                    results.append({"date": dates[i], "acc": accnums[i]})
            except:
                pass

        print(f"      Submissions API: {len(results)} Form 4s found")
        return results
    except Exception as e:
        print(f"      Submissions parse error: {e}")
        return None

def fetch_form4_xml(ticker, acc_raw, date):
    """Fetch and parse a Form 4 XML filing."""
    cik     = CIKS.get(ticker, "").lstrip("0")
    acc     = acc_raw.replace("-", "")
    pub_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{acc_raw}-index.htm"

    for fname in [f"{acc_raw}.xml", "form4.xml"]:
        r = safe_get(
            f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{fname}",
            SEC_HEADERS2, timeout=15
        )
        if r and "ownershipDocument" in r.text:
            return parse_form4_xml(r.text, ticker, COMPANY_NAMES.get(ticker, ticker), date, pub_url)

    # Scrape index for XML filename
    r = safe_get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/", SEC_HEADERS2, timeout=10)
    if r:
        for fname in re.findall(r'href="([^"]+\.xml)"', r.text):
            url = f"https://www.sec.gov{fname}" if fname.startswith("/") else \
                  f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{fname}"
            xr = safe_get(url, SEC_HEADERS2, timeout=15)
            if xr and "ownershipDocument" in xr.text:
                return parse_form4_xml(xr.text, ticker, COMPANY_NAMES.get(ticker, ticker), date, pub_url)
    return []

def parse_form4_xml(xml, ticker, company, date, pub_url):
    """Parse Form 4 XML — extract all P (purchase) and S (sale) transactions."""
    results = []

    name_m  = re.search(r"<rptOwnerName>(.*?)</rptOwnerName>", xml, re.IGNORECASE)
    name    = name_m.group(1).strip() if name_m else "Unknown"
    title_m = re.search(r"<officerTitle>(.*?)</officerTitle>", xml, re.IGNORECASE)
    role    = title_m.group(1).strip() if title_m else (
        "Director" if "<isDirector>1</isDirector>" in xml else "Insider"
    )

    def flt(s):
        try: return float(str(s).replace(",","").strip())
        except: return 0.0

    # Non-derivative transactions (regular stock buys/sells)
    for blk in re.findall(
        r"<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>",
        xml, re.DOTALL | re.IGNORECASE
    ):
        code_m = re.search(r"<transactionCode>(.*?)</transactionCode>", blk, re.IGNORECASE)
        code   = code_m.group(1).strip() if code_m else ""
        if code not in ("P", "S"):
            continue

        sh_m  = re.search(r"<transactionShares>\s*<value>(.*?)</value>", blk, re.DOTALL|re.IGNORECASE)
        px_m  = re.search(r"<transactionPricePerShare>\s*<value>(.*?)</value>", blk, re.DOTALL|re.IGNORECASE)
        rem_m = re.search(r"<sharesOwnedFollowingTransaction>\s*<value>(.*?)</value>", blk, re.DOTALL|re.IGNORECASE)
        dir_m = re.search(r"<transactionAcquiredDisposedCode>\s*<value>(.*?)</value>", blk, re.DOTALL|re.IGNORECASE)

        sh  = flt(sh_m.group(1)  if sh_m  else 0)
        px  = flt(px_m.group(1)  if px_m  else 0)
        rem = flt(rem_m.group(1) if rem_m else 0)
        direction = dir_m.group(1).strip() if dir_m else ("A" if code=="P" else "D")

        print(f"        {code} {direction} {int(sh):,} shares @ ${px:.2f}")
        results.append({
            "ticker": ticker, "company": company, "insider": name, "role": role,
            "code": code, "direction": direction, "shares": int(sh),
            "value": round(sh * px), "shares_remaining": int(rem),
            "date": date, "filing_url": pub_url,
        })

    # Derivative transactions (options) — disposals only
    for blk in re.findall(
        r"<derivativeTransaction>(.*?)</derivativeTransaction>",
        xml, re.DOTALL | re.IGNORECASE
    ):
        code_m = re.search(r"<transactionCode>(.*?)</transactionCode>", blk, re.IGNORECASE)
        code   = code_m.group(1).strip() if code_m else ""
        if code not in ("P","S","M","X"):
            continue
        dir_m = re.search(r"<transactionAcquiredDisposedCode>\s*<value>(.*?)</value>", blk, re.DOTALL|re.IGNORECASE)
        direction = dir_m.group(1).strip() if dir_m else ""
        if direction != "D":
            continue
        sh_m  = re.search(r"<transactionShares>\s*<value>(.*?)</value>", blk, re.DOTALL|re.IGNORECASE)
        px_m  = re.search(r"<transactionPricePerShare>\s*<value>(.*?)</value>", blk, re.DOTALL|re.IGNORECASE)
        rem_m = re.search(r"<sharesOwnedFollowingTransaction>\s*<value>(.*?)</value>", blk, re.DOTALL|re.IGNORECASE)
        exp_m = re.search(r"<expirationDate>\s*<value>(.*?)</value>", blk, re.DOTALL|re.IGNORECASE)
        sh  = flt(sh_m.group(1)  if sh_m  else 0)
        px  = flt(px_m.group(1)  if px_m  else 0)
        rem = flt(rem_m.group(1) if rem_m else 0)
        results.append({
            "ticker": ticker, "company": company, "insider": name, "role": role,
            "code": code, "direction": direction, "shares": int(sh),
            "value": round(sh * px), "shares_remaining": int(rem),
            "expiry": exp_m.group(1).strip() if exp_m else None,
            "date": date, "filing_url": pub_url,
        })

    return results

# =============================================================================
# SOURCE 3: OpenInsider screener (fallback)
# =============================================================================
def fetch_via_openinsider(ticker):
    url = (
        f"http://openinsider.com/screener?s={ticker}&o=&pl=&ph=&ll=&lh="
        f"&fd=30&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=30&xp=1&xs=1"
        f"&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999"
        f"&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h="
        f"&sortcol=0&cnt=40&page=1"
    )
    r = safe_get(url, BROWSER_HEADERS, timeout=20)
    if not r:
        return []

    company = COMPANY_NAMES.get(ticker, ticker)
    results = []
    table_m = re.search(r'<tbody>(.*?)</tbody>', r.text, re.DOTALL | re.IGNORECASE)
    if not table_m:
        return []

    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', table_m.group(1), re.DOTALL | re.IGNORECASE):
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL | re.IGNORECASE)
        clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
        if len(clean) < 10:
            continue
        try:
            def n(s):
                try: return float(re.sub(r'[^\d.-]', '', s) or '0')
                except: return 0.0
            insider  = clean[4] if len(clean) > 4 else "Unknown"
            role     = clean[5] if len(clean) > 5 else "Insider"
            ttype    = clean[6] if len(clean) > 6 else ""
            qty      = abs(int(n(clean[8] if len(clean) > 8 else "0")))
            owned    = abs(int(n(clean[9] if len(clean) > 9 else "0")))
            value    = abs(int(n(clean[11] if len(clean) > 11 else "0")))
            price    = n(clean[7] if len(clean) > 7 else "0")
            date_str = clean[2] if len(clean) > 2 else clean[1] if len(clean) > 1 else ""
            if qty == 0: continue
            tt = ttype.upper()
            is_buy  = tt.startswith("P") or "PURCHASE" in tt
            is_sell = "S" in tt or "SALE" in tt
            if not is_buy and not is_sell: continue
            val = value if value > 0 else round(qty * price)
            record = {"ticker": ticker, "company": company, "insider": insider,
                      "role": role, "date": date_str,
                      "filing_url": f"http://openinsider.com/screener?s={ticker}"}
            if is_buy:
                record["shares"] = qty
                record["value"]  = val
                results.append(("buy", record))
            else:
                record["shares_sold"] = qty
                record["shares_remaining"] = owned
                record["expiry"] = None
                record["value"]  = val
                results.append(("sell", record))
        except:
            continue
    return results

# =============================================================================
# MAIN: Try each source in order, use first that returns data
# =============================================================================
def fetch_ticker(ticker):
    print(f"\n  {ticker}:", flush=True)

    # --- SOURCE 1: SEC EFTS ---
    print(f"    Trying SEC EFTS API...")
    hits = fetch_via_efts(ticker)
    if hits is not None:
        results = []
        for hit in hits[:5]:
            txns = parse_efts_filing(hit, ticker)
            results.extend(txns)
            time.sleep(0.2)
        if results:
            print(f"    SEC EFTS: {len(results)} transactions")
            return results

    # --- SOURCE 2: SEC Submissions ---
    print(f"    Trying SEC Submissions API...")
    filings = fetch_via_submissions(ticker)
    if filings:
        results = []
        for f in filings[:5]:
            txns = fetch_form4_xml(ticker, f["acc"], f["date"])
            results.extend(txns)
            time.sleep(0.2)
        if results:
            print(f"    SEC Submissions: {len(results)} transactions")
            return results

    # --- SOURCE 3: OpenInsider ---
    print(f"    Trying OpenInsider (fallback)...")
    results = fetch_via_openinsider(ticker)
    if results:
        print(f"    OpenInsider: {len(results)} transactions")
        return results

    print(f"    All sources returned 0 for {ticker}")
    return []

def main():
    buys, sells = [], []
    source_counts = {"efts": 0, "submissions": 0, "openinsider": 0}

    for ticker in DJIA_TICKERS:
        txns = fetch_ticker(ticker)
        for t in txns:
            if isinstance(t, tuple):
                kind, record = t
            elif isinstance(t, dict):
                kind   = "buy" if t.get("code") in ("P",) or t.get("direction") == "A" else "sell"
                record = t
            else:
                continue
            if kind == "buy":
                buys.append({k: record[k] for k in
                    ["ticker","company","insider","role","shares","value","date","filing_url"]
                    if k in record})
            else:
                sells.append({
                    "ticker":           record.get("ticker"),
                    "company":          record.get("company"),
                    "insider":          record.get("insider"),
                    "role":             record.get("role"),
                    "shares_sold":      record.get("shares", record.get("shares_sold", 0)),
                    "shares_remaining": record.get("shares_remaining", 0),
                    "expiry":           record.get("expiry"),
                    "value":            record.get("value", 0),
                    "date":             record.get("date"),
                    "filing_url":       record.get("filing_url"),
                })
        time.sleep(1.0)

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

    print(f"\n{'='*50}")
    print(f"DONE: {len(buys)} buys, {len(sells)} sells")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
