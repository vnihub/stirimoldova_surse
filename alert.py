# alert.py – send crash alert to private Telegram channel

import os
from telegram import Bot

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALERT_CHAT_ID = os.getenv("ALERT_CHAT_ID")

if not BOT_TOKEN or not ALERT_CHAT_ID:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or ALERT_CHAT_ID in .env")

ALERT_BOT = Bot(BOT_TOKEN)

async def send_alert(msg: str):
    try:
        await ALERT_BOT.send_message(
            chat_id=int(ALERT_CHAT_ID),
            text=f"🚨 <b>Bot Alert</b>\n\n{msg}",
            parse_mode="HTML"
        )
    except Exception as e:
        print("❌ Failed to send alert:", e)