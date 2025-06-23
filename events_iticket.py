import datetime
import pytz
from playwright.async_api import async_playwright
from composer import send_telegram_message

CITY = "moldova"
CHANNEL = "@stirimoldova_surse"  # Adjust if needed

async def fetch_today_events():
    today_str = datetime.datetime.now(pytz.timezone("Europe/Chisinau")).strftime("%Y-%m-%d")
    events = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://iticket.md/events", timeout=30000)
        cards = await page.locator(".event-card").all()

        for card in cards:
            try:
                title = await card.locator('[itemprop="name"]').get_attribute("content")
                date = await card.locator('[itemprop="startDate"]').get_attribute("content")
                url = await card.locator("a").get_attribute("href")

                if date and date.startswith(today_str):
                    time = date[11:16] if "T" in date else ""
                    events.append(f"🎟️ <b>{title.strip()}</b>\n🕒 {time} | <a href=\"{url}\">Vezi detalii</a>")
            except Exception:
                continue

        await browser.close()

    return events

async def events_iticket_job():
    events = await fetch_today_events()
    if not events:
        message = "📅 Astăzi nu sunt evenimente în Chișinău."
    else:
        message = "<b>📍 Evenimente azi în Chișinău:</b>\n\n" + "\n\n".join(events)

    await send_telegram_message(CHANNEL, message)