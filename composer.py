# composer.py – build the Telegram post and send it
import os
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing in .env")
BOT = Bot(BOT_TOKEN)

# ---------------------------------------------------------------- i18n
LOCAL_HEADERS = {
    "en": "Now", "es": "Ahora", "de": "Jetzt", "fr": "Maintenant",
    "ro": "Acum", "ja": "今", "no": "Nå", "pt": "Agora",
    "tr": "Şimdi", "bn": "এখন", "it": "Ora",
}
LOCAL_CTA_TEXT = {
    "en": "Subscribe. Daily news!",
    "es": "¡Suscríbete. Noticias diarias!",
    "de": "Abonniere. Tägliche Neuigkeiten!",
    "fr": "Abonnez-vous. Infos quotidiennes!",
    "ro": "Abonează-te. Noutăți zilnice!",
    "ja": "購読. 毎日ニュース！",
    "no": "Abonner. Daglige nyheter!",
    "pt": "Inscreva-se. Notícias diárias!",
    "tr": "Abone ol. Günlük haberler!",
    "bn": "সাবস্ক্রাইব করুন. দৈনিক খবর!",
    "it": "Iscriviti. Notizie quotidiane!",
}

# ------------------------------------------------ helpers
def _chat_id(city_key: str) -> str | None:
    numeric = os.getenv(f"CHAT_{city_key.upper()}")
    if numeric:
        return numeric
    username = os.getenv(f"CHAT_{city_key.upper()}_USERNAME")
    if username:
        return username if username.startswith("@") else "@" + username
    return None

def _display_city(city_key: str) -> str:
    from config import CONFIG
    cfg = CONFIG.get(city_key, {})
    return cfg.get("city_local") or cfg.get("city") or city_key.replace("_", " ").title()

# ------------------------------------------------ main API
async def compose_and_send(city_key: str,
                           news_lines: list[str],
                           extras: str | None = ""):
    # 0️⃣  skip sending if there are no fresh headlines
    if not news_lines:
        print(f"ℹ️  No fresh headlines for {city_key} – post skipped.")
        return

    chat = _chat_id(city_key)
    if not chat:
        return  # channel not configured

    from config import CONFIG
    lang  = str(CONFIG.get(city_key, {}).get("lang", "en")).lower()
    label = LOCAL_HEADERS.get(lang, "Now")

    # CTA link
    if chat.startswith("@"):
        subscribe_link = f"https://t.me/{chat.lstrip('@')}"
        cta = f'🔔 <a href="{subscribe_link}">{LOCAL_CTA_TEXT.get(lang, LOCAL_CTA_TEXT["en"])}</a> 👈'
    else:
        cta = f'🔔 {LOCAL_CTA_TEXT.get(lang, LOCAL_CTA_TEXT["en"])} 👈'

    header = f'📰 <b>{_display_city(city_key)} {label}</b>\n\n'
    body = "\n\n".join(line for line in news_lines if line)
    text   = header + body + (f"\n\n{extras}" if extras else "") + f"\n\n{cta}"

    await BOT.send_message(
        chat_id=int(chat) if chat.lstrip("-").isdigit() else chat,
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=False,
    )

async def compose_events_and_send(city_key: str, events: list[dict]):
    """Builds and sends a Telegram post for iTicket events."""
    if not events:
        print(f"ℹ️  No events for {city_key} – post skipped.")
        return

    chat = _chat_id(city_key)
    if not chat:
        return

    from config import CONFIG
    lang = str(CONFIG.get(city_key, {}).get("lang", "ro")).lower()
    
    # Header
    header = f"🗓️ <b>Evenimente Azi în {_display_city(city_key)}</b>\n\n"

    # Event lines
    event_lines = []
    for event in events:
        title = event.get('title', 'N/A')
        location = event.get('location', 'N/A')
        url = event.get('event_url', '#')
        price = event.get('price', 'N/A')

        # Format the price to be bold
        if price != 'N/A':
            price_text = f" • <b>{price}</b>"
        else:
            price_text = ""

        event_lines.append(
            f"📍 {title}\n"
            f"🏢 {location}{price_text}\n"
            f'<a href="{url}">Bilete</a>'
        )
    
    body = "\n\n".join(event_lines)

    # CTA link
    if chat.startswith("@"):
        subscribe_link = f"https://t.me/{chat.lstrip('@')}"
        cta = f'\n\n🔔 <a href="{subscribe_link}">{LOCAL_CTA_TEXT.get(lang, LOCAL_CTA_TEXT["en"])}</a> 👈'
    else:
        cta = f'\n\n🔔 {LOCAL_CTA_TEXT.get(lang, LOCAL_CTA_TEXT["en"])} 👈'

    text = header + body + cta

    # For events, let's send with photo if available, otherwise just text
    photo_url = events[0].get('image_url') if events else None

    if photo_url and photo_url != "N/A":
        try:
            await BOT.send_photo(
                chat_id=int(chat) if chat.lstrip("-").isdigit() else chat,
                photo=photo_url,
                caption=text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"❌ Failed to send photo for event, sending text instead. Error: {e}")
            await BOT.send_message(
                chat_id=int(chat) if chat.lstrip("-").isdigit() else chat,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=False
            )
    else:
        await BOT.send_message(
            chat_id=int(chat) if chat.lstrip("-").isdigit() else chat,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=False
        )
