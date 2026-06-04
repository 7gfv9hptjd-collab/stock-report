import os
import json
import re
import math
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from openai import OpenAI

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
    "GS","MS","WFC","USB","PNC","TFC","BK","SCHW","AXP","COF",
    "LULU","TGT","DG","DLTR","CROX","NKE","EL","ULTA","BBY",
    "TSM","ASML","ARM","MRVL","MPWR","MCHP","NXPI","SWKS",
    "BIIB","MRNA","BNTX","VRTX","REGN","HUM","CI","CVS","HCA",
    "GEV","CEG","NRG","DUK","SO","AEP","EXC","XEL",
    "FCX","NEM","AA","CLF","X","NUE","STLD",
    "OXY","SLB","HAL","BKR","EOG","PXD","DVN","MPC","VLO"
]

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
    start = (today - timedelta(days=14)).isoformat()
    end = today.isoformat()
    url = f"{ALPACA_TRADING_BASE}/v2/calendar"
    data = alpaca_get(url, {"start": start, "end": end})
    days = [d["date"] for d in data]
    return days[-count:]

def get_snapshot(symbols):
    url = f"{ALPACA_BASE}/v2/stocks/snapshots"
    params = {
        "symbols": ",".join(symbols),
        "feed": "iex"
    }
    try:
        return alpaca_get(url, params)
    except Exception:
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
    except Exception:
        return None

