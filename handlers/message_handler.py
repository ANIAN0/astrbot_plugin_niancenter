import os
import json
import asyncio
from typing import Any

from astrbot.api.event import AstrMessageEvent
from astrbot.core.message.components import Plain, Image, Video
from core.request import fetch_json
from core.unified_store import UnifiedStore
from astrbot.api.event import MessageChain


class MessageHandler:
    def __init__(self, context, config_path: str, unified_store: UnifiedStore, logger):
        self.context = context
        self.config_path = config_path
        self._config = {}
        self.logger = logger
        self.unified_store = unified_store
        self._load_config()

    def _load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
            else:
                self._config = {}
        except Exception:
            self._config = {}

    async def match_and_handle(self, event: AstrMessageEvent):
        message_str = getattr(event, "message_str", "") or ""
        if not message_str:
            return

        rules = self._config.get("rules", [])
        for rule in rules:
            keywords = rule.get("keywords", [])
            if isinstance(keywords, str):
                keywords = [keywords]
            if any(k in message_str for k in keywords):
                # record unified
                try:
                    umo = getattr(event, "unified_msg_origin", None)
                    key = None
                    try:
                        if hasattr(event, "get_sender_id"):
                            key = str(event.get_sender_id())
                    except Exception:
                        key = None
                    if not key and isinstance(umo, dict):
                        for candidate in ("sender", "user", "target", "id", "user_id"):
                            if candidate in umo:
                                val = umo.get(candidate)
                                if isinstance(val, (str, int)):
                                    key = str(val)
                                    break
                    if not key:
                        try:
                            key = str(event.get_sender_name())
                        except Exception:
                            key = None
                    if key and umo is not None:
                        self.unified_store.set(key, umo)
                except Exception:
                    self.logger.exception("记录 unified 失败")

                # call external api
                url = rule.get("url")
                method = (rule.get("method") or "GET").upper()
                params = rule.get("params") or {}
                if rule.get("pass_event"):
                    params.update({
                        "session_id": getattr(event, "session_id", None),
                        "message_id": getattr(event, "message_id", None),
                        "message_str": getattr(event, "message_str", None),
                        "timestamp": getattr(event, "timestamp", None),
                    })
                try:
                    resp = await fetch_json(url, method=method, params=params, headers=rule.get("headers"))
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
                    if isinstance(image_path, str) and os.path.exists(image_path):
                        chain = [Image.fromFileSystem(str(image_path))]
                        await event.send(event.chain_result(chain))
                    else:
                        await event.send(event.image_result(image_path))
                    event.stop_event()
                    return
                elif reply_type == "video":
                    video_path = rule.get("video_path") or resp
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
                else:
                    await event.send(event.plain_result(str(resp)))
                    event.stop_event()
                    return

    async def send_proactive(self, unified: dict, msg_type: str, content: Any):
        """主动发送：构造 MessageChain 并使用 context.send_message(unified, chain)"""
        try:
            mc = MessageChain()
            if msg_type == "text":
                mc = mc.message(content)
            elif msg_type == "image":
                if hasattr(mc, "file_image"):
                    mc = mc.file_image(content)
                else:
                    mc = mc.message(content)
            elif msg_type == "video":
                if hasattr(mc, "file_video"):
                    mc = mc.file_video(content)
                else:
                    mc = mc.message(content)
            else:
                mc = mc.message(content)
            await self.context.send_message(unified, mc)
        except Exception:
            self.logger.exception("send_proactive 发送失败")
