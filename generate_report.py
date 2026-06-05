import os
import json
import re
import math
import time
import html
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from openai import OpenAI

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

ALPACA_KEY = os.environ["ALPACA_KEY"]
ALPACA_SECRET = os.environ["ALPACA_SECRET"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

ALPACA_BASE = "https://data.alpaca.markets"
ALPACA_TRADING_BASE = "https://api.alpaca.markets"
REPORT_FILE = "latest.json"

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET,
}

YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

client = OpenAI(api_key=OPENAI_API_KEY)

# Broad liquid US mid/large-cap universe.
# You can expand this later; keep it reasonable to avoid slow GitHub Actions runs.
UNIVERSE = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","AVGO","TSLA","LLY","JPM","V","UNH","XOM","MA","COST","HD","PG","JNJ","ABBV","NFLX",
    "CRM","BAC","ORCL","AMD","KO","PEP","WMT","MRK","CVX","ADBE","CSCO","QCOM","TMO","MCD","GE","ABT","AMAT","TXN","INTU","IBM","CAT","VZ",
    "NOW","BKNG","GS","ISRG","SPGI","RTX","AXP","PFE","UBER","LOW","NEE","HON","PGR","SYK","BLK","TJX","ETN","VRTX","LRCX","PANW","C","DE",
    "ADP","MDT","REGN","ADI","MMC","CB","KLAC","SCHW","PLTR","MU","BSX","AMGN","GILD","INTC","SO","UPS","COP","NKE","BA","SBUX","ELV","FI",
    "SHOP","ANET","MELI","SNOW","CRWD","NET","DDOG","TEAM","MDB","ZS","OKTA","HUBS","WDAY","ROKU","COIN","RBLX","DKNG","RIVN","LCID","U",
    "SQ","PYPL","AFRM","HOOD","SOFI","ON","SMCI","DELL","HPE","HPQ","F","GM","STLA","NIO","LI","XPEV","ENPH","SEDG","FSLR","RUN",
    "CCL","RCL","NCLH","DAL","UAL","AAL","LUV","MAR","HLT","ABNB","DIS","PARA","WBD","CMCSA","TMUS","T","CHTR","MS","WFC","USB","PNC","TFC","BK","COF",
    "LULU","TGT","DG","DLTR","CROX","EL","ULTA","BBY","TSM","ASML","ARM","MRVL","MPWR","MCHP","NXPI","SWKS","BIIB","MRNA","BNTX","HUM","CI","CVS","HCA",
    "GEV","CEG","NRG","DUK","AEP","EXC","XEL","FCX","NEM","AA","CLF","X","NUE","STLD","OXY","SLB","HAL","BKR","EOG","DVN","MPC","VLO"
]

