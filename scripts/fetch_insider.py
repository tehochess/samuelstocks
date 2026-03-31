"""
fetch_insider.py
Fetches SEC EDGAR Form 4 insider trading filings for all 30 DJIA stocks.
Runs nightly via GitHub Actions. Outputs data/insider.json for the website.
"""

import json
import os
import time
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# ── DJIA 30 tickers ────────────────────────────────────────────────────────────
DJIA = {
    "AAPL": "Apple", "AMGN": "Amgen", "AXP": "American Express",
    "BA": "Boeing", "CAT": "Caterpillar", "CRM": "Salesforce",
    "CSCO": "Cisco", "CVX": "Chevron", "DIS": "Disney",
    "DOW": "Dow Inc", "GS": "Goldman Sachs", "HD": "Home Depot",
    "HON": "Honeywell", "IBM": "IBM", "INTC": "Intel",
    "JNJ": "Johnson & Johnson", "JPM": "JPMorgan Chase", "KO": "Coca-Cola",
    "MCD": "McDonald's", "MMM": "3M", "MRK": "Merck",
    "MSFT": "Microsoft", "NKE": "Nike", "PG": "Procter & Gamble",
    "TRV": "Travelers", "UNH": "UnitedHealth", "V": "Visa",
    "VZ": "Verizon", "WBA": "Walgreens", "WMT": "Walmart"
}

# SEC EDGAR headers (required by SEC — must include contact info)
HEADERS = {
    "User-Agent": "samuelstocks-dashboard contact@example.com",
    "Accept-Encoding": "gzip, deflate",
}

PST = ZoneInfo("America/Los_Angeles")


def get_cik(ticker):
    """Get SEC CIK number for a ticker symbol."""
    url = "https://efts.sec.gov/LATEST/search-index?q=%22{}%22&dateRange=custom&startdt=2020-01-01&forms=4".format(ticker)
    # Use the company tickers mapping instead
    url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=&CIK={}&type=4&dateb=&owner=include&count=10&search_text=&output=atom".format(ticker)
    try:
        r = requests.get(
            "https://data.sec.gov/submissions/CIK{}.json".format("0" * (10 - len(ticker)) + ticker),
            headers=HEADERS, timeout=10
        )
    except Exception:
        pass

    # Use the ticker-to-CIK mapping file from SEC
    try:
        r = requests.get("https://www.sec.gov/files/company_tickers.json", headers=HEADERS, timeout=15)
        mapping = r.json()
        for entry in mapping.values():
            if entry.get("ticker", "").upper() == ticker.upper():
                return str(entry["cik_str"]).zfill(10)
    except Exception:
        pass
    return None


