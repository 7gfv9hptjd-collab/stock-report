
import os
import json
import re
import math
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from openai import OpenAI

# ============================================================
# Environment variables from GitHub Secrets
# ============================================================

ALPACA_KEY = os.environ["ALPACA_KEY"]
ALPACA_SECRET = os.environ["ALPACA_SECRET"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
NEWS_API_KEY = os.environ["NEWS_API_KEY"]

ALPACA_BASE = "https://data.alpaca.markets"
ALPACA_TRADING_BASE = "https://api.alpaca.markets"
NEWS_BASE = "https://newsapi.org/v2/everything"

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET
}

client = OpenAI(api_key=OPENAI_API_KEY)

REPORT_FILE = "latest.json"

# If you manually click "Run workflow" in GitHub Actions, the script is allowed to run
# even if it is not exactly 15:00 Amsterdam time.
# Scheduled runs still only generate a report at 15:00 Amsterdam time.
GITHUB_EVENT_NAME = os.getenv("GITHUB_EVENT_NAME", "")
FORCE_RUN = os.getenv("FORCE_RUN", "false").lower() == "true"


# ============================================================
# Stock universe
# Broad liquid US mid/large-cap universe.
# ============================================================

UNIVERSE = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","AVGO","TSLA","LLY",
    "JPM","V","UNH","XOM","MA","COST","HD","PG","JNJ","ABBV","NFLX",
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
    "DIS","PARA","WBD","CMCSA","TMUS","T","CHTR",
    "MS","WFC","USB","PNC","TFC","BK","COF",
    "LULU","TGT","DG","DLTR","CROX","EL","ULTA","BBY",
    "TSM","ASML","ARM","MRVL","MPWR","MCHP","NXPI","SWKS",
    "BIIB","MRNA","BNTX","HUM","CI","CVS","HCA",
    "GEV","CEG","NRG","DUK","AEP","EXC","XEL",
    "FCX","NEM","AA","CLF","NUE","STLD",
    "OXY","SLB","HAL","BKR","EOG","DVN","MPC","VLO"
]

