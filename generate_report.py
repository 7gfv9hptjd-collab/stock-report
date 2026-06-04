import os
import json
import re
import math
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from openai import OpenAI

ALPACA_KEY = os.environ["ALPACA_KEY"]
ALPACA_SECRET = os.environ["ALPACA_SECRET"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
FMP_API_KEY = os.environ["FMP_API_KEY"]

ALPACA_BASE = "https://data.alpaca.markets"
ALPACA_TRADING_BASE = "https://api.alpaca.markets"
FMP_BASE = "https://financialmodelingprep.com/api/v3"

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET,
}

client = OpenAI(api_key=OPENAI_API_KEY)
REPORT_FILE = "latest.json"

# Broad liquid US mid/large-cap universe.
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
    "DIS","PARA","WBD","CMCSA","TMUS","T","CHTR","MS","WFC","USB","PNC",
    "TFC","BK","COF","LULU","TGT","DG","DLTR","CROX","EL","ULTA","BBY",
    "TSM","ASML","ARM","MRVL","MPWR","MCHP","NXPI","SWKS","BIIB","MRNA",
    "BNTX","HUM","CI","CVS","HCA","GEV","CEG","NRG","DUK","AEP","EXC",
    "XEL","FCX","NEM","AA","CLF","X","NUE","STLD","OXY","SLB","HAL",
    "BKR","EOG","DVN","MPC","VLO"
]

COMPANY_NAMES = {
    "AAPL":"Apple", "MSFT":"Microsoft", "NVDA":"Nvidia", "AMZN":"Amazon", "META":"Meta Platforms",
    "GOOGL":"Alphabet", "GOOG":"Alphabet", "AVGO":"Broadcom", "TSLA":"Tesla", "LLY":"Eli Lilly",
    "JPM":"JPMorgan Chase", "V":"Visa", "UNH":"UnitedHealth", "XOM":"Exxon Mobil", "MA":"Mastercard",
    "COST":"Costco", "HD":"Home Depot", "PG":"Procter & Gamble", "JNJ":"Johnson & Johnson",
    "ABBV":"AbbVie", "NFLX":"Netflix", "CRM":"Salesforce", "BAC":"Bank of America", "ORCL":"Oracle",
    "AMD":"Advanced Micro Devices", "WMT":"Walmart", "MRK":"Merck", "CVX":"Chevron", "ADBE":"Adobe",
    "QCOM":"Qualcomm", "NOW":"ServiceNow", "GS":"Goldman Sachs", "PFE":"Pfizer", "UBER":"Uber",
    "SHOP":"Shopify", "SNOW":"Snowflake", "CRWD":"CrowdStrike", "DDOG":"Datadog", "COIN":"Coinbase",
    "RIVN":"Rivian", "SOFI":"SoFi", "SMCI":"Super Micro Computer", "DELL":"Dell", "HPE":"Hewlett Packard Enterprise",
    "F":"Ford", "GM":"General Motors", "ENPH":"Enphase Energy", "FSLR":"First Solar", "CCL":"Carnival",
    "RCL":"Royal Caribbean", "DAL":"Delta Air Lines", "UAL":"United Airlines", "DIS":"Disney", "PYPL":"PayPal"
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
    data = alpaca_get(f"{ALPACA_TRADING_BASE}/v2/calendar", {"start": today, "end": today})
    return len(data) > 0


def get_last_trading_days(count=6):
    today = now_amsterdam().date()
    start = (today - timedelta(days=21)).isoformat()
    end = today.isoformat()
    data = alpaca_get(f"{ALPACA_TRADING_BASE}/v2/calendar", {"start": start, "end": end})
    return [d["date"] for d in data][-count:]


def get_snapshot(symbols):
    try:
        return alpaca_get(
            f"{ALPACA_BASE}/v2/stocks/snapshots",
            {"symbols": ",".join(symbols), "feed": "iex"},
        )
    except Exception as e:
        print(f"Snapshot failed for batch: {e}")
        return {}


def get_daily_bar(symbol, date):
    try:
        data = alpaca_get(
            f"{ALPACA_BASE}/v2/stocks/{symbol}/bars",
            {
                "timeframe": "1Day",
                "start": date,
                "end": date,
                "feed": "iex",
                "adjustment": "raw",
            },
        )
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
    with open(REPORT_FILE, "r") as f:
        return json.load(f)


def save_report(report):
    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)


