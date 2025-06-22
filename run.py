# run.py  – Chişinău-only bot with Telegram crash/start alerts

import sys
sys.stdout.reconfigure(line_buffering=True)
print("🟢 Bot is starting…", flush=True)

from dotenv import load_dotenv
load_dotenv()  # read .env first

import asyncio, yaml
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from collectors import get_latest_items, get_extras
from composer import compose_and_send
from alert import send_alert  # 🚨 alert system import
import threading

with open("config.yaml", "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

CITY_KEY = "chisinau"
cfg = CONFIG[CITY_KEY]
tz = ZoneInfo(cfg.get("tz", "UTC"))

# five news slots per day
SLOTS = [(8, 8), (11, 11), (14, 14), (18, 18), (21, 12)]

async def job():
    news   = await get_latest_items(CITY_KEY, cfg, limit=7)
    extras = await get_extras(CITY_KEY, cfg)
    await compose_and_send(CITY_KEY, news, extras)

def heartbeat():
    print("✅ Bot is still running…", flush=True)
    threading.Timer(900, heartbeat).start()  # every 15 minutes

def main():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        sched = AsyncIOScheduler(event_loop=loop)

        # schedule news posts
        for h, m in SLOTS:
            sched.add_job(
                job,
                "cron",
                hour=h,
                minute=m,
                timezone=tz,
            )

        sched.start()
        print("Chişinău-bot scheduler started. Loop running forever …", flush=True)
        heartbeat()

        # ✅ Notify successful start
        loop.create_task(send_alert("✅ Chişinău bot started successfully."))

        loop.run_forever()

    except Exception as e:
        # 🚨 Notify on crash
        loop.run_until_complete(send_alert(f"❌ Chişinău bot crashed:\n{str(e)}"))
        raise

if __name__ == "__main__":
    main()