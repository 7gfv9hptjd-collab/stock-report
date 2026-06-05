import os
import json
import re
import math
import time
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from openai import OpenAI

ALPACA_KEY = os.environ["ALPACA_KEY"]
ALPACA_SECRET = os.environ["ALPACA_SECRET"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

ALPACA_BASE = "https://data.alpaca.markets"
ALPACA_TRADING_BASE = "https://api.alpaca.markets"
REPORT_FILE = "latest.json"

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET
}

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive"
}

client = OpenAI(api_key=OPENAI_API_KEY)

UNIVERSE = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","AVGO","TSLA","BRK.B",
    "LLY","JPM","V","UNH","XOM","MA","COST","HD","PG","JNJ","ABBV","NFLX",
    "CRM","BAC","ORCL","AMD","KO","PEP","WMT","MRK","CVX","ADBE","CSCO",
    "QCOM","TMO","MCD","GE","ABT","AMAT","TXN","INTU","IBM","CAT","VZ",
    "NOW","BKNG","GS","ISRG","SPGI","RTX","AXP","PFE","UBER","LOW","NEE",
    "HON","PGR","SYK","BLK","TJX","ETN","VRTX","LRCX","PANW","C","DE",
    "ADP","MDT","REGN","ADI","MMC","CB","KLAC","SCHW","PLTR","MU","BSX",
    "AMGN","GILD","INTC","SO","UPS","COP","NKE","BA","SBUX","ELV","FI",
    "SHOP","ANET","MELI","SNOW","CRWD","NET","DDOG","TEAM","MDB","ZS",
    "OKTA","HUBS","WDAY","ROKU","COIN","RBLX","DKNG","RIVN","LCID","U",
    "SQ","PYPL","AFRM","HOOD","SOFI","ON","SMCI","DELL","HPE","HPQ",
    "F","GM","STLA","NIO","LI","XPEV","ENPH","SEDG","FSLR","RUN",
    "CCL","RCL","NCLH","DAL","UAL","AAL","LUV","MAR","HLT","ABNB",
    "DIS","PARA","WBD","CMCSA","TMUS","T","VZ","CHTR",
    "MS","WFC","USB","PNC","TFC","BK","SCHW","COF",
    "LULU","TGT","DG","DLTR","CROX","EL","ULTA","BBY",
    "TSM","ASML","ARM","MRVL","MPWR","MCHP","NXPI","SWKS",
    "BIIB","MRNA","BNTX","HUM","CI","CVS","HCA",
    "GEV","CEG","NRG","DUK","AEP","EXC","XEL",
    "FCX","NEM","AA","CLF","X","NUE","STLD",
    "OXY","SLB","HAL","BKR","EOG","DVN","MPC","VLO"
]

COMPANY_NAMES = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "Nvidia", "AMZN": "Amazon",
    "META": "Meta Platforms", "GOOGL": "Alphabet", "GOOG": "Alphabet", "AVGO": "Broadcom",
    "TSLA": "Tesla", "LLY": "Eli Lilly", "JPM": "JPMorgan Chase", "UNH": "UnitedHealth",
    "XOM": "Exxon Mobil", "COST": "Costco", "NFLX": "Netflix", "AMD": "Advanced Micro Devices",
    "SMCI": "Super Micro Computer", "HOOD": "Robinhood", "HUM": "Humana", "NCLH": "Norwegian Cruise Line",
    "PARA": "Paramount", "MU": "Micron", "MRNA": "Moderna", "LULU": "Lululemon",
    "MDT": "Medtronic", "VZ": "Verizon", "ANET": "Arista Networks", "T": "AT&T",
    "MRK": "Merck", "USB": "U.S. Bancorp", "AFRM": "Affirm", "ARM": "Arm Holdings",
    "GS": "Goldman Sachs", "C": "Citigroup", "CSCO": "Cisco", "CRWD": "CrowdStrike",
    "AAL": "American Airlines", "QCOM": "Qualcomm", "HPE": "Hewlett Packard Enterprise", "F": "Ford"
}

SECTOR_MAP = {
    "NVDA": "Semiconductors", "AVGO": "Semiconductors", "AMD": "Semiconductors", "MU": "Semiconductors",
    "QCOM": "Semiconductors", "ARM": "Semiconductors", "SMCI": "AI Servers", "HPE": "Enterprise Hardware",
    "MSFT": "Software", "NOW": "Software", "CRWD": "Cybersecurity", "WDAY": "Software",
    "TSLA": "EV", "RIVN": "EV", "F": "Autos", "GM": "Autos",
    "HOOD": "Fintech", "AFRM": "Fintech", "COIN": "Crypto", "SOFI": "Fintech",
    "NCLH": "Travel", "AAL": "Airlines", "LULU": "Retail", "HUM": "Healthcare",
    "UNH": "Healthcare", "MRK": "Pharma", "MRNA": "Biotech", "PARA": "Media"
}


