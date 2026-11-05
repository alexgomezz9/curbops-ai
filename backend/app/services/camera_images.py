"""Bounded municipal still-image proxy. Only URLs parsed from official camera KML.

Not a video stream, not archival footage. No user-supplied destination URLs.
"""
from __future__ import annotations
import asyncio
import time
import httpx
from ..integrations.madrid import _safe_image

_MAX_IMAGE_BYTES=3_000_000
_MAX_CACHE_ENTRIES=24
_cache: dict[str,tuple[float,bytes,str]]={}
_lock=asyncio.Lock()

async def camera_snapshot(image_url:str)->tuple[bytes,str,bool]:
    if not _safe_image(image_url):
        raise ValueError('Invalid or untrusted municipal image URL')
    now=time.monotonic()
    cached=_cache.get(image_url)
    if cached and now-cached[0]<75:
        return cached[1],cached[2],True
    async with _lock:
        cached=_cache.get(image_url)
        if cached and time.monotonic()-cached[0]<75:
            return cached[1],cached[2],True
        current=image_url
        async with httpx.AsyncClient(timeout=9,follow_redirects=False) as client:
            for _ in range(3):
                response=await client.get(current,headers={'User-Agent':'CurbOpsPortfolio/0.6'})
                if response.status_code in (301,302,303,307,308):
                    from urllib.parse import urljoin
                    target=urljoin(current,response.headers.get('location',''))
                    if not _safe_image(target):
                        raise ValueError('Municipal image redirected outside approved camera hosts')
                    current=target
                    continue
                response.raise_for_status()
                data=response.content
                if len(data)>_MAX_IMAGE_BYTES:raise ValueError('Camera image exceeds maximum size')
                # Avoid serving HTML or SVG under an image content-type.
                if data.startswith(b'\xff\xd8\xff'):
                    content_type='image/jpeg'
                elif data.startswith(b'\x89PNG\r\n\x1a\n'):
                    content_type='image/png'
                else:raise ValueError('Municipal camera did not return JPEG or PNG image data')
                if len(_cache)>=_MAX_CACHE_ENTRIES:
                    _cache.pop(next(iter(_cache)))
                _cache[image_url]=(time.monotonic(),data,content_type)
                return data,content_type,False
        raise ValueError('Too many municipal redirects')