# Optional friendly company names for dashboard display and better news matching.
NAME_MAP = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "Nvidia",
    "AMZN": "Amazon",
    "META": "Meta Platforms",
    "GOOGL": "Alphabet",
    "GOOG": "Alphabet",
    "AVGO": "Broadcom",
    "TSLA": "Tesla",
    "LLY": "Eli Lilly",
    "JPM": "JPMorgan Chase",
    "UNH": "UnitedHealth",
    "XOM": "Exxon Mobil",
    "COST": "Costco",
    "HD": "Home Depot",
    "PG": "Procter & Gamble",
    "JNJ": "Johnson & Johnson",
    "ABBV": "AbbVie",
    "NFLX": "Netflix",
    "CRM": "Salesforce",
    "BAC": "Bank of America",
    "ORCL": "Oracle",
    "AMD": "Advanced Micro Devices",
    "PEP": "PepsiCo",
    "WMT": "Walmart",
    "MRK": "Merck",
    "CVX": "Chevron",
    "ADBE": "Adobe",
    "CSCO": "Cisco",
    "QCOM": "Qualcomm",
    "TMO": "Thermo Fisher",
    "MCD": "McDonald's",
    "GE": "GE Aerospace",
    "ABT": "Abbott",
    "AMAT": "Applied Materials",
    "TXN": "Texas Instruments",
    "INTU": "Intuit",
    "IBM": "IBM",
    "CAT": "Caterpillar",
    "VZ": "Verizon",
    "NOW": "ServiceNow",
    "BKNG": "Booking Holdings",
    "GS": "Goldman Sachs",
    "ISRG": "Intuitive Surgical",
    "SPGI": "S&P Global",
    "RTX": "RTX",
    "AXP": "American Express",
    "PFE": "Pfizer",
    "UBER": "Uber",
    "LOW": "Lowe's",
    "NEE": "NextEra Energy",
    "HON": "Honeywell",
    "PGR": "Progressive",
    "SYK": "Stryker",
    "BLK": "BlackRock",
    "TJX": "TJX",
    "ETN": "Eaton",
    "VRTX": "Vertex",
    "LRCX": "Lam Research",
    "PANW": "Palo Alto Networks",
    "DE": "Deere",
    "PLTR": "Palantir",
    "MU": "Micron",
    "SHOP": "Shopify",
    "ANET": "Arista Networks",
    "MELI": "MercadoLibre",
    "SNOW": "Snowflake",
    "CRWD": "CrowdStrike",
    "NET": "Cloudflare",
    "DDOG": "Datadog",
    "TEAM": "Atlassian",
    "MDB": "MongoDB",
    "ZS": "Zscaler",
    "OKTA": "Okta",
    "HUBS": "HubSpot",
    "WDAY": "Workday",
    "ROKU": "Roku",
    "COIN": "Coinbase",
    "RBLX": "Roblox",
    "DKNG": "DraftKings",
    "RIVN": "Rivian",
    "LCID": "Lucid",
    "SQ": "Block",
    "PYPL": "PayPal",
    "AFRM": "Affirm",
    "HOOD": "Robinhood",
    "SOFI": "SoFi",
    "SMCI": "Super Micro Computer",
    "DELL": "Dell",
    "HPE": "Hewlett Packard Enterprise",
    "F": "Ford",
    "GM": "General Motors",
    "NIO": "Nio",
    "LI": "Li Auto",
    "XPEV": "XPeng",
    "ENPH": "Enphase",
    "SEDG": "SolarEdge",
    "FSLR": "First Solar",
    "RUN": "Sunrun",
    "CCL": "Carnival",
    "RCL": "Royal Caribbean",
    "NCLH": "Norwegian Cruise Line",
    "DAL": "Delta Air Lines",
    "UAL": "United Airlines",
    "AAL": "American Airlines",
    "LUV": "Southwest Airlines",
    "MAR": "Marriott",
    "HLT": "Hilton",
    "ABNB": "Airbnb",
    "DIS": "Disney",
    "PARA": "Paramount",
    "WBD": "Warner Bros Discovery",
    "CMCSA": "Comcast",
    "TMUS": "T-Mobile",
    "CHTR": "Charter",
    "MS": "Morgan Stanley",
    "WFC": "Wells Fargo",
    "USB": "U.S. Bancorp",
    "PNC": "PNC",
    "TFC": "Truist",
    "COF": "Capital One",
    "LULU": "Lululemon",
    "TGT": "Target",
    "DG": "Dollar General",
    "DLTR": "Dollar Tree",
    "CROX": "Crocs",
    "ULTA": "Ulta Beauty",
    "BBY": "Best Buy",
    "TSM": "Taiwan Semiconductor",
    "ASML": "ASML",
    "ARM": "Arm",
    "MRVL": "Marvell",
    "MPWR": "Monolithic Power",
    "MCHP": "Microchip",
    "NXPI": "NXP",
    "SWKS": "Skyworks",
    "BIIB": "Biogen",
    "MRNA": "Moderna",
    "BNTX": "BioNTech",
    "HUM": "Humana",
    "CI": "Cigna",
    "CVS": "CVS Health",
    "HCA": "HCA Healthcare",
    "GEV": "GE Vernova",
    "CEG": "Constellation Energy",
    "NRG": "NRG Energy",
    "DUK": "Duke Energy",
    "AEP": "American Electric Power",
    "EXC": "Exelon",
    "XEL": "Xcel Energy",
    "FCX": "Freeport-McMoRan",
    "NEM": "Newmont",
    "CLF": "Cleveland-Cliffs",
    "NUE": "Nucor",
    "STLD": "Steel Dynamics",
    "OXY": "Occidental Petroleum",
    "SLB": "SLB",
    "HAL": "Halliburton",
    "BKR": "Baker Hughes",
    "EOG": "EOG Resources",
    "DVN": "Devon Energy",
    "MPC": "Marathon Petroleum",
    "VLO": "Valero"
}


# ============================================================
# Time, files and API helpers
# ============================================================

def now_amsterdam():
    return datetime.now(ZoneInfo("Europe/Amsterdam"))


def today_yyyy_mm_dd():
    return now_amsterdam().date().isoformat()


def alpaca_get(url, params=None):
    r = requests.get(url, headers=HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def is_us_market_open_today():
    today = today_yyyy_mm_dd()
    url = f"{ALPACA_TRADING_BASE}/v2/calendar"
    data = alpaca_get(url, {"start": today, "end": today})
    return len(data) > 0


def get_last_trading_days(count=6):
    today = now_amsterdam().date()
    start = (today - timedelta(days=21)).isoformat()
    end = today.isoformat()
    url = f"{ALPACA_TRADING_BASE}/v2/calendar"
    data = alpaca_get(url, {"start": start, "end": end})
    days = [d["date"] for d in data]
    return days[-count:]


def load_existing_report():
    if not os.path.exists(REPORT_FILE):
        return {
            "reportDate": "",
            "reportDateISO": "",
            "marketRegime": "",
            "marketOverview": "",
            "picks": [],
            "history": []
        }

    with open(REPORT_FILE, "r") as f:
        return json.load(f)


def save_report(report):
    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)


