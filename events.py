# events.py – fetch and post daily events via Ticketmaster

import os, aiohttp
from datetime import datetime as dt
from zoneinfo import ZoneInfo
from urllib.parse import quote_plus
from composer import BOT, _chat_id

TM_KEY = os.getenv("TICKETMASTER_KEY")

TM_URL = (
    "https://app.ticketmaster.com/discovery/v2/events.json?"
    "city={city}&size=7&sort=date,asc&apikey={key}&startDateTime={start}"
)

def _event_url(city: str, key: str, tz: str) -> str:
    now = dt.now(ZoneInfo(tz)).replace(hour=0, minute=0, second=0, microsecond=0)
    iso = now.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
    city_encoded = quote_plus(city)
    return TM_URL.format(city=city_encoded, key=key, start=iso)


async def compose_events_and_send(city_key: str):
    from config import CONFIG  # local import to avoid circular dependency
    cfg = CONFIG[city_key]
    chat_id = _chat_id(city_key)

    # 👇 Diagnostics
    print(f"\n🎟 Posting events for: {city_key}")
    print("Chat ID         :", chat_id)
    print("TM_KEY present? :", bool(TM_KEY))
    print("City in config  :", cfg.get("city"))
    print("Timezone        :", cfg.get("tz"))

    if not chat_id or not TM_KEY or "city" not in cfg:
        print("❌ Missing chat_id, Ticketmaster key, or city name")
        return

    url = _event_url(cfg["city"], TM_KEY, cfg.get("tz", "UTC"))
    print("Ticketmaster URL:", url)

    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, timeout=10) as r:
                data = await r.json()
    except Exception as e:
        print("❌ Request failed:", e)
        return

    events = data.get("_embedded", {}).get("events", [])
    print("Found events    :", len(events))

    if not events:
        print("⚠ No events found for today.")
        return

    lines = [f"<b>🎟️ Events in {cfg['city']} Today</b>\n"]
    for e in events:
        name = e["name"]
        time = e["dates"]["start"].get("localTime", "")[:5]
        venue = e["_embedded"]["venues"][0]["name"]
        link = e.get("url", "")
        
        cat = e.get("classifications", [{}])[0].get("segment", {}).get("name", "").lower()
        emoji = (
            "🎵" if "music" in cat else
            "🎭" if "arts" in cat else
            "🏟" if "sports" in cat else
            "🎪" if "family" in cat else
            "🎬" if "film" in cat else
            "🎉"
        )

        lines.append(f"{emoji} {name} – {venue}, {time} → <a href=\"{link}\">link</a>")

    # ➕ Add CTA to share
    lines.append(f"\n💬 Know someone in {cfg['city']}? Forward this post now!")

    msg = "\n\n".join(lines)

    print("✅ Sending to Telegram…\n")
    await BOT.send_message(
        chat_id=chat_id,
        text=msg,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )