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
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "AVGO", "TSLA", "BRK.B",
    "LLY", "JPM", "V", "UNH", "XOM", "MA", "COST", "HD", "PG", "JNJ", "ABBV", "NFLX",
    "CRM", "BAC", "ORCL", "AMD", "KO", "PEP", "WMT", "MRK", "CVX", "ADBE", "CSCO",
    "QCOM", "TMO", "MCD", "GE", "ABT", "AMAT", "TXN", "INTU", "IBM", "CAT", "VZ",
    "NOW", "BKNG", "GS", "ISRG", "SPGI", "RTX", "AXP", "PFE", "UBER", "LOW", "NEE",
    "HON", "PGR", "SYK", "BLK", "TJX", "ETN", "VRTX", "LRCX", "PANW", "C", "DE",
    "ADP", "MDT", "REGN", "ADI", "MMC", "CB", "KLAC", "SCHW", "PLTR", "MU", "BSX",
    "AMGN", "GILD", "INTC", "SO", "UPS", "COP", "NKE", "BA", "SBUX", "ELV", "FI",
    "SHOP", "ANET", "MELI", "SNOW", "CRWD", "NET", "DDOG", "TEAM", "MDB", "ZS",
    "OKTA", "HUBS", "WDAY", "ROKU", "COIN", "RBLX", "DKNG", "RIVN", "LCID", "U",
    "SQ", "PYPL", "AFRM", "HOOD", "SOFI", "ON", "SMCI", "DELL", "HPE", "HPQ",
    "F", "GM", "STLA", "NIO", "LI", "XPEV", "ENPH", "SEDG", "FSLR", "RUN",
    "CCL", "RCL", "NCLH", "DAL", "UAL", "AAL", "LUV", "MAR", "HLT", "ABNB",
    "DIS", "PARA", "WBD", "CMCSA", "TMUS", "T", "VZ", "CHTR",
    "MS", "WFC", "USB", "PNC", "TFC", "BK", "COF",
    "LULU", "TGT", "DG", "DLTR", "CROX", "EL", "ULTA", "BBY",
    "TSM", "ASML", "ARM", "MRVL", "MPWR", "MCHP", "NXPI", "SWKS",
    "BIIB", "MRNA", "BNTX", "HUM", "CI", "CVS", "HCA",
    "GEV", "CEG", "NRG", "DUK", "AEP", "EXC", "XEL",
    "FCX", "NEM", "AA", "CLF", "X", "NUE", "STLD",
    "OXY", "SLB", "HAL", "BKR", "EOG", "DVN", "MPC", "VLO"
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
    start = (today - timedelta(days=21)).isoformat()
    end = today.isoformat()
    url = f"{ALPACA_TRADING_BASE}/v2/calendar"
    data = alpaca_get(url, {"start": start, "end": end})
    days = [d["date"] for d in data]
    return days[-count:]


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
        print(f"Daily bar failed for {symbol} on {date}: {e}")
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
    query = (
        f'({symbol} OR "{symbol} stock") AND '
        '(earnings OR guidance OR upgrade OR downgrade OR analyst OR revenue OR profit OR lawsuit OR FDA OR merger OR acquisition OR demand OR margin OR AI OR chip OR cloud OR sales OR investigation OR approval OR forecast OR outlook)'
    )
    from_date = (datetime.now(timezone.utc) - timedelta(days=3)).date().isoformat()
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
    except Exception as e:
        print(f"News failed for {symbol}: {e}")
        return []


