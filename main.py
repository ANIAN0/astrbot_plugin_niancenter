import astrbot.api.message_components as Comp
from astrbot.core.message.components import BaseMessageComponent, Image, Plain, Record, Video
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult, MessageChain
from astrbot.core.star.filter.event_message_type import EventMessageType
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import json
import asyncio
import os
from .core.unified_store import UnifiedStore
from .handlers.message_handler import MessageHandler
from .http_server import HttpServer

@register("helloworld", "YourName", "一个简单的 Hello World 插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config_path = os.path.join(os.path.dirname(__file__), "configs", "config.json")
        self._config = {}
        self._http_runner = None
        self.unified_store_path = os.path.join(os.path.dirname(__file__), "configs", "unified_store.json")
        self.unified_store = UnifiedStore(self.unified_store_path)
        self.message_handler = MessageHandler(context, self.config_path, self.unified_store, logger)
        self.http_server = HttpServer("0.0.0.0", int(self._config.get("http_port", 6180)), self.config_path, self.unified_store, self.message_handler, logger)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        # 加载本地配置
        await self.load_config()
        # 延后启动 http_server 直到 config 被加载
        # 注意： HttpServer 在 start 时会调用 handler._load_config() 以确保使用最新配置
        asyncio.create_task(self.http_server.start())

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

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    async def on_private_message(self, event: AstrMessageEvent):
        # 将私聊事件交由 handlers/message_handler.py 处理
        try:
            await self.message_handler.match_and_handle(event)
        except Exception:
            logger.exception("message_handler 处理失败")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        try:
            await self.http_server.stop()
        except Exception:
            pass
