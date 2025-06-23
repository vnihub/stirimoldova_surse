# events_iticket.py – fetch and post today’s events from iTicket

import datetime
import pytz
import aiohttp
from bs4 import BeautifulSoup
from composer import compose_and_send  # ✅ fixed import

URL = "https://iticket.md/events"
CHANNEL = "chisinau"

async def fetch_today_iticket_events() -> list[str]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(URL, timeout=20) as resp:
                html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        today = datetime.datetime.now(pytz.timezone("Europe/Chisinau")).day
        entries = []

        for card in soup.select(".event-card"):
            date_block = card.select_one(".e-c-time span")
            title = card.select_one(".e-c-name")
            link = card.select_one("a[href]")
            if not (date_block and title and link):
                continue

            try:
                event_day = int(date_block.text.strip())
                if event_day != today:
                    continue
            except ValueError:
                continue

            href = link["href"]
            full_url = f"https://iticket.md{href}" if href.startswith("/") else href
            entries.append(f"🎫 <b>{title.text.strip()}</b>\n{full_url}")

        return entries

    except Exception as e:
        print(f"❌ Error fetching iTicket events: {e}")
        return []

async def events_iticket_job():
    events = await fetch_today_iticket_events()
    if events:
        await compose_and_send(CHANNEL, events)