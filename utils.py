# utils.py
import aiohttp, asyncio, urllib.parse

_TINY_API = "https://tinyurl.com/api-create.php?url="

async def tiny(url: str, retries: int = 3, timeout: int = 2) -> str:
    """
    Return a TinyURL-shortened link, or the original URL on failure.

    Parameters
    ----------
    url : str
        The URL to shorten.
    retries : int
        How many times to retry on error (default 3).
    timeout : int
        Per-request timeout in seconds (default 2).
    """
    # Already quite short → nothing to gain
    if len(url) < 30:
        return url

    query = urllib.parse.quote_plus(url, safe="")
    api_url = f"{_TINY_API}{query}"

    for attempt in range(1, retries + 1):
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(api_url, timeout=timeout) as resp:
                    if resp.status == 200:
                        short = (await resp.text()).strip()
                        if short.startswith("http"):
                            return short
        except Exception:
            # network error, timeout, etc. – retry if attempts remain
            if attempt < retries:
                await asyncio.sleep(0.2)   # brief back-off
            else:
                break

    return url  # graceful fallback