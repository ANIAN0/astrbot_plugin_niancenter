import aiohttp


async def fetch_json(url: str, method: str = "GET", params: dict | None = None, headers: dict | None = None, timeout: int = 10):
    try:
        async with aiohttp.ClientSession() as session:
            if method.upper() == "GET":
                async with session.get(url, params=params, headers=headers, timeout=timeout) as resp:
                    ct = resp.headers.get("content-type", "")
                    if "application/json" in ct:
                        return await resp.json()
                    else:
                        text = await resp.text()
                        return text
            else:
                async with session.post(url, json=params, headers=headers, timeout=timeout) as resp:
                    ct = resp.headers.get("content-type", "")
                    if "application/json" in ct:
                        return await resp.json()
                    else:
                        text = await resp.text()
                        return text
    except Exception as e:
        raise