# ============================================================
# Alpaca market data
# ============================================================

def get_snapshot(symbols):
    url = f"{ALPACA_BASE}/v2/stocks/snapshots"
    params = {
        "symbols": ",".join(symbols),
        "feed": "iex"
    }

    try:
        return alpaca_get(url, params)
    except Exception as e:
        print(f"Snapshot failed for batch {symbols[:3]}...: {e}")
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
        print(f"Daily bar failed for {symbol} on {date}: {e}")
        return None


# ============================================================
# News handling
# This version avoids one request per ticker.
# It makes only a few broad NewsAPI requests, then matches locally.
# ============================================================

def fetch_broad_market_news():
    from_date = (datetime.now(timezone.utc) - timedelta(days=3)).date().isoformat()

    queries = [
        'stock earnings guidance analyst upgrade downgrade revenue profit forecast outlook',
        'stocks premarket movers merger acquisition lawsuit investigation FDA approval demand margin',
        'AI chip cloud software semiconductor bank retail energy airline crypto stock market'
    ]

    all_articles = []
    seen_urls = set()

    for query in queries:
        params = {
            "q": query,
            "from": from_date,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 100,
            "apiKey": NEWS_API_KEY
        }

        try:
            r = requests.get(NEWS_BASE, params=params, timeout=25)
            r.raise_for_status()

            for a in r.json().get("articles", []):
                url = a.get("url") or ""
                if url and url in seen_urls:
                    continue

                if url:
                    seen_urls.add(url)

                all_articles.append({
                    "title": a.get("title") or "",
                    "source": (a.get("source") or {}).get("name", ""),
                    "description": a.get("description") or "",
                    "publishedAt": a.get("publishedAt") or "",
                    "url": url
                })

        except Exception as e:
            print(f"Broad news query failed: {e}")

    print(f"Fetched {len(all_articles)} broad news articles.")
    return all_articles


def text_contains_ticker_or_name(text, ticker):
    company = NAME_MAP.get(ticker, "")
    lower = text.lower()

    # Exact ticker matching. This tries to avoid matching normal words like "ON", "C", "F", "T".
    if len(ticker) >= 2:
        if re.search(rf"\b{re.escape(ticker)}\b", text):
            return True

    if company and company.lower() in lower:
        return True

    return False


def articles_for_symbol(all_articles, ticker, limit=5):
    matched = []

    for article in all_articles:
        text = f"{article['title']} {article['description']}"
        if text_contains_ticker_or_name(text, ticker):
            matched.append(article)

        if len(matched) >= limit:
            break

    return matched


# ============================================================
# Quantitative scoring
# ============================================================

def keyword_score(text):
    bullish_words = [
        "upgrade", "upgraded", "beats", "beat", "raises", "raised", "strong",
        "surge", "record", "growth", "approval", "approved", "contract",
        "partnership", "buyback", "outperform", "positive", "demand",
        "ai", "accelerates", "tops", "bullish", "higher", "expands"
    ]

    bearish_words = [
        "downgrade", "downgraded", "miss", "misses", "cuts", "cut", "weak",
        "falls", "lawsuit", "probe", "investigation", "warning",
        "guidance cut", "underperform", "negative", "recall", "delay",
        "slump", "margin pressure", "bearish", "lower", "disappoints"
    ]

    lower = text.lower()
    bull = sum(1 for w in bullish_words if w in lower)
    bear = sum(1 for w in bearish_words if w in lower)

    return bull, bear