def now_amsterdam():
    return datetime.now(ZoneInfo("Europe/Amsterdam"))


def alpaca_get(url, params=None):
    r = requests.get(url, headers=HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def is_manual_github_run():
    return os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"


def is_us_market_open_today():
    today = now_amsterdam().date().isoformat()
    url = f"{ALPACA_TRADING_BASE}/v2/calendar"
    data = alpaca_get(url, {"start": today, "end": today})
    return len(data) > 0


def get_last_trading_days(count=6):
    today = now_amsterdam().date()
    start = (today - timedelta(days=21)).isoformat()
    end = today.isoformat()
    url = f"{ALPACA_TRADING_BASE}/v2/calendar"
    data = alpaca_get(url, {"start": start, "end": end})
    return [d["date"] for d in data][-count:]


def get_snapshot(symbols):
    url = f"{ALPACA_BASE}/v2/stocks/snapshots"
    params = {"symbols": ",".join(symbols), "feed": "iex"}
    try:
        return alpaca_get(url, params)
    except Exception as e:
        print(f"Snapshot batch failed: {e}")
        return {}


def get_daily_bar(symbol, date):
    url = f"{ALPACA_BASE}/v2/stocks/{symbol}/bars"
    params = {
        "timeframe": "1Day",
        "start": date,
        "end": date,
        "feed": "iex",
        "adjustment": "raw"
    }
    try:
        data = alpaca_get(url, params)
        bars = data.get("bars", [])
        if not bars:
            return None
        bar = bars[0]
        return {
            "regularOpenPrice": round(float(bar["o"]), 4),
            "regularClosePrice": round(float(bar["c"]), 4)
        }
    except Exception as e:
        print(f"Daily bar failed for {symbol} {date}: {e}")
        return None


def load_existing_report():
    if not os.path.exists(REPORT_FILE):
        return {"reportDate": "", "marketRegime": "", "marketOverview": "", "picks": [], "history": []}
    try:
        with open(REPORT_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"reportDate": "", "marketRegime": "", "marketOverview": "", "picks": [], "history": []}


def save_report(report):
    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)


def keyword_score(text):
    bullish_words = [
        "upgrade", "beats", "beat", "raises", "raised", "strong", "surge", "record",
        "growth", "approval", "contract", "partnership", "buyback", "outperform",
        "positive", "demand", "ai", "accelerates", "guidance raise", "higher forecast"
    ]
    bearish_words = [
        "downgrade", "miss", "misses", "cuts", "cut", "weak", "falls", "lawsuit",
        "probe", "investigation", "warning", "guidance cut", "underperform", "negative",
        "recall", "delay", "slump", "margin pressure", "lower forecast"
    ]
    lower = text.lower()
    bull = sum(1 for w in bullish_words if w in lower)
    bear = sum(1 for w in bearish_words if w in lower)
    return bull, bear


def normalize_yahoo_symbol(symbol):
    # Yahoo uses BRK-B rather than BRK.B. Most normal tickers are unchanged.
    return symbol.replace(".", "-")


def extract_headlines_from_html(html, ticker):
    soup = BeautifulSoup(html, "html.parser")
    headlines = []
    seen = set()

    # Yahoo often includes useful article data in links and h3 tags.
    selectors = ["h3", "a", "li"]
    for selector in selectors:
        for tag in soup.select(selector):
            text = tag.get_text(" ", strip=True)
            if not text:
                continue
            if len(text) < 25 or len(text) > 220:
                continue
            lower = text.lower()
            noisy = ["sign in", "subscribe", "privacy", "terms", "advertisement", "watchlist", "finance home"]
            if any(n in lower for n in noisy):
                continue
            if text in seen:
                continue
            seen.add(text)
            headlines.append({
                "title": text,
                "source": "Yahoo Finance",
                "description": "",
                "publishedAt": "",
                "url": f"https://finance.yahoo.com/quote/{normalize_yahoo_symbol(ticker)}/news"
            })
            if len(headlines) >= 8:
                return headlines

    return headlines


