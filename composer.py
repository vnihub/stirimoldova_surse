# composer.py – localized title + underscore fix + universal CTA with clickable subscribe link + city_local support

from dotenv import load_dotenv
load_dotenv()  # load .env first

import os
from telegram import Bot

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing in .env")

BOT = Bot(BOT_TOKEN)

# Language-specific word for "Now"
LOCAL_HEADERS = {
    "en": "Now",
    "es": "Ahora",
    "de": "Jetzt",
    "fr": "Maintenant",
    "ro": "Acum",
    "ja": "今",            # Japanese
    "no": "Nå",           # Norwegian Bokmål
    "pt": "Agora",        # Portuguese
    "tr": "Şimdi",        # Turkish
    "bn": "এখন",          # Bengali
    "it": "Ora",          # Italian
}

LOCAL_CTA_TEXT = {
    "en": "Subscribe for daily news!",
    "es": "¡Suscríbete para noticias diarias!",
    "de": "Abonniere für tägliche Neuigkeiten!",
    "fr": "Abonnez-vous aux infos quotidiennes!",
    "ro": "Abonează-te pentru noutăți zilnice!",
    "ja": "毎日のニュースを購読しましょう！",  # Japanese
    "no": "Abonner for daglige nyheter!",      # Norwegian
    "pt": "Inscreva-se para notícias diárias!", # Portuguese
    "tr": "Günlük haberler için abone olun!",
    "bn": "দৈনিক খবরের জন্য সাবস্ক্রাইব করুন!",
    "it": "Iscriviti per le notizie quotidiane!",
}


def _chat_id(city_key: str) -> str | None:
    """Return channel chat-ID or username env var, prioritizing numeric ID."""
    numeric = os.getenv(f"CHAT_{city_key.upper()}")
    if numeric:
        return numeric
    username = os.getenv(f"CHAT_{city_key.upper()}_USERNAME")
    if username:
        return username if username.startswith("@") else "@" + username
    return None


def _get_display_city(city_key: str) -> str:
    """Get localized city name from config, fallback to prettified key."""
    from config import CONFIG
    cfg = CONFIG.get(city_key, {})
    return cfg.get("city_local") or cfg.get("city") or city_key.replace("_", " ").title()


async def compose_and_send(city_key: str,
                           news_lines: list[str],
                           extras: str | None = ""):
    chat_id = _chat_id(city_key)
    if not chat_id:
        return

    from config import CONFIG
    lang = CONFIG.get(city_key, {}).get("lang", "en")
    lang = lang.lower().strip()  # Normalize language code

    label = LOCAL_HEADERS.get(lang, "Now")

    # Compose clickable subscribe link using the channel username if available
    if chat_id.startswith("@"):
        channel_username = chat_id.lstrip("@")
        subscribe_link = f"https://t.me/{channel_username}"
    else:
        subscribe_link = None

    cta_text = LOCAL_CTA_TEXT.get(lang, LOCAL_CTA_TEXT["en"])

    if subscribe_link:
        cta = f'🔔 <a href="{subscribe_link}">{cta_text}</a> 👈'
    else:
        cta = f"🔔 {cta_text} 👈"

    city_display = _get_display_city(city_key)

    header = f"📰 <b>{city_display} {label}</b>\n\n"
    body = "\n\n".join(f"{line}" for line in news_lines) \
        if news_lines else "_No fresh headlines yet._"
    text = header + body + (f"\n\n{extras}" if extras else "") + f"\n\n{cta}"

    await BOT.send_message(
        chat_id=int(chat_id) if chat_id.isdigit() else chat_id,
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=False,
    )