def build_candidates():
    candidates = []
    batch_size = 50
    snapshots = {}

    all_news = fetch_broad_market_news()

    for i in range(0, len(UNIVERSE), batch_size):
        batch = UNIVERSE[i:i + batch_size]
        snapshots.update(get_snapshot(batch))

    for symbol in UNIVERSE:
        snap = snapshots.get(symbol, {})
        latest = snap.get("latestTrade") or {}
        daily = snap.get("dailyBar") or {}
        prev = snap.get("prevDailyBar") or {}

        latest_price = latest.get("p")
        prev_close = prev.get("c")
        volume = daily.get("v") or 0

        if not latest_price or not prev_close:
            continue

        premarket_move = ((latest_price - prev_close) / prev_close) * 100

        symbol_news = articles_for_symbol(all_news, symbol, limit=5)
        news_text = " ".join(
            [n["title"] + " " + n["description"] for n in symbol_news]
        )

        bull_words, bear_words = keyword_score(news_text)

        news_count = len(symbol_news)
        catalyst_score = min(25, news_count * 5 + max(bull_words, bear_words) * 2)
        volume_score = min(10, math.log10(max(volume, 1)) * 1.5)
        movement_score = min(10, abs(premarket_move) * 1.5)

        # Direction-aware scoring:
        # Positive premarket action helps upside.
        # Negative premarket action helps downside.
        directional_up_score = max(premarket_move, 0) * 1.25
        directional_down_score = abs(min(premarket_move, 0)) * 1.25

        bullish_raw = (
            catalyst_score
            + volume_score
            + movement_score
            + directional_up_score
            + bull_words * 3
            - bear_words * 1.5
        )

        bearish_raw = (
            catalyst_score
            + volume_score
            + movement_score
            + directional_down_score
            + bear_words * 3
            - bull_words * 1.5
        )

        # Avoid negative raw scores.
        bullish_raw = max(0, bullish_raw)
        bearish_raw = max(0, bearish_raw)

        candidates.append({
            "ticker": symbol,
            "name": NAME_MAP.get(symbol, symbol),
            "premarketMoveRaw": premarket_move,
            "premarketMove": f"{premarket_move:+.2f}%",
            "latestPrice": latest_price,
            "prevClose": prev_close,
            "volume": volume,
            "news": symbol_news,
            "newsText": news_text[:2500],
            "bullishRaw": round(bullish_raw, 2),
            "bearishRaw": round(bearish_raw, 2)
        })

    candidates = sorted(
        candidates,
        key=lambda x: max(x["bullishRaw"], x["bearishRaw"]),
        reverse=True
    )

    print(f"Built {len(candidates)} candidates.")
    return candidates[:120]


def get_recent_tickers(existing_report):
    tickers = set()

    for pick in existing_report.get("picks", []):
        if pick.get("ticker"):
            tickers.add(pick.get("ticker"))

    for day in existing_report.get("history", []):
        for pick in day.get("picks", []):
            if pick.get("ticker"):
                tickers.add(pick.get("ticker"))

    return sorted(list(tickers))


# ============================================================
# Hybrid OpenAI selector
# Quant first, OpenAI final decision.
# ============================================================

