"""
每日待办总结任务
总结用户今日待办进展，以Markdown格式发送给用户
"""
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List


class TodoSummaryTask:
    """每日待办总结任务"""
    
    def __init__(self, todo_manager, users_manager, context, logger):
        """
        初始化待办总结任务
        
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
        self.is_running = False
        self.task = None
    
    def _generate_todo_summary(self, user_id: str, date_str: str = None) -> str:
        """
        生成待办总结Markdown文件
        
        Args:
            user_id: 用户ID
            date_str: 日期字符串（YYYY-MM-DD），默认为今天
            
        Returns:
            总结文件路径，失败返回None
        """
        try:
            if not date_str:
                date_str = datetime.now().strftime("%Y-%m-%d")
            
            # 获取所有待办
            todos_data = self.todo_manager._load_todos(user_id)
            all_todos = todos_data.get("todos", [])
            
            # 筛选今日相关的待办
            today_created = []  # 今日创建
            today_updated = []  # 今日有跟进
            today_completed = []  # 今日完成
            still_active = []  # 仍在进行中
            
            for todo in all_todos:
                # 检查创建时间
                created_at = todo.get("created_at", "")
                if created_at.startswith(date_str):
                    today_created.append(todo)
                
                # 检查完成时间
                finished_at = todo.get("finished_at")
                if finished_at and finished_at.startswith(date_str):
                    today_completed.append(todo)
                
                # 检查跟进时间
                follow_ups = todo.get("follow_ups", [])
                for fu in follow_ups:
                    fu_created_at = fu.get("created_at", "")
                    if fu_created_at.startswith(date_str):
                        if todo not in today_updated:
                            today_updated.append(todo)
                        break
                
                # 进行中的待办
                if todo.get("status") == "进行中":
                    still_active.append(todo)
            
            # 如果今日没有任何活动，不生成总结
            if not today_created and not today_updated and not today_completed:
                return None
            
            # 生成Markdown内容
            md_lines = [
                f"# 待办总结 - {date_str}\n",
                f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
                "---\n"
            ]
            
            # 今日创建的待办
            if today_created:
                md_lines.append(f"\n## 📝 今日新增 ({len(today_created)}个)\n")
                for todo in today_created:
                    display_id = todo.get("display_id", 0)
                    content = todo.get("content", "")
                    status = todo.get("status", "")
                    est_time = todo.get("estimated_finish_time", "")
                    
                    time_str = ""
                    if est_time:
                        try:
                            dt = datetime.fromisoformat(est_time.replace("Z", "+00:00"))
                            time_str = dt.strftime("%m-%d %H:%M")
                        except:
                            pass
                    
                    status_emoji = "✅" if status == "已完成" else "⏳"
                    md_lines.append(f"- {status_emoji} [{display_id}] {content}")
                    if time_str:
                        md_lines.append(f"  - 预计: {time_str}")
                    md_lines.append("")
            
            # 今日有跟进的待办
            if today_updated:
                md_lines.append(f"\n## 🔄 今日跟进 ({len(today_updated)}个)\n")
                for todo in today_updated:
                    display_id = todo.get("display_id", 0)
                    content = todo.get("content", "")
                    follow_ups = todo.get("follow_ups", [])
                    
                    # 今日的跟进
                    today_fus = [
                        fu for fu in follow_ups 
                        if fu.get("created_at", "").startswith(date_str)
                    ]
                    
                    md_lines.append(f"- [{display_id}] {content}")
                    md_lines.append(f"  - 今日跟进 {len(today_fus)} 条:")
                    for fu in today_fus:
                        fu_content = fu.get("content", "")
                        fu_type = fu.get("type", "text")
                        fu_time = fu.get("created_at", "")[:16].replace("T", " ")
                        
                        if fu_type == "text":
                            preview = fu_content[:50] + "..." if len(fu_content) > 50 else fu_content
                            md_lines.append(f"    - [{fu_time}] {preview}")
                        else:
                            md_lines.append(f"    - [{fu_time}] {fu_type}附件")
                    md_lines.append("")
            
            # 今日完成的待办
            if today_completed:
                md_lines.append(f"\n## ✅ 今日完成 ({len(today_completed)}个)\n")
                for todo in today_completed:
                    display_id = todo.get("display_id", 0)
                    content = todo.get("content", "")
                    finished_at = todo.get("finished_at", "")
                    
                    finish_time = ""
                    if finished_at:
                        try:
                            dt = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
                            finish_time = dt.strftime("%H:%M")
                        except:
                            pass
                    
                    md_lines.append(f"- ✅ [{display_id}] {content}")
                    if finish_time:
                        md_lines.append(f"  - 完成于: {finish_time}")
                    md_lines.append("")
            
            # 待办概览
            md_lines.append(f"\n## 📊 待办概览\n")
            md_lines.append(f"- 进行中: {len(still_active)} 个")
            md_lines.append(f"- 今日新增: {len(today_created)} 个")
            md_lines.append(f"- 今日完成: {len(today_completed)} 个")
            md_lines.append(f"- 完成率: {len(today_completed) / max(1, len(today_created)) * 100:.1f}%")
            
            # 保存文件
            user_dir = self.users_manager._user_dir(user_id)
            summaries_dir = os.path.join(user_dir, "todo_summaries")
            os.makedirs(summaries_dir, exist_ok=True)
            
            summary_file = os.path.join(summaries_dir, f"summary_{date_str}.md")
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write("\n".join(md_lines))
            
            return summary_file
            
        except Exception as e:
            self.logger.exception(f"生成待办总结失败: {e}")
            return None
    
    async def _send_summary_to_user(self, user_id: str, summary_file: str):
        """
        发送总结文件给用户
        
        Args:
            user_id: 用户ID
            summary_file: 总结文件路径
        """
        try:
            # 读取用户配置获取unified_msg_origin
            user_dir = self.users_manager._user_dir(user_id)
            config_file = os.path.join(user_dir, "config.json")
            
            if not os.path.exists(config_file):
                return
            
            import json
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            unified_msg_origin = config.get("unified_msg_origin")
            if not unified_msg_origin:
                return
            
            # 读取总结内容
            with open(summary_file, "r", encoding="utf-8") as f:
                summary_content = f.read()
            
            # 发送消息（发送文件方式）
            from astrbot.api.event import MessageChain
            from astrbot.api.message_components import File
            
            try:
                # 构建消息：发送文件
                filename = os.path.basename(summary_file)
                
                self.logger.info(f"开始发送待办总结: {user_id}, 文件: {filename}")
                
                # 使用 MessageChain 构造器封装 File 组件
                message_chain = MessageChain([File(file=summary_file, name=filename)])
                await self.context.send_message(unified_msg_origin, message_chain)
                
                self.logger.info(f"已发送待办总结给用户: {user_id}")
                
            except Exception as send_e:
                self.logger.exception(f"发送待办总结失败: {user_id} - {send_e}")
                raise
            
        except Exception as e:
            self.logger.exception(f"发送总结失败 (用户: {user_id}): {e}")
    
    async def _generate_daily_summaries(self):
        """生成所有用户的每日待办总结"""
        try:
            user_data_dir = self.users_manager.user_data_dir
            if not os.path.exists(user_data_dir):
                return
            
            today = datetime.now().strftime("%Y-%m-%d")
            
            # 遍历所有用户
            for user_folder in os.listdir(user_data_dir):
                if not user_folder.startswith("u_"):
                    continue
                
                user_id = user_folder
                
                try:
                    # 检查用户是否存在
                    if not self.users_manager.user_exists(user_id):
                        continue
                    
                    # 生成总结
                    summary_file = self._generate_todo_summary(user_id, today)
                    
                    if summary_file:
                        self.logger.info(f"生成待办总结: {user_id}, 文件: {summary_file}")
                        # 发送给用户
                        await self._send_summary_to_user(user_id, summary_file)
                    
                except Exception as e:
                    self.logger.exception(f"处理用户 {user_id} 的总结失败: {e}")
            
        except Exception as e:
            self.logger.exception(f"生成每日待办总结失败: {e}")
    
    async def _schedule_task(self, hour: int = 22, minute: int = 30):
        """
        定时任务调度器
        
        Args:
            hour: 执行小时 (0-23)
            minute: 执行分钟 (0-59)
        """
        while self.is_running:
            try:
                now = datetime.now()
                target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # 如果目标时间已过，设置为明天
                if now >= target_time:
                    target_time += timedelta(days=1)
                
                # 计算等待时间
                wait_seconds = (target_time - now).total_seconds()
                
                self.logger.info(f"待办总结任务将在 {target_time.strftime('%Y-%m-%d %H:%M:%S')} 执行")
                
                # 等待到目标时间
                await asyncio.sleep(wait_seconds)
                
                # 执行总结任务
                if self.is_running:
                    self.logger.info("开始执行每日待办总结任务")
                    await self._generate_daily_summaries()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"定时任务执行失败: {e}")
                # 出错后等待1小时再重试
                await asyncio.sleep(3600)
    
    async def start(self, hour: int = 22, minute: int = 30):
        """
        启动定时任务
        
        Args:
            hour: 执行小时 (0-23，默认22点)
            minute: 执行分钟 (0-59，默认30分)
        """
        if self.is_running:
            self.logger.warning("待办总结任务已在运行")
            return
        
        self.is_running = True
        self.task = asyncio.create_task(self._schedule_task(hour, minute))
        self.logger.info(f"待办总结任务已启动，每天 {hour:02d}:{minute:02d} 执行")
    
    async def stop(self):
        """停止定时任务"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("待办总结任务已停止")
