# composer.py  – safe title + underscore fix

from dotenv import load_dotenv
load_dotenv()                                   # load .env first

import os
from telegram import Bot

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing in .env")

BOT = Bot(BOT_TOKEN)


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
        return                                   # no channel configured

    header = f"**📰 {_pretty(city_key)} Now**\n\n"
    body = "\n\n".join(f"{line}" for line in news_lines) \
       if news_lines else "_No fresh headlines yet._"
    text = header + body + (f"\n\n{extras}" if extras else "")

    await BOT.send_message(
        chat_id=int(chat_id),
        text=text,
        parse_mode="Markdown",
        disable_web_page_preview=False,
    )