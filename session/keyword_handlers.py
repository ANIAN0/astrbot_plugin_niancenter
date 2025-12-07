"""
关键字处理器 - 处理特殊关键字触发的事件
"""
import os
import re
from datetime import datetime
from typing import Any, Optional
from ..users.user_manager import UsersManager
from ..notes.note_manager import NoteManager
from ..todos.todo_manager import TodoManager


class KeywordHandler:
    """处理各种特殊关键字的事件"""
    
    def __init__(self, context, unified_store, logger, data_dir: str, plugin_config: dict):
        self.context = context
        self.unified_store = unified_store
        self.logger = logger
        self.data_dir = data_dir  # 数据目录
        self.plugin_config = plugin_config or {}
        self.users_manager = UsersManager(data_dir, logger, self.plugin_config)
        
        # 缓存NoteManager实例（按用户）
        self._note_managers = {}
        
        # 初始化TodoManager（共享实例）
        user_data_dir = os.path.join(data_dir, "users")
        self.todo_manager = TodoManager(user_data_dir, logger)
        
        # 加载关键字配置
        self._load_keyword_config()
    
    def _load_keyword_config(self):
        """从配置文件加载关键字映射"""
        import json
        
        # 默认关键字映射（作为备用）
        default_map = {
            "N登录": "create_user",
            "n登录": "create_user",
            "n修改密码": "change_password",
            "n记录": "add_note",
            "n搜索": "search_note",
            "nt1": "trigger_note_summary",
            "n待办": "add_todo",
            "n跟进": "add_follow_up",
            "n关闭": "close_todo",
            "n看待办": "list_todos",
            "nt2": "trigger_todo_summary",
            "n当前时间": "get_current_time",
        }
        
        try:
            # 获取配置文件路径
            config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "keywords.json")
            
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    keyword_config = json.load(f)
                
                # 从配置构建关键字映射
                self.handler_map = {}
                for keyword, config in keyword_config.items():
                    handler_name = config.get("handler")
                    if handler_name:
                        self.handler_map[keyword] = handler_name
                        # 支持 /keyword 和 keyword 两种格式
                        if keyword.startswith("n"):
                            # N登录 特殊处理
                            if keyword == "n登录":
                                self.handler_map["N登录"] = handler_name
                
                self.logger.info(f"从配置文件加载了 {len(self.handler_map)} 个关键字映射")
            else:
                self.logger.warning(f"关键字配置文件不存在: {config_file}，使用默认配置")
                self.handler_map = default_map
                
        except Exception as e:
            self.logger.exception(f"加载关键字配置失败: {e}，使用默认配置")
            self.handler_map = default_map
    
    def reload_keyword_config(self):
        """重新加载关键字配置（用于热更新）"""
        self._load_keyword_config()
        self.logger.info("关键字配置已重新加载")
    
    
    def _get_note_manager(self, user_id: str) -> NoteManager:
        """获取或创建用户的NoteManager实例"""
        if user_id not in self._note_managers:
            user_dir = self.users_manager._user_dir(user_id)
            self._note_managers[user_id] = NoteManager(user_dir, self.logger)
        return self._note_managers[user_id]
    
    def _parse_note_command(self, message_str: str) -> dict:
        """
        解析记录命令
        格式: n记录 记录内容 # 分组 @关键字
        
        Returns:
            {"content": str, "group": str, "keywords": str}
        """
        # 移除命令前缀
        text = message_str.strip()
        if text.startswith("/n记录"):
            text = text[4:].strip()
        elif text.startswith("n记录"):
            text = text[3:].strip()
        
        # 提取分组（# 后面的内容，到 @ 或结尾）
        group = None
        group_match = re.search(r'#\s*([^@]+?)(?=@|$)', text)
        if group_match:
            group = group_match.group(1).strip()
            # 移除分组标记
            text = text.replace(group_match.group(0), "").strip()
        
        # 提取关键字（@ 后面的内容）
        keywords = None
        keyword_match = re.search(r'@\s*(.+?)$', text)
        if keyword_match:
            keywords = keyword_match.group(1).strip()
            # 移除关键字标记
            text = text[:keyword_match.start()].strip()
        
        # 剩余的就是内容
        content = text.strip()
        
        return {
            "content": content,
            "group": group,
            "keywords": keywords
        }
    
    async def add_note(self, event: Any) -> bool:
        """
        添加笔记记录
        格式: n记录 记录内容 # 分组 @关键字
        """
        try:
            message_str = getattr(event, "message_str", "") or ""
            user_id = self.users_manager._derive_user_id(event)
            
            # 检查用户是否存在
            if not self.users_manager.user_exists(user_id):
                await event.send(event.plain_result("✗ 请先使用 /n登录 创建账户"))
                return False
            
            # 解析命令
            parsed = self._parse_note_command(message_str)
            content = parsed["content"]
            group = parsed["group"]
            keywords = parsed["keywords"]
            
            # 如果内容为空且消息中没有其他组件，提示用户
            if not content:
                message_chain = event.get_messages()
                has_media = any(not hasattr(c, 'text') for c in message_chain)
                if not has_media:
                    await event.send(event.plain_result("✗ 请提供记录内容"))
                    return False
            
            # 获取笔记管理器
            note_manager = self._get_note_manager(user_id)
            
            # 添加笔记
            result = await note_manager.add_note(user_id, event, content, group, keywords)
            
            if result["success"]:
                note_count = result["note_count"]
                group_name = result["group"]
                msg = f"✓ 记录成功\n分组: {group_name}\n条数: {note_count}"
                await event.send(event.plain_result(msg))
                return True
            else:
                error_msg = result.get("error", "未知错误")
                await event.send(event.plain_result(f"✗ 记录失败: {error_msg}"))
                return False
                
        except Exception as e:
            self.logger.exception(f"添加笔记失败: {e}")
            try:
                await event.send(event.plain_result("✗ 记录失败"))
            except Exception:
                pass
            return False
    
    async def search_note(self, event: Any) -> bool:
        """
        搜索笔记
        格式: n搜索 关键字
        """
        try:
            message_str = getattr(event, "message_str", "") or ""
            user_id = self.users_manager._derive_user_id(event)
            
            # 检查用户是否存在
            if not self.users_manager.user_exists(user_id):
                await event.send(event.plain_result("✗ 请先使用 /n登录 创建账户"))
                return False
            
            # 提取搜索关键字
            text = message_str.strip()
            if text.startswith("/n搜索"):
                keywords = text[4:].strip()
            elif text.startswith("n搜索"):
                keywords = text[3:].strip()
            else:
                keywords = ""
            
            if not keywords:
                await event.send(event.plain_result("✗ 请提供搜索关键字"))
                return False
            
            # 搜索笔记
            note_manager = self._get_note_manager(user_id)
            results = note_manager.search_notes(keywords)
            
            if not results:
                await event.send(event.plain_result("未找到相关记录"))
                return True
            
            # 发送搜索结果
            await event.send(event.plain_result(f"找到 {len(results)} 条记录:"))
            
            for note in results[:10]:  # 最多返回10条
                content_type = note.get("content_type", "text")
                content = note.get("content", "")
                group = note.get("group", "")
                created_at = note.get("created_at", "")
                
                # 使用时间作为标识
                time_str = created_at[:19].replace("T", " ") if created_at else "未知时间"
                
                # 文本类型直接发送
                if content_type == "text":
                    # 预览内容（最多100字）
                    preview = content[:100] + "..." if len(content) > 100 else content
                    msg = f"[{group}] {time_str}\n{preview}"
                    await event.send(event.plain_result(msg))
                
                # 媒体类型发送文件
                elif content_type == "image":
                    storage_path = note.get("storage_path", "")
                    if storage_path:
                        import os
                        full_path = os.path.join(self.users_manager._user_dir(user_id), storage_path)
                        if os.path.exists(full_path):
                            await event.send(event.image_result(full_path))
                        else:
                            await event.send(event.plain_result(f"[{group}] {time_str}（图片文件不存在）"))
                
                elif content_type == "video":
                    storage_path = note.get("storage_path", "")
                    if storage_path:
                        import os
                        full_path = os.path.join(self.users_manager._user_dir(user_id), storage_path)
                        msg = f"[{group}] {time_str}\n视频文件: {full_path}"
                        await event.send(event.plain_result(msg))
                
                elif content_type in ["audio", "file"]:
                    storage_path = note.get("storage_path", "")
                    msg = f"[{group}] {time_str}\n文件路径: {storage_path}"
                    await event.send(event.plain_result(msg))
            
            return True
            
        except Exception as e:
            self.logger.exception(f"搜索笔记失败: {e}")
            try:
                await event.send(event.plain_result("✗ 搜索失败"))
            except Exception:
                pass
            return False
    
    async def create_user(self, event: Any) -> bool:
        return await self.users_manager.create_user(event)
    
    async def change_password(self, event: Any) -> bool:
        return await self.users_manager.change_password(event)
    
    def _parse_todo_command(self, message_str: str) -> dict:
        """
        解析待办命令
        格式: n待办 待办内容 by预计完成时间
        
        Returns:
            {"content": str, "estimated_time": str}
        """
        # 移除命令前缀
        text = message_str.strip()
        if text.startswith("/n待办"):
            text = text[4:].strip()
        elif text.startswith("n待办"):
            text = text[3:].strip()
        
        # 提取时间（by 后面的内容，空格可选）
        estimated_time = None
        time_match = re.search(r'by\s*(.+?)$', text, re.IGNORECASE)
        if time_match:
            estimated_time = time_match.group(1).strip()
            # 移除时间标记
            text = text[:time_match.start()].strip()
        
        # 剩余的就是内容
        content = text.strip()
        
        return {
            "content": content,
            "estimated_time": estimated_time
        }
    
    async def add_todo(self, event: Any) -> bool:
        """
        添加待办
        格式: n待办 待办内容 by预计完成时间
        """
        try:
            message_str = getattr(event, "message_str", "") or ""
            user_id = self.users_manager._derive_user_id(event)
            
            # 检查用户是否存在
            if not self.users_manager.user_exists(user_id):
                await event.send(event.plain_result("✗ 请先使用 /n登录 创建账户"))
                return False
            
            # 解析命令
            parsed = self._parse_todo_command(message_str)
            content = parsed["content"]
            estimated_time = parsed["estimated_time"]
            
            # 调试日志
            self.logger.info(f"[待办解析] 原始消息: {message_str}")
            self.logger.info(f"[待办解析] 内容: {content}, 时间: {estimated_time}")
            
            if not content:
                await event.send(event.plain_result("✗ 请提供待办内容"))
                return False
            
            # 添加待办
            result = self.todo_manager.add_todo(user_id, content, estimated_time)
            
            if result["success"]:
                display_id = result["display_id"]
                est_time = result["estimated_time"]
                msg = f"✓ 待办创建成功\n序号: {display_id}\n预计完成: {est_time}"
                await event.send(event.plain_result(msg))
                return True
            else:
                error_msg = result.get("error", "未知错误")
                await event.send(event.plain_result(f"✗ 创建失败: {error_msg}"))
                return False
                
        except Exception as e:
            self.logger.exception(f"添加待办失败: {e}")
            try:
                await event.send(event.plain_result("✗ 创建失败"))
            except Exception:
                pass
            return False
    
    async def add_follow_up(self, event: Any) -> bool:
        """
        添加待办跟进
        格式: n跟进 序号 跟进内容
        """
        try:
            message_str = getattr(event, "message_str", "") or ""
            user_id = self.users_manager._derive_user_id(event)
            
            # 检查用户是否存在
            if not self.users_manager.user_exists(user_id):
                await event.send(event.plain_result("✗ 请先使用 /n登录 创建账户"))
                return False
            
            # 解析命令：提取序号
            text = message_str.strip()
            if text.startswith("/n跟进"):
                text = text[4:].strip()
            elif text.startswith("n跟进"):
                text = text[3:].strip()
            
            # 提取序号（第一个数字）
            match = re.match(r'(\d+)\s*(.*)', text)
            if not match:
                await event.send(event.plain_result("✗ 请提供待办序号"))
                return False
            
            display_id = int(match.group(1))
            content = match.group(2).strip()
            
            # 添加跟进
            result = self.todo_manager.add_follow_up(user_id, display_id, event, content)
            
            if result["success"]:
                follow_up_count = result["follow_up_count"]
                msg = f"✓ 跟进成功\n序号: {display_id}\n跟进条目: {follow_up_count}"
                await event.send(event.plain_result(msg))
                return True
            else:
                error_msg = result.get("error", "未知错误")
                await event.send(event.plain_result(f"✗ 跟进失败: {error_msg}"))
                return False
                
        except Exception as e:
            self.logger.exception(f"添加跟进失败: {e}")
            try:
                await event.send(event.plain_result("✗ 跟进失败"))
            except Exception:
                pass
            return False
    
    async def close_todo(self, event: Any) -> bool:
        """
        关闭待办
        格式: n关闭 序号
        """
        try:
            message_str = getattr(event, "message_str", "") or ""
            user_id = self.users_manager._derive_user_id(event)
            
            # 检查用户是否存在
            if not self.users_manager.user_exists(user_id):
                await event.send(event.plain_result("✗ 请先使用 /n登录 创建账户"))
                return False
            
            # 提取序号
            text = message_str.strip()
            if text.startswith("/n关闭"):
                text = text[4:].strip()
            elif text.startswith("n关闭"):
                text = text[3:].strip()
            
            # 提取数字
            match = re.match(r'(\d+)', text)
            if not match:
                await event.send(event.plain_result("✗ 请提供待办序号"))
                return False
            
            display_id = int(match.group(1))
            
            # 关闭待办
            result = self.todo_manager.close_todo(user_id, display_id)
            
            if result["success"]:
                msg = f"✓ 待办已关闭\n序号: {display_id}"
                await event.send(event.plain_result(msg))
                return True
            else:
                error_msg = result.get("error", "未知错误")
                await event.send(event.plain_result(f"✗ 关闭失败: {error_msg}"))
                return False
                
        except Exception as e:
            self.logger.exception(f"关闭待办失败: {e}")
            try:
                await event.send(event.plain_result("✗ 关闭失败"))
            except Exception:
                pass
            return False
    
    async def list_todos(self, event: Any) -> bool:
        """
        查询待办
        格式: n看待办
        """
        try:
            user_id = self.users_manager._derive_user_id(event)
            
            # 检查用户是否存在
            if not self.users_manager.user_exists(user_id):
                await event.send(event.plain_result("✗ 请先使用 /n登录 创建账户"))
                return False
            
            # 获取待办列表
            todos = self.todo_manager.list_todos(user_id)
            
            if not todos:
                await event.send(event.plain_result("暂无进行中的待办"))
                return True
            
            # 构建消息
            msg_lines = [f"当前共有 {len(todos)} 个进行中的待办:\n"]
            for todo in todos:
                display_id = todo.get("display_id", 0)
                content = todo.get("content", "")
                est_time = todo.get("estimated_finish_time", "")
                follow_ups = todo.get("follow_ups", [])
                
                # 格式化时间
                time_str = ""
                if est_time:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(est_time.replace("Z", "+00:00"))
                        time_str = dt.strftime("%m-%d %H:%M")
                    except:
                        time_str = est_time[:16]
                
                # 构建待办信息
                todo_line = f"{display_id}. {content}"
                if time_str:
                    todo_line += f" (by {time_str})"
                if follow_ups:
                    todo_line += f" [跟进{len(follow_ups)}条]"
                
                msg_lines.append(todo_line)
            
            await event.send(event.plain_result("\n".join(msg_lines)))
            return True
            
        except Exception as e:
            self.logger.exception(f"查询待办失败: {e}")
            try:
                await event.send(event.plain_result("✗ 查询失败"))
            except Exception:
                pass
            return False
    
    async def get_current_time(self, event: Any) -> bool:
        """
        获取当前服务器时间
        格式: n当前时间
        """
        try:
            from datetime import datetime
            import time
            
            # 获取本地时间
            local_now = datetime.now()
            
            # 获取UTC时间
            utc_now = datetime.utcnow()
            
            # 获取时区信息
            timezone_offset = time.timezone if not time.daylight else time.altzone
            timezone_hours = -timezone_offset // 3600
            timezone_sign = "+" if timezone_hours >= 0 else "-"
            timezone_str = f"UTC{timezone_sign}{abs(timezone_hours)}"
            
            msg = f"""🕒 服务器时间信息

本地时间: {local_now.strftime("%Y-%m-%d %H:%M:%S")}
UTC时间: {utc_now.strftime("%Y-%m-%d %H:%M:%S")}
时区: {timezone_str}

星期: {local_now.strftime("%A")}
时间戳: {int(local_now.timestamp())}"""
            
            await event.send(event.plain_result(msg))
            return True
            
        except Exception as e:
            self.logger.exception(f"获取当前时间失败: {e}")
            try:
                await event.send(event.plain_result("✗ 获取时间失败"))
            except Exception:
                pass
            return False
    
    async def trigger_note_summary(self, event: Any) -> bool:
        """
        手动触发笔记汇总
        格式: nt1
        """
        user_id = None
        try:
            self.logger.info("开始处理笔记汇总命令")
            user_id = self.users_manager._derive_user_id(event)
            self.logger.info(f"用户ID: {user_id}")
            
            # 检查用户是否存在
            if not self.users_manager.user_exists(user_id):
                self.logger.warning(f"用户不存在: {user_id}")
                await event.send(event.plain_result("✗ 请先使用 /n登录 创建账户"))
                return False
            
            await event.send(event.plain_result("⚙️ 正在生成笔记汇总..."))
            self.logger.info(f"开始生成笔记汇总: {user_id}")
            
            # 获取笔记管理器
            note_manager = self._get_note_manager(user_id)
            
            # 生成今日汇总
            today = datetime.now().strftime("%Y-%m-%d")
            self.logger.info(f"正在生成 {today} 的笔记汇总")
            summary_file = note_manager.generate_daily_summary(today)
            
            if not summary_file:
                self.logger.info(f"今日暂无笔记记录: {user_id}")
                await event.send(event.plain_result("✗ 今日暂无笔记记录"))
                return False
            
            self.logger.info(f"汇总文件生成成功: {summary_file}")
            
            # 发送文件（按官方文档方式）
            from astrbot.api.event import MessageChain
            from astrbot.api.message_components import File
            
            filename = os.path.basename(summary_file)
            
            # 构建消息链：使用 MessageChain 封装列表
            self.logger.info(f"正在发送笔记汇总文件: {filename}")
            
            # 使用 MessageChain 构造器
            message_chain = MessageChain([File(file=summary_file, name=filename)])
            
            await self.context.send_message(event.unified_msg_origin, message_chain)
            self.logger.info(f"手动触发笔记汇总成功: {user_id}")
            return True
            
        except Exception as e:
            self.logger.exception(f"手动触发笔记汇总失败 (user_id={user_id}): {e}")
            await event.send(event.plain_result("✗ 生成汇总失败"))
            return False
    
    async def trigger_todo_summary(self, event: Any) -> bool:
        """
        手动触发待办汇总
        格式: nt2
        """
        user_id = None
        try:
            self.logger.info("开始处理待办汇总命令")
            user_id = self.users_manager._derive_user_id(event)
            self.logger.info(f"用户ID: {user_id}")
            
            # 检查用户是否存在
            if not self.users_manager.user_exists(user_id):
                self.logger.warning(f"用户不存在: {user_id}")
                await event.send(event.plain_result("✗ 请先使用 /n登录 创建账户"))
                return False
            
            await event.send(event.plain_result("⚙️ 正在生成待办汇总..."))
            self.logger.info(f"开始生成待办汇总: {user_id}")
            
            # 生成今日汇总
            today = datetime.now().strftime("%Y-%m-%d")
            
            # 调用 TodoSummaryTask 的生成逻辑
            from ..scheduler.todo_summary_task import TodoSummaryTask
            self.logger.info("创建 TodoSummaryTask 实例")
            summary_task = TodoSummaryTask(
                todo_manager=self.todo_manager,
                users_manager=self.users_manager,
                context=self.context,
                logger=self.logger
            )
            
            self.logger.info(f"正在生成 {today} 的待办汇总")
            summary_file = summary_task._generate_todo_summary(user_id, today)
            
            if not summary_file or not os.path.exists(summary_file):
                self.logger.info(f"今日暂无待办记录: {user_id}, summary_file={summary_file}")
                await event.send(event.plain_result("✗ 今日暂无待办记录"))
                return False
            
            self.logger.info(f"汇总文件生成成功: {summary_file}")
            
            # 发送文件（按官方文档方式）
            from astrbot.api.event import MessageChain
            from astrbot.api.message_components import File
            
            filename = os.path.basename(summary_file)
            
            # 构建消息链：使用 MessageChain 封装列表
            self.logger.info(f"正在发送待办汇总文件: {filename}")
            
            # 使用 MessageChain 构造器
            message_chain = MessageChain([File(file=summary_file, name=filename)])
            
            await self.context.send_message(event.unified_msg_origin, message_chain)
            self.logger.info(f"手动触发待办汇总成功: {user_id}")
            return True
            
        except Exception as e:
            self.logger.exception(f"手动触发待办汇总失败 (user_id={user_id}): {e}")
            await event.send(event.plain_result("✗ 生成汇总失败"))
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
        # 优先匹配长关键字（从消息开头匹配）
        message_str = getattr(event, "message_str", "") or ""
        message_str = message_str.strip()
        
        # 移除可能的 / 前缀
        if message_str.startswith("/"):
            message_str = message_str[1:]
        
        # 按关键字长度从长到短排序匹配（解决 "n记录" 覆盖 "n记录汇总" 的问题）
        sorted_keywords = sorted(self.handler_map.keys(), key=lambda x: len(x), reverse=True)
        
        handler_name = None
        for kw in sorted_keywords:
            if message_str.startswith(kw):
                handler_name = self.handler_map[kw]
                self.logger.debug(f"匹配到关键字: {kw} -> {handler_name}")
                break
        
        if handler_name and hasattr(self, handler_name):
            handler = getattr(self, handler_name)
            return await handler(event)
        
        return False
