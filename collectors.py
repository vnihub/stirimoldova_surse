import os, re, time, asyncio, aiohttp, feedparser
from datetime import datetime as dt, timedelta
from zoneinfo import ZoneInfo
from summariser import summarise_article
from openai import AsyncOpenAI
from numpy import dot
from numpy.linalg import norm
import numpy as np

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 CityBot/0.1"
    )
}

OWM_KEY = os.getenv("WEATHER_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

SEEN_IDS: dict[str, list[tuple[float, str]]] = {}
TOPICS_SEEN: dict[str, list[tuple[float, list[float]]]] = {}

def _is_recent(entry, tz: ZoneInfo, hours: int = 24) -> bool:
    tm = entry.get("published_parsed") or entry.get("updated_parsed")
    if not tm:
        return False
    entry_dt = dt.fromtimestamp(time.mktime(tm), tz)
    return (dt.now(tz) - entry_dt) <= timedelta(hours=hours)

async def _get_embedding(entry) -> list[float]:
    title = entry.get("title", "")
    summary = entry.get("summary", "")
    content = f"{title}\n{summary}"
    try:
        resp = await client.embeddings.create(
            input=content[:1000],
            model="text-embedding-3-small"
        )
        return resp.data[0].embedding
    except Exception:
        return []

def _cosine_sim(a: list[float], b: list[float]) -> float:
    a, b = np.array(a), np.array(b)
    return dot(a, b) / (norm(a) * norm(b) + 1e-8)

async def fetch_feed(url: str) -> list[feedparser.FeedParserDict]:
    async with aiohttp.ClientSession(headers=HEADERS) as sess:
        async with sess.get(url, timeout=15) as resp:
            raw = await resp.read()
    return feedparser.parse(raw).entries

async def get_latest_items(city_key: str, cfg: dict, limit: int = 7) -> list[str]:
    tz = ZoneInfo(cfg.get("tz", "UTC"))
    now = time.time()
    cutoff = now - 86400

    SEEN_IDS[city_key] = [(ts, uid) for ts, uid in SEEN_IDS.get(city_key, []) if ts >= cutoff]
    TOPICS_SEEN[city_key] = [(ts, emb) for ts, emb in TOPICS_SEEN.get(city_key, []) if ts >= cutoff]

    ids_seen = set(uid for ts, uid in SEEN_IDS[city_key])
    topic_embs = [emb for ts, emb in TOPICS_SEEN[city_key]]

    tasks = [fetch_feed(u) for u in cfg.get("feeds", [])]
    all_entries: list = []
    for coro in asyncio.as_completed(tasks):
        all_entries.extend(e for e in await coro if _is_recent(e, tz))

    all_entries.sort(
        key=lambda e: e.get("published_parsed") or time.gmtime(0),
        reverse=True,
    )

    fresh = []
    for e in all_entries:
        uid = e.get("id") or e.get("link")
        emb = await _get_embedding(e)
        if not emb:
            continue

        is_duplicate = (
            (uid and uid in ids_seen) or
            any(_cosine_sim(emb, seen) >= 0.93 for seen in topic_embs)
        )
        if is_duplicate:
            continue

        fresh.append(e)
        if uid:
            SEEN_IDS[city_key].append((now, uid))
        TOPICS_SEEN[city_key].append((now, emb))
        topic_embs.append(emb)

        if len(fresh) >= limit:
            break

    lang = str(cfg.get("lang", "en"))
    return [await summarise_article(e, lang) for e in fresh]

async def get_extras(city_key: str, cfg: dict) -> str:
    if not (OWM_KEY and cfg.get("lat") and cfg.get("lon")):
        return ""

    lang = cfg.get("lang", "en")
    use_f = cfg.get("tz", "").startswith("America/") and lang == "en"
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
        tz = ZoneInfo(cfg.get("tz", "UTC"))
        temp = round(data["main"]["temp"])
        descr = data["weather"][0]["description"].capitalize()
        low = descr.lower()

        if any(k in low for k in ("sol", "sun", "sonne", "soleil")): emoji = "☀️"
        elif any(k in low for k in ("lluvia", "rain", "regen", "pluie")): emoji = "🌧"
        elif any(k in low for k in ("nieve", "snow", "schnee", "neige")): emoji = "❄️"
        else: emoji = "☁️"

        sunrise = dt.fromtimestamp(data["sys"]["sunrise"], tz).strftime("%H:%M")
        sunset = dt.fromtimestamp(data["sys"]["sunset"], tz).strftime("%H:%M")

        return f"------\n{emoji} {temp} {sym}, {descr}\n☀ {sunrise} • 🌇 {sunset}\n-------"
    except Exception:
        return ""