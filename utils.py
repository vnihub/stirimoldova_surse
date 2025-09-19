# utils.py
import os
import aiohttp
import asyncio

_TINY_API_ENDPOINT = "https://api.tinyurl.com/create"
_TINY_API_TOKEN = os.getenv("TINYURL_API_TOKEN")

async def tiny(url: str, retries: int = 3, timeout: int = 5) -> str:
    """
    Return a TinyURL-shortened link using the new API, or the original URL on failure.

    Parameters
    ----------
    url : str
        The URL to shorten.
    retries : int
        How many times to retry on error (default 3).
    timeout : int
        Per-request timeout in seconds (default 5).
    """
    if not _TINY_API_TOKEN:
        print("⚠️ TINYURL_API_TOKEN not found. Skipping shortening.")
        return url

    if len(url) < 30:
        return url

    headers = {
        "Authorization": f"Bearer {_TINY_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"url": url}

    for attempt in range(1, retries + 1):
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post(_TINY_API_ENDPOINT, headers=headers, json=payload, timeout=timeout) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("data", {}).get("tiny_url", url)
                    else:
                        print(f"❌ TinyURL API error (attempt {attempt}): {resp.status} {await resp.text()}")

        except Exception as e:
            print(f"❌ Exception during TinyURL request (attempt {attempt}): {e}")
            if attempt < retries:
                await asyncio.sleep(0.5)  # brief back-off
            else:
                break

    return url  # graceful fallback
