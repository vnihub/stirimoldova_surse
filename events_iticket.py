import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
from composer import BOT, _chat_id
from utils import tiny
import logging

# ✅ Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

CITY_KEY = "chisinau"
CATEGORY_URLS = [
    "https://iticket.md/events/iticket",
    "https://iticket.md/events/concert",
    "https://iticket.md/events/teatru",
    "https://iticket.md/events/festival",
    "https://iticket.md/events/divers",
    "https://iticket.md/events/copii",
]

tz = ZoneInfo("Europe/Chisinau")

def extract_event_cards(html):
    soup = BeautifulSoup(html, "html.parser")
    return soup.select(".event-card")

def extract_event_data(card):
    try:
        link_tag = card.find("a", href=True)
        url = link_tag["href"]
        title = card.select_one(".e-c-name").get_text(strip=True)
        date = card.select_one(".e-c-time span").get_text(strip=True)
        month = card.select_one(".e-c-month").get_text(strip=True)
        venue = card.select_one(".e-c-location-title").get_text(strip=True)
        return {"url": url, "title": title, "date": date, "month": month, "venue": venue}
    except Exception as e:
        logging.warning(f"❌ Failed to extract event data: {e}")
        return None

def match_today(event):
    try:
        today = datetime.now(tz)
        expected_day = str(today.day)
        expected_month_prefix = today.strftime("%b").lower()

        actual_day = event["date"].strip()
        actual_month = event["month"].strip().lower()

        logging.info(
            f"🧪 Comparing: actual='{actual_day} {actual_month}' vs expected='{expected_day} {expected_month_prefix}'"
        )

        return actual_day == expected_day and actual_month.startswith(expected_month_prefix)
    except Exception as e:
        logging.warning(f"❌ Failed to match date for event: {e}")
        return False

async def fetch_events_from_url(session, url):
    logging.info(f"🌐 Fetching events from: {url}")
    try:
        async with session.get(url, timeout=10) as resp:
            html = await resp.text()
            cards = extract_event_cards(html)
            logging.info(f"🧩 Found {len(cards)} event cards at {url}")
            return [e for card in cards if (e := extract_event_data(card))]
    except Exception as e:
        logging.error(f"❌ Error fetching events from {url}: {e}")
        return []

async def events_iticket_job():
    async with aiohttp.ClientSession() as session:
        all_events = []
        for url in CATEGORY_URLS:
            events = await fetch_events_from_url(session, url)
            all_events.extend(events)

    logging.info(f"📦 Total events scraped: {len(all_events)}")

    seen = set()
    today_events = []
    for e in all_events:
        if not match_today(e):
            continue
        key = (e["title"], e["url"])
        if key in seen:
            continue
        seen.add(key)
        short_url = await tiny(e["url"])
        line = f"🎫 <b>{e['title']}</b> – {e['venue']} → <a href='{short_url}'>link</a>"
        today_events.append(line)
        logging.info(f"✅ Event matched: {e['title']} @ {e['venue']}")

    if not today_events:
        logging.info("ℹ️ No events found for today – skipping events post.")
        return

    chat = _chat_id(CITY_KEY)
    if not chat:
        logging.warning("❌ No chat ID found for city")
        return

    header = "🎭 <b>Evenimente astăzi</b>\n\n"
    body = "\n\n".join(today_events)
    footer = "\n\n🔁 Trimite prietenilor care ar vrea să iasă în oraș!"
    text = header + body + footer

    await BOT.send_message(
        chat_id=int(chat) if chat.lstrip("-").isdigit() else chat,
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=False,
    )

    logging.info(f"📨 Events post sent with {len(today_events)} items.")