def ask_openai_for_picks(candidates, existing_report):
    recent_tickers = get_recent_tickers(existing_report)

    upside_candidates = sorted(
        candidates,
        key=lambda x: x["bullishRaw"],
        reverse=True
    )[:20]

    downside_candidates = sorted(
        candidates,
        key=lambda x: x["bearishRaw"],
        reverse=True
    )[:20]

    def compact(c):
        return {
            "ticker": c["ticker"],
            "name": c["name"],
            "premarketMove": c["premarketMove"],
            "volume": c["volume"],
            "bullishRaw": c["bullishRaw"],
            "bearishRaw": c["bearishRaw"],
            "news": c["news"][:3]
        }

    prompt = f"""
You are selecting intraday U.S. stock movement candidates.

Goal:
Choose exactly 8 stocks for today's trading session:
- 4 upside candidates
- 4 downside candidates

Important rules:
- Do NOT choose the same stock for both upside and downside.
- Do NOT simply pick the biggest premarket movers.
- Do NOT repeatedly default to the same mega-cap stocks unless today's catalyst clearly justifies it.
- Avoid repeating these recent tickers unless their current catalyst is genuinely strong:
{recent_tickers}

Use this hybrid process:
1. Treat the quantitative scores as the first filter, not the final answer.
2. Evaluate catalyst quality from the news.
3. Prefer stocks with fresh, specific catalysts:
   - earnings beat or miss
   - guidance raise or cut
   - analyst upgrade or downgrade
   - M&A
   - FDA/regulatory/legal event
   - unusual volume
   - sector rotation
   - macro alignment
4. Penalize vague or stale news.
5. Penalize stocks that only moved premarket with no clear catalyst.
6. Select stocks most likely to continue moving during the regular session.

Scoring weights:
- News catalyst strength: 25%
- Analyst action/commentary: 15%
- Social/public sentiment proxy: 15%
- Options/volume proxy: 15%
- Relative volume/liquidity: 10%
- Sector strength: 10%
- Macro alignment: 10%

Top quantitative upside candidates:
{json.dumps([compact(c) for c in upside_candidates], indent=2)}

Top quantitative downside candidates:
{json.dumps([compact(c) for c in downside_candidates], indent=2)}

Return ONLY valid JSON.

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
            {
                "role": "system",
                "content": "Return only valid JSON. No markdown. Pick exactly 4 upside and 4 downside stocks. Never duplicate tickers."
            },
            {
                "role": "user",
                "content": prompt
            }
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

        if not ticker or not side:
            continue

        ticker = ticker.upper().strip()
        side = side.lower().strip()

        if ticker in seen:
            continue

        if side not in ["upside", "downside"]:
            continue

        p["ticker"] = ticker
        p["side"] = side
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


# ============================================================
# Fallback if OpenAI fails
# Now unique and direction-aware.
# ============================================================

def fallback_picks(candidates):
    used = set()
    picks = []

    upside = sorted(candidates, key=lambda x: x["bullishRaw"], reverse=True)

    for c in upside:
        if len([p for p in picks if p["side"] == "upside"]) >= 4:
            break

        if c["ticker"] in used:
            continue

        # Avoid calling a collapsing stock an upside candidate without AI review.
        if c["premarketMoveRaw"] < -8:
            continue

        used.add(c["ticker"])

        picks.append({
            "side": "upside",
            "rank": len([p for p in picks if p["side"] == "upside"]) + 1,
            "ticker": c["ticker"],
            "name": c["name"],
            "cap": "Mid/Large",
            "premarketMove": c["premarketMove"],
            "probabilityScore": min(95, max(50, int(65 + c["bullishRaw"]))),
            "conviction": "High",
            "catalyst": "Selected by quantitative catalyst, volume and news screen.",
            "analyst": "Analyst signal unavailable; news proxy used.",
            "social": "Public sentiment proxy based on recent news tone.",
            "options": "Volume proxy used.",
            "macro": "Selected based on sector/news alignment.",
            "view": "Catalyst stack points to possible upside.",
            "risk": "Signal may fade after market open."
        })

    downside = sorted(candidates, key=lambda x: x["bearishRaw"], reverse=True)

    for c in downside:
        if len([p for p in picks if p["side"] == "downside"]) >= 4:
            break

        if c["ticker"] in used:
            continue

        # Avoid calling a strongly rallying stock a downside candidate without AI review.
        if c["premarketMoveRaw"] > 8:
            continue

        used.add(c["ticker"])

        picks.append({
            "side": "downside",
            "rank": len([p for p in picks if p["side"] == "downside"]) + 1,
            "ticker": c["ticker"],
            "name": c["name"],
            "cap": "Mid/Large",
            "premarketMove": c["premarketMove"],
            "probabilityScore": min(95, max(50, int(65 + c["bearishRaw"]))),
            "conviction": "High",
            "catalyst": "Selected by quantitative catalyst, volume and news screen.",
            "analyst": "Analyst signal unavailable; news proxy used.",
            "social": "Public sentiment proxy based on recent news tone.",
            "options": "Volume proxy used.",
            "macro": "Selected based on sector/news alignment.",
            "view": "Catalyst stack points to possible downside.",
            "risk": "Short-covering or positive headline."
        })

    return {
        "marketRegime": "Hybrid fallback quantitative screen",
        "marketOverview": "OpenAI scoring failed, so unique quantitative picks were selected using broad news, volume and premarket signals.",
        "picks": picks[:8]
    }


# ============================================================
# History update
# Moves yesterday's picks into the 5-day accuracy section
# after prices become available.
# ============================================================

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


# ============================================================
# Main
# ============================================================

def main():
    now = now_amsterdam()

    # Allow manual workflow tests at any time.
    # Scheduled GitHub runs only proceed at 15:00 Amsterdam time.
    if not FORCE_RUN and GITHUB_EVENT_NAME != "workflow_dispatch" and now.hour != 15:
        print("Not 15:00 Amsterdam time. Exiting.")
        return

    if not is_us_market_open_today():
        print("US market closed today. No report generated.")
        return

    existing_report = load_existing_report()

    history = update_history(existing_report)

    candidates = build_candidates()

    if not candidates:
        raise RuntimeError("No candidates were built. Check Alpaca and NewsAPI data.")

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