def get_form4_filings(cik, days=7):
    """Fetch recent Form 4 filings for a CIK."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])
        accnums = filings.get("accessionNumber", [])

        cutoff = (datetime.now(PST) - timedelta(days=days)).date()
        results = []
        for i, form in enumerate(forms):
            if form == "4":
                try:
                    fdate = datetime.strptime(dates[i], "%Y-%m-%d").date()
                    if fdate >= cutoff:
                        results.append({
                            "date": dates[i],
                            "accession": accnums[i].replace("-", ""),
                            "accession_raw": accnums[i],
                        })
                except Exception:
                    continue
        return results
    except Exception:
        return []


def parse_form4(cik, accession, ticker, company):
    """Parse a Form 4 filing and extract transaction details."""
    # Build filing URL
    acc_clean = accession.replace("-", "")
    filing_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=4&dateb=&owner=include&count=10"
    sec_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/"

    try:
        # Get filing index
        idx_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=4&dateb=&owner=include&count=40&search_text=&output=atom"
        # Directly fetch the XML
        xml_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/{accession}.xml"
        r = requests.get(xml_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            # Try alternate naming
            idx_r = requests.get(
                f"https://data.sec.gov/submissions/CIK{cik}.json",
                headers=HEADERS, timeout=10
            )
            return []

        xml = r.text
        transactions = []
        public_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/{accession}-index.htm"

        # Extract reporter name
        import re
        name_match = re.search(r'<rptOwnerName>(.*?)</rptOwnerName>', xml)
        insider_name = name_match.group(1).strip() if name_match else "Unknown"

        # Extract title/role
        title_match = re.search(r'<officerTitle>(.*?)</officerTitle>', xml)
        role = title_match.group(1).strip() if title_match else ""
        is_director = '<isDirector>1</isDirector>' in xml
        is_officer = '<isOfficer>1</isOfficer>' in xml
        if not role:
            if is_director:
                role = "Director"
            elif is_officer:
                role = "Officer"
            else:
                role = "Insider"

        # Extract non-derivative transactions
        trans_blocks = re.findall(
            r'<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>', xml, re.DOTALL
        )
        for block in trans_blocks:
            try:
                sec_title = re.search(r'<securityTitle>.*?<value>(.*?)</value>', block, re.DOTALL)
                trans_code = re.search(r'<transactionCode>(.*?)</transactionCode>', block)
                shares_match = re.search(r'<transactionShares>.*?<value>(.*?)</value>', block, re.DOTALL)
                price_match = re.search(r'<transactionPricePerShare>.*?<value>(.*?)</value>', block, re.DOTALL)
                acquired = re.search(r'<transactionAcquiredDisposedCode>.*?<value>(.*?)</value>', block, re.DOTALL)
                remaining = re.search(r'<sharesOwnedFollowingTransaction>.*?<value>(.*?)</value>', block, re.DOTALL)
                date_match = re.search(r'<transactionDate>.*?<value>(.*?)</value>', block, re.DOTALL)

                code = trans_code.group(1) if trans_code else ""
                # P = open market purchase, S = open market sale
                if code not in ("P", "S"):
                    continue

                shares = float(shares_match.group(1).replace(",", "")) if shares_match else 0
                price = float(price_match.group(1).replace(",", "")) if price_match else 0
                value = shares * price
                direction = acquired.group(1).strip() if acquired else ""
                shares_left = float(remaining.group(1).replace(",", "")) if remaining else 0
                trans_date = date_match.group(1).strip() if date_match else ""

                transactions.append({
                    "ticker": ticker,
                    "company": company,
                    "insider": insider_name,
                    "role": role,
                    "transaction_code": code,
                    "direction": direction,  # A=acquired, D=disposed
                    "shares": int(shares),
                    "price": round(price, 2),
                    "value": round(value, 0),
                    "shares_remaining": int(shares_left),
                    "date": trans_date,
                    "filing_url": public_url,
                })
            except Exception:
                continue

        # Also check derivative transactions (options)
        deriv_blocks = re.findall(
            r'<derivativeTransaction>(.*?)</derivativeTransaction>', xml, re.DOTALL
        )
        for block in deriv_blocks:
            try:
                import re as _re
                expiry_match = _re.search(r'<expirationDate>.*?<value>(.*?)</value>', block, re.DOTALL)
                trans_code = _re.search(r'<transactionCode>(.*?)</transactionCode>', block)
                shares_match = _re.search(r'<transactionShares>.*?<value>(.*?)</value>', block, re.DOTALL)
                price_match = _re.search(r'<transactionPricePerShare>.*?<value>(.*?)</value>', block, re.DOTALL)
                acquired = _re.search(r'<transactionAcquiredDisposedCode>.*?<value>(.*?)</value>', block, re.DOTALL)
                remaining = _re.search(r'<sharesOwnedFollowingTransaction>.*?<value>(.*?)</value>', block, re.DOTALL)
                date_match = _re.search(r'<transactionDate>.*?<value>(.*?)</value>', block, re.DOTALL)

                code = trans_code.group(1) if trans_code else ""
                if code not in ("P", "S", "M", "X"):
                    continue

                shares = float(shares_match.group(1).replace(",", "")) if shares_match else 0
                price = float(price_match.group(1).replace(",", "")) if price_match else 0
                value = shares * price
                direction = acquired.group(1).strip() if acquired else ""
                shares_left = float(remaining.group(1).replace(",", "")) if remaining else 0
                trans_date = date_match.group(1).strip() if date_match else ""
                expiry = expiry_match.group(1).strip() if expiry_match else None

                if direction == "D":  # Sale/exercise
                    transactions.append({
                        "ticker": ticker,
                        "company": company,
                        "insider": insider_name,
                        "role": role,
                        "transaction_code": code,
                        "direction": direction,
                        "shares_sold": int(shares),
                        "price": round(price, 2),
                        "value": round(value, 0),
                        "shares_remaining": int(shares_left),
                        "expiry": expiry,
                        "date": trans_date,
                        "filing_url": public_url,
                        "is_derivative": True,
                    })
            except Exception:
                continue

        return transactions

    except Exception as e:
        print(f"  Error parsing {ticker} filing {accession}: {e}")
        return []


def fetch_all():
    """Main function — fetch all DJIA insider filings."""
    print("Fetching CIK mapping from SEC...")
    try:
        r = requests.get("https://www.sec.gov/files/company_tickers.json", headers=HEADERS, timeout=20)
        ticker_map = r.json()
        cik_lookup = {
            v["ticker"].upper(): str(v["cik_str"]).zfill(10)
            for v in ticker_map.values()
        }
        print(f"  Loaded {len(cik_lookup)} tickers from SEC")
    except Exception as e:
        print(f"  Failed to load CIK map: {e}")
        cik_lookup = {}

    buys = []
    sells = []

    for ticker, company in DJIA.items():
        cik = cik_lookup.get(ticker)
        if not cik:
            print(f"  {ticker}: CIK not found, skipping")
            continue

        print(f"  {ticker} (CIK {cik})...")
        filings = get_form4_filings(cik, days=7)
        print(f"    Found {len(filings)} Form 4 filings")

        for filing in filings[:10]:  # cap per ticker
            txns = parse_form4(cik, filing["accession_raw"], ticker, company)
            for t in txns:
                t["date"] = filing["date"]  # use filing date as fallback
                if t.get("direction") == "A" or t.get("transaction_code") == "P":
                    buys.append({
                        "ticker": t["ticker"],
                        "company": t["company"],
                        "insider": t["insider"],
                        "role": t["role"],
                        "shares": t.get("shares", 0),
                        "value": t.get("value", 0),
                        "date": t["date"],
                        "filing_url": t["filing_url"],
                    })
                elif t.get("direction") == "D" or t.get("transaction_code") == "S":
                    sells.append({
                        "ticker": t["ticker"],
                        "company": t["company"],
                        "insider": t["insider"],
                        "role": t["role"],
                        "shares_sold": t.get("shares", t.get("shares_sold", 0)),
                        "shares_remaining": t.get("shares_remaining", 0),
                        "expiry": t.get("expiry", None),
                        "value": t.get("value", 0),
                        "date": t["date"],
                        "filing_url": t["filing_url"],
                    })
            time.sleep(0.15)  # SEC rate limit: be respectful

    # Sort: CEO/CFO first, then by value descending
    def sort_key(x):
        role = x.get("role", "").upper()
        priority = 0 if "CEO" in role else (1 if "CFO" in role else 2)
        return (priority, -x.get("value", 0))

    buys.sort(key=sort_key)
    sells.sort(key=sort_key)

    now_pst = datetime.now(PST)
    output = {
        "updated": now_pst.strftime("%b %d, %Y %I:%M %p PST"),
        "updated_iso": now_pst.isoformat(),
        "buys": buys,
        "sells": sells,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/insider.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nDone. {len(buys)} buys, {len(sells)} sells written to data/insider.json")
    return output


if __name__ == "__main__":
    result = fetch_all()
