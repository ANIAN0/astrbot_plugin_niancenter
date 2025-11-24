import os
import json
import asyncio
from typing import Any

from astrbot.api.event import AstrMessageEvent
from astrbot.core.message.components import Plain, Image, Video
from ..core.request import fetch_json
from ..core.unified_store import UnifiedStore
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
                # record unified_msg_origin (prefer storing the unified string per official docs)
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

    async def send_proactive(self, unified: str, msg_type: str, content: Any):
        """主动发送：`unified` 应为 `unified_msg_origin` 的字符串，按官方文档使用 `context.send_message(unified, MessageChain)`。"""
        try:
            mc = MessageChain()
            if msg_type == "text":
                mc = mc.message(content)
            elif msg_type == "image":
                # prefer file_image/url helpers if available on MessageChain
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

            # official API expects a unified_msg_origin string
            await self.context.send_message(unified, mc)
        except Exception:
            self.logger.exception("send_proactive 发送失败")