COMPANY_NAMES = {
    "AAPL":"Apple","MSFT":"Microsoft","NVDA":"Nvidia","AMZN":"Amazon","META":"Meta Platforms","GOOGL":"Alphabet","GOOG":"Alphabet","AVGO":"Broadcom","TSLA":"Tesla","LLY":"Eli Lilly","JPM":"JPMorgan Chase","V":"Visa","UNH":"UnitedHealth","XOM":"Exxon Mobil","MA":"Mastercard","COST":"Costco","HD":"Home Depot","PG":"Procter & Gamble","JNJ":"Johnson & Johnson","ABBV":"AbbVie","NFLX":"Netflix","CRM":"Salesforce","BAC":"Bank of America","ORCL":"Oracle","AMD":"Advanced Micro Devices","KO":"Coca-Cola","PEP":"PepsiCo","WMT":"Walmart","MRK":"Merck","CVX":"Chevron","ADBE":"Adobe","CSCO":"Cisco","QCOM":"Qualcomm","TMO":"Thermo Fisher","MCD":"McDonald's","GE":"GE Aerospace","ABT":"Abbott","AMAT":"Applied Materials","TXN":"Texas Instruments","INTU":"Intuit","IBM":"IBM","CAT":"Caterpillar","VZ":"Verizon","NOW":"ServiceNow","BKNG":"Booking Holdings","GS":"Goldman Sachs","ISRG":"Intuitive Surgical","SPGI":"S&P Global","RTX":"RTX","AXP":"American Express","PFE":"Pfizer","UBER":"Uber","LOW":"Lowe's","NEE":"NextEra Energy","HON":"Honeywell","PGR":"Progressive","SYK":"Stryker","BLK":"BlackRock","TJX":"TJX","ETN":"Eaton","VRTX":"Vertex","LRCX":"Lam Research","PANW":"Palo Alto Networks","C":"Citigroup","DE":"Deere","PLTR":"Palantir","MU":"Micron","INTC":"Intel","SHOP":"Shopify","SNOW":"Snowflake","CRWD":"CrowdStrike","NET":"Cloudflare","DDOG":"Datadog","TEAM":"Atlassian","MDB":"MongoDB","ZS":"Zscaler","OKTA":"Okta","HUBS":"HubSpot","WDAY":"Workday","ROKU":"Roku","COIN":"Coinbase","RBLX":"Roblox","DKNG":"DraftKings","RIVN":"Rivian","SOFI":"SoFi","SMCI":"Super Micro Computer","DELL":"Dell","HPE":"Hewlett Packard Enterprise","F":"Ford","GM":"General Motors","ENPH":"Enphase","FSLR":"First Solar","CCL":"Carnival","RCL":"Royal Caribbean","DAL":"Delta Air Lines","UAL":"United Airlines","AAL":"American Airlines","ABNB":"Airbnb","DIS":"Disney","WBD":"Warner Bros Discovery","TSM":"Taiwan Semiconductor","ASML":"ASML","ARM":"Arm Holdings","MRVL":"Marvell","MCHP":"Microchip","BIIB":"Biogen","MRNA":"Moderna","HUM":"Humana","CVS":"CVS Health","HCA":"HCA Healthcare","CEG":"Constellation Energy","NRG":"NRG Energy","FCX":"Freeport-McMoRan","NEM":"Newmont","AA":"Alcoa","NUE":"Nucor","OXY":"Occidental Petroleum","SLB":"Schlumberger","HAL":"Halliburton","DVN":"Devon Energy","MPC":"Marathon Petroleum","VLO":"Valero"
}

