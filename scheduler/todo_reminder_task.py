"""
待办提醒定时任务
每日8点和14点提醒用户当前进行中的待办
"""
import asyncio
from datetime import datetime, time
from typing import Any


class TodoReminderTask:
    """待办提醒定时任务"""
    
    def __init__(self, todo_manager, users_manager, context, logger):
        """
        初始化提醒任务
        
        Args:
            todo_manager: 待办管理器
            users_manager: 用户管理器
            context: AstrBot上下文
            logger: 日志记录器
        """
        self.todo_manager = todo_manager
        self.users_manager = users_manager
        self.context = context
        self.logger = logger
        self.running = False
        self.task = None
    
    async def _send_reminder(self, user_id: str, todos: list, reminder_type: str = "daily"):
        """
        发送待办提醒
        
        Args:
            user_id: 用户ID
            todos: 待办列表
            reminder_type: 提醒类型（daily=定时提醒, due=到期提醒）
        """
        try:
            if not todos:
                return
            
            # 加载用户配置获取消息来源
            user_dir = self.users_manager._user_dir(user_id)
            import os
            import json
            config_path = os.path.join(user_dir, "config.json")
            if not os.path.exists(config_path):
                return
            
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            
            unified_msg_origin = user_config.get("unified_msg_origin")
            if not unified_msg_origin:
                return
            
            # 构建提醒消息
            if reminder_type == "due":
                # 到期提醒：简洁格式，直接显示
                msg_lines = [f"⏰ 待办到期提醒\n"]
                for todo in todos:
                    display_id = todo.get("display_id", 0)
                    content = todo.get("content", "")
                    est_time = todo.get("estimated_finish_time", "")
                    
                    time_str = ""
                    if est_time:
                        try:
                            dt = datetime.fromisoformat(est_time.replace("Z", "+00:00"))
                            time_str = dt.strftime("%m-%d %H:%M")
                        except:
                            time_str = est_time[:16]
                    
                    msg_lines.append(f"⚠️ 序号 {display_id}: {content}")
                    if time_str:
                        msg_lines.append(f"   预计完成时间: {time_str}")
                    msg_lines.append("   已到达预计完成时间，请及时处理！\n")
                
                reminder_msg = "\n".join(msg_lines)
            else:
                # 定时提醒：详细分类格式
                now = datetime.now()
                overdue_todos = []  # 已到期
                soon_todos = []     # 2小时内到期
                today_todos = []    # 1天内到期
                normal_todos = []   # 正常待办
                
                for todo in todos:
                    est_time = todo.get("estimated_finish_time", "")
                    if not est_time:
                        normal_todos.append(todo)
                        continue
                    
                    try:
                        # 解析预计完成时间（与到期检查保持一致）
                        if isinstance(est_time, str):
                            time_str = est_time.rstrip("Z")
                            if "+" in time_str:
                                time_str = time_str.split("+")[0]
                            dt = datetime.fromisoformat(time_str)
                        else:
                            dt = datetime.fromtimestamp(est_time)
                        
                        # 计算到期时间差（秒）
                        diff = (dt - now).total_seconds()
                        
                        if diff < 0:
                            # 已到期
                            overdue_todos.append(todo)
                        elif diff < 7200:  # 2小时 = 7200秒
                            # 即将到期
                            soon_todos.append(todo)
                        elif diff < 86400:  # 24小时 = 86400秒
                            # 1天内到期
                            today_todos.append(todo)
                        else:
                            # 正常待办
                            normal_todos.append(todo)
                    except Exception as parse_e:
                        self.logger.debug(f"无法解析待办时间: {est_time} - {parse_e}")
                        normal_todos.append(todo)
                
                msg_lines = [f"⏰ 待办提醒 ({len(todos)}个进行中):\n"]
                # 已到期待办（重点提醒）
                if overdue_todos:
                    msg_lines.append(f"⚠️ 【已到期】({len(overdue_todos)}个)")
                for todo in overdue_todos:
                    display_id = todo.get("display_id", 0)
                    content = todo.get("content", "")
                    est_time = todo.get("estimated_finish_time", "")
                    follow_ups = todo.get("follow_ups", [])
                    
                    time_str = ""
                    if est_time:
                        try:
                            dt = datetime.fromisoformat(est_time.replace("Z", "+00:00"))
                            time_str = dt.strftime("%m-%d %H:%M")
                        except:
                            time_str = est_time[:16]
                    
                    todo_line = f"  {display_id}. {content}"
                    if time_str:
                        todo_line += f" (by {time_str})"
                    if follow_ups:
                        todo_line += f" [跟进{len(follow_ups)}条]"
                    
                    msg_lines.append(todo_line)
                msg_lines.append("")
            
                # 即将到期待办（2小时内）
                if soon_todos:
                    msg_lines.append(f"🔴 【即将到期】2小时内）({len(soon_todos)}个)")
                for todo in soon_todos:
                    display_id = todo.get("display_id", 0)
                    content = todo.get("content", "")
                    est_time = todo.get("estimated_finish_time", "")
                    follow_ups = todo.get("follow_ups", [])
                    
                    time_str = ""
                    if est_time:
                        try:
                            dt = datetime.fromisoformat(est_time.replace("Z", "+00:00"))
                            time_str = dt.strftime("%m-%d %H:%M")
                        except:
                            time_str = est_time[:16]
                    
                    todo_line = f"  {display_id}. {content}"
                    if time_str:
                        todo_line += f" (by {time_str})"
                    if follow_ups:
                        todo_line += f" [跟进{len(follow_ups)}条]"
                    
                    msg_lines.append(todo_line)
                msg_lines.append("")
            
                # 1天内到期待办
                if today_todos:
                    msg_lines.append(f"🟡 【今日到期】({len(today_todos)}个)")
                for todo in today_todos:
                    display_id = todo.get("display_id", 0)
                    content = todo.get("content", "")
                    est_time = todo.get("estimated_finish_time", "")
                    follow_ups = todo.get("follow_ups", [])
                    
                    time_str = ""
                    if est_time:
                        try:
                            dt = datetime.fromisoformat(est_time.replace("Z", "+00:00"))
                            time_str = dt.strftime("%m-%d %H:%M")
                        except:
                            time_str = est_time[:16]
                    
                    todo_line = f"  {display_id}. {content}"
                    if time_str:
                        todo_line += f" (by {time_str})"
                    if follow_ups:
                        todo_line += f" [跟进{len(follow_ups)}条]"
                    
                    msg_lines.append(todo_line)
                msg_lines.append("")
            
                # 正常待办
                if normal_todos:
                    msg_lines.append(f"🟢 【正常待办】({len(normal_todos)}个)")
                for todo in normal_todos:
                    display_id = todo.get("display_id", 0)
                    content = todo.get("content", "")
                    est_time = todo.get("estimated_finish_time", "")
                    follow_ups = todo.get("follow_ups", [])
                    
                    time_str = ""
                    if est_time:
                        try:
                            dt = datetime.fromisoformat(est_time.replace("Z", "+00:00"))
                            time_str = dt.strftime("%m-%d %H:%M")
                        except:
                            time_str = est_time[:16]
                    
                    todo_line = f"  {display_id}. {content}"
                    if time_str:
                        todo_line += f" (by {time_str})"
                    if follow_ups:
                        todo_line += f" [跟进{len(follow_ups)}条]"
                    
                    msg_lines.append(todo_line)
            
                reminder_msg = "\n".join(msg_lines)
            
            # 发送消息（使用 context.send_message 方式）
            from astrbot.api.event import MessageChain
            
            try:
                message = MessageChain().message(reminder_msg)
                self.logger.info(f"开始发送待办提醒: {user_id}, 类型: {reminder_type}, 消息长度: {len(reminder_msg)}")
                self.logger.debug(f"提醒消息内容: {reminder_msg[:200]}...")
                
                await self.context.send_message(unified_msg_origin, message)
                
                self.logger.info(f"待办提醒发送成功: {user_id} (type={reminder_type})")
                
                # 记录提醒时间（仅对定时提醒）
                if reminder_type == "daily":
                    todos_data = self.todo_manager._load_todos(user_id)
                    current_time = datetime.utcnow().isoformat() + "Z"
                    for todo in todos_data.get("todos", []):
                        if todo.get("status") == "进行中":
                            if "reminded_at" not in todo:
                                todo["reminded_at"] = []
                            todo["reminded_at"].append(current_time)
                    self.todo_manager._save_todos(user_id, todos_data)
                    
            except Exception as send_e:
                self.logger.exception(f"发送待办提醒失败: {user_id} - {send_e}")
                raise
                
        except Exception as e:
            self.logger.exception(f"发送待办提醒失败: {e}")
    
    async def _run_reminder(self):
        """执行一次提醒"""
        try:
            # 遍历所有用户
            import os
            user_data_dir = self.users_manager.user_data_dir
            if not os.path.exists(user_data_dir):
                return
            
            for user_folder in os.listdir(user_data_dir):
                if not user_folder.startswith("u_"):
                    continue
                
                user_id = user_folder
                
                # 检查用户是否存在
                if not self.users_manager.user_exists(user_id):
                    continue
                
                # 获取进行中的待办
                todos = self.todo_manager.get_active_todos(user_id)
                if todos:
                    await self._send_reminder(user_id, todos)
                    
        except Exception as e:
            self.logger.exception(f"执行待办提醒失败: {e}")
    
    async def _check_due_todos(self):
        """检查到期待办并发送提醒"""
        try:
            import os
            user_data_dir = self.users_manager.user_data_dir
            if not os.path.exists(user_data_dir):
                return
            
            now = datetime.now()
            self.logger.debug(f"[到期检查] 当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 遍历所有用户
            for user_folder in os.listdir(user_data_dir):
                if not user_folder.startswith("u_"):
                    continue
                
                user_id = user_folder
                
                # 检查用户是否存在
                if not self.users_manager.user_exists(user_id):
                    continue
                
                # 加载待办数据
                todos_data = self.todo_manager._load_todos(user_id)
                todos = todos_data.get("todos", [])
                
                # 查找到期且未发送过到期提醒的待办
                due_todos = []
                
                for todo in todos:
                    if todo.get("status") != "进行中":
                        continue
                    
                    est_time = todo.get("estimated_finish_time", "")
                    if not est_time:
                        continue
                    
                    # 检查是否已发送过到期提醒
                    if todo.get("due_reminded", False):
                        continue
                    
                    try:
                        # 解析预计完成时间（参考 TaskManager 的时间解析逻辑）
                        if isinstance(est_time, str):
                            # 移除末尾的 Z 和时区信息
                            time_str = est_time.rstrip("Z")
                            if "+" in time_str:
                                time_str = time_str.split("+")[0]
                            dt = datetime.fromisoformat(time_str)
                        else:
                            dt = datetime.fromtimestamp(est_time)
                        
                        # 计算时间差（秒）
                        diff = (now - dt).total_seconds()
                        
                        # 在到期时间后0-5分钟内发送提醒
                        if 0 <= diff <= 300:  # 5分钟 = 300秒
                            due_todos.append(todo)
                            # 标记为已提醒
                            todo["due_reminded"] = True
                            self.logger.info(f"待办已到期: {todo.get('display_id')} - {todo.get('content')} (差异: {diff}秒)")
                    except Exception as parse_e:
                        self.logger.debug(f"无法解析待办时间: {est_time} - {parse_e}")
                        continue
                
                # 发送到期提醒
                if due_todos:
                    self.logger.info(f"发现 {len(due_todos)} 个到期待办: {user_id}")
                    await self._send_reminder(user_id, due_todos, reminder_type="due")
                    # 保存更新
                    self.todo_manager._save_todos(user_id, todos_data)
                    
        except Exception as e:
            self.logger.exception(f"检查到期待办失败: {e}")
    
    async def _schedule_loop(self):
        """定时任务循环"""
        self.logger.info("待办提醒任务已启动")
        
        while self.running:
            try:
                now = datetime.now()
                current_time = now.time()
                
                # 检查是否为定时提醒时间（8:00 或 14:00）
                morning_reminder = time(8, 0)
                afternoon_reminder = time(14, 0)
                
                # 允许1分钟的时间窗口
                is_morning = (
                    current_time.hour == 8 and 
                    current_time.minute < 1
                )
                is_afternoon = (
                    current_time.hour == 14 and 
                    current_time.minute < 1
                )
                
                if is_morning or is_afternoon:
                    self.logger.info("开始执行定时待办提醒...")
                    await self._run_reminder()
                    # 等待1分钟，避免重复提醒
                    await asyncio.sleep(60)
                else:
                    # 每分钟检查一次到期待办
                    await self._check_due_todos()
                    await asyncio.sleep(60)
                    
            except Exception as e:
                self.logger.exception(f"待办提醒任务异常: {e}")
                await asyncio.sleep(60)
    
    def start(self):
        """启动提醒任务"""
        if not self.running:
            self.running = True
            self.task = asyncio.create_task(self._schedule_loop())
            self.logger.info("待办提醒任务已创建")
    
    def stop(self):
        """停止提醒任务"""
        if self.running:
            self.running = False
            if self.task:
                self.task.cancel()
            self.logger.info("待办提醒任务已停止")
