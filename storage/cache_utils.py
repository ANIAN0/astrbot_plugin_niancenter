import os
import base64
from datetime import datetime
from typing import Optional

class CacheUtils:
    def __init__(self, plugin_dir: str):
        self.cache_dir = os.path.join(plugin_dir, "cache")
        self._init_cache_dirs()

    def _init_cache_dirs(self):
        cache_types = ["image", "voice", "video", "file"]
        for cache_type in cache_types:
            type_dir = os.path.join(self.cache_dir, cache_type)
            os.makedirs(type_dir, exist_ok=True)

    async def cache_media(self, source: str, media_type: str) -> str:
        try:
            cache_dir = os.path.join(self.cache_dir, media_type)
            os.makedirs(cache_dir, exist_ok=True)
            if isinstance(source, str) and (source.startswith("http://") or source.startswith("https://")):
                return await self._download_and_save(source, cache_dir, media_type)
            elif isinstance(source, str) and (source.startswith("data:") or self._is_base64(source)):
                return await self._decode_and_save_base64(source, cache_dir, media_type)
            else:
                return source
        except Exception:
            return source

    async def _download_and_save(self, url: str, cache_dir: str, media_type: str) -> str:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        content_type = resp.headers.get("content-type", "")
                        ext = self._get_extension_from_content_type(content_type, media_type)
                        filename = f"{datetime.utcnow().timestamp()}{ext}"
                        file_path = os.path.join(cache_dir, filename)
                        with open(file_path, "wb") as f:
                            f.write(content)
                        return file_path
                    else:
                        raise Exception(f"下载失败: HTTP {resp.status}")
        except Exception as e:
            raise

    async def _decode_and_save_base64(self, content: str, cache_dir: str, media_type: str) -> str:
        try:
            if content.startswith("data:"):
                content = content.split(",", 1)[1]
            decoded = base64.b64decode(content)
            ext = self._get_extension_by_type(media_type)
            filename = f"{datetime.utcnow().timestamp()}{ext}"
            file_path = os.path.join(cache_dir, filename)
            with open(file_path, "wb") as f:
                f.write(decoded)
            return file_path
        except Exception:
            raise

    def _is_base64(self, s: str) -> bool:
        try:
            if isinstance(s, str):
                s_bytes = bytes(s, 'utf-8')
            elif isinstance(s, bytes):
                s_bytes = s
            else:
                return False
            return base64.b64encode(base64.b64decode(s_bytes)) == s_bytes
        except Exception:
            return False

    def _get_extension_from_content_type(self, content_type: str, default_type: str) -> str:
        mime_to_ext = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "audio/mpeg": ".mp3",
            "audio/wav": ".wav",
            "video/mp4": ".mp4",
            "video/webm": ".webm",
            "application/pdf": ".pdf",
        }
        for mime, ext in mime_to_ext.items():
            if mime in content_type:
                return ext
        return self._get_extension_by_type(default_type)

    def _get_extension_by_type(self, media_type: str) -> str:
        defaults = {
            "image": ".png",
            "voice": ".wav",
            "video": ".mp4",
            "file": "",
            "text": ".txt"
        }
        return defaults.get(media_type, "")
