# run.py  – per-city time-zone aware

import sys
sys.stdout.reconfigure(line_buffering=True)

print("🟢 Bot is starting…", flush=True)

from events import compose_events_and_send
from dotenv import load_dotenv
load_dotenv()                                     # read .env first

import asyncio, yaml
from zoneinfo import ZoneInfo                     # std-lib tz support (Py ≥ 3.9)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from collectors import get_latest_items, get_extras
from composer import compose_and_send
import threading

with open("config.yaml", "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

SLOTS = [(8, 0), (13, 0), (16, 30)]               # hours, minutes


async def job(city_key: str):
    news   = await get_latest_items(city_key, CONFIG[city_key])
    extras = await get_extras(city_key, CONFIG[city_key])
    await compose_and_send(city_key, news, extras)


def heartbeat():
    print("✅ Bot is still running…", flush=True)
    threading.Timer(300, heartbeat).start()  # every 5 minutes


def main():
    # 1️⃣ create a fresh event-loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # 2️⃣ attach APScheduler to that loop
    sched = AsyncIOScheduler(event_loop=loop)

    for city_key, cfg in CONFIG.items():
        tz = ZoneInfo(cfg.get("tz", "UTC"))        # read tz from config.yaml

        # 🗞 Regular news+weather posts
        for h, m in SLOTS:
            sched.add_job(
                job,
                "cron",
                args=[city_key],
                hour=h,
                minute=m,
                timezone=tz,
            )

        # ⏰ 4th job – Events only at 09:00 local time
        sched.add_job(
            compose_events_and_send,
            "cron",
            args=[city_key],
            hour=9,
            minute=0,
            timezone=tz,
        )

    sched.start()
    print("City-bot scheduler started. Loop running forever …", flush=True)
    heartbeat()
    loop.run_forever()


if __name__ == "__main__":
    main()