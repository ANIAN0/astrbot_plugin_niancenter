"""
关键字处理器 - 处理特殊关键字触发的事件
"""
from datetime import datetime
from typing import Any, Optional


class KeywordHandler:
    """处理各种特殊关键字的事件"""
    
    def __init__(self, unified_store, logger):
        self.unified_store = unified_store
        self.logger = logger
    
    async def login(self, event: Any) -> bool:
        """
        处理N登录关键字
        记录用户的session_id、group_id、sender、unified_msg_origin等信息
        """
        try:
            # 提取用户信息
            session_id = getattr(event, "session_id", None)
            group_id = getattr(event, "group_id", None)
            sender_id = None
            sender_name = None
            unified_msg_origin = getattr(event, "unified_msg_origin", None)
            
            # 尝试获取sender_id
            try:
                if hasattr(event, "get_sender_id"):
                    sender_id = event.get_sender_id()
            except Exception:
                pass
            
            # 尝试获取sender_name
            try:
                if hasattr(event, "get_sender_name"):
                    sender_name = event.get_sender_name()
            except Exception:
                pass
            
            # 构建用户记录
            user_record = {
                "session_id": session_id,
                "group_id": group_id,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "unified_msg_origin": unified_msg_origin,
                "login_time": datetime.utcnow().isoformat() + "Z"
            }
            
            # 使用session_id或sender_id作为key
            store_key = session_id or sender_id or sender_name
            if store_key:
                self.unified_store.set(str(store_key), user_record)
                self.logger.info(f"用户登录记录: {store_key}")
                await event.send(event.plain_result(f"✓ 登录成功，session_id: {session_id}"))
                return True
            else:
                await event.send(event.plain_result("✗ 无法获取用户标识"))
                return False
                
        except Exception as e:
            self.logger.exception(f"处理登录关键字失败: {e}")
            try:
                await event.send(event.plain_result("✗ 登录处理失败"))
            except Exception:
                pass
            return False
    
    async def handle(self, keyword: str, event: Any) -> bool:
        """
        统一的关键字处理入口
        根据关键字找到对应的handler方法并执行
        
        Args:
            keyword: 触发的关键字
            event: 事件对象
            
        Returns:
            是否处理成功
        """
        handler_name = None
        
        # 标准化关键字处理映射
        handler_map = {
            "N登录": "login",
            "n登录": "login",
        }
        
        handler_name = handler_map.get(keyword)
        
        if handler_name and hasattr(self, handler_name):
            handler = getattr(self, handler_name)
            return await handler(event)
        
        return False
