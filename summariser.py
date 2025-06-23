import os
import asyncio
import aiohttp
from openai import OpenAI
from bs4 import BeautifulSoup
from readability import Document
from utils import tiny
from playwright.async_api import async_playwright

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
        return text[:3000]
    except Exception:
        return ""

async def is_advertorial(url: str) -> bool:
    """Check if the full rendered page contains both 'Companii' and 'Advertoriale'."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=15000)
            content = await page.content()
            await browser.close()
        return "Companii" in content and "Advertoriale" in content
    except Exception:
        return False  # Fail-safe: don’t skip if check fails

async def summarise_article(entry, lang: str) -> str | None:
    title = entry.get("title", "")
    link = entry.get("link", "")

    lang = lang.lower()

    # Skip Agora advertorials
    if "agora.md" in link:
        if await is_advertorial(link):
            return None

    article_text = await fetch_article_text(link)

    if not article_text:
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

async def get_embedding(text: str) -> list[float]:
    """Return the OpenAI embedding vector for a given string."""
    try:
        resp = await asyncio.to_thread(
            lambda: client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
        )
        return resp.data[0].embedding
    except Exception:
        return []