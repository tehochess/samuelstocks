# ── Single source of truth for all tickers ────────────────────
# All 3 fetch scripts import from here.
# To add/remove tickers, edit only this file.

DJIA_TICKERS = [
    "AAPL","AMGN","AXP","BA","CAT","CRM","CSCO","CVX","DIS","DOW",
    "GS","HD","HON","IBM","INTC","JNJ","JPM","KO","MCD","MMM",
    "MRK","MSFT","NKE","PG","TRV","UNH","V","VZ","WMT","SHW"
]

# S&P 100 (includes all DJIA stocks above)
SP100_TICKERS = [
    "AAPL","ABBV","ABT","ACN","ADBE","AIG","AMD","AMGN","AMT","AMZN",
    "AXP","BA","BAC","BK","BLK","BMY","BRK-B","C","CAT","CHTR",
    "CL","CMCSA","COF","COP","CRM","CSCO","CVS","CVX","DE","DIS",
    "DOW","DUK","EMR","EXC","F","FDX","GD","GE","GILD","GM",
    "GOOG","GOOGL","GS","HD","HON","IBM","INTC","INTU","JNJ","JPM",
    "KHC","KO","LIN","LLY","LMT","LOW","MA","MCD","MDLZ","MDT",
    "MET","META","MMM","MO","MRK","MS","MSFT","NEE","NFLX","NKE",
    "NVDA","ORCL","OXY","PEP","PFE","PG","PM","PYPL","QCOM","RTX",
    "SBUX","SCHW","SHW","SO","SPG","T","TGT","TMO","TRV","TXN",
    "UNH","UNP","UPS","USB","V","VZ","WFC","WMT","XOM","ZTS"
]

# Combined company name lookup (DJIA + S&P 100)
COMPANY_NAMES = {
    "AAPL":"Apple","ABBV":"AbbVie","ABT":"Abbott","ACN":"Accenture",
    "ADBE":"Adobe","AIG":"AIG","AMD":"AMD","AMGN":"Amgen",
    "AMT":"American Tower","AMZN":"Amazon","AXP":"American Express",
    "BA":"Boeing","BAC":"Bank of America","BK":"BNY Mellon",
    "BLK":"BlackRock","BMY":"Bristol-Myers Squibb","BRK-B":"Berkshire Hathaway",
    "C":"Citigroup","CAT":"Caterpillar","CHTR":"Charter Communications",
    "CL":"Colgate-Palmolive","CMCSA":"Comcast","COF":"Capital One",
    "COP":"ConocoPhillips","CRM":"Salesforce","CSCO":"Cisco",
    "CVS":"CVS Health","CVX":"Chevron","DE":"Deere & Co","DIS":"Disney",
    "DOW":"Dow Inc","DUK":"Duke Energy","EMR":"Emerson Electric",
    "EXC":"Exelon","F":"Ford","FDX":"FedEx","GD":"General Dynamics",
    "GE":"GE Aerospace","GILD":"Gilead Sciences","GM":"General Motors",
    "GOOG":"Alphabet C","GOOGL":"Alphabet A","GS":"Goldman Sachs",
    "HD":"Home Depot","HON":"Honeywell","IBM":"IBM","INTC":"Intel",
    "INTU":"Intuit","JNJ":"Johnson & Johnson","JPM":"JPMorgan Chase",
    "KHC":"Kraft Heinz","KO":"Coca-Cola","LIN":"Linde","LLY":"Eli Lilly",
    "LMT":"Lockheed Martin","LOW":"Lowe's","MA":"Mastercard",
    "MCD":"McDonald's","MDLZ":"Mondelez","MDT":"Medtronic",
    "MET":"MetLife","META":"Meta","MMM":"3M","MO":"Altria",
    "MRK":"Merck","MS":"Morgan Stanley","MSFT":"Microsoft",
    "NEE":"NextEra Energy","NFLX":"Netflix","NKE":"Nike",
    "NVDA":"Nvidia","ORCL":"Oracle","OXY":"Occidental Petroleum",
    "PEP":"PepsiCo","PFE":"Pfizer","PG":"Procter & Gamble",
    "PM":"Philip Morris","PYPL":"PayPal","QCOM":"Qualcomm",
    "RTX":"RTX Corp","SBUX":"Starbucks","SCHW":"Charles Schwab",
    "SHW":"Sherwin-Williams","SO":"Southern Company","SPG":"Simon Property",
    "T":"AT&T","TGT":"Target","TMO":"Thermo Fisher",
    "TRV":"Travelers","TXN":"Texas Instruments","UNH":"UnitedHealth",
    "UNP":"Union Pacific","UPS":"UPS","USB":"U.S. Bancorp",
    "V":"Visa","VZ":"Verizon","WFC":"Wells Fargo","WMT":"Walmart",
    "XOM":"ExxonMobil","ZTS":"Zoetis",
}

# Set for fast membership checks on the website filter
DJIA_SET = set(DJIA_TICKERS)
