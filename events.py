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

LANG_TEXTS = {
    "en": {
        "title": "🎟️ Events in {city} Today",
        "cta":   "💬 Know someone in {city}? Forward this post now!",
    },
    "es": {
        "title": "🎟️ Eventos en {city} Hoy",
        "cta":   "💬 ¿Conoces a alguien en {city}? ¡Comparte este post ahora!",
    },
    "ja": {
        "title": "🎟️ {city} の今日のイベント",
        "cta":   "💬 {city} にいる人にこの投稿を共有してください！",
    },
    "de": {
        "title": "🎟️ Veranstaltungen in {city} heute",
        "cta":   "💬 Kennst du jemanden in {city}? Teile diesen Beitrag jetzt!",
    },
    "fr": {
        "title": "🎟️ Événements à {city} aujourd'hui",
        "cta":   "💬 Connais-tu quelqu'un à {city} ? Partage ce post maintenant !",
    },
    "ro": {
        "title": "🎟️ Evenimente în {city} astăzi",
        "cta":   "💬 Cunoști pe cineva în {city}? Distribuie această postare acum!",
    },
    "no": {
        "title": "🎟️ Arrangementer i {city} i dag",
        "cta":   "💬 Kjenner du noen i {city}? Del dette innlegget nå!",
    },
    "pt": {
        "title": "🎟️ Eventos em {city} hoje",
        "cta":   "💬 Conhece alguém em {city}? Compartilhe esta publicação agora!",
    },
}

# keywords to filter “evergreen” tour / demo items
FILTER_KEYWORDS = {
    "tour experience", "tour", "exhibition", "guided tour",
    "daily tour", "demo",
}


def _event_url(city: str, key: str, tz: str) -> str:
    """Return a Ticketmaster Discovery-API URL for *today* (00:00 local)."""
    start_local = dt.now(ZoneInfo(tz)).replace(hour=0, minute=0,
                                              second=0, microsecond=0)
    start_iso   = start_local.astimezone(ZoneInfo("UTC")).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return TM_URL.format(city=quote_plus(city), key=key, start=start_iso)


async def compose_events_and_send(city_key: str):
    # ── pull config + chat/channel reference ───────────────────────────
    from config import CONFIG                         # avoid circular import
    cfg     = CONFIG[city_key]
    chat_id = _chat_id(city_key)

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

    # ── fetch events from Ticketmaster ────────────────────────────────
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

    lang  = cfg.get("lang", "en")
    texts = LANG_TEXTS.get(lang, LANG_TEXTS["en"])
    lines = [f"<b>{texts['title'].format(city=cfg['city'])}</b>\n"]

    # ── build list, skipping tours & badly-formed items ───────────────
    for ev in events:
        name_low = ev["name"].lower()

        # 1) filter “evergreen” tour-like items
        if any(k in name_low for k in FILTER_KEYWORDS):
            print(f"⏭ Skipping repetitive event: {ev['name']}")
            continue
        # 2) keep only real events (Ticketmaster also has e.g. venues)
        if ev.get("type") != "event":
            print(f"⏭ Skipping non-event type: {ev.get('type')}")
            continue

        # 3) robust venue extraction
        try:
            venue = ev["_embedded"]["venues"][0]["name"]
        except (KeyError, IndexError, TypeError):
            print(f"⏭ Skipping event with missing venue: {ev.get('name')}")
            continue

        # remaining details
        time  = ev["dates"]["start"].get("localTime", "")[:5]
        link  = ev.get("url", "")
        cat   = ev.get("classifications", [{}])[0] \
                    .get("segment", {}).get("name", "").lower()

        emoji = (
            "🎵" if "music"  in cat else
            "🎭" if "arts"   in cat else
            "🏟" if "sports" in cat else
            "🎪" if "family" in cat else
            "🎬" if "film"   in cat else
            "🎉"
        )

        lines.append(f"{emoji} {ev['name']} – {venue}, {time} → "
                     f'<a href="{link}">link</a>')

    # nothing survived filtering?
    if len(lines) == 1:
        print("⚠ No valid events after filtering, skipping post.")
        return

    lines.append(f"\n{texts['cta'].format(city=cfg['city'])}")
    message = "\n\n".join(lines)

    print("✅ Sending to Telegram…")
    await BOT.send_message(
        chat_id=int(chat_id) if chat_id.isdigit() else chat_id,
        text=message,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )