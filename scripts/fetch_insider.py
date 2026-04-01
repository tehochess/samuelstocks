import json, os, re, time, requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

DJIA = {
    "AAPL":"Apple","AMGN":"Amgen","AXP":"American Express","BA":"Boeing",
    "CAT":"Caterpillar","CRM":"Salesforce","CSCO":"Cisco","CVX":"Chevron",
    "DIS":"Disney","DOW":"Dow Inc","GS":"Goldman Sachs","HD":"Home Depot",
    "HON":"Honeywell","IBM":"IBM","INTC":"Intel","JNJ":"Johnson & Johnson",
    "JPM":"JPMorgan Chase","KO":"Coca-Cola","MCD":"McDonald's","MMM":"3M",
    "MRK":"Merck","MSFT":"Microsoft","NKE":"Nike","PG":"Procter & Gamble",
    "TRV":"Travelers","UNH":"UnitedHealth","V":"Visa","VZ":"Verizon",
    "WBA":"Walgreens","WMT":"Walmart",
}

HEADERS = {"User-Agent": "samuelstocks-dashboard tehochess@github.com"}
PST = ZoneInfo("America/Los_Angeles")

# Hardcoded CIK map as fallback so we never fail on the SEC CIK lookup
HARDCODED_CIKS = {
    "AAPL":"0000320193","AMGN":"0000820081","AXP":"0000004962","BA":"0000012927",
    "CAT":"0000018230","CRM":"0001108524","CSCO":"0000858877","CVX":"0000093410",
    "DIS":"0001001039","DOW":"0001751788","GS":"0000886982","HD":"0000354950",
    "HON":"0000773840","IBM":"0000051143","INTC":"0000050863","JNJ":"0000200406",
    "JPM":"0000019617","KO":"0000021344","MCD":"0000063908","MMM":"0000066740",
    "MRK":"0000310158","MSFT":"0000789019","NKE":"0000320187","PG":"0000080424",
    "TRV":"0000086312","UNH":"0000731766","V":"0001403161","VZ":"0000732712",
    "WBA":"0001141788","WMT":"0000104169",
}

def safe_get(url, retries=3, delay=5):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200 and r.text.strip():
                return r
            print(f"    Empty/bad response (attempt {attempt+1}/{retries}), waiting {delay}s...")
        except Exception as e:
            print(f"    Request error: {e} (attempt {attempt+1}/{retries}), waiting {delay}s...")
        time.sleep(delay)
    return None

def get_cik_map():
    print("  Fetching CIK map from SEC...")
    r = safe_get("https://www.sec.gov/files/company_tickers.json", retries=3, delay=5)
    if r:
        try:
            data = r.json()
            result = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in data.values()}
            print(f"  Loaded {len(result)} tickers from SEC")
            return result
        except Exception as e:
            print(f"  Failed to parse SEC CIK map: {e}")
    print("  Falling back to hardcoded CIK map")
    return HARDCODED_CIKS

def get_recent_form4(cik, days=30):
    r = safe_get(f"https://data.sec.gov/submissions/CIK{cik}.json", retries=3, delay=3)
    if not r:
        return []
    try:
        rec = r.json().get("filings", {}).get("recent", {})
        cutoff = (datetime.now(PST) - timedelta(days=days)).date()
        out = []
        for i, form in enumerate(rec.get("form", [])):
            if form == "4":
                try:
                    d = datetime.strptime(rec["filingDate"][i], "%Y-%m-%d").date()
                    if d >= cutoff:
                        out.append({
                            "date": rec["filingDate"][i],
                            "acc": rec["accessionNumber"][i]
                        })
                except:
                    pass
        return out
    except Exception as e:
        print(f"    Error parsing filings: {e}")
        return []

def get_xml(cik, acc_raw):
    acc = acc_raw.replace("-", "")
    pub_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{acc_raw}-index.htm"
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/"

    for candidate in [f"{acc_raw}.xml", "form4.xml"]:
        r = safe_get(base + candidate, retries=2, delay=2)
        if r and "ownershipDocument" in r.text:
            return r.text, pub_url

    r = safe_get(base, retries=2, delay=2)
    if r:
        for fname in re.findall(r'href="([^"]+\.xml)"', r.text):
            url = f"https://www.sec.gov{fname}" if fname.startswith("/") else base + fname
            xr = safe_get(url, retries=2, delay=2)
            if xr and "ownershipDocument" in xr.text:
                return xr.text, pub_url

    return None, pub_url

def flt(s):
    try:
        return float(str(s).replace(",", "").strip())
    except:
        return 0.0

