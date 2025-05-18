import aiohttp, functools

_TINY = "https://tinyurl.com/api-create.php?url={u}"

@functools.lru_cache(maxsize=2000)      # avoids re-shortening the same link
async def tiny(url: str) -> str:
    async with aiohttp.ClientSession() as sess:
        async with sess.get(_TINY.format(u=url), timeout=10) as r:
            return await r.text()