def fetch_yahoo_news_for_symbol(symbol):
    yahoo_symbol = normalize_yahoo_symbol(symbol)

    urls = [
        f"https://finance.yahoo.com/quote/{yahoo_symbol}/news",
        f"https://finance.yahoo.com/quote/{yahoo_symbol}",
        f"https://finance.yahoo.com/quote/{yahoo_symbol}/",
    ]

    last_error = None

    for url in urls:
        try:
            r = requests.get(url, headers=HTTP_HEADERS, timeout=20, allow_redirects=True)

            # Do not fail immediately on one URL format. Try the next variant.
            if r.status_code in [403, 404, 429, 500, 502, 503]:
                last_error = f"{r.status_code} for {url}"
                continue

            r.raise_for_status()
            headlines = extract_headlines_from_html(r.text, symbol)
            if headlines:
                return headlines

            last_error = f"No headlines parsed from {url}"
        except Exception as e:
            last_error = str(e)
            continue

    print(f"Yahoo news unavailable for {symbol}: {last_error}")
    return []


def enrich_shortlist_with_yahoo(candidates):
    upside = sorted(candidates, key=lambda x: x["bullishRaw"], reverse=True)[:20]
    downside = sorted(candidates, key=lambda x: x["bearishRaw"], reverse=True)[:20]

    shortlist = []
    seen = set()
    for c in upside + downside:
        if c["ticker"] in seen:
            continue
        seen.add(c["ticker"])
        shortlist.append(c)

    print(f"Fetching Yahoo Finance news for {len(shortlist)} shortlisted tickers.")

    for index, c in enumerate(shortlist, 1):
        ticker = c["ticker"]
        headlines = fetch_yahoo_news_for_symbol(ticker)
        c["news"] = headlines
        c["newsText"] = " ".join([h.get("title", "") for h in headlines])[:2500]

        bull_words, bear_words = keyword_score(c["newsText"])
        c["bullishRaw"] = round(c["bullishRaw"] + bull_words * 3 + min(10, len(headlines) * 1.5), 2)
        c["bearishRaw"] = round(c["bearishRaw"] + bear_words * 3 + min(10, len(headlines) * 1.5), 2)

        print(f"Yahoo {index}/{len(shortlist)} {ticker}: {len(headlines)} headlines")
        time.sleep(0.6)

    enriched_by_ticker = {c["ticker"]: c for c in shortlist}
    return [enriched_by_ticker.get(c["ticker"], c) for c in candidates]


def build_candidates():
    candidates = []
    snapshots = {}
    batch_size = 50

    for i in range(0, len(UNIVERSE), batch_size):
        batch = UNIVERSE[i:i + batch_size]
        snapshots.update(get_snapshot(batch))

    for symbol in UNIVERSE:
        snap = snapshots.get(symbol, {})
        latest = snap.get("latestTrade") or {}
        daily = snap.get("dailyBar") or {}
        prev = snap.get("prevDailyBar") or {}

        latest_price = latest.get("p")
        daily_open = daily.get("o")
        prev_close = prev.get("c")
        volume = daily.get("v") or 0

        if not latest_price or not daily_open or not prev_close:
            continue

        premarket_move = ((latest_price - prev_close) / prev_close) * 100
        abs_premarket = abs(premarket_move)

        volume_score = min(10, math.log10(max(volume, 1)) * 1.5)
        movement_score = min(12, abs_premarket * 1.5)
        liquidity_score = 5 if volume > 1_000_000 else 2

        # Direction-aware initial quant signal.
        bullish_direction_bonus = max(0, premarket_move) * 1.2
        bearish_direction_bonus = max(0, -premarket_move) * 1.2

        bullish_raw = volume_score + movement_score + liquidity_score + bullish_direction_bonus
        bearish_raw = volume_score + movement_score + liquidity_score + bearish_direction_bonus

        candidates.append({
            "ticker": symbol,
            "name": COMPANY_NAMES.get(symbol, symbol),
            "sector": SECTOR_MAP.get(symbol, "General"),
            "premarketMoveRaw": premarket_move,
            "premarketMove": f"{premarket_move:+.2f}%",
            "latestPrice": latest_price,
            "prevClose": prev_close,
            "volume": volume,
            "news": [],
            "newsText": "",
            "bullishRaw": round(bullish_raw, 2),
            "bearishRaw": round(bearish_raw, 2)
        })

    candidates = sorted(candidates, key=lambda x: max(x["bullishRaw"], x["bearishRaw"]), reverse=True)
    print(f"Built {len(candidates)} initial candidates from Alpaca.")
    candidates = enrich_shortlist_with_yahoo(candidates)
    return sorted(candidates, key=lambda x: max(x["bullishRaw"], x["bearishRaw"]), reverse=True)[:120]