def parse_xml(xml, ticker, company, date, pub_url):
    results = []

    name_m = re.search(r"<rptOwnerName>(.*?)</rptOwnerName>", xml, re.IGNORECASE)
    name = name_m.group(1).strip() if name_m else "Unknown"

    title_m = re.search(r"<officerTitle>(.*?)</officerTitle>", xml, re.IGNORECASE)
    if title_m:
        role = title_m.group(1).strip()
    elif "<isDirector>1</isDirector>" in xml:
        role = "Director"
    else:
        role = "Insider"

    for blk in re.findall(
        r"<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>",
        xml, re.DOTALL | re.IGNORECASE
    ):
        code_m = re.search(r"<transactionCode>(.*?)</transactionCode>", blk, re.IGNORECASE)
        code = code_m.group(1).strip() if code_m else ""
        if code not in ("P", "S"):
            continue

        sh_m = re.search(r"<transactionShares>\s*<value>(.*?)</value>", blk, re.DOTALL | re.IGNORECASE)
        px_m = re.search(r"<transactionPricePerShare>\s*<value>(.*?)</value>", blk, re.DOTALL | re.IGNORECASE)
        rem_m = re.search(r"<sharesOwnedFollowingTransaction>\s*<value>(.*?)</value>", blk, re.DOTALL | re.IGNORECASE)
        dir_m = re.search(r"<transactionAcquiredDisposedCode>\s*<value>(.*?)</value>", blk, re.DOTALL | re.IGNORECASE)

        sh = flt(sh_m.group(1) if sh_m else 0)
        px = flt(px_m.group(1) if px_m else 0)
        rem = flt(rem_m.group(1) if rem_m else 0)
        direction = dir_m.group(1).strip() if dir_m else ("A" if code == "P" else "D")

        print(f"        {code} {direction} {int(sh)} shares @ ${px}")
        results.append({
            "ticker": ticker, "company": company, "insider": name, "role": role,
            "code": code, "direction": direction, "shares": int(sh),
            "value": round(sh * px), "shares_remaining": int(rem),
            "date": date, "filing_url": pub_url
        })

    for blk in re.findall(
        r"<derivativeTransaction>(.*?)</derivativeTransaction>",
        xml, re.DOTALL | re.IGNORECASE
    ):
        code_m = re.search(r"<transactionCode>(.*?)</transactionCode>", blk, re.IGNORECASE)
        code = code_m.group(1).strip() if code_m else ""
        if code not in ("P", "S", "M", "X"):
            continue

        dir_m = re.search(r"<transactionAcquiredDisposedCode>\s*<value>(.*?)</value>", blk, re.DOTALL | re.IGNORECASE)
        direction = dir_m.group(1).strip() if dir_m else ""
        if direction != "D":
            continue

        sh_m = re.search(r"<transactionShares>\s*<value>(.*?)</value>", blk, re.DOTALL | re.IGNORECASE)
        px_m = re.search(r"<transactionPricePerShare>\s*<value>(.*?)</value>", blk, re.DOTALL | re.IGNORECASE)
        rem_m = re.search(r"<sharesOwnedFollowingTransaction>\s*<value>(.*?)</value>", blk, re.DOTALL | re.IGNORECASE)
        exp_m = re.search(r"<expirationDate>\s*<value>(.*?)</value>", blk, re.DOTALL | re.IGNORECASE)

        sh = flt(sh_m.group(1) if sh_m else 0)
        px = flt(px_m.group(1) if px_m else 0)
        rem = flt(rem_m.group(1) if rem_m else 0)

        results.append({
            "ticker": ticker, "company": company, "insider": name, "role": role,
            "code": code, "direction": direction, "shares": int(sh),
            "value": round(sh * px), "shares_remaining": int(rem),
            "expiry": exp_m.group(1).strip() if exp_m else None,
            "date": date, "filing_url": pub_url
        })

    return results

def main():
    print("Loading SEC CIK map...")
    cik_map = get_cik_map()
    buys = []
    sells = []

    for ticker, company in DJIA.items():
        cik = cik_map.get(ticker)
        if not cik:
            print(f"  {ticker}: no CIK, skipping")
            continue

        print(f"  {ticker} (CIK {cik})...", flush=True)
        try:
            filings = get_recent_form4(cik)
            print(f"    {len(filings)} Form 4(s) in last 30 days")

            for f in filings[:5]:
                xml, pub_url = get_xml(cik, f["acc"])
                if not xml:
                    print(f"    could not get XML for {f['acc']}")
                    time.sleep(0.5)
                    continue

                txns = parse_xml(xml, ticker, company, f["date"], pub_url)
                for t in txns:
                    if t["direction"] == "A" or t["code"] == "P":
                        buys.append({
                            "ticker": t["ticker"], "company": t["company"],
                            "insider": t["insider"], "role": t["role"],
                            "shares": t["shares"], "value": t["value"],
                            "date": t["date"], "filing_url": t["filing_url"]
                        })
                    elif t["direction"] == "D" or t["code"] == "S":
                        sells.append({
                            "ticker": t["ticker"], "company": t["company"],
                            "insider": t["insider"], "role": t["role"],
                            "shares_sold": t["shares"],
                            "shares_remaining": t["shares_remaining"],
                            "expiry": t.get("expiry"),
                            "value": t["value"],
                            "date": t["date"],
                            "filing_url": t["filing_url"]
                        })
                time.sleep(0.3)

        except Exception as e:
            print(f"    ERROR processing {ticker}: {e}")

        time.sleep(0.2)

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
