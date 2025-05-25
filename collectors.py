# collectors.py – robust fetch with browser-like headers + weather + °F + local sunrise/sunset + localized description + improved deduplication

import asyncio, time, aiohttp, feedparser, os
from datetime import datetime as dt
from zoneinfo import ZoneInfo
from summariser import summarise_article

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 CityBot/0.1"
    )
}

SEEN: dict[str, set[str]] = {}

OWM_KEY = os.getenv("WEATHER_KEY")


async def fetch_feed(url: str) -> list[feedparser.FeedParserDict]:
    async with aiohttp.ClientSession(headers=HEADERS) as sess:
        async with sess.get(url, timeout=15) as resp:
            raw = await resp.read()
    return feedparser.parse(raw).entries


async def get_latest_items(city_key: str, cfg: dict, limit: int = 5) -> list[str]:
    # Fetch all feeds concurrently
    tasks = [fetch_feed(u) for u in cfg.get("feeds", [])]
    all_entries = []
    for task in asyncio.as_completed(tasks):
        entries = await task
        all_entries.extend(entries)

    # Sort all entries by published date descending, safely handling None
    def sort_key(e):
        val = e.get("published_parsed")
        return val if val is not None else time.gmtime(0)

    all_entries.sort(key=sort_key, reverse=True)

    # Deduplicate globally by city_key across all feeds
    fresh = []
    seen_ids = SEEN.setdefault(city_key, set())

    for entry in all_entries:
        uid = entry.get("id") or entry.get("link")
        if not uid:
            continue
        if uid in seen_ids:
            continue
        fresh.append(entry)
        seen_ids.add(uid)
        if len(fresh) >= limit:
            break

    # Summarize fresh unique items only, ensure lang is string
    summaries = []
    lang = str(cfg.get("lang", "en"))
    for entry in fresh:
        summaries.append(await summarise_article(entry, lang))

    return summaries


async def get_extras(city_key: str, cfg: dict) -> str:
    """Return weather line in °F for US cities, °C elsewhere, with local sunrise/sunset."""
    if not OWM_KEY or "lat" not in cfg or "lon" not in cfg:
        return ""

    lang = cfg.get("lang", "en")
    use_fahrenheit = cfg.get("tz", "").startswith("America/") and lang == "en"
    units = "imperial" if use_fahrenheit else "metric"
    unit_symbol = "°F" if use_fahrenheit else "°C"

    url = (
        "https://api.openweathermap.org/data/2.5/weather?"
        f"lat={cfg['lat']}&lon={cfg['lon']}&units={units}&lang={lang}&appid={OWM_KEY}"
    )

    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, timeout=10) as resp:
                data = await resp.json()
    except Exception:
        return ""

    try:
        tz = ZoneInfo(cfg.get("tz", "UTC"))
        temp = round(data["main"]["temp"])
        descr = data["weather"][0]["description"].capitalize()
        # Use language aware keyword checks for emojis
        descr_lower = descr.lower()
        if any(k in descr_lower for k in ["sol", "sun", "sonne", "soleil"]):
            emoji = "☀️"
        elif any(k in descr_lower for k in ["lluvia", "rain", "regen", "pluie"]):
            emoji = "🌧"
        elif any(k in descr_lower for k in ["nieve", "snow", "schnee", "neige"]):
            emoji = "❄️"
        else:
            emoji = "☁️"
        sunrise = dt.fromtimestamp(data["sys"]["sunrise"], tz).strftime("%H:%M")
        sunset = dt.fromtimestamp(data["sys"]["sunset"], tz).strftime("%H:%M")
        return f"{emoji} {temp} {unit_symbol}, {descr} • ☀ {sunrise} • 🌇 {sunset}"
    except Exception:
        return ""