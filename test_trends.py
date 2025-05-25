from dotenv import load_dotenv
load_dotenv()

import asyncio, yaml
from trends import compose_trends_and_send

with open("config.yaml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

city = "london"

asyncio.run(compose_trends_and_send(city))