import asyncio
from datetime import datetime, timedelta
from ..api.request import fetch_json

class TaskSyncManager:
    def __init__(self, task_center_url: str, authorization: str, logger, tasks_list, save_callback):
        self.task_center_url = task_center_url
        self.authorization = authorization
        self.logger = logger
        self.tasks = tasks_list
        self.save_callback = save_callback
        self._last_sync_time = None

    async def sync_tasks(self):
        if not self.authorization:
            self.logger.warning("未配置authorization，跳过任务同步")
            return
        try:
            headers = {"Authorization": self.authorization}
            now = datetime.utcnow()
            created_after = (now - timedelta(hours=24)).isoformat() + "Z"
            created_before = now.isoformat() + "Z"
            self.logger.info("开始同步任务...")
            await self._fetch_and_sync_all_tasks(created_after, created_before, headers)
            self._last_sync_time = datetime.utcnow()
            self.logger.info("任务同步完成")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.exception(f"任务同步失败: {e}")

    async def _fetch_and_sync_all_tasks(self, created_after: str, created_before: str, headers: dict):
        try:
            params = {
                "type": "get",
                "synced": "false",
                "created_after": created_after,
                "created_before": created_before
            }
            if self.logger.should_log_detail():
                self.logger.debug(f"获取任务 - URL: {self.task_center_url}")
                self.logger.debug(f"获取任务 - 请求参数: {params}")
                self.logger.debug(f"获取任务 - 请求头: {headers}")
            resp = await fetch_json(
                self.task_center_url,
                method="GET",
                params=params,
                headers=headers
            )
            if self.logger.should_log_detail():
                self.logger.debug(f"获取任务 - 响应: {resp}")
            new_tasks = resp.get("data", []) if isinstance(resp, dict) else (resp if isinstance(resp, list) else [])
            sync_count = 0
            for task in new_tasks:
                if isinstance(task, dict):
                    try:
                        task_id = task.get("task_id")
                        if not task_id:
                            self.logger.warning("任务缺少task_id")
                            continue
                        try:
                            await self._mark_task_synced(task_id, headers)
                            task_record = next((t for t in self.tasks if t.get("task_id") == task_id), None)
                            if task_record:
                                task_record["synced"] = True
                        except Exception as e:
                            self.logger.exception(f"标记{task_id}同步失败: {e}")
                        existing = next((t for t in self.tasks if t.get("task_id") == task_id), None)
                        if not existing:
                            content = task.get("content", {})
                            task_type = task.get("task_type", "unknown")
                            local_task = {
                                "task_id": task_id,
                                "type": task_type,
                                "unified_msg_origin": content.get("unified_msg_origin"),
                                "message_type": content.get("type", "text"),
                                "context": content.get("context", ""),
                                "execution_time": task.get("execution_time"),
                                "created_at": task.get("created_at"),
                                "status": task.get("status", "pending"),
                                "synced": task.get("synced", False),
                                "result": task.get("result")
                            }
                            self.tasks.append(local_task)
                            sync_count += 1
                            self.logger.info(f"添加新任务: {task_id} (类型: {task_type})")
                            try:
                                await self._mark_task_synced(task_id, headers)
                                local_task["synced"] = True
                            except Exception as e:
                                self.logger.exception(f"标记{task_id}同步失败: {e}")
                    except Exception as e:
                        self.logger.exception(f"处理任务失败: {e}")
            if sync_count > 0:
                self.save_callback()
                self.logger.info(f"同步了{sync_count}个新任务並更新了synced状态")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.exception(f"获取任务失败: {e}")

    async def _mark_task_synced(self, task_id: str, headers: dict):
        try:
            params = {
                "type": "update",
                "task_id": task_id,
                "synced": "true"
            }
            if self.logger.should_log_detail():
                self.logger.debug(f"标记任务同步 - URL: {self.task_center_url}")
                self.logger.debug(f"标记任务同步 - 请求参数: {params}")
                self.logger.debug(f"标记任务同步 - 请求头: {headers}")
            resp = await fetch_json(
                self.task_center_url,
                method="GET",
                params=params,
                headers=headers
            )
            if self.logger.should_log_detail():
                self.logger.debug(f"标记任务同步 - 响应: {resp}")
            self.logger.info(f"任务 {task_id} 标记为已同步")
        except Exception as e:
            self.logger.exception(f"标记任务同步失败 {task_id}: {e}")
