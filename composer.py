# composer.py – build the Telegram post and send it
import os
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing in .env")
BOT = Bot(BOT_TOKEN)

# -------------------------------- i18n --------------------------------
LOCAL_HEADERS = {
    "en": "Now", "es": "Ahora", "de": "Jetzt", "fr": "Maintenant",
    "ro": "Acum", "ja": "今", "no": "Nå", "pt": "Agora",
    "tr": "Şimdi", "bn": "এখন", "it": "Ora",
}
LOCAL_CTA_TEXT = {
    "en": "Subscribe for daily news!",
    "es": "¡Suscríbete para noticias diarias!",
    "de": "Abonniere für tägliche Neuigkeiten!",
    "fr": "Abonnez-vous aux infos quotidiennes!",
    "ro": "Abonează-te pentru noutăți zilnice!",
    "ja": "毎日のニュースを購読しましょう！",
    "no": "Abonner for daglige nyheter!",
    "pt": "Inscreva-se para notícias diárias!",
    "tr": "Günlük haberler için abone olun!",
    "bn": "দৈনিক খবরের জন্য সাবস্ক্রাইব করুন!",
    "it": "Iscriviti per le notizie quotidiane!",
}

# ---------------------------- helpers ---------------------------------
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

# ---------------------------- main API --------------------------------
async def compose_and_send(city_key: str,
                           news_lines: list[str],
                           extras: str | None = ""):
    chat = _chat_id(city_key)
    if not chat:
        return                     # no channel

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
    body   = "\n\n".join(news_lines) if news_lines else "_No fresh headlines yet._"
    text   = header + body + (f"\n\n{extras}" if extras else "") + f"\n\n{cta}"

    await BOT.send_message(
        chat_id = int(chat) if chat.lstrip("-").isdigit() else chat,
        text    = text,
        parse_mode = "HTML",
        disable_web_page_preview = False,
    )