import os
import json
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..storage.cache_utils import CacheUtils
from ..processing.message_chain_builder import MessageChainBuilder
from ..scheduler.task_sync_manager import TaskSyncManager
from ..scheduler.task_executor import TaskExecutor


class TaskManager:
    """管理主动消息任务和本地存储任务的轮询、同步和执行"""
    
    def __init__(self, plugin_dir: str, config: dict, logger, context):
        self.plugin_dir = plugin_dir
        self.config = config
        self.logger = logger
        self.context = context
        
        # 初始化任务存储路径
        self.tasks_dir = os.path.join(plugin_dir, "configs")
        os.makedirs(self.tasks_dir, exist_ok=True)
        
        self.tasks_file = os.path.join(self.tasks_dir, "tasks.json")
        self.tasks: List[Dict[str, Any]] = []
        self._load_tasks()
        
        # API 配置
        self.task_center_url = config.get("task_center_url", "https://hunian003-message.hf.space/plugins/astr_task_center/api/tasks")
        self.authorization = config.get("authorization", "")
        
        # 轮询状态
        self._polling = False
        self._poll_interval = config.get("task_poll_interval", 60)
        
        # 初始化缓存工具
        self.cache_utils = CacheUtils(plugin_dir)
        
        # 初始化消息构建器
        self.message_chain_builder = MessageChainBuilder(logger)
        
        # 初始化同步管理器
        self.sync_manager = TaskSyncManager(
            self.task_center_url, self.authorization, logger, 
            self.tasks, self._save_tasks
        )
        
        # 初始化执行器
        self.executor = TaskExecutor(
            logger, context, self.task_center_url, self.authorization,
            self.cache_utils, self.message_chain_builder, self._save_tasks
        )
        
    def _load_tasks(self):
        """从本地加载任务列表"""
        try:
            if os.path.exists(self.tasks_file):
                with open(self.tasks_file, "r", encoding="utf-8") as f:
                    self.tasks = json.load(f)
            else:
                self.tasks = []
        except Exception as e:
            self.logger.exception(f"加载任务文件失败: {e}")
            self.tasks = []
    
    def _save_tasks(self):
        """保存任务列表到本地"""
        try:
            os.makedirs(os.path.dirname(self.tasks_file), exist_ok=True)
            with open(self.tasks_file, "w", encoding="utf-8") as f:
                json.dump(self.tasks, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.exception(f"保存任务文件失败: {e}")
    
    async def start_polling(self):
        """启动后台轮询任务"""
        if self._polling:
            self.logger.warning("任务轮询已经在运行中")
            return
        
        self._polling = True
        self.logger.info("启动任务轮询线程")
        asyncio.create_task(self._polling_loop())
    
    async def stop_polling(self):
        """停止后台轮询任务"""
        self._polling = False
        self.logger.info("停止任务轮询线程")
    
    async def _polling_loop(self):
        """轮询主循环"""
        consecutive_errors = 0
        max_consecutive_errors = 5
        self.logger.info(f"轮询循环已启动，轮询间隔: {self._poll_interval}秒")
        
        while self._polling:
            try:
                # 轮询获取新任务
                await self.sync_manager.sync_tasks()
                
                # 执行到期的任务
                await self._execute_pending_tasks()
                
                # 重置错误计数
                consecutive_errors = 0
                
                # 等待下一个轮询周期
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                self.logger.info("轮询循环已取消")
                break
            except Exception as e:
                consecutive_errors += 1
                self.logger.exception(f"轮询循环出错 ({consecutive_errors}/{max_consecutive_errors}): {e}")
                
                # 如果连续错误次数过多，增加等待时间
                wait_time = self._poll_interval * (2 ** min(consecutive_errors - 1, 3))
                self.logger.warning(f"轮询循环等待 {wait_time}秒后重试")
                
                try:
                    await asyncio.sleep(wait_time)
                except asyncio.CancelledError:
                    break
                
                # 如果连续错误次数过多，停止轮询
                if consecutive_errors >= max_consecutive_errors:
                    self.logger.error(f"轮询循环连续失败{max_consecutive_errors}次，停止轮询")
                    self._polling = False
                    break
    
    async def _execute_pending_tasks(self):
        """执行到期的待执行任务"""
        try:
            now = datetime.utcnow()
            executed_count = 0
            
            for task in self.tasks:
                try:
                    if task.get("status") != "pending":
                        continue
                    
                    execution_time = task.get("execution_time") or task.get("created_at")
                    if not execution_time:
                        continue
                    
                    try:
                        if isinstance(execution_time, str):
                            time_str = execution_time.rstrip("Z")
                            if "+" in time_str:
                                time_str = time_str.split("+")[0]
                            exec_time = datetime.fromisoformat(time_str)
                        else:
                            exec_time = datetime.fromtimestamp(execution_time)
                    except Exception as parse_e:
                        self.logger.debug(f"无法解析任务执行时间: {execution_time} - {parse_e}")
                        continue
                    
                    time_diff = (now - exec_time).total_seconds()
                    if 0 <= time_diff <= 300:
                        task_type = task.get("type", "unknown")
                        task_id = task.get("task_id", "unknown")
                        
                        try:
                            if task_type == "active_message":
                                await self.executor.execute_active_message(task)
                                executed_count += 1
                            elif task_type == "local_storage":
                                await self.executor.execute_local_storage(task)
                                executed_count += 1
                            else:
                                self.logger.warning(f"未知的任务类型: {task_type} ({task_id})")
                        except Exception as exec_e:
                            self.logger.exception(f"执行{task_type}类型任务失败 ({task_id}): {exec_e}")
                except Exception as task_e:
                    self.logger.exception(f"处理任务出错失败: {task_e}")
            
            if executed_count > 0:
                self.logger.info(f"执行了{executed_count}个任务")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.exception(f"执行待执行任务失败: {e}")
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        return next((t for t in self.tasks if t.get("task_id") == task_id), None)
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """获取所有任务"""
        return self.tasks.copy()
    
    def get_tasks_by_type(self, task_type: str) -> List[Dict[str, Any]]:
        """获取特定类型的任务"""
        return [t for t in self.tasks if t.get("type") == task_type]
