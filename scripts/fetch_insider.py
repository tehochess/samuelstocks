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

def get_cik_map():
    r = requests.get("https://www.sec.gov/files/company_tickers.json", headers=HEADERS, timeout=20)
    return {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in r.json().values()}

def recent_form4(cik, days=30):
    r = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=HEADERS, timeout=15)
    r.raise_for_status()
    rec = r.json().get("filings", {}).get("recent", {})
    cutoff = (datetime.now(PST) - timedelta(days=days)).date()
    out = []
    for i, form in enumerate(rec.get("form", [])):
        if form == "4":
            try:
                d = datetime.strptime(rec["filingDate"][i], "%Y-%m-%d").date()
                if d >= cutoff:
                    out.append({"date": rec["filingDate"][i], "acc": rec["accessionNumber"][i]})
            except:
                pass
    return out

def get_xml(cik, acc_raw):
    acc = acc_raw.replace("-", "")
    pub_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{acc_raw}-index.htm"
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/"
    for candidate in [f"{acc_raw}.xml", "form4.xml"]:
        try:
            r = requests.get(base + candidate, headers=HEADERS, timeout=10)
            if r.status_code == 200 and "ownershipDocument" in r.text:
                return r.text, pub_url
        except:
            pass
    try:
        r = requests.get(base, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            for fname in re.findall(r'href="([^"]+\.xml)"', r.text):
                url = f"https://www.sec.gov{fname}" if fname.startswith("/") else base + fname
                xr = requests.get(url, headers=HEADERS, timeout=10)
                if xr.status_code == 200 and "ownershipDocument" in xr.text:
                    return xr.text, pub_url
    except:
        pass
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

    for blk in re.findall(r"<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>", xml, re.DOTALL | re.IGNORECASE):
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
            "code": code, "direction": direction, "shares": int(sh), "value": round(sh * px),
            "shares_remaining": int(rem), "date": date, "filing_url": pub_url
        })

    for blk in re.findall(r"<derivativeTransaction>(.*?)</derivativeTransaction>", xml, re.DOTALL | re.IGNORECASE):
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
            "code": code, "direction": direction, "shares": int(sh), "value": round(sh * px),
            "shares_remaining": int(rem), "expiry": exp_m.group(1).strip() if exp_m else None,
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
        print(f"  {ticker}...", flush=True)
        try:
            filings = recent_form4(cik)
            print(f"    {len(filings)} Form 4(s)")
            for f in filings[:5]:
                xml, pub_url = get_xml(cik, f["acc"])
                if not xml:
                    print(f"    could not get XML")
                    time.sleep(0.2)
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
                time.sleep(0.2)
        except Exception as e:
            print(f"    ERROR: {e}")
        time.sleep(0.15)

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
