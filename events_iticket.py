import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
from composer import BOT, _chat_id
from utils import tiny
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

CITY_KEY = "chisinau"
CATEGORY_URLS = [
    "https://iticket.md/events/iticket",
    "https://iticket.md/events/concert",
    "https://iticket.md/events/teatru",
    "https://iticket.md/events/festival",
    "https://iticket.md/events/divers",
    "https://iticket.md/events/copii",
    "https://iticket.md/events/standup",
    "https://iticket.md/events/concert",
]
TRAINING_URL = "https://iticket.md/events/training"

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
    except Exception:
        return None

def match_today(event):
    ro_to_en_months = {
        "ian.": "jan", "feb.": "feb", "mar.": "mar", "apr.": "apr", "mai.": "may",
        "iun.": "jun", "iul.": "jul", "aug.": "aug", "sep.": "sep",
        "oct.": "oct", "noi.": "nov", "dec.": "dec"
    }
    today = datetime.now(tz)
    expected_day = str(today.day)
    expected_month = today.strftime("%b").lower()
    actual_day = event["date"].strip()
    actual_month_ro = event["month"].strip().lower()
    translated_month = ro_to_en_months.get(actual_month_ro, "")
    return actual_day == expected_day and translated_month == expected_month

async def fetch_events_from_url(session, url):
    try:
        async with session.get(url, timeout=10) as resp:
            html = await resp.text()
            cards = extract_event_cards(html)
            return [e for card in cards if (e := extract_event_data(card))]
    except:
        return []

async def events_iticket_job():
    async with aiohttp.ClientSession() as session:
        all_events = []
        for url in CATEGORY_URLS:
            events = await fetch_events_from_url(session, url)
            all_events.extend(events)
        
        # also fetch training events for filtering
        training_events = await fetch_events_from_url(session, TRAINING_URL)
        training_blacklist = {(e['title'], e['url']) for e in training_events}

    seen = set()
    today_events = []
    for e in all_events:
        if (e["title"], e["url"]) in training_blacklist:
            continue
        if not match_today(e):
            continue
        key = (e["title"], e["url"])
        if key in seen:
            continue
        seen.add(key)
        short_url = await tiny(e["url"])
        line = f"🎫 {e['title']} – {e['venue']} → <a href='{short_url}'>link</a>"
        today_events.append(line)

    if not today_events:
        return

    chat = _chat_id(CITY_KEY)
    if not chat:
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