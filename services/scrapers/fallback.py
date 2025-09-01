from __future__ import annotations

import os
from typing import List
import httpx


async def search_image_urls_bing(query: str, top: int = 3) -> List[str]:
    key = os.getenv("BING_API_KEY")
    endpoint = os.getenv("BING_IMAGE_SEARCH_URL", "https://api.bing.microsoft.com/v7.0/images/search")
    if not key:
        return []
    headers = {"Ocp-Apim-Subscription-Key": key}
    params = {"q": query, "count": top, "safeSearch": "Moderate"}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(endpoint, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
        urls: List[str] = []
        for v in data.get("value", [])[:top]:
            u = v.get("contentUrl") or v.get("thumbnailUrl")
            if u:
                urls.append(u)
        return urls