SECTOR_MAP = {
    "NVDA":"Semiconductors","AMD":"Semiconductors","AVGO":"Semiconductors","MU":"Semiconductors","INTC":"Semiconductors","TSM":"Semiconductors","ASML":"Semiconductors","ARM":"Semiconductors","MRVL":"Semiconductors","MCHP":"Semiconductors","QCOM":"Semiconductors","AMAT":"Semiconductor Equipment","LRCX":"Semiconductor Equipment","KLAC":"Semiconductor Equipment",
    "MSFT":"Mega-cap Technology","AAPL":"Mega-cap Technology","GOOGL":"Mega-cap Technology","GOOG":"Mega-cap Technology","META":"Mega-cap Technology","AMZN":"Consumer/Cloud","NFLX":"Streaming","CRM":"Software","NOW":"Software","SNOW":"Software","CRWD":"Cybersecurity","PANW":"Cybersecurity","NET":"Software","DDOG":"Software","TEAM":"Software","MDB":"Software","ZS":"Cybersecurity","OKTA":"Cybersecurity","WDAY":"Software",
    "JPM":"Banks","BAC":"Banks","GS":"Banks","MS":"Banks","WFC":"Banks","C":"Banks","AXP":"Financials","COF":"Financials","SCHW":"Brokerage","COIN":"Crypto","HOOD":"Brokerage","SOFI":"Fintech","PYPL":"Fintech","SQ":"Fintech","AFRM":"Fintech",
    "LLY":"Healthcare","UNH":"Healthcare","JNJ":"Healthcare","ABBV":"Healthcare","MRK":"Healthcare","PFE":"Healthcare","AMGN":"Biotech","GILD":"Biotech","VRTX":"Biotech","REGN":"Biotech","MRNA":"Biotech","BIIB":"Biotech","HUM":"Healthcare","CVS":"Healthcare","HCA":"Healthcare",
    "XOM":"Energy","CVX":"Energy","OXY":"Energy","SLB":"Energy Services","HAL":"Energy Services","BKR":"Energy Services","EOG":"Energy","DVN":"Energy","MPC":"Refining","VLO":"Refining",
    "TSLA":"EV/Autos","RIVN":"EV/Autos","LCID":"EV/Autos","F":"Autos","GM":"Autos","NIO":"EV/Autos","LI":"EV/Autos","XPEV":"EV/Autos",
    "COST":"Retail","WMT":"Retail","HD":"Retail","LOW":"Retail","TGT":"Retail","DG":"Retail","DLTR":"Retail","NKE":"Consumer","LULU":"Consumer","ULTA":"Consumer","CROX":"Consumer","EL":"Consumer",
    "DAL":"Airlines","UAL":"Airlines","AAL":"Airlines","LUV":"Airlines","CCL":"Cruise Lines","RCL":"Cruise Lines","NCLH":"Cruise Lines","MAR":"Hotels","HLT":"Hotels","ABNB":"Travel",
    "CEG":"Utilities/Power","NRG":"Utilities/Power","DUK":"Utilities","SO":"Utilities","AEP":"Utilities","EXC":"Utilities","XEL":"Utilities","GEV":"Power/Industrials","GE":"Industrials","CAT":"Industrials","DE":"Industrials","BA":"Aerospace","RTX":"Aerospace",
    "ENPH":"Solar","SEDG":"Solar","FSLR":"Solar","RUN":"Solar",
    "FCX":"Materials","NEM":"Gold Miners","AA":"Materials","CLF":"Steel","X":"Steel","NUE":"Steel","STLD":"Steel"
}


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
        "adjustment": "raw",
    }
    try:
        data = alpaca_get(url, params)
        bars = data.get("bars", [])
        if not bars:
            return None
        bar = bars[0]
        return {
            "regularOpenPrice": round(float(bar["o"]), 4),
            "regularClosePrice": round(float(bar["c"]), 4),
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
        "upgrade", "upgraded", "beats", "beat", "raises", "raised", "strong", "surge",
        "record", "growth", "approval", "approved", "contract", "partnership", "buyback",
        "outperform", "positive", "demand", "ai", "accelerates", "guidance raise", "tops estimates",
        "profit jumps", "revenue growth", "price target raised", "initiated at buy"
    ]
    bearish_words = [
        "downgrade", "downgraded", "miss", "misses", "cuts", "cut", "weak", "falls",
        "lawsuit", "probe", "investigation", "warning", "guidance cut", "underperform",
        "negative", "recall", "delay", "slump", "margin pressure", "price target cut",
        "initiated at sell", "fraud", "sec", "doj", "layoffs", "shortfall"
    ]
    lower = text.lower()
    bull = sum(1 for w in bullish_words if w in lower)
    bear = sum(1 for w in bearish_words if w in lower)
    return bull, bear


def yahoo_news_for_symbol(symbol, max_items=8):
    """
    Lightweight Yahoo Finance headline scrape for one ticker.
    This is intentionally limited to shortlisted tickers only.
    Yahoo has no official free API for this page; this may occasionally break or be rate-limited.
    """
    url = f"https://finance.yahoo.com/quote/{symbol}/news/"
    try:
        r = requests.get(url, headers=YAHOO_HEADERS, timeout=20)
        if r.status_code in (403, 429):
            print(f"Yahoo blocked/rate-limited {symbol}: {r.status_code}")
            return []
        r.raise_for_status()
        body = r.text
    except Exception as e:
        print(f"Yahoo news failed for {symbol}: {e}")
        return []

    items = []
    seen_titles = set()

    # Method 1: Parse visible headlines if BeautifulSoup is available.
    if BeautifulSoup:
        try:
            soup = BeautifulSoup(body, "html.parser")
            for tag in soup.find_all(["h3", "a"]):
                text = tag.get_text(" ", strip=True)
                if not text or len(text) < 25:
                    continue
                if any(skip in text.lower() for skip in ["sign in", "subscribe", "portfolio", "advertisement"]):
                    continue
                key = text.lower()
                if key in seen_titles:
                    continue
                href = tag.get("href") or ""
                if href.startswith("/"):
                    href = "https://finance.yahoo.com" + href
                seen_titles.add(key)
                items.append({"title": html.unescape(text), "source": "Yahoo Finance", "url": href})
                if len(items) >= max_items:
                    break
        except Exception:
            pass

    # Method 2: Extract JSON embedded titles.
    if len(items) < max_items:
        try:
            title_matches = re.findall(r'"title"\s*:\s*"(.*?)"', body)
            provider_matches = re.findall(r'"providerDisplayName"\s*:\s*"(.*?)"', body)
            for idx, raw_title in enumerate(title_matches):
                title = bytes(raw_title, "utf-8").decode("unicode_escape", errors="ignore")
                title = html.unescape(title).strip()
                if not title or len(title) < 25:
                    continue
                key = title.lower()
                if key in seen_titles:
                    continue
                source = "Yahoo Finance"
                if idx < len(provider_matches):
                    source = html.unescape(provider_matches[idx]) or source
                seen_titles.add(key)
                items.append({"title": title, "source": source, "url": url})
                if len(items) >= max_items:
                    break
        except Exception:
            pass

    return items[:max_items]


