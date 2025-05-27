# collectors.py – fetch today’s RSS items, deduplicate by topic *per day*,
# summarise them, plus weather helper.

import os, re, time, asyncio, aiohttp, feedparser
from datetime import datetime as dt, date
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
SEEN_IDS:     dict[str, set[str]] = {}   # city → set[entry-uid] (for link/GUID dedup)
TOPICS_SEEN:  dict[str, set[str]] = {}   # city → set[topic keys] (cross-feed dedup)
CACHE_DAY:    dict[str, date]      = {}  # city → date when the two sets were last reset


# ──────────────────────────── helpers ───────────────────────────────
def _reset_daily_caches(city: str, today: date) -> None:
    """Flush per-city caches if the day has changed."""
    if CACHE_DAY.get(city) != today:
        SEEN_IDS.pop(city,  None)        # forget yesterday’s IDs
        TOPICS_SEEN.pop(city, None)      # forget yesterday’s topics
        CACHE_DAY[city] = today


def _is_today(entry, tz: ZoneInfo) -> bool:
    """True if entry’s pub/updated date is today *in the city’s TZ*."""
    tm = entry.get("published_parsed") or entry.get("updated_parsed")
    if not tm:                              # keep undated items
        return True
    entry_date = dt.fromtimestamp(time.mktime(tm), tz).date()
    return entry_date == dt.now(tz).date()


_topic_re = re.compile(r"[^\w\s]", re.UNICODE)  # strip punctuation

def _topic_key(entry) -> str:
    """
    Crude topic fingerprint: first 8 lowercase words of the headline,
    punctuation removed. Good enough for same-day dedup.
    """
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
    """Return ≤ `limit` summaries of today’s *unique* news items for one city."""
    tz      = ZoneInfo(cfg.get("tz", "UTC"))
    today   = dt.now(tz).date()
    _reset_daily_caches(city_key, today)

    # 1️⃣ fetch feeds concurrently & keep only today’s items
    tasks = [fetch_feed(u) for u in cfg.get("feeds", [])]
    all_entries: list = []
    for coro in asyncio.as_completed(tasks):
        all_entries.extend(e for e in await coro if _is_today(e, tz))

    # 2️⃣ newest → oldest (missing dates fall back to epoch start)
    all_entries.sort(key=lambda e: e.get("published_parsed") or time.gmtime(0),
                     reverse=True)

    # 3️⃣ deduplicate by UID *and* by topic across all feeds
    fresh          : list = []
    ids_seen       = SEEN_IDS.setdefault(city_key, set())
    topics_seen    = TOPICS_SEEN.setdefault(city_key, set())

    for e in all_entries:
        uid    = e.get("id") or e.get("link")
        topic  = _topic_key(e)

        if (uid and uid in ids_seen) or topic in topics_seen:
            continue

        fresh.append(e)
        if uid:
            ids_seen.add(uid)
        topics_seen.add(topic)

        if len(fresh) >= limit:
            break

    # 4️⃣ summarise
    lang       = str(cfg.get("lang", "en"))
    summaries  = [await summarise_article(e, lang) for e in fresh]
    return summaries


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

        if any(k in low for k in ("sol", "sun", "sonne", "soleil")):   emoji = "☀️"
        elif any(k in low for k in ("lluvia", "rain", "regen", "pluie")): emoji = "🌧"
        elif any(k in low for k in ("nieve", "snow", "schnee", "neige")): emoji = "❄️"
        else:                                                           emoji = "☁️"

        sunrise = dt.fromtimestamp(data["sys"]["sunrise"], tz).strftime("%H:%M")
        sunset  = dt.fromtimestamp(data["sys"]["sunset"],  tz).strftime("%H:%M")

        return f"{emoji} {temp} {sym}, {descr} • ☀ {sunrise} • 🌇 {sunset}"
    except Exception:
        return ""