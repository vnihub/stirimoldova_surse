# test_post.py – manual test trigger for events for a specific city

from dotenv import load_dotenv
load_dotenv()

import asyncio, yaml, os
from events_iticket import events_iticket_job
from composer import compose_events_and_send

# Load config
with open('config.yaml', 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

# 👇 Change city key here
city = "chisinau"

if city not in cfg:
    raise RuntimeError(f"City '{city}' not found in config.yaml")

chat_env = f"CHAT_{city.upper()}"
print("City key  :", city)
print("Env var   :", chat_env)
print("Chat ID   :", os.getenv(chat_env))

async def once():
    events = await events_iticket_job()
    print("Events found:", events)
    if events:
        await compose_events_and_send(city, events)
    else:
        print("No events found for today.")

asyncio.run(once())