def build_candidates_without_news():
    candidates = []
    snapshots = {}
    batch_size = 50

    for i in range(0, len(UNIVERSE), batch_size):
        batch = UNIVERSE[i:i + batch_size]
        snapshots.update(get_snapshot(batch))
        time.sleep(0.25)

    for symbol in UNIVERSE:
        snap = snapshots.get(symbol, {})
        latest = snap.get("latestTrade") or {}
        daily = snap.get("dailyBar") or {}
        prev = snap.get("prevDailyBar") or {}
        minute = snap.get("minuteBar") or {}

        latest_price = latest.get("p")
        prev_close = prev.get("c")
        daily_open = daily.get("o")
        day_high = daily.get("h")
        day_low = daily.get("l")
        volume = daily.get("v") or 0
        minute_volume = minute.get("v") or 0

        if not latest_price or not prev_close:
            continue

        premarket_move = ((latest_price - prev_close) / prev_close) * 100
        intraday_range = 0
        if day_high and day_low and latest_price:
            intraday_range = abs((day_high - day_low) / latest_price) * 100

        volume_score = min(15, math.log10(max(volume, 1)) * 2)
        move_score = min(15, abs(premarket_move) * 2)
        range_score = min(10, intraday_range * 2)
        minute_score = min(8, math.log10(max(minute_volume, 1)) * 1.5)

        # Initial quant direction before news:
        bullish_raw = volume_score + move_score + range_score + minute_score
        bearish_raw = volume_score + move_score + range_score + minute_score

        # Modest directional bias from price action.
        if premarket_move > 0:
            bullish_raw += min(8, premarket_move)
            bearish_raw += min(3, premarket_move / 2)
        elif premarket_move < 0:
            bearish_raw += min(8, abs(premarket_move))
            bullish_raw += min(3, abs(premarket_move) / 2)

        candidates.append({
            "ticker": symbol,
            "name": COMPANY_NAMES.get(symbol, symbol),
            "sector": SECTOR_MAP.get(symbol, "Unknown"),
            "premarketMoveRaw": premarket_move,
            "premarketMove": f"{premarket_move:+.2f}%",
            "latestPrice": latest_price,
            "prevClose": prev_close,
            "volume": volume,
            "minuteVolume": minute_volume,
            "news": [],
            "newsText": "",
            "bullishRaw": round(bullish_raw, 2),
            "bearishRaw": round(bearish_raw, 2),
        })

    print(f"Built {len(candidates)} initial candidates from Alpaca.")
    return candidates


def shortlist_for_yahoo(candidates):
    upside = sorted(candidates, key=lambda x: x["bullishRaw"], reverse=True)[:20]
    downside = sorted(candidates, key=lambda x: x["bearishRaw"], reverse=True)[:20]
    merged = []
    seen = set()
    for c in upside + downside:
        if c["ticker"] in seen:
            continue
        seen.add(c["ticker"])
        merged.append(c)
    return merged


