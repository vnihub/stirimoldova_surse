# collectors.py – fetch recent RSS items (≤24 h), deduplicate by topic
# per-day, summarise, plus weather helper.

import os, re, time, asyncio, aiohttp, feedparser
from datetime import datetime as dt, date, timedelta               # ← added timedelta
from zoneinfo import ZoneInfo
from summariser import summarise_article

# ───────────────────────────── constants ─────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 CityBot/0.1"
    )
}

OWM_KEY = os.getenv("WEATHER_KEY")

# ─────────────────────────── in-memory caches ────────────────────────
SEEN_IDS:     dict[str, set[str]] = {}   # city → {entry-uid}
TOPICS_SEEN:  dict[str, set[str]] = {}   # city → {topic keys}
CACHE_DAY:    dict[str, date]      = {}  # city → date when caches were reset

# ──────────────────────────── helpers ───────────────────────────────
def _reset_daily_caches(city: str, today: date) -> None:
    """Flush per-city caches if the calendar day has changed."""
    if CACHE_DAY.get(city) != today:
        SEEN_IDS.pop(city,  None)
        TOPICS_SEEN.pop(city, None)
        CACHE_DAY[city] = today


def _is_recent(entry, tz: ZoneInfo, hours: int = 24) -> bool:
    """
    True ⇢ entry published/updated within the last `hours` in the city TZ.
    Undated items are skipped (too risky).
    """
    tm = entry.get("published_parsed") or entry.get("updated_parsed")
    if not tm:
        return False
    entry_dt = dt.fromtimestamp(time.mktime(tm), tz)
    return (dt.now(tz) - entry_dt) <= timedelta(hours=hours)


_topic_re = re.compile(r"[^\w\s]", re.UNICODE)  # strip punctuation

def _topic_key(entry) -> str:
    """Topic fingerprint: first 8 lowercase words of the headline."""
    title = entry.get("title", "")
    words = _topic_re.sub("", title.lower()).split()[:8]
    return " ".join(words)


async def fetch_feed(url: str) -> list[feedparser.FeedParserDict]:
    async with aiohttp.ClientSession(headers=HEADERS) as sess:
        async with sess.get(url, timeout=15) as resp:
            raw = await resp.read()
    return feedparser.parse(raw).entries


# ─────────────────────── core: latest items per city ─────────────────
async def get_latest_items(city_key: str, cfg: dict, limit: int = 5) -> list[str]:
    """Return ≤ `limit` summaries of recent (≤24 h) unique news items."""
    tz    = ZoneInfo(cfg.get("tz", "UTC"))
    today = dt.now(tz).date()
    _reset_daily_caches(city_key, today)

    # 1️⃣ fetch feeds & keep only recent items
    tasks = [fetch_feed(u) for u in cfg.get("feeds", [])]
    all_entries: list = []
    for coro in asyncio.as_completed(tasks):
        all_entries.extend(e for e in await coro if _is_recent(e, tz))

    # 2️⃣ newest → oldest; tolerate missing dates (already filtered)
    all_entries.sort(
        key=lambda e: e.get("published_parsed") or time.gmtime(0),
        reverse=True,
    )

    # 3️⃣ deduplicate by UID *and* by topic
    fresh, ids_seen, topics_seen = [], SEEN_IDS.setdefault(city_key, set()), TOPICS_SEEN.setdefault(city_key, set())

    for e in all_entries:
        uid   = e.get("id") or e.get("link")
        topic = _topic_key(e)
        if (uid and uid in ids_seen) or topic in topics_seen:
            continue
        fresh.append(e)
        if uid:
            ids_seen.add(uid)
        topics_seen.add(topic)
        if len(fresh) >= limit:
            break

    # 4️⃣ summarise
    lang = str(cfg.get("lang", "en"))
    return [await summarise_article(e, lang) for e in fresh]


# ───────────────────────── weather extra line ───────────────────────
async def get_extras(city_key: str, cfg: dict) -> str:
    """Return weather line with emoji + sunrise/sunset, localised."""
    if not (OWM_KEY and cfg.get("lat") and cfg.get("lon")):
        return ""

    lang   = cfg.get("lang", "en")
    use_f  = cfg.get("tz", "").startswith("America/") and lang == "en"
    units, sym = ("imperial", "°F") if use_f else ("metric", "°C")

    url = (
        "https://api.openweathermap.org/data/2.5/weather?"
        f"lat={cfg['lat']}&lon={cfg['lon']}&units={units}"
        f"&lang={lang}&appid={OWM_KEY}"
    )

    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, timeout=10) as r:
                data = await r.json()
    except Exception:
        return ""

    try:
        tz      = ZoneInfo(cfg.get("tz", "UTC"))
        temp    = round(data["main"]["temp"])
        descr   = data["weather"][0]["description"].capitalize()
        low     = descr.lower()

        if any(k in low for k in ("sol", "sun", "sonne", "soleil")):            emoji = "☀️"
        elif any(k in low for k in ("lluvia", "rain", "regen", "pluie")):       emoji = "🌧"
        elif any(k in low for k in ("nieve", "snow", "schnee", "neige")):       emoji = "❄️"
        else:                                                                   emoji = "☁️"

        sunrise = dt.fromtimestamp(data["sys"]["sunrise"], tz).strftime("%H:%M")
        sunset  = dt.fromtimestamp(data["sys"]["sunset"],  tz).strftime("%H:%M")

        return f"{emoji} {temp} {sym}, {descr} • ☀ {sunrise} • 🌇 {sunset}"
    except Exception:
        return ""