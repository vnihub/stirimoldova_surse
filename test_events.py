from dotenv import load_dotenv
load_dotenv()

import asyncio, yaml
from events import compose_events_and_send

with open("config.yaml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

city = "new_york"

asyncio.run(compose_events_and_send(city))