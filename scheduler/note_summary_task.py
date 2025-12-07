"""
每日笔记汇总任务
"""
import os
import asyncio
from datetime import datetime
from typing import Dict, Any


class NoteSummaryTask:
    """每日笔记汇总任务"""
    
    def __init__(self, data_dir: str, logger, context):
        """
        初始化笔记汇总任务
        
        Args:
            data_dir: 数据目录
            logger: 日志记录器
            context: AstrBot上下文
        """
        self.data_dir = data_dir
        self.logger = logger
        self.context = context
        self.users_dir = os.path.join(data_dir, "users")
        self.is_running = False
        self.task = None
    
    async def _send_summary_to_user(self, user_id: str, summary_file: str):
        """
        发送汇总文件给用户
        
        Args:
            user_id: 用户ID
            summary_file: 汇总文件路径
        """
        try:
            # 读取用户配置获取unified_msg_origin
            user_dir = os.path.join(self.users_dir, user_id)
            config_file = os.path.join(user_dir, "config.json")
            
            if not os.path.exists(config_file):
                return
            
            import json
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            unified_msg_origin = config.get("unified_msg_origin")
            if not unified_msg_origin:
                return
            
            # 读取汇总内容
            with open(summary_file, "r", encoding="utf-8") as f:
                summary_content = f.read()
            
            # 发送消息（发送文件方式）
            from astrbot.api.event import MessageChain
            from astrbot.api.message_components import File
            
            try:
                # 构建消息：发送文件
                filename = os.path.basename(summary_file)
                
                self.logger.info(f"开始发送笔记汇总: {user_id}, 文件: {filename}")
                
                # 使用 MessageChain 构造器封装 File 组件
                message_chain = MessageChain([File(file=summary_file, name=filename)])
                await self.context.send_message(unified_msg_origin, message_chain)
                
                self.logger.info(f"已发送每日汇总给用户: {user_id}")
                
            except Exception as send_e:
                self.logger.exception(f"发送笔记汇总失败: {user_id} - {send_e}")
                raise
            
        except Exception as e:
            self.logger.exception(f"发送汇总失败 (用户: {user_id}): {e}")
    
    async def _generate_daily_summaries(self):
        """生成所有用户的每日汇总"""
        try:
            if not os.path.exists(self.users_dir):
                return
            
            # 遍历所有用户目录
            for user_id in os.listdir(self.users_dir):
                user_dir = os.path.join(self.users_dir, user_id)
                if not os.path.isdir(user_dir):
                    continue
                
                try:
                    # 导入NoteManager
                    from ..notes.note_manager import NoteManager
                    
                    note_manager = NoteManager(user_dir, self.logger)
                    
                    # 获取今日笔记
                    today = datetime.now().strftime("%Y-%m-%d")
                    daily_notes = note_manager.get_daily_notes(today)
                    
                    # 如果有笔记，生成汇总
                    if daily_notes:
                        summary_file = note_manager.generate_daily_summary(today)
                        if summary_file:
                            self.logger.info(f"生成每日汇总: {user_id}, 文件: {summary_file}")
                            # 发送给用户
                            await self._send_summary_to_user(user_id, summary_file)
                    
                except Exception as e:
                    self.logger.exception(f"处理用户 {user_id} 的汇总失败: {e}")
            
        except Exception as e:
            self.logger.exception(f"生成每日汇总失败: {e}")
    
    async def _schedule_task(self, hour: int = 22, minute: int = 0):
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
                    from datetime import timedelta
                    target_time += timedelta(days=1)
                
                # 计算等待时间
                wait_seconds = (target_time - now).total_seconds()
                
                self.logger.info(f"笔记汇总任务将在 {target_time.strftime('%Y-%m-%d %H:%M:%S')} 执行")
                
                # 等待到目标时间
                await asyncio.sleep(wait_seconds)
                
                # 执行汇总任务
                if self.is_running:
                    self.logger.info("开始执行每日笔记汇总任务")
                    await self._generate_daily_summaries()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"定时任务执行失败: {e}")
                # 出错后等待1小时再重试
                await asyncio.sleep(3600)
    
    async def start(self, hour: int = 22, minute: int = 0):
        """
        启动定时任务
        
        Args:
            hour: 执行小时 (0-23，默认22点)
            minute: 执行分钟 (0-59，默认0分)
        """
        if self.is_running:
            self.logger.warning("笔记汇总任务已在运行")
            return
        
        self.is_running = True
        self.task = asyncio.create_task(self._schedule_task(hour, minute))
        self.logger.info(f"笔记汇总任务已启动，每天 {hour:02d}:{minute:02d} 执行")
    
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
        
        self.logger.info("笔记汇总任务已停止")
    
    async def manual_trigger(self, date_str: str = None):
        """
        手动触发汇总生成
        
        Args:
            date_str: 日期字符串 (YYYY-MM-DD)，默认为今天
        """
        try:
            self.logger.info(f"手动触发笔记汇总: {date_str or '今天'}")
            
            if not os.path.exists(self.users_dir):
                return
            
            # 遍历所有用户
            for user_id in os.listdir(self.users_dir):
                user_dir = os.path.join(self.users_dir, user_id)
                if not os.path.isdir(user_dir):
                    continue
                
                try:
                    from ..notes.note_manager import NoteManager
                    note_manager = NoteManager(user_dir, self.logger)
                    
                    daily_notes = note_manager.get_daily_notes(date_str)
                    if daily_notes:
                        summary_file = note_manager.generate_daily_summary(date_str)
                        if summary_file:
                            self.logger.info(f"手动生成汇总: {user_id}, 文件: {summary_file}")
                            await self._send_summary_to_user(user_id, summary_file)
                
                except Exception as e:
                    self.logger.exception(f"手动生成用户 {user_id} 汇总失败: {e}")
        
        except Exception as e:
            self.logger.exception(f"手动触发汇总失败: {e}")