def fmp_get(path, params=None):
    params = dict(params or {})
    params["apikey"] = FMP_API_KEY
    url = f"{FMP_BASE}{path}"
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_fmp_news():
    """
    Uses FMP instead of NewsAPI. Pulls a small number of broad stock-news and press-release records,
    then matches them locally to our ticker universe. This avoids one request per ticker.
    """
    articles = []
    calls = [
        ("/stock_news", {"limit": 250}),
        ("/press-releases", {"limit": 150}),
    ]

    for path, params in calls:
        try:
            data = fmp_get(path, params)
            if isinstance(data, list):
                articles.extend(data)
            print(f"FMP {path} fetched {len(data) if isinstance(data, list) else 0} items.")
        except Exception as e:
            print(f"FMP {path} failed: {e}")

    return articles


def normalize_article(a):
    title = a.get("title") or ""
    text = a.get("text") or a.get("content") or a.get("description") or ""
    site = a.get("site") or a.get("publisher") or a.get("source") or ""
    published = a.get("publishedDate") or a.get("date") or ""
    symbol = a.get("symbol") or ""
    url = a.get("url") or ""
    return {
        "title": title,
        "description": text[:500],
        "source": site,
        "publishedAt": published,
        "symbol": symbol,
        "url": url,
    }


def map_news_to_tickers(articles):
    news_map = {s: [] for s in UNIVERSE}
    name_lookup = {s: COMPANY_NAMES.get(s, s).lower() for s in UNIVERSE}

    for raw in articles:
        a = normalize_article(raw)
        body = f"{a['title']} {a['description']} {a.get('symbol','')}".lower()
        explicit_symbol = str(a.get("symbol") or "").upper().strip()

        matched = set()
        if explicit_symbol in news_map:
            matched.add(explicit_symbol)

        for ticker in UNIVERSE:
            ticker_pattern = rf"\b{re.escape(ticker.lower())}\b"
            company = name_lookup[ticker]
            if re.search(ticker_pattern, body) or (len(company) > 3 and company in body):
                matched.add(ticker)

        for ticker in matched:
            if len(news_map[ticker]) < 8:
                news_map[ticker].append(a)

    return news_map


def keyword_score(text):
    bullish_words = [
        "upgrade", "beats", "beat", "raises", "raised", "strong", "surge", "record", "growth",
        "approval", "contract", "partnership", "buyback", "outperform", "positive", "demand",
        "accelerates", "guidance raise", "higher forecast", "profit rises", "revenue rises"
    ]
    bearish_words = [
        "downgrade", "miss", "misses", "cuts", "cut", "weak", "falls", "lawsuit", "probe",
        "investigation", "warning", "guidance cut", "underperform", "negative", "recall", "delay",
        "slump", "margin pressure", "lower forecast", "profit falls", "revenue falls"
    ]
    lower = text.lower()
    bull = sum(1 for w in bullish_words if w in lower)
    bear = sum(1 for w in bearish_words if w in lower)
    return bull, bear


def build_candidates():
    all_news = fetch_fmp_news()
    print(f"Fetched {len(all_news)} FMP news/press-release items.")
    news_map = map_news_to_tickers(all_news)

    snapshots = {}
    for i in range(0, len(UNIVERSE), 50):
        batch = UNIVERSE[i:i + 50]
        snapshots.update(get_snapshot(batch))

    candidates = []

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
        symbol_news = news_map.get(symbol, [])
        news_text = " ".join([n["title"] + " " + n["description"] for n in symbol_news])
        bull_words, bear_words = keyword_score(news_text)

        news_count = len(symbol_news)
        catalyst_score = min(25, news_count * 4 + max(bull_words, bear_words) * 3)
        volume_score = min(10, math.log10(max(volume, 1)) * 1.35)
        movement_score = min(10, abs(premarket_move) * 1.25)

        bullish_raw = catalyst_score + volume_score + movement_score + bull_words * 2
        bearish_raw = catalyst_score + volume_score + movement_score + bear_words * 2

        # Directional nudge: positive premarket helps bullish; negative helps bearish.
        if premarket_move > 0:
            bullish_raw += min(8, premarket_move)
        elif premarket_move < 0:
            bearish_raw += min(8, abs(premarket_move))

        candidates.append({
            "ticker": symbol,
            "premarketMoveRaw": premarket_move,
            "premarketMove": f"{premarket_move:+.2f}%",
            "latestPrice": latest_price,
            "prevClose": prev_close,
            "volume": volume,
            "news": symbol_news[:5],
            "newsText": news_text[:2500],
            "bullishRaw": round(bullish_raw, 2),
            "bearishRaw": round(bearish_raw, 2),
        })

    candidates = sorted(candidates, key=lambda x: max(x["bullishRaw"], x["bearishRaw"]), reverse=True)
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
    return list(tickers)