def load_existing_report():
    if not os.path.exists(REPORT_FILE):
        return {
            "reportDate": "",
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

def fetch_news_for_symbol(symbol):
    query = f'({symbol} OR "{symbol} stock") AND (earnings OR guidance OR upgrade OR downgrade OR analyst OR revenue OR profit OR lawsuit OR FDA OR merger OR acquisition OR demand OR margin OR AI OR chip OR cloud OR sales)'
    from_date = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()

    params = {
        "q": query,
        "from": from_date,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 5,
        "apiKey": NEWS_API_KEY
    }

    try:
        r = requests.get(NEWS_BASE, params=params, timeout=20)
        r.raise_for_status()
        articles = r.json().get("articles", [])
        return [
            {
                "title": a.get("title") or "",
                "source": (a.get("source") or {}).get("name", ""),
                "description": a.get("description") or "",
                "publishedAt": a.get("publishedAt") or ""
            }
            for a in articles
        ]
    except Exception:
        return []

def keyword_score(text):
    bullish_words = [
        "upgrade", "beats", "beat", "raises", "raised", "strong", "surge",
        "record", "growth", "approval", "contract", "partnership", "buyback",
        "outperform", "positive", "demand", "ai", "accelerates"
    ]

    bearish_words = [
        "downgrade", "miss", "misses", "cuts", "cut", "weak", "falls",
        "lawsuit", "probe", "investigation", "warning", "guidance cut",
        "underperform", "negative", "recall", "delay", "slump", "margin pressure"
    ]

    lower = text.lower()
    bull = sum(1 for w in bullish_words if w in lower)
    bear = sum(1 for w in bearish_words if w in lower)

    return bull, bear

def build_candidates():
    candidates = []

    batch_size = 50
    snapshots = {}

    for i in range(0, len(UNIVERSE), batch_size):
        batch = UNIVERSE[i:i + batch_size]
        snapshots.update(get_snapshot(batch))

    for symbol in UNIVERSE:
        snap = snapshots.get(symbol, {})
        latest = snap.get("latestTrade") or {}
        minute = snap.get("minuteBar") or {}
        daily = snap.get("dailyBar") or {}
        prev = snap.get("prevDailyBar") or {}

        latest_price = latest.get("p")
        daily_open = daily.get("o")
        prev_close = prev.get("c")
        volume = daily.get("v") or 0

        if not latest_price or not daily_open or not prev_close:
            continue

        premarket_move = ((latest_price - prev_close) / prev_close) * 100

        news = fetch_news_for_symbol(symbol)
        news_text = " ".join(
            [n["title"] + " " + n["description"] for n in news]
        )

        bull_words, bear_words = keyword_score(news_text)

        news_count = len(news)
        catalyst_score = min(25, news_count * 5 + max(bull_words, bear_words) * 2)
        volume_score = min(10, math.log10(max(volume, 1)) * 1.5)

        abs_premarket = abs(premarket_move)
        movement_score = min(10, abs_premarket * 1.5)

        bullish_raw = catalyst_score + volume_score + movement_score + bull_words * 2
        bearish_raw = catalyst_score + volume_score + movement_score + bear_words * 2

        candidates.append({
            "ticker": symbol,
            "premarketMoveRaw": premarket_move,
            "premarketMove": f"{premarket_move:+.2f}%",
            "latestPrice": latest_price,
            "prevClose": prev_close,
            "volume": volume,
            "news": news,
            "newsText": news_text[:2500],
            "bullishRaw": round(bullish_raw, 2),
            "bearishRaw": round(bearish_raw, 2)
        })

    candidates = sorted(
        candidates,
        key=lambda x: max(x["bullishRaw"], x["bearishRaw"]),
        reverse=True
    )

    return candidates[:60]

def get_recent_tickers(existing_report):
    tickers = set()

    for pick in existing_report.get("picks", []):
        tickers.add(pick.get("ticker"))

    for day in existing_report.get("history", []):
        for pick in day.get("picks", []):
            tickers.add(pick.get("ticker"))

    return list(tickers)

def ask_openai_for_picks(candidates, existing_report):
    recent_tickers = get_recent_tickers(existing_report)

    compact_candidates = []
    for c in candidates:
        compact_candidates.append({
            "ticker": c["ticker"],
            "premarketMove": c["premarketMove"],
            "volume": c["volume"],
            "bullishRaw": c["bullishRaw"],
            "bearishRaw": c["bearishRaw"],
            "news": c["news"][:3]
        })

    prompt = f"""
You are building an intraday stock movement dashboard.

Task:
Identify exactly 8 U.S. mid-cap or large-cap liquid stocks for today:
- 4 upside candidates
- 4 downside candidates

Do not pick the same mega-cap names repeatedly unless the current catalyst clearly justifies it.
Avoid overusing these recent tickers unless they are genuinely among today's strongest candidates:
{recent_tickers}

Use this weighted model:
- News catalyst strength: 25%
- Analyst action/commentary: 15%
- Social/public sentiment proxy from news tone: 15%
- Options/volume proxy: 15%
- Relative volume / liquidity: 10%
- Sector strength: 10%
- Macro alignment: 10%

Candidate data:
{json.dumps(compact_candidates, indent=2)}

Return ONLY valid JSON with this structure:
{{
  "marketRegime": "short market regime",
  "marketOverview": "short explanation",
  "picks": [
    {{
      "side": "upside or downside",
      "rank": 1,
      "ticker": "ABC",
      "name": "Company name",
      "cap": "Mid/Large/Mega",
      "premarketMove": "+1.23%",
      "probabilityScore": 88,
      "conviction": "Medium/High/Very High",
      "catalyst": "why selected",
      "analyst": "analyst/news read",
      "social": "public sentiment proxy",
      "options": "options/volume proxy",
      "macro": "macro/sector alignment",
      "view": "why it may move today",
      "risk": "main risk"
    }}
  ]
}}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "Return only valid JSON. No markdown."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.25
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```json", "", raw)
    raw = re.sub(r"```$", "", raw).strip()

    result = json.loads(raw)

    picks = result.get("picks", [])

    upside = [p for p in picks if p.get("side") == "upside"][:4]
    downside = [p for p in picks if p.get("side") == "downside"][:4]

    for i, p in enumerate(upside, 1):
        p["rank"] = i

    for i, p in enumerate(downside, 1):
        p["rank"] = i

    result["picks"] = upside + downside

    return result

def fallback_picks(candidates):
    upside = sorted(candidates, key=lambda x: x["bullishRaw"], reverse=True)[:4]
    downside = sorted(candidates, key=lambda x: x["bearishRaw"], reverse=True)[:4]

    picks = []

    for i, c in enumerate(upside, 1):
        picks.append({
            "side": "upside",
            "rank": i,
            "ticker": c["ticker"],
            "name": c["ticker"],
            "cap": "Mid/Large",
            "premarketMove": c["premarketMove"],
            "probabilityScore": min(95, int(65 + c["bullishRaw"])),
            "conviction": "High",
            "catalyst": "Selected from broad premarket/news/volume screen.",
            "analyst": "Analyst signal unavailable; news proxy used.",
            "social": "Public sentiment proxy based on recent news tone.",
            "options": "Volume proxy used.",
            "macro": "Selected based on sector/news alignment.",
            "view": "Momentum and catalyst stack point to possible upside.",
            "risk": "Signal may fade after market open."
        })

    for i, c in enumerate(downside, 1):
        picks.append({
            "side": "downside",
            "rank": i,
            "ticker": c["ticker"],
            "name": c["ticker"],
            "cap": "Mid/Large",
            "premarketMove": c["premarketMove"],
            "probabilityScore": min(95, int(65 + c["bearishRaw"])),
            "conviction": "High",
            "catalyst": "Selected from broad premarket/news/volume screen.",
            "analyst": "Analyst signal unavailable; news proxy used.",
            "social": "Public sentiment proxy based on recent news tone.",
            "options": "Volume proxy used.",
            "macro": "Selected based on sector/news alignment.",
            "view": "Catalyst stack points to possible downside.",
            "risk": "Short-covering or positive headline."
        })

    return {
        "marketRegime": "Automated broad-market screen",
        "marketOverview": "Fallback model used because AI scoring failed.",
        "picks": picks
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
    if False:
        print("Not 15:00 Amsterdam time. Exiting.")
        return

    if not is_us_market_open_today():
        print("US market closed today. No report generated.")
        return

    existing_report = load_existing_report()
    trading_days = get_last_trading_days()

    history = update_history(existing_report, trading_days)

    candidates = build_candidates()

    try:
        ai_result = ask_openai_for_picks(candidates, existing_report)
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