def keyword_score(text):
    bullish_words = [
        "upgrade", "beats", "beat", "raises", "raised", "strong", "surge", "rally",
        "record", "growth", "approval", "contract", "partnership", "buyback",
        "outperform", "positive", "demand", "ai", "accelerates", "guidance raise",
        "higher forecast", "profit jumps", "revenue growth", "price target raised"
    ]
    bearish_words = [
        "downgrade", "miss", "misses", "cuts", "cut", "weak", "falls", "slump",
        "lawsuit", "probe", "investigation", "warning", "guidance cut", "lower forecast",
        "underperform", "negative", "recall", "delay", "margin pressure", "profit falls",
        "revenue decline", "price target cut"
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
        daily = snap.get("dailyBar") or {}
        prev = snap.get("prevDailyBar") or {}

        latest_price = latest.get("p")
        daily_open = daily.get("o")
        prev_close = prev.get("c")
        volume = daily.get("v") or 0
        prev_volume = prev.get("v") or 0

        if not latest_price or not daily_open or not prev_close:
            continue

        premarket_move = ((latest_price - prev_close) / prev_close) * 100
        intraday_move_from_open = ((latest_price - daily_open) / daily_open) * 100 if daily_open else 0
        relative_volume = volume / prev_volume if prev_volume else 1

        news = fetch_news_for_symbol(symbol)
        news_text = " ".join([n["title"] + " " + n["description"] for n in news])
        bull_words, bear_words = keyword_score(news_text)

        news_count = len(news)
        catalyst_score = min(25, news_count * 4 + max(bull_words, bear_words) * 2)
        volume_score = min(10, max(0, math.log10(max(volume, 1)) * 1.2))
        rel_volume_score = min(10, max(0, relative_volume * 3))
        movement_score = min(10, abs(premarket_move) * 1.2 + abs(intraday_move_from_open) * 0.8)

        bullish_raw = catalyst_score + volume_score + rel_volume_score + movement_score + bull_words * 2 - bear_words
        bearish_raw = catalyst_score + volume_score + rel_volume_score + movement_score + bear_words * 2 - bull_words

        candidates.append({
            "ticker": symbol,
            "premarketMoveRaw": premarket_move,
            "premarketMove": f"{premarket_move:+.2f}%",
            "latestPrice": latest_price,
            "prevClose": prev_close,
            "dailyOpen": daily_open,
            "volume": volume,
            "relativeVolume": round(relative_volume, 2),
            "news": news,
            "newsText": news_text[:2500],
            "bullishRaw": round(max(0, bullish_raw), 2),
            "bearishRaw": round(max(0, bearish_raw), 2)
        })

    candidates = sorted(candidates, key=lambda x: max(x["bullishRaw"], x["bearishRaw"]), reverse=True)
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
    return sorted(tickers)


def ask_openai_for_picks(candidates, existing_report):
    recent_tickers = get_recent_tickers(existing_report)

    upside_candidates = sorted(candidates, key=lambda x: x["bullishRaw"], reverse=True)[:20]
    downside_candidates = sorted(candidates, key=lambda x: x["bearishRaw"], reverse=True)[:20]

    def compact(c):
        return {
            "ticker": c["ticker"],
            "premarketMove": c["premarketMove"],
            "volume": c["volume"],
            "relativeVolume": c.get("relativeVolume"),
            "bullishRaw": c["bullishRaw"],
            "bearishRaw": c["bearishRaw"],
            "news": c["news"][:3]
        }

    prompt = f"""
You are selecting intraday U.S. stock movement candidates.

Goal:
Choose exactly 8 liquid U.S. mid-cap, large-cap, or mega-cap stocks for today's regular trading session:
- 4 upside candidates
- 4 downside candidates

Important rules:
- Do NOT choose the same stock for both upside and downside.
- Do NOT simply pick the biggest premarket movers.
- Do NOT repeatedly default to the same mega-cap stocks unless today's catalyst clearly justifies it.
- Avoid repeating these recent tickers unless their current catalyst is genuinely strong: {recent_tickers}
- Prefer stocks with fresh, specific catalysts and enough liquidity.
- Penalize vague, stale, or generic news.
- Penalize stocks that only moved premarket with no clear catalyst.
- Select names most likely to continue moving during the regular session.

Use this weighted model:
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
            {"role": "system", "content": "Return only valid JSON. No markdown. Pick exactly 4 upside and 4 downside stocks. Never duplicate tickers."},
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

    candidate_by_ticker = {c["ticker"]: c for c in candidates}

    for p in picks:
        ticker = str(p.get("ticker", "")).upper().strip()
        side = str(p.get("side", "")).lower().strip()
        if not ticker or not side:
            continue
        if ticker in seen:
            continue
        if side not in ["upside", "downside"]:
            continue
        if ticker not in candidate_by_ticker:
            continue

        c = candidate_by_ticker[ticker]
        p["ticker"] = ticker
        p["side"] = side
        p["premarketMove"] = c.get("premarketMove", p.get("premarketMove", ""))
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

    upside = sorted(candidates, key=lambda x: x["bullishRaw"], reverse=True)
    for c in upside:
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
            "name": c["ticker"],
            "cap": "Mid/Large",
            "premarketMove": c["premarketMove"],
            "probabilityScore": min(95, int(65 + c["bullishRaw"])),
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
        if c["premarketMoveRaw"] > 8:
            continue
        used.add(c["ticker"])
        picks.append({
            "side": "downside",
            "rank": len([p for p in picks if p["side"] == "downside"]) + 1,
            "ticker": c["ticker"],
            "name": c["ticker"],
            "cap": "Mid/Large",
            "premarketMove": c["premarketMove"],
            "probabilityScore": min(95, int(65 + c["bearishRaw"])),
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
        "marketOverview": "OpenAI scoring failed, so unique quantitative picks were selected using news, volume and premarket signals.",
        "picks": picks[:8]
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
    # Keep this as False while testing manually. For production, replace this block with:
    # if now_amsterdam().hour != 15:
    #     print("Not 15:00 Amsterdam time. Exiting.")
    #     return
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
    if not candidates:
        raise RuntimeError("No candidates were built. Check Alpaca data access and universe symbols.")

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
