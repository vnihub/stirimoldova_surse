# composer.py – localized title + underscore fix + universal CTA

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
}

# Language-specific shorter subscribe CTA (optional, fallback to English)
LOCAL_CTA = {
    "en": "**👉🔔 Subscribe for daily updates! 🔔👈**",
    "es": "**👉🔔 ¡Suscríbete para recibir actualizaciones diarias! 🔔👈**",
    "de": "**👉🔔 Abonniere für tägliche Updates! 🔔👈**",
    "fr": "**👉🔔 Abonnez-vous pour les mises à jour quotidiennes ! 🔔👈**",
    "ro": "**👉🔔 Abonează-te pentru actualizări zilnice! 🔔👈**",
}


def _chat_id(city_key: str) -> str | None:
    """Return channel chat-ID env var, e.g. CHAT_NEW_YORK."""
    return os.getenv(f"CHAT_{city_key.upper()}")


def _pretty(city_key: str) -> str:
    """new_york → New York (no underscore, title-case)."""
    return city_key.replace("_", " ").title()


async def compose_and_send(city_key: str,
                           news_lines: list[str],
                           extras: str | None = ""):
    chat_id = _chat_id(city_key)
    if not chat_id:
        return

    from config import CONFIG
    lang = CONFIG.get(city_key, {}).get("lang", "en")
    label = LOCAL_HEADERS.get(lang, "Now")
    cta = LOCAL_CTA.get(lang, LOCAL_CTA["en"])

    header = f"**📰 {_pretty(city_key)} {label}**\n\n"
    body = "\n\n".join(f"{line}" for line in news_lines) \
        if news_lines else "_No fresh headlines yet._"
    text = header + body + (f"\n\n{extras}" if extras else "") + f"\n\n{cta}"

    await BOT.send_message(
        chat_id=int(chat_id),
        text=text,
        parse_mode="Markdown",
        disable_web_page_preview=False,
    )