def enrich_shortlist_with_yahoo_news(candidates):
    shortlisted = shortlist_for_yahoo(candidates)
    print(f"Fetching Yahoo Finance news for {len(shortlisted)} shortlisted tickers.")

    candidate_by_ticker = {c["ticker"]: c for c in candidates}

    for idx, c in enumerate(shortlisted, 1):
        symbol = c["ticker"]
        articles = yahoo_news_for_symbol(symbol, max_items=8)
        news_text = " ".join([a.get("title", "") for a in articles])
        bull_words, bear_words = keyword_score(news_text)
        news_count = len(articles)

        catalyst_score = min(30, news_count * 3 + max(bull_words, bear_words) * 4)
        bullish_boost = catalyst_score + bull_words * 5
        bearish_boost = catalyst_score + bear_words * 5

        target = candidate_by_ticker[symbol]
        target["news"] = articles[:6]
        target["newsText"] = news_text[:2500]
        target["bullishRaw"] = round(target["bullishRaw"] + bullish_boost, 2)
        target["bearishRaw"] = round(target["bearishRaw"] + bearish_boost, 2)

        print(f"Yahoo {idx}/{len(shortlisted)} {symbol}: {len(articles)} headlines")
        time.sleep(0.4)

    return candidates


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


def ask_openai_for_picks(candidates, existing_report):
    recent_tickers = get_recent_tickers(existing_report)

    upside_candidates = sorted(candidates, key=lambda x: x["bullishRaw"], reverse=True)[:20]
    downside_candidates = sorted(candidates, key=lambda x: x["bearishRaw"], reverse=True)[:20]

    def compact(c):
        return {
            "ticker": c["ticker"],
            "name": c.get("name", c["ticker"]),
            "sector": c.get("sector", "Unknown"),
            "premarketMove": c["premarketMove"],
            "volume": c["volume"],
            "bullishRaw": c["bullishRaw"],
            "bearishRaw": c["bearishRaw"],
            "yahooHeadlines": c.get("news", [])[:6],
        }

    prompt = f"""
You are selecting intraday U.S. stock movement candidates for a trading dashboard.

Goal:
Choose exactly 8 liquid U.S. mid-cap or large-cap stocks for today's regular trading session:
- 4 upside candidates
- 4 downside candidates

Selection process already completed before this step:
1. Alpaca scanned roughly 200 liquid stocks.
2. Quant model ranked by premarket move, volume, liquidity and activity.
3. Yahoo Finance news headlines were scraped only for the top quant candidates below.

Important rules:
- Do NOT choose the same stock for both upside and downside.
- Do NOT simply choose the biggest premarket movers.
- Do NOT repeatedly default to the same mega-cap names unless today's catalyst clearly justifies it.
- Avoid these recent tickers unless the current setup is genuinely stronger than alternatives:
{recent_tickers}
- Prefer fresh, specific catalysts over generic headlines.
- Penalize vague headlines, stale stories, or moves with no clear catalyst.
- Pick stocks most likely to continue moving during the regular trading session.

Decision weights:
- News/catalyst strength: 25%
- Analyst or market commentary: 15%
- Public sentiment proxy from headlines: 15%
- Options/volume/activity proxy: 15%
- Relative volume/liquidity: 10%
- Sector strength: 10%
- Macro alignment: 10%

Top quantitative upside candidates:
{json.dumps([compact(c) for c in upside_candidates], indent=2)}

Top quantitative downside candidates:
{json.dumps([compact(c) for c in downside_candidates], indent=2)}

Return ONLY valid JSON with this exact structure:
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
      "catalyst": "specific catalyst based on headlines and data",
      "analyst": "analyst/news read, or 'No clear analyst action found'",
      "social": "public sentiment proxy from headlines",
      "options": "volume/activity proxy",
      "macro": "sector or macro alignment",
      "view": "why it may move today",
      "risk": "main risk"
    }}
  ]
}}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "Return only valid JSON. No markdown. Pick exactly 4 upside and 4 downside stocks. Never duplicate tickers."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```json", "", raw)
    raw = re.sub(r"```$", "", raw).strip()
    result = json.loads(raw)

    picks = result.get("picks", [])
    seen = set()
    clean = []
    ticker_to_candidate = {c["ticker"]: c for c in candidates}

    for p in picks:
        ticker = p.get("ticker")
        side = p.get("side")
        if not ticker or not side:
            continue
        ticker = ticker.upper().strip()
        if ticker in seen:
            continue
        if side not in ["upside", "downside"]:
            continue
        if ticker not in ticker_to_candidate:
            continue

        c = ticker_to_candidate[ticker]
        p["ticker"] = ticker
        p["name"] = p.get("name") or c.get("name", ticker)
        p["premarketMove"] = c.get("premarketMove", p.get("premarketMove", ""))
        p["sourceHeadlines"] = c.get("news", [])[:5]
        seen.add(ticker)
        clean.append(p)

    upside = [p for p in clean if p["side"] == "upside"][:4]
    downside = [p for p in clean if p["side"] == "downside"][:4]

    if len(upside) < 4 or len(downside) < 4:
        raise ValueError("OpenAI did not return exactly 4 upside and 4 downside unique valid picks.")

    for i, p in enumerate(upside, 1):
        p["rank"] = i
    for i, p in enumerate(downside, 1):
        p["rank"] = i

    result["picks"] = upside + downside
    return result


def fallback_picks(candidates):
    used = set()
    picks = []

    upside_pool = sorted(candidates, key=lambda x: x["bullishRaw"], reverse=True)
    for c in upside_pool:
        if len([p for p in picks if p["side"] == "upside"]) >= 4:
            break
        if c["ticker"] in used:
            continue
        if c["premarketMoveRaw"] < -8:
            continue
        used.add(c["ticker"])
        picks.append({
            "side": "upside",
            "rank": len([p for p in picks if p["side"] == "upside"]) + 1,
            "ticker": c["ticker"],
            "name": c.get("name", c["ticker"]),
            "cap": "Mid/Large",
            "premarketMove": c["premarketMove"],
            "probabilityScore": min(95, int(60 + c["bullishRaw"])),
            "conviction": "High",
            "catalyst": "Selected by quant model using market data and Yahoo headline scrape.",
            "analyst": "No clear analyst action found in automated fallback.",
            "social": "Headline sentiment proxy used.",
            "options": "Volume/activity proxy used.",
            "macro": f"Sector: {c.get('sector', 'Unknown')}",
            "view": "Catalyst and activity stack point to possible upside.",
            "risk": "Signal may fade after market open.",
            "sourceHeadlines": c.get("news", [])[:5],
        })

    downside_pool = sorted(candidates, key=lambda x: x["bearishRaw"], reverse=True)
    for c in downside_pool:
        if len([p for p in picks if p["side"] == "downside"]) >= 4:
            break
        if c["ticker"] in used:
            continue
        if c["premarketMoveRaw"] > 8:
            continue
        used.add(c["ticker"])
        picks.append({
            "side": "downside",
            "rank": len([p for p in picks if p["side"] == "downside"]) + 1,
            "ticker": c["ticker"],
            "name": c.get("name", c["ticker"]),
            "cap": "Mid/Large",
            "premarketMove": c["premarketMove"],
            "probabilityScore": min(95, int(60 + c["bearishRaw"])),
            "conviction": "High",
            "catalyst": "Selected by quant model using market data and Yahoo headline scrape.",
            "analyst": "No clear analyst action found in automated fallback.",
            "social": "Headline sentiment proxy used.",
            "options": "Volume/activity proxy used.",
            "macro": f"Sector: {c.get('sector', 'Unknown')}",
            "view": "Catalyst and activity stack point to possible downside.",
            "risk": "Short-covering or positive headline risk.",
            "sourceHeadlines": c.get("news", [])[:5],
        })

    return {
        "marketRegime": "Yahoo + Alpaca quantitative fallback",
        "marketOverview": "OpenAI scoring failed; unique fallback picks were selected using Alpaca market data and Yahoo headline signals.",
        "picks": picks[:8],
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
                    "regularClosePrice": bar["regularClosePrice"],
                })
            if completed:
                history.insert(0, {
                    "date": datetime.fromisoformat(old_date).strftime("%A %d %B %Y"),
                    "dateISO": old_date,
                    "label": "Previous trading day",
                    "picks": completed,
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
    # The GitHub schedule controls timing. Manual workflow runs are allowed for testing.
    if not is_us_market_open_today():
        print("US market closed today. No report generated.")
        return

    existing_report = load_existing_report()
    history = update_history(existing_report)

    candidates = build_candidates_without_news()
    candidates = enrich_shortlist_with_yahoo_news(candidates)

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
        "history": history,
        "dataSources": {
            "marketData": "Alpaca",
            "news": "Yahoo Finance ticker news pages for shortlisted candidates",
            "aiSelection": "OpenAI",
        },
    }

    save_report(report)
    print("latest.json updated successfully.")


if __name__ == "__main__":
    main()
