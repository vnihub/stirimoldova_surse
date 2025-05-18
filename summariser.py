# summariser.py – compatible with openai-python ≥1.0 and TinyURL

import os, asyncio
from openai import OpenAI
from utils import tiny

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def summarise_article(entry, lang: str) -> str:
    title = entry.get("title", "")
    link  = entry.get("link", "")

    prompt = (
        f"Summarise the headline '{title}' in ≤15 words, keep language {lang}, "
        "add one emoji prefix."
    )

    # Run the blocking OpenAI call in a thread so the event-loop stays responsive
    resp = await asyncio.to_thread(
        lambda: client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
    )

    summary = resp.choices[0].message.content.strip()

    # Shorten the link with TinyURL (fallback to original on error)
    try:
        short_link = await tiny(link)
    except Exception:
        short_link = link

    return f"{summary} → {short_link}"