import astrbot.api.message_components as Comp
from astrbot.core.message.components import BaseMessageComponent, Image, Plain, Record, Video
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult, MessageChain
from astrbot.core.star.filter.event_message_type import EventMessageType
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import json
import asyncio
import os
from .core.unified_store import UnifiedStore
from .core.task_manager import TaskManager
from .handlers.message_handler import MessageHandler
from .core.logger_manager import LoggerManager
from .core.data_viewer import DataViewer

@register("helloworld", "YourName", "一个简单的 Hello World 插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config_path = os.path.join(os.path.dirname(__file__), "configs", "config.json")
        self._config = {}
        self._http_runner = None
        self.unified_store_path = os.path.join(os.path.dirname(__file__), "configs", "unified_store.json")
        self.unified_store = UnifiedStore(self.unified_store_path)
        self.message_handler = MessageHandler(context, self.config_path, self.unified_store, logger)
        self.http_server = None
        self.task_manager = None
        
        # 初始化配置和日志
        self.plugin_config = config
        self.plugin_dir = os.path.dirname(__file__)
        self.log_manager = LoggerManager(self.plugin_dir, config)
        self.data_viewer = DataViewer(self.plugin_dir)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        # 加载本地配置
        await self.load_config()
        
        # 初始化日志系统
        enable_logging = self.plugin_config.get("enable_logging", True)
        log_level = self.plugin_config.get("log_level", "INFO")
        max_log_size = self.plugin_config.get("max_log_size_mb", 10)
        log_backup_count = self.plugin_config.get("log_backup_count", 5)
        
        if enable_logging:
            self.log_manager.setup_file_logging(log_level, max_log_size, log_backup_count)
            self.log_manager.log(f"插件日志已启用，级别: {log_level}", "INFO")
        
        # 初始化任务管理器
        enable_polling = self.plugin_config.get("enable_task_polling", False)
        if enable_polling:
            plugin_dir = os.path.dirname(__file__)
            self.task_manager = TaskManager(
                plugin_dir,
                self.plugin_config,
                self.log_manager,
                self.context
            )
            
            try:
                await self.task_manager.start_polling()
                self.log_manager.log("任务管理器已启动", "INFO")
            except Exception as e:
                self.log_manager.log(f"启动任务管理器失败: {e}", "ERROR")
        else:
            self.log_manager.log("任务轮询已禁用，未启动任务管理器", "INFO")

    @filter.command("niancenter_logs")
    async def view_logs(self, event: AstrMessageEvent):
        """查看插件日志"""
        try:
            logs = self.log_manager.get_recent_logs(50)
            if logs:
                yield event.plain_result(f"最近日志\n{logs}")
            else:
                yield event.plain_result("暂无日志记录")
        except Exception as e:
            yield event.plain_result(f"获取日志失败: {e}")

    @filter.command("niancenter_tasks")
    async def view_tasks(self, event: AstrMessageEvent):
        """查看本地任务"""
        try:
            summary = self.data_viewer.get_tasks_summary()
            msg = f"本地任务统计\n"
            msg += f"总数: {summary.get('total', 0)}\n"
            
            status_dist = summary.get('status_distribution', {})
            if status_dist:
                msg += f"任务码\u5206布: {status_dist}\n"
            
            task_types = summary.get('task_types', {})
            if task_types:
                msg += f"类型分布: {task_types}\n"
            
            yield event.plain_result(msg)
        except Exception as e:
            yield event.plain_result(f"获取任务失败: {e}")

    @filter.command("niancenter_origins")
    async def view_origins(self, event: AstrMessageEvent):
        """查看用户映射"""
        try:
            summary = self.data_viewer.get_unified_origins_summary()
            msg = f"本地用户映射统计\n"
            msg += f"总数: {summary.get('total', 0)}\n"
            msg += summary.get('message', '')
            
            yield event.plain_result(msg)
        except Exception as e:
            yield event.plain_result(f"获取用户映射失败: {e}")

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
        # 停止后台任务轮询
        if self.task_manager:
            try:
                await self.task_manager.stop_polling()
                self.log_manager.log("任务管理器已停止", "INFO")
            except Exception as e:
                self.log_manager.log(f"停止任务管理器失败: {e}", "ERROR")
        
        # 关闭日志
        self.log_manager.close()
