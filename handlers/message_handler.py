import os
import json
from typing import Any

from astrbot.api.event import AstrMessageEvent
from ..storage.unified_store import UnifiedStore
from ..session.keyword_handlers import KeywordHandler
from ..storage.cache_utils import CacheUtils
from ..processing.rule_processor import RuleProcessor
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
        
        # 初始化缓存工具
        self.cache_utils = CacheUtils(self.plugin_dir)
        
        # 初始化规则处理器
        self.rule_processor = RuleProcessor(
            logger, unified_store, self._config, 
            self.keywords_config, self.cache_utils, context
        )
    
    def _load_config(self):
        """加载业务规则配置"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
            else:
                self._config = {}
        except Exception:
            self._config = {}

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

        # 交由规则处理器处理
        if await self.rule_processor.handle(event):
            return

    async def send_proactive(self, unified: str, msg_type: str, content: Any):
        """主动发送：`unified` 应为 `unified_msg_origin` 的字符串，按官方文档使用 `context.send_message(unified, MessageChain)`。"""
        try:
            from astrbot.core.message.components import Record
            mc = MessageChain()
            if msg_type == "text":
                mc = mc.message(content)
            elif msg_type == "image":
                if isinstance(content, str) and not os.path.exists(content):
                    content = await self.cache_utils.cache_media(content, "image")
                if hasattr(mc, "file_image") and os.path.exists(content):
                    mc = mc.file_image(content)
                else:
                    mc = mc.message(content)
            elif msg_type == "video":
                if isinstance(content, str) and not os.path.exists(content):
                    content = await self.cache_utils.cache_media(content, "video")
                if hasattr(mc, "file_video") and os.path.exists(content):
                    mc = mc.file_video(content)
                else:
                    mc = mc.message(content)
            elif msg_type == "voice":
                if isinstance(content, str) and not os.path.exists(content):
                    content = await self.cache_utils.cache_media(content, "voice")
                if os.path.exists(content):
                    mc = mc.message(Record(file=content, url=content))
                else:
                    mc = mc.message(content)
            elif msg_type == "file":
                if isinstance(content, str) and not os.path.exists(content):
                    content = await self.cache_utils.cache_media(content, "file")
                if os.path.exists(content):
                    from astrbot.api.message_components import File
                    filename = os.path.basename(content)
                    mc = mc.message(File(file=content, name=filename))
                else:
                    mc = mc.message(content)
            else:
                mc = mc.message(content)
            await self.context.send_message(unified, mc)
        except Exception:
            self.logger.exception("send_proactive 发送失败")


