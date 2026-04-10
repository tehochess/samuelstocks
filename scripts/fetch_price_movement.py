import json, os, time
from datetime import datetime, timedelta, date
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

def analyze_ticker(ticker):
    company = COMPANY_NAMES.get(ticker, ticker)
    try:
        # Fetch last 10 trading days of data (enough to find 3 consecutive)
        stock = yf.Ticker(ticker)
        hist = stock.history(period="10d")

        if hist is None or len(hist) < 4:
            print("  " + ticker + ": not enough data")
            return None

        # Calculate daily % change and volume vs average
        hist = hist.copy()
        hist["pct_change"] = hist["Close"].pct_change() * 100
        avg_volume = hist["Volume"].mean()

        # Look at the last 3 trading days (index -3, -2, -1)
        last3 = hist.iloc[-3:]
        changes = last3["pct_change"].tolist()
        volumes = last3["Volume"].tolist()
        closes  = last3["Close"].tolist()
        dates   = [str(d.date()) for d in last3.index]

        # Are all 3 days DOWN?
        all_down = all(c < 0 for c in changes)
        # Are all 3 days UP?
        all_up   = all(c > 0 for c in changes)

        # Volume on the most recent day vs average
        latest_vol     = volumes[-1]
        vol_vs_avg_pct = round(((latest_vol - avg_volume) / avg_volume) * 100, 1)
        vol_signal     = "light" if vol_vs_avg_pct < -15 else ("heavy" if vol_vs_avg_pct > 15 else "normal")

        current_price  = round(closes[-1], 2)
        total_move_pct = round(sum(changes), 2)  # total % move over 3 days

        result = {
            "ticker":       ticker,
            "company":      company,
            "price":        current_price,
            "day1":         {"date": dates[0], "pct": round(changes[0], 2), "vol": int(volumes[0])},
            "day2":         {"date": dates[1], "pct": round(changes[1], 2), "vol": int(volumes[1])},
            "day3":         {"date": dates[2], "pct": round(changes[2], 2), "vol": int(volumes[2])},
            "totalMove":    total_move_pct,
            "volVsAvg":     vol_vs_avg_pct,
            "volSignal":    vol_signal,
            "avgVolume":    int(avg_volume),
            "allDown":      all_down,
            "allUp":        all_up,
        }

        # Bottom signal: down 3 days AND volume lighter than average today
        # (sellers are exhausting, fewer people left to sell)
        result["nearBottom"] = all_down and vol_signal == "light"

        # Peak signal: up 3 days AND volume heavier than average today
        # (buyers piling in, euphoria = often near the top)
        result["nearPeak"]   = all_up and vol_signal == "heavy"

        direction = "DOWN" if all_down else ("UP" if all_up else "MIXED")
        print("  " + ticker + ": " + direction + " " + str(total_move_pct) + "% | vol " + vol_signal)
        return result

    except Exception as e:
        print("  " + ticker + ": ERROR - " + str(e))
        return None


def main():
    all_results = []

    for ticker in DJIA_TICKERS:
        r = analyze_ticker(ticker)
        if r:
            all_results.append(r)
        time.sleep(0.5)

    # Split into down streaks and up streaks
    down_streaks = [r for r in all_results if r["allDown"]]
    up_streaks   = [r for r in all_results if r["allUp"]]

    # Sort: biggest total move first
    down_streaks.sort(key=lambda x: x["totalMove"])          # most negative first
    up_streaks.sort(key=lambda x: -x["totalMove"])           # most positive first

    now = datetime.now(PST)
    os.makedirs("data", exist_ok=True)
    with open("data/price_movement.json", "w") as f:
        json.dump({
            "updated":     now.strftime("%b %d, %Y %I:%M %p PST"),
            "updated_iso": now.isoformat(),
            "downStreaks": down_streaks,
            "upStreaks":   up_streaks,
            "allStocks":   all_results,
        }, f, indent=2)

    print("Done: " + str(len(down_streaks)) + " down streaks, " + str(len(up_streaks)) + " up streaks")


if __name__ == "__main__":
    main()