def get_recent_tickers(existing_report):
    tickers = set()
    for pick in existing_report.get("picks", []):
        if pick.get("ticker"):
            tickers.add(pick.get("ticker"))
    for day in existing_report.get("history", []):
        for pick in day.get("picks", []):
            if pick.get("ticker"):
                tickers.add(pick.get("ticker"))
    return sorted(tickers)


def ask_openai_for_picks(candidates, existing_report):
    recent_tickers = get_recent_tickers(existing_report)

    upside_candidates = sorted(candidates, key=lambda x: x["bullishRaw"], reverse=True)[:20]
    downside_candidates = sorted(candidates, key=lambda x: x["bearishRaw"], reverse=True)[:20]

    def compact(c):
        return {
            "ticker": c["ticker"],
            "name": c.get("name", c["ticker"]),
            "sector": c.get("sector", "General"),
            "premarketMove": c["premarketMove"],
            "volume": c["volume"],
            "bullishRaw": c["bullishRaw"],
            "bearishRaw": c["bearishRaw"],
            "yahooHeadlines": [n.get("title", "") for n in c.get("news", [])[:8]]
        }

    prompt = f"""
You are selecting intraday U.S. stock movement candidates.

Goal:
Choose exactly 8 stocks for today's regular trading session:
- 4 upside candidates
- 4 downside candidates

Important rules:
- Do NOT choose the same stock for both upside and downside.
- Do NOT simply pick the biggest premarket movers.
- Prefer stocks with fresh, specific catalysts from Yahoo Finance headlines where available.
- If Yahoo headlines are missing for a stock, you may still select it only if market/volume/premarket evidence is strong.
- Avoid repeatedly defaulting to the same mega-cap names unless today's catalyst clearly justifies it.
- Avoid these recent tickers unless they genuinely rank highly today: {recent_tickers}

Scoring weights:
- News catalyst strength: 25%
- Analyst/news commentary: 15%
- Social/public sentiment proxy from headlines: 15%
- Options/volume proxy: 15%
- Relative volume/liquidity: 10%
- Sector strength: 10%
- Macro alignment: 10%

Top quantitative upside candidates:
{json.dumps([compact(c) for c in upside_candidates], indent=2)}

Top quantitative downside candidates:
{json.dumps([compact(c) for c in downside_candidates], indent=2)}

Return ONLY valid JSON. No markdown.

Required structure:
{{
  "marketRegime": "short market regime",
  "marketOverview": "short explanation of today's setup",
  "picks": [
    {{
      "side": "upside",
      "rank": 1,
      "ticker": "ABC",
      "name": "Company name",
      "cap": "Mid/Large/Mega",
      "premarketMove": "+1.23%",
      "probabilityScore": 88,
      "conviction": "Medium/High/Very High",
      "catalyst": "specific catalyst",
      "analyst": "analyst or news read",
      "social": "public sentiment proxy",
      "options": "volume/options proxy",
      "macro": "macro or sector alignment",
      "view": "why it may move today",
      "risk": "main risk"
    }}
  ]
}}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "Return only valid JSON. Pick exactly 4 upside and 4 downside unique tickers."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```json", "", raw)
    raw = re.sub(r"```$", "", raw).strip()
    result = json.loads(raw)

    picks = result.get("picks", [])
    seen = set()
    clean = []

    for p in picks:
        ticker = p.get("ticker")
        side = p.get("side")
        if not ticker or ticker in seen or side not in ["upside", "downside"]:
            continue
        seen.add(ticker)
        clean.append(p)

    upside = [p for p in clean if p["side"] == "upside"][:4]
    downside = [p for p in clean if p["side"] == "downside"][:4]

    if len(upside) < 4 or len(downside) < 4:
        raise ValueError("OpenAI did not return exactly 4 upside and 4 downside unique picks.")

    for i, p in enumerate(upside, 1):
        p["rank"] = i
    for i, p in enumerate(downside, 1):
        p["rank"] = i

    result["picks"] = upside + downside
    return result


def fallback_picks(candidates):
    used = set()
    picks = []

    for c in sorted(candidates, key=lambda x: x["bullishRaw"], reverse=True):
        if len([p for p in picks if p["side"] == "upside"]) >= 4:
            break
        if c["ticker"] in used or c["premarketMoveRaw"] < -8:
            continue
        used.add(c["ticker"])
        picks.append({
            "side": "upside",
            "rank": len([p for p in picks if p["side"] == "upside"]) + 1,
            "ticker": c["ticker"],
            "name": c.get("name", c["ticker"]),
            "cap": "Mid/Large",
            "premarketMove": c["premarketMove"],
            "probabilityScore": min(95, int(65 + c["bullishRaw"])),
            "conviction": "High",
            "catalyst": "Selected by quantitative screen and Yahoo headline check where available.",
            "analyst": "Analyst/news signal inferred from available headlines.",
            "social": "Public sentiment proxy based on headline tone.",
            "options": "Volume proxy used.",
            "macro": "Selected based on sector and market data alignment.",
            "view": "Catalyst and market data point to possible upside.",
            "risk": "Signal may fade after market open."
        })

    for c in sorted(candidates, key=lambda x: x["bearishRaw"], reverse=True):
        if len([p for p in picks if p["side"] == "downside"]) >= 4:
            break
        if c["ticker"] in used or c["premarketMoveRaw"] > 8:
            continue
        used.add(c["ticker"])
        picks.append({
            "side": "downside",
            "rank": len([p for p in picks if p["side"] == "downside"]) + 1,
            "ticker": c["ticker"],
            "name": c.get("name", c["ticker"]),
            "cap": "Mid/Large",
            "premarketMove": c["premarketMove"],
            "probabilityScore": min(95, int(65 + c["bearishRaw"])),
            "conviction": "High",
            "catalyst": "Selected by quantitative screen and Yahoo headline check where available.",
            "analyst": "Analyst/news signal inferred from available headlines.",
            "social": "Public sentiment proxy based on headline tone.",
            "options": "Volume proxy used.",
            "macro": "Selected based on sector and market data alignment.",
            "view": "Catalyst and market data point to possible downside.",
            "risk": "Short-covering or positive headline."
        })

    return {
        "marketRegime": "Yahoo-enhanced quantitative fallback",
        "marketOverview": "OpenAI scoring failed, so unique quantitative picks were selected using Alpaca market data and Yahoo headlines where available.",
        "picks": picks[:8]
    }


def update_history(existing_report):
    history = existing_report.get("history", [])
    old_picks = existing_report.get("picks", [])
    old_date = existing_report.get("reportDateISO")

    if old_picks and old_date:
        already_exists = any(day.get("dateISO") == old_date for day in history)
        if not already_exists:
            completed = []
            for p in old_picks:
                symbol = p.get("ticker")
                if not symbol:
                    continue
                bar = get_daily_bar(symbol, old_date)
                if not bar:
                    continue
                completed.append({
                    "ticker": symbol,
                    "side": p.get("side"),
                    "probabilityScore": p.get("probabilityScore"),
                    "regularOpenPrice": bar["regularOpenPrice"],
                    "regularClosePrice": bar["regularClosePrice"]
                })

            if completed:
                history.insert(0, {
                    "date": datetime.fromisoformat(old_date).strftime("%A %d %B %Y"),
                    "dateISO": old_date,
                    "label": "Previous trading day",
                    "picks": completed
                })

    deduped = []
    seen_dates = set()
    for day in history:
        date_iso = day.get("dateISO") or day.get("date")
        if date_iso in seen_dates:
            continue
        seen_dates.add(date_iso)
        deduped.append(day)

    return deduped[:5]


def main():
    # Manual GitHub workflow runs are allowed at any time for testing.
    # Scheduled runs only proceed during the 15:00 Amsterdam hour.
    if not is_manual_github_run() and now_amsterdam().hour != 15:
        print("Not 15:00 Amsterdam time. Exiting.")
        return

    if not is_us_market_open_today():
        print("US market closed today. No report generated.")
        return

    existing_report = load_existing_report()
    history = update_history(existing_report)

    candidates = build_candidates()

    try:
        ai_result = ask_openai_for_picks(candidates, existing_report)
        print("OpenAI hybrid scoring succeeded.")
    except Exception as e:
        print(f"OpenAI scoring failed, using fallback: {e}")
        ai_result = fallback_picks(candidates)

    today = now_amsterdam()
    today_iso = today.date().isoformat()

    report = {
        "reportDate": today.strftime("%A %d %B %Y"),
        "reportDateISO": today_iso,
        "marketRegime": ai_result.get("marketRegime", ""),
        "marketOverview": ai_result.get("marketOverview", ""),
        "picks": ai_result.get("picks", [])[:8],
        "history": history
    }

    save_report(report)
    print("latest.json updated successfully.")


if __name__ == "__main__":
    main()
