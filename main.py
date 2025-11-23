import astrbot.api.message_components as Comp
from astrbot.core.message.components import BaseMessageComponent, Image, Plain, Record, Video
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult, MessageChain, EventMessageType
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import json
import asyncio
import aiohttp
import os
from aiohttp import web

@register("helloworld", "YourName", "一个简单的 Hello World 插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config_path = os.path.join(os.path.dirname(__file__), "configs", "config.json")
        self._config = {}
        self._http_runner = None
        self.unified_store_path = os.path.join(os.path.dirname(__file__), "configs", "unified_store.json")
        self._unified_store = {}

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        # 加载本地配置
        await self.load_config()
        # 启动对外 HTTP 接口，供外部调用发送私聊消息
        asyncio.create_task(self._start_http_server())
        # 加载已保存的 unified_store（如果有）
        await self._load_unified_store()

    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
    @filter.command("helloworld")
    async def helloworld(self, event: AstrMessageEvent):
        """这是一个 hello world 指令""" # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        user_name = event.get_sender_name()
        message_str = event.message_str # 用户发的纯文本消息字符串
        message_chain = event.get_messages() # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)
        yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!") # 发送一条纯文本消息

    async def load_config(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
            logger.info(f"Loaded config from {self.config_path}")
        except FileNotFoundError:
            logger.warning(f"Config file not found: {self.config_path}")
            self._config = {}
        except Exception as e:
            logger.exception("Failed to load config")
            self._config = {}

    async def _load_unified_store(self):
        try:
            if os.path.exists(self.unified_store_path):
                with open(self.unified_store_path, "r", encoding="utf-8") as f:
                    try:
                        self._unified_store = json.load(f)
                    except Exception:
                        # 如果文件里不是严格 JSON，则忽略
                        self._unified_store = {}
            else:
                self._unified_store = {}
            logger.info(f"Loaded unified_store from {self.unified_store_path}")
        except Exception:
            logger.exception("加载 unified_store 失败")
            self._unified_store = {}

    # 被动监听私聊消息（使用官方示例的事件装饰器）
    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def on_message(self, event: AstrMessageEvent):
        try:

            text = getattr(event, "message_str", "") or ""
            if not text:
                return

            # 匹配配置中的关键字
            rules = self._config.get("rules", [])
            for rule in rules:
                keywords = rule.get("keywords", [])
                if isinstance(keywords, str):
                    keywords = [keywords]
                matched = any(k in text for k in keywords)
                if not matched:
                    continue

                # 在触发关键词时尝试记录 unified_msg_origin，供后续主动发送使用
                try:
                    umo = getattr(event, "unified_msg_origin", None)
                    if umo is not None:
                        # 先尝试通过 event.get_sender_id() 获取稳定 id
                        key = None
                        try:
                            if hasattr(event, "get_sender_id"):
                                key = str(event.get_sender_id())
                        except Exception:
                            key = None
                        # 备用：从 unified 对象中提取可能的 id 字段
                        if not key and isinstance(umo, dict):
                            for candidate in ("sender", "user", "target", "id", "user_id"):
                                if candidate in umo:
                                    val = umo.get(candidate)
                                    if isinstance(val, (str, int)):
                                        key = str(val)
                                        break
                        # 最后备用：使用发送者名称
                        if not key:
                            try:
                                key = str(event.get_sender_name())
                            except Exception:
                                key = None

                        if key:
                            self._unified_store[key] = umo
                            try:
                                os.makedirs(os.path.dirname(self.unified_store_path), exist_ok=True)
                                with open(self.unified_store_path, "w", encoding="utf-8") as f:
                                    json.dump(self._unified_store, f, ensure_ascii=False, indent=2)
                                logger.info(f"Saved unified for key {key}")
                            except Exception:
                                logger.exception("写入 unified_store 失败")
                except Exception:
                    logger.exception("记录 unified_msg_origin 失败")

                # 调用外部接口
                url = rule.get("url")
                method = (rule.get("method") or "GET").upper()
                params = rule.get("params") or {}
                # 如果配置要求把事件信息传给接口，构造默认参数
                if rule.get("pass_event"):
                    def _getattr_or_call(obj, name):
                        val = getattr(obj, name, None)
                        if callable(val):
                            try:
                                return val()
                            except Exception:
                                return None
                        return val

                    session_id = _getattr_or_call(event, "session_id") or _getattr_or_call(event, "get_session_id")
                    message_id = _getattr_or_call(event, "message_id") or _getattr_or_call(event, "get_message_id")
                    message = getattr(event, "get_messages", None)
                    try:
                        message_chain = event.get_messages() if callable(getattr(event, "get_messages", None)) else None
                    except Exception:
                        message_chain = None
                    message_str = getattr(event, "message_str", None) or _getattr_or_call(event, "get_message_str")
                    timestamp = getattr(event, "timestamp", None) or _getattr_or_call(event, "get_timestamp")

                    event_params = {
                        "session_id": session_id,
                        "message_id": message_id,
                        "message": message_chain,
                        "message_str": message_str,
                        "timestamp": timestamp,
                    }
                    # 将用户静态 params 与 event params 合并，优先使用 rule.params 明确设置的字段
                    merged = {}
                    merged.update(event_params)
                    merged.update(params or {})
                    params = merged
                headers = rule.get("headers") or {}
                timeout = rule.get("timeout", 10)

                response_data = None
                try:
                    async with aiohttp.ClientSession() as session:
                        if method == "GET":
                            async with session.get(url, params=params, headers=headers, timeout=timeout) as resp:
                                response_data = await resp.json(content_type=None)
                        else:
                            async with session.post(url, json=params, headers=headers, timeout=timeout) as resp:
                                response_data = await resp.json(content_type=None)
                except Exception as e:
                    logger.exception("外部接口调用失败")
                    # 回复接口错误信息（可配置）
                    err_msg = rule.get("on_error") or "接口调用失败"
                    yield event.plain_result(err_msg)
                    return

                # 根据配置的回复类型发送消息，支持 text / image / video / sequence
                reply_type = rule.get("reply_type", "text")
                if reply_type == "text":
                    # 支持通过 jsonpath 或 format 将 response_data 转为文本，这里简单转换为 str
                    content = rule.get("text_template") or str(response_data)
                    chain = [Plain(content)]
                    await event.send(event.chain_result(chain))
                    event.stop_event()
                elif reply_type == "image":
                    # 如果返回中包含图片 url，则发送图片；优先尝试本地文件路径构造
                    image_path = rule.get("image_path") or response_data
                    try:
                        # 如果是本地文件路径，使用 Image.fromFileSystem
                        if isinstance(image_path, str) and os.path.exists(image_path):
                            chain = [Image.fromFileSystem(str(image_path))]
                            await event.send(event.chain_result(chain))
                        else:
                            # 否则直接使用 event 的 image_result（兼容 URL）
                            await event.send(event.image_result(image_path))
                        event.stop_event()
                    except Exception:
                        logger.exception("发送图片失败")
                        await event.send(event.plain_result(rule.get("on_error") or "图片发送失败"))
                        event.stop_event()
                elif reply_type == "video":
                    video_path = rule.get("video_path") or response_data
                    try:
                        if isinstance(video_path, str) and os.path.exists(video_path):
                            chain = [Video.fromFileSystem(str(video_path))]
                            await event.send(event.chain_result(chain))
                        else:
                            if hasattr(event, "video_result"):
                                await event.send(event.video_result(video_path))
                            else:
                                await event.send(event.plain_result(f"[视频] {video_path}"))
                        event.stop_event()
                    except Exception:
                        logger.exception("发送视频失败")
                        await event.send(event.plain_result(rule.get("on_error") or "视频发送失败"))
                        event.stop_event()
                elif reply_type == "sequence":
                    # 允许配置多条消息按顺序发送
                    items = rule.get("items") or []
                    for it in items:
                        t = it.get("type")
                        if t == "text":
                            await event.send(event.plain_result(it.get("content", "")))
                        elif t == "image":
                            await event.send(event.image_result(it.get("content", "")))
                    event.stop_event()
                else:
                    await event.send(event.plain_result(str(response_data)))
                    event.stop_event()
                # 只触发第一个匹配规则
                return
        except Exception:
            logger.exception("on_message 处理失败")

    async def _start_http_server(self):
        # 简单的 aiohttp HTTP 接口，暴露一个 /send_message 路由
        try:
            app = web.Application()

            async def send_message_handler(request):
                try:
                    data = await request.json()
                except Exception:
                    return web.json_response({"error": "invalid json"}, status=400)
                # 支持两种调用方式：
                # 1) 提供 unified_msg_origin（完整目标对象），并提供 type/content
                # 2) 提供 user_id（简化）
                unified = data.get("unified_msg_origin")
                msg_type = data.get("type", "text")
                content = data.get("content")
                user_id = data.get("user_id")

                if unified:
                    # 构造 MessageChain 并调用 context.send_message
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
                        # 这里 unified 应为从外部传入的 dict/序列化对象，直接传给 context.send_message
                        await self.context.send_message(unified, mc)
                        return web.json_response({"ok": True})
                    except Exception:
                        logger.exception("使用 unified_msg_origin 发送消息失败")
                        return web.json_response({"ok": False}, status=500)

                # fallback: 使用 user_id
                if not user_id or not content:
                    return web.json_response({"error": "user_id (or unified_msg_origin) and content required"}, status=400)

                ok = await self._send_to_user(user_id, msg_type, content)
                return web.json_response({"ok": ok})

            app.router.add_post("/send_message", send_message_handler)
            # 返回当前配置
            async def get_config_handler(request):
                return web.json_response(self._config)

            async def list_unified_handler(request):
                return web.json_response(self._unified_store)

            async def delete_unified_handler(request):
                try:
                    data = await request.json()
                except Exception:
                    return web.json_response({"error": "invalid json"}, status=400)
                key = data.get("key")
                if not key:
                    return web.json_response({"error": "key required"}, status=400)
                if key in self._unified_store:
                    del self._unified_store[key]
                    try:
                        with open(self.unified_store_path, "w", encoding="utf-8") as f:
                            json.dump(self._unified_store, f, ensure_ascii=False, indent=2)
                    except Exception:
                        logger.exception("删除 unified 后写文件失败")
                    return web.json_response({"ok": True})
                return web.json_response({"ok": False, "error": "not found"}, status=404)

            async def update_config_handler(request):
                try:
                    data = await request.json()
                except Exception:
                    return web.json_response({"error": "invalid json"}, status=400)
                # 保存到 configs/config.json
                try:
                    config_dir = os.path.dirname(self.config_path)
                    os.makedirs(config_dir, exist_ok=True)
                    with open(self.config_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    # 重新加载
                    await self.load_config()
                    return web.json_response({"ok": True})
                except Exception:
                    logger.exception("保存配置失败")
                    return web.json_response({"ok": False}, status=500)

            app.router.add_get("/get_config", get_config_handler)
            app.router.add_post("/update_config", update_config_handler)
            app.router.add_get("/list_unified", list_unified_handler)
            app.router.add_post("/delete_unified", delete_unified_handler)

            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", int(self._config.get("http_port", 6180)))
            await site.start()
            self._http_runner = runner
            logger.info("HTTP server started on port %s", self._config.get("http_port", 8080))
        except Exception:
            logger.exception("Failed to start HTTP server")

    async def _send_to_user(self, user_id, msg_type, content):
        # 尝试使用若干常见方法发送私聊消息，适配不同的 astrbot 版本
        try:
            # 优先尝试使用保存的 unified（以 user_id 为键）
            try:
                stored_unified = None
                if user_id and self._unified_store:
                    stored_unified = self._unified_store.get(str(user_id))
                if stored_unified and hasattr(self.context, "send_message"):
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
                    try:
                        await self.context.send_message(stored_unified, mc)
                        return True
                    except Exception:
                        logger.debug("使用保存的 unified 发送失败，继续回退")
                        pass
            except Exception:
                logger.exception("尝试使用保存的 unified 发送时异常")

            # 最常见的方式：context 提供 send_private_message
            if hasattr(self.context, "send_private_message"):
                if msg_type == "text":
                    await self.context.send_private_message(user_id, content)
                    return True
                elif msg_type == "image":
                    await self.context.send_private_message(user_id, {"type": "image", "data": content})
                    return True
                elif msg_type == "video":
                    await self.context.send_private_message(user_id, {"type": "video", "data": content})
                    return True

            # 另一种可能：context.bot
            bot = getattr(self.context, "bot", None)
            if bot and hasattr(bot, "send_private_message"):
                if msg_type == "text":
                    await bot.send_private_message(user_id, content)
                    return True

            # 最后尝试通过 SDK 的低层客户端
            client = getattr(self.context, "client", None)
            if client and hasattr(client, "send_private_message"):
                if msg_type == "text":
                    await client.send_private_message(user_id, content)
                    return True

            logger.warning("没有找到发送私聊的方法，请根据 astrbot 运行时适配发送实现")
            return False
        except Exception:
            logger.exception("发送私聊失败")
            return False

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
