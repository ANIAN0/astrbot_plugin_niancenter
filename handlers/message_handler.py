import os
import json
import asyncio
import base64
from typing import Any
from pathlib import Path
from datetime import datetime

from astrbot.api.event import AstrMessageEvent
from astrbot.core.message.components import Plain, Image, Video, Record
from ..core.request import fetch_json
from ..core.unified_store import UnifiedStore
from ..core.keyword_handlers import KeywordHandler
from astrbot.api.event import MessageChain


class MessageHandler:
    def __init__(self, context, config_path: str, unified_store: UnifiedStore, logger):
        self.context = context
        self.config_path = config_path
        self._config = {}
        self.logger = logger
        self.unified_store = unified_store
        self.keyword_handler = KeywordHandler(unified_store, logger)
        self._load_config()
        
        # 加载关键字配置
        self.plugin_dir = os.path.dirname(os.path.dirname(config_path))
        self.keywords_config = self._load_keywords()
        
        # 初始化缓存目录
        self.plugin_dir = os.path.dirname(os.path.dirname(config_path))
        self.cache_dir = os.path.join(self.plugin_dir, "cache")
        self._init_cache_dirs()

    def _load_keywords(self):
        """加载关键字配置文件"""
        try:
            keywords_path = os.path.join(self.plugin_dir, "configs", "keywords.json")
            if os.path.exists(keywords_path):
                with open(keywords_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.exception(f"加载关键字配置失败: {e}")
            return {}

    def _init_cache_dirs(self):
        """初始化缓存目录结构"""
        cache_types = ["image", "voice", "video", "file"]
        for cache_type in cache_types:
            type_dir = os.path.join(self.cache_dir, cache_type)
            os.makedirs(type_dir, exist_ok=True)

    async def match_and_handle(self, event: AstrMessageEvent):
        message_str = getattr(event, "message_str", "") or ""
        if not message_str:
            return
        
        # 优先检查特殊关键字（从配置文件读取）
        for keyword_name in self.keywords_config.keys():
            if keyword_name in message_str:
                if await self.keyword_handler.handle(keyword_name, event):
                    event.stop_event()
                    return

        # 再检查规则规则
        rules = self._config.get("rules", [])
        for rule in rules:
            keywords = rule.get("keywords", [])
            if isinstance(keywords, str):
                keywords = [keywords]
            if any(k in message_str for k in keywords):
                try:
                    umo = getattr(event, "unified_msg_origin", None)
                    unified_value = None
                    if isinstance(umo, str):
                        unified_value = umo
                    elif isinstance(umo, dict) and isinstance(umo.get("unified_msg_origin"), str):
                        unified_value = umo.get("unified_msg_origin")

                    # choose a stable key to map to the unified string: prefer sender id, then sender name, then the unified string itself
                    store_key = None
                    try:
                        if hasattr(event, "get_sender_id"):
                            sid = event.get_sender_id()
                            if sid is not None:
                                store_key = str(sid)
                    except Exception:
                        store_key = None

                    if not store_key:
                        try:
                            sname = event.get_sender_name()
                            if sname:
                                store_key = str(sname)
                        except Exception:
                            store_key = None

                    if not store_key and unified_value:
                        store_key = unified_value

                    if store_key and unified_value:
                        # persist mapping: store_key -> unified_msg_origin (string)
                        self.unified_store.set(store_key, unified_value)
                except Exception:
                    self.logger.exception("记录 unified 失败")

                # call external api
                url = rule.get("url")
                method = (rule.get("method") or "GET").upper()
                # build request body/params according to rule.body_fields if provided
                request_params = {}

                # helper: extract message components
                def _collect_components(ev):
                    texts = []
                    images = []
                    videos = []
                    records = []
                    # try event.get_messages()
                    comps = None
                    try:
                        if hasattr(ev, "get_messages") and callable(ev.get_messages):
                            comps = ev.get_messages()
                    except Exception:
                        comps = None
                    if comps is None:
                        try:
                            mo = getattr(ev, "message_obj", None)
                            if mo is not None and hasattr(mo, "message"):
                                comps = mo.message
                        except Exception:
                            comps = None
                    if comps is None:
                        try:
                            comps = getattr(ev, "message", None)
                        except Exception:
                            comps = None

                    # fallback: use message_str as single text
                    message_str_all = getattr(ev, "message_str", "") or ""

                    if not comps:
                        if message_str_all:
                            texts = [message_str_all]
                        return texts, images, videos, records

                    for c in comps:
                        try:
                            c_cls = c.__class__.__name__.lower()
                        except Exception:
                            c_cls = ""
                        # text/plain
                        txt = None
                        if hasattr(c, "text"):
                            txt = getattr(c, "text")
                        elif hasattr(c, "content"):
                            txt = getattr(c, "content")
                        elif hasattr(c, "data"):
                            txt = getattr(c, "data")
                        # image
                        img = None
                        if hasattr(c, "url"):
                            img = getattr(c, "url")
                        elif hasattr(c, "file"):
                            img = getattr(c, "file")
                        elif hasattr(c, "path"):
                            img = getattr(c, "path")
                        # video
                        vid = None
                        if hasattr(c, "url") and "video" in c_cls:
                            vid = getattr(c, "url")
                        elif hasattr(c, "file") and "video" in c_cls:
                            vid = getattr(c, "file")

                        if txt is not None and isinstance(txt, str) and txt:
                            texts.append(txt)
                        elif img is not None:
                            images.append(str(img))
                        elif vid is not None:
                            videos.append(str(vid))
                        else:
                            # fallback: if class name suggests image/video
                            if "image" in c_cls and hasattr(c, "url"):
                                images.append(str(getattr(c, "url")))
                            elif "video" in c_cls and hasattr(c, "url"):
                                videos.append(str(getattr(c, "url")))

                    return texts, images, videos, records

                texts, images, videos, records = _collect_components(event)

                # determine matched keyword (first occurrence)
                matched_keyword = None
                for k in (keywords if isinstance(keywords, (list, tuple)) else [keywords]):
                    if k and k in message_str:
                        matched_keyword = k
                        break

                body_fields = rule.get("body_fields")
                if body_fields and isinstance(body_fields, list):
                    for fld in body_fields:
                        fname = fld.get("name")
                        ftype = (fld.get("type") or "text").lower()
                        if not fname:
                            continue
                        if ftype == "text":
                            # build text param: remove first occurrence of matched keyword and following spaces
                            if matched_keyword:
                                # remove first occurrence only
                                proc = message_str.replace(matched_keyword, "", 1)
                                proc = proc.lstrip()
                            else:
                                proc = message_str
                            # if we have separate Plain segments, use joined texts otherwise proc
                            if texts:
                                # prefer proc as representative; otherwise join texts
                                value = proc if proc else ",".join(t.strip() for t in texts if t and t.strip())
                            else:
                                value = proc
                            request_params[fname] = value
                        elif ftype == "image":
                            request_params[fname] = ",".join(images)
                        elif ftype == "video":
                            request_params[fname] = ",".join(videos)
                        elif ftype == "record" or ftype == "voice":
                            request_params[fname] = ",".join(records)
                        else:
                            # unknown type: try text
                            request_params[fname] = ",".join(texts) if texts else message_str
                else:
                    # fallback to old behavior: use explicit params and pass_event
                    request_params = rule.get("params") or {}
                    if rule.get("pass_event"):
                        request_params.update({
                            "session_id": getattr(event, "session_id", None),
                            "message_id": getattr(event, "message_id", None),
                            "message_str": getattr(event, "message_str", None),
                            "timestamp": getattr(event, "timestamp", None),
                        })

                try:
                    resp = await fetch_json(url, method=method, params=request_params, headers=rule.get("headers"))
                except Exception:
                    self.logger.exception("外部接口失败")
                    await event.send(event.plain_result(rule.get("on_error") or "接口调用失败"))
                    event.stop_event()
                    return

                # reply based on type
                reply_type = rule.get("reply_type", "text")
                if reply_type == "text":
                    content = rule.get("text_template") or str(resp)
                    chain = [Plain(content)]
                    await event.send(event.chain_result(chain))
                    event.stop_event()
                    return
                elif reply_type == "image":
                    image_path = rule.get("image_path") or resp
                    # 检查是否需要缓存
                    if isinstance(resp, str) and not os.path.exists(image_path):
                        image_path = await self._cache_media(str(resp), "image")
                    if isinstance(image_path, str) and os.path.exists(image_path):
                        chain = [Image.fromFileSystem(str(image_path))]
                        await event.send(event.chain_result(chain))
                    else:
                        await event.send(event.image_result(image_path))
                    event.stop_event()
                    return
                elif reply_type == "video":
                    video_path = rule.get("video_path") or resp
                    # 检查是否需要缓存
                    if isinstance(resp, str) and not os.path.exists(video_path):
                        video_path = await self._cache_media(str(resp), "video")
                    if isinstance(video_path, str) and os.path.exists(video_path):
                        chain = [Video.fromFileSystem(str(video_path))]
                        await event.send(event.chain_result(chain))
                    else:
                        if hasattr(event, "video_result"):
                            await event.send(event.video_result(video_path))
                        else:
                            await event.send(event.plain_result(f"[视频] {video_path}"))
                    event.stop_event()
                    return
                elif reply_type == "voice":
                    voice_path = rule.get("voice_path") or resp
                    # 检查是否需要缓存
                    if isinstance(resp, str) and not os.path.exists(voice_path):
                        voice_path = await self._cache_media(str(resp), "voice")
                    if isinstance(voice_path, str) and os.path.exists(voice_path):
                        chain = [Record(file=voice_path, url=voice_path)]
                        await event.send(event.chain_result(chain))
                    else:
                        await event.send(event.plain_result(f"[语音] {voice_path}"))
                    event.stop_event()
                    return
                elif reply_type == "file":
                    file_path = rule.get("file_path") or resp
                    # 检查是否需要缓存
                    if isinstance(resp, str) and not os.path.exists(file_path):
                        file_path = await self._cache_media(str(resp), "file")
                    if isinstance(file_path, str) and os.path.exists(file_path):
                        from astrbot.api.message_components import File
                        filename = os.path.basename(file_path)
                        chain = [File(file=file_path, name=filename)]
                        await event.send(event.chain_result(chain))
                    else:
                        await event.send(event.plain_result(f"[文件] {file_path}"))
                    event.stop_event()
                    return
                else:
                    await event.send(event.plain_result(str(resp)))
                    event.stop_event()
                    return

    async def send_proactive(self, unified: str, msg_type: str, content: Any):
        """主动发送：`unified` 应为 `unified_msg_origin` 的字符串，按官方文档使用 `context.send_message(unified, MessageChain)`。"""
        try:
            mc = MessageChain()
            if msg_type == "text":
                mc = mc.message(content)
            elif msg_type == "image":
                # 检查是否需要缓存
                if isinstance(content, str) and not os.path.exists(content):
                    content = await self._cache_media(content, "image")
                if hasattr(mc, "file_image") and os.path.exists(content):
                    mc = mc.file_image(content)
                else:
                    mc = mc.message(content)
            elif msg_type == "video":
                # 检查是否需要缓存
                if isinstance(content, str) and not os.path.exists(content):
                    content = await self._cache_media(content, "video")
                if hasattr(mc, "file_video") and os.path.exists(content):
                    mc = mc.file_video(content)
                else:
                    mc = mc.message(content)
            elif msg_type == "voice":
                # 检查是否需要缓存
                if isinstance(content, str) and not os.path.exists(content):
                    content = await self._cache_media(content, "voice")
                if os.path.exists(content):
                    mc = mc.message(Record(file=content, url=content))
                else:
                    mc = mc.message(content)
            elif msg_type == "file":
                # 检查是否需要缓存
                if isinstance(content, str) and not os.path.exists(content):
                    content = await self._cache_media(content, "file")
                if os.path.exists(content):
                    from astrbot.api.message_components import File
                    filename = os.path.basename(content)
                    mc = mc.message(File(file=content, name=filename))
                else:
                    mc = mc.message(content)
            else:
                mc = mc.message(content)

            # official API expects a unified_msg_origin string
            await self.context.send_message(unified, mc)
        except Exception:
            self.logger.exception("send_proactive 发送失败")
    
    async def _cache_media(self, source: str, media_type: str) -> str:
        """缓存媒体文件（URL或base64），返回本地路径"""
        try:
            cache_dir = os.path.join(self.cache_dir, media_type)
            os.makedirs(cache_dir, exist_ok=True)
            
            # 检查是否是URL
            if source.startswith("http://") or source.startswith("https://"):
                return await self._download_and_save(source, cache_dir, media_type)
            # 检查是否是base64编码
            elif source.startswith("data:") or self._is_base64(source):
                return await self._decode_and_save_base64(source, cache_dir, media_type)
            else:
                # 其他情况返回原值
                return source
        except Exception as e:
            self.logger.exception(f"缓存{media_type}文件失败: {e}")
            # 缓存失败时返回原值
            return source
    
    async def _download_and_save(self, url: str, cache_dir: str, media_type: str) -> str:
        """从URL下载文件并保存到缓存"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        
                        # 根据Content-Type确定文件扩展名
                        content_type = resp.headers.get("content-type", "")
                        ext = self._get_extension_from_content_type(content_type, media_type)
                        
                        filename = f"{datetime.utcnow().timestamp()}{ext}"
                        file_path = os.path.join(cache_dir, filename)
                        
                        with open(file_path, "wb") as f:
                            f.write(content)
                        
                        self.logger.info(f"缓存文件下载成功: {url} -> {file_path}")
                        return file_path
                    else:
                        raise Exception(f"下载失败: HTTP {resp.status}")
        except Exception as e:
            self.logger.exception(f"下载文件失败: {url}")
            raise
    
    async def _decode_and_save_base64(self, content: str, cache_dir: str, media_type: str) -> str:
        """解码base64内容并保存到缓存"""
        try:
            # 处理 data:image/png;base64, 格式
            if content.startswith("data:"):
                content = content.split(",", 1)[1]
            
            # 解码base64
            decoded = base64.b64decode(content)
            
            # 确定文件扩展名
            ext = self._get_extension_by_type(media_type)
            filename = f"{datetime.utcnow().timestamp()}{ext}"
            file_path = os.path.join(cache_dir, filename)
            
            with open(file_path, "wb") as f:
                f.write(decoded)
            
            self.logger.info(f"Base64解码缓存成功: {file_path}")
            return file_path
        except Exception as e:
            self.logger.exception("Base64解码失败")
            raise
    
    def _is_base64(self, s: str) -> bool:
        """检查字符串是否是base64编码"""
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
        """根据Content-Type获取文件扩展名"""
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
        """根据媒体类型获取默认扩展名"""
        defaults = {
            "image": ".png",
            "voice": ".wav",
            "video": ".mp4",
            "file": "",
            "text": ".txt"
        }
        return defaults.get(media_type, "")