def ask_openai_for_picks(candidates, existing_report):
    recent_tickers = get_recent_tickers(existing_report)
    upside_candidates = sorted(candidates, key=lambda x: x["bullishRaw"], reverse=True)[:20]
    downside_candidates = sorted(candidates, key=lambda x: x["bearishRaw"], reverse=True)[:20]

    def compact(c):
        return {
            "ticker": c["ticker"],
            "companyName": COMPANY_NAMES.get(c["ticker"], c["ticker"]),
            "premarketMove": c["premarketMove"],
            "volume": c["volume"],
            "bullishRaw": c["bullishRaw"],
            "bearishRaw": c["bearishRaw"],
            "news": c["news"][:4],
        }

    prompt = f"""
You are selecting intraday U.S. stock movement candidates for a dashboard.

Choose exactly 8 liquid U.S. mid/large-cap stocks for today's regular session:
- 4 upside candidates
- 4 downside candidates

Rules:
- Do NOT choose the same ticker for both upside and downside.
- Do NOT simply pick the biggest premarket movers.
- Do NOT repeatedly default to the same mega-cap stocks unless today's catalyst clearly justifies it.
- Avoid overusing these recent tickers unless their current catalyst is genuinely strong: {recent_tickers}
- Prefer fresh, specific catalysts: earnings, guidance, analyst action, M&A, FDA/regulatory/legal event, unusual volume, sector rotation, macro alignment.
- Penalize vague/stale/no-news situations.

Weights:
- News catalyst strength: 25%
- Analyst action/commentary: 15%
- Social/public sentiment proxy from news tone: 15%
- Options/volume proxy: 15%
- Relative volume/liquidity: 10%
- Sector strength: 10%
- Macro alignment: 10%

Top quantitative upside candidates:
{json.dumps([compact(c) for c in upside_candidates], indent=2)}

Top quantitative downside candidates:
{json.dumps([compact(c) for c in downside_candidates], indent=2)}

Return ONLY valid JSON with this structure:
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
    for p in picks:
        ticker = p.get("ticker")
        side = p.get("side")
        if not ticker or not side or side not in ["upside", "downside"]:
            continue
        if ticker in seen:
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
            "name": COMPANY_NAMES.get(c["ticker"], c["ticker"]),
            "cap": "Mid/Large",
            "premarketMove": c["premarketMove"],
            "probabilityScore": min(95, int(65 + c["bullishRaw"])),
            "conviction": "High",
            "catalyst": "Selected by FMP news, volume and premarket catalyst screen.",
            "analyst": "Analyst signal inferred from available FMP news where present.",
            "social": "Public sentiment proxy based on FMP news tone.",
            "options": "Volume proxy used.",
            "macro": "Selected based on sector/news alignment.",
            "view": "Catalyst stack points to possible upside.",
            "risk": "Signal may fade after market open.",
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
            "name": COMPANY_NAMES.get(c["ticker"], c["ticker"]),
            "cap": "Mid/Large",
            "premarketMove": c["premarketMove"],
            "probabilityScore": min(95, int(65 + c["bearishRaw"])),
            "conviction": "High",
            "catalyst": "Selected by FMP news, volume and premarket catalyst screen.",
            "analyst": "Analyst signal inferred from available FMP news where present.",
            "social": "Public sentiment proxy based on FMP news tone.",
            "options": "Volume proxy used.",
            "macro": "Selected based on sector/news alignment.",
            "view": "Catalyst stack points to possible downside.",
            "risk": "Short-covering or positive headline.",
        })

    return {
        "marketRegime": "Hybrid fallback quantitative screen",
        "marketOverview": "OpenAI scoring failed, so unique quantitative picks were selected using Alpaca market data and FMP catalyst data.",
        "picks": picks[:8],
    }


def update_history(existing_report, trading_days):
    history = existing_report.get("history", [])
    old_picks = existing_report.get("picks", [])
    old_date = existing_report.get("reportDateISO")

    if old_picks and old_date:
        already_exists = any(day.get("dateISO") == old_date for day in history)
        if not already_exists:
            completed = []
            for p in old_picks:
                symbol = p.get("ticker")
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
    # Manual workflow_dispatch tests should run immediately. Scheduled jobs still run at workflow time.
    if not is_us_market_open_today():
        print("US market closed today. No report generated.")
        return

    existing_report = load_existing_report()
    trading_days = get_last_trading_days()
    history = update_history(existing_report, trading_days)
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
        "history": history,
    }

    save_report(report)
    print("latest.json updated successfully.")


if __name__ == "__main__":
    main()
