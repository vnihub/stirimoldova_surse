import os
import asyncio
import aiohttp
from openai import OpenAI
from bs4 import BeautifulSoup
from readability import Document
from utils import tiny

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def fetch_article_text(url: str) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                html = await resp.text()

        doc = Document(html)
        summary_html = doc.summary()
        soup = BeautifulSoup(summary_html, "html.parser")
        text = soup.get_text(separator="\n").strip()
        # Limit length to avoid huge prompts (optional)
        return text[:3000]  # first 3000 chars or less
    except Exception:
        return ""

async def summarise_article(entry, lang: str) -> str:
    title = entry.get("title", "")
    link = entry.get("link", "")

    lang = lang.lower()

    article_text = await fetch_article_text(link)
    if not article_text:
        # fallback to headline only
        prompt_text = f"Summarise the headline '{title}' in ≤15 words, keep language {lang}, add one emoji prefix."
    else:
        prompt_text = (
            f"Summarise the following news article in ≤30 words, keep language {lang}, add one emoji prefix.\n\n"
            f"{article_text}"
        )

    resp = await asyncio.to_thread(
        lambda: client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt_text}],
            temperature=0.3,
        )
    )

    summary = resp.choices[0].message.content.strip()

    try:
        short_link = await tiny(link)
    except Exception:
        short_link = link

    return f"{summary} → {short_link}"