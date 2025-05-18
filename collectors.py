# collectors.py – robust fetch with browser-like headers + weather + °F + local sunrise/sunset + localized description

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


async def get_latest_items(city_key: str, cfg: dict, limit: int = 3) -> list[str]:
    tasks = [fetch_feed(u) for u in cfg.get("feeds", [])]
    entries: list = []
    for t in asyncio.as_completed(tasks):
        entries.extend(await t)

    entries.sort(key=lambda e: e.get("published_parsed", time.gmtime(0)), reverse=True)

    fresh: list = []
    for e in entries:
        uid = e.get("id") or e.get("link")
        if uid and uid not in SEEN.get(city_key, set()):
            fresh.append(e)
            SEEN.setdefault(city_key, set()).add(uid)
        if len(fresh) == limit:
            break

    summaries: list[str] = []
    for e in fresh:
        summaries.append(await summarise_article(e, cfg["lang"]))
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
        emoji = "☀️" if "sol" in descr.lower() or "sun" in descr.lower() else \
                "🌧" if "lluvia" in descr.lower() or "rain" in descr.lower() else \
                "❄️" if "nieve" in descr.lower() or "snow" in descr.lower() else "☁️"
        sunrise = dt.fromtimestamp(data["sys"]["sunrise"], tz).strftime("%H:%M")
        sunset  = dt.fromtimestamp(data["sys"]["sunset"], tz).strftime("%H:%M")
        return f"{emoji} {temp} {unit_symbol}, {descr} • ☀ {sunrise} • 🌇 {sunset}"
    except Exception:
        return ""