from dotenv import load_dotenv
load_dotenv()

import asyncio, yaml, os
from collectors import get_latest_items, get_extras
from composer import compose_and_send

# Load config safely
with open('config.yaml', 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f) or {}

# Find the first valid city
city = next((k for k, v in cfg.items() if isinstance(v, dict) and v.get("feeds")), None)

if not city or city not in cfg:
    raise RuntimeError("No valid city found in config.yaml")

print("City key  :", city)
chat_env = f"CHAT_{city.upper()}"
print("Env var   :", chat_env)
print("Chat ID   :", os.getenv(chat_env))

async def once():
    news   = await get_latest_items(city, cfg[city])
    extras = await get_extras(city, cfg[city])
    print("News lines:", news)
    print("Extras    :", extras)
    await compose_and_send(city, news, extras)

asyncio.run(once())