import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional
from ..api.request import fetch_json

class TaskExecutor:
    def __init__(self, logger, context, task_center_url: str, authorization: str, 
                 cache_utils, message_chain_builder, save_callback):
        self.logger = logger
        self.context = context
        self.task_center_url = task_center_url
        self.authorization = authorization
        self.cache_utils = cache_utils
        self.message_chain_builder = message_chain_builder
        self.save_callback = save_callback

    async def execute_active_message(self, task: Dict[str, Any]):
        task_id = task.get("task_id", "unknown")
        try:
            await self._update_task_status(task, task_id, "running")
            unified_msg_origin = task.get("unified_msg_origin")
            msg_type = task.get("message_type", "text")
            context = task.get("context", "")
            if not unified_msg_origin:
                raise ValueError("缺少unified_msg_origin")
            try:
                if msg_type == "text":
                    await self.context.send_message(unified_msg_origin, self.message_chain_builder.build(msg_type, context))
                elif msg_type in ["image", "voice", "video", "file"]:
                    local_path = await self.cache_utils.cache_media(context, msg_type)
                    await self.context.send_message(unified_msg_origin, self.message_chain_builder.build(msg_type, local_path))
                else:
                    await self.context.send_message(unified_msg_origin, self.message_chain_builder.build("text", str(context)))
            except Exception as send_e:
                self.logger.exception(f"发送消息失败: {send_e}")
                raise
            await self._update_task_status(task, task_id, "success", {"sent": True})
            self.logger.info(f"主动消息任务执行成功: {task_id}")
        except Exception as e:
            self.logger.exception(f"执行主动消息任务失败 {task_id}: {e}")
            try:
                await self._update_task_status(task, task_id, "failed", {"error": str(e)})
            except Exception as status_e:
                self.logger.exception(f"更新任务状态失败: {status_e}")

    async def execute_local_storage(self, task: Dict[str, Any]):
        task_id = task.get("task_id", "unknown")
        try:
            await self._update_task_status(task, task_id, "running")
            msg_type = task.get("message_type", "text")
            context = task.get("context", "")
            try:
                local_path = await self.cache_utils.cache_media(context, msg_type)
            except Exception as save_e:
                self.logger.exception(f"保存文件失败: {save_e}")
                raise
            await self._update_task_status(task, task_id, "success", {"saved_path": local_path})
            self.logger.info(f"本地存储任务执行成功: {task_id} -> {local_path}")
        except Exception as e:
            self.logger.exception(f"执行本地存储任务失败 {task_id}: {e}")
            try:
                await self._update_task_status(task, task_id, "failed", {"error": str(e)})
            except Exception as status_e:
                self.logger.exception(f"更新任务状态失败: {status_e}")

    async def _update_task_status(self, task: Dict[str, Any], task_id: str, status: str, result: Optional[dict] = None):
        try:
            task["status"] = status
            task["updated_at"] = datetime.utcnow().isoformat() + "Z"
            if result:
                task["result"] = result
            self.save_callback()
            if self.authorization:
                try:
                    headers = {"Authorization": self.authorization}
                    params = {
                        "type": "update",
                        "task_id": task_id,
                        "status": status
                    }
                    if result:
                        params["result"] = json.dumps(result)
                    await fetch_json(self.task_center_url, method="GET", params=params, headers=headers)
                    self.logger.debug(f"任务 {task_id} 状态更新为 {status}")
                except Exception as remote_e:
                    self.logger.exception(f"更新远程任务状态失败 {task_id}: {remote_e}")
        except Exception as e:
            self.logger.exception(f"更新任务状态失败 {task_id}: {e}")
