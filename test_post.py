# test_post.py – manual test trigger for a specific city

from dotenv import load_dotenv
load_dotenv()

import asyncio, yaml, os
from collectors import get_latest_items, get_extras
from composer import compose_and_send

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
    news   = await get_latest_items(city, cfg[city])
    extras = await get_extras(city, cfg[city])
    print("News lines:", news)
    print("Extras    :", extras)
    await compose_and_send(city, news, extras)

asyncio.run(once())