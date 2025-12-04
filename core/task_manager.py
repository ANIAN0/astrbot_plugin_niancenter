import os
import json
import asyncio
import base64
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from pathlib import Path
import aiohttp

from .request import fetch_json


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
        
        # 初始化缓存目录
        self.cache_dir = os.path.join(plugin_dir, "cache")
        self._init_cache_dirs()
        
        # API 配置
        self.task_center_url = config.get("task_center_url", "https://hunian003-message.hf.space/plugins/astr_task_center/api/tasks")
        self.authorization = config.get("authorization", "")
        
        # 轮询状态
        self._polling = False
        self._poll_interval = config.get("task_poll_interval", 60)  # 默认60秒轮询一次
        self._last_sync_time = None
        
    def _init_cache_dirs(self):
        """初始化缓存目录结构"""
        cache_types = ["image", "voice", "video", "file"]
        for cache_type in cache_types:
            type_dir = os.path.join(self.cache_dir, cache_type)
            os.makedirs(type_dir, exist_ok=True)
    
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
                await self._sync_tasks()
                
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
                wait_time = self._poll_interval * (2 ** min(consecutive_errors - 1, 3))  # 最多增加8倍
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
    
    async def _sync_tasks(self):
        """与远程服务器同步任务列表"""
        if not self.authorization:
            self.logger.warning("未配置authorization，跳过任务同步")
            return
        
        try:
            headers = {"Authorization": self.authorization}
            
            # 构建查询参数
            now = datetime.utcnow()
            created_after = (now - timedelta(hours=24)).isoformat() + "Z"  # 获取过去24小时的任务
            created_before = now.isoformat() + "Z"
            
            self.logger.info("开始同步任务...")
            
            # 合并请求：一次性获取所有任务类型
            await self._fetch_and_sync_all_tasks(created_after, created_before, headers)
            
            self._last_sync_time = datetime.utcnow()
            self.logger.info("任务同步完成")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.exception(f"任务同步失败: {e}")
    
    async def _fetch_and_sync_all_tasks(self, created_after: str, created_before: str, headers: dict):
        """获取所有任务类型（无task_type参数）并进行同步"""
        try:
            # 合并请求：不带task_type参数
            params = {
                "type": "get",
                "synced": "false",
                "created_after": created_after,
                "created_before": created_before
            }
            
            # 详细日志模式：记录请求详情
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
            
            # 详细日志模式：记录完整响应
            if self.logger.should_log_detail():
                self.logger.debug(f"获取任务 - 响应: {resp}")
            
            # 假设响应格式为 {"data": [...]} 或直接是列表
            new_tasks = resp.get("data", []) if isinstance(resp, dict) else (resp if isinstance(resp, list) else [])
            
            sync_count = 0
            for task in new_tasks:
                if isinstance(task, dict):
                    try:
                        task_id = task.get("task_id")
                        if not task_id:
                            self.logger.warning("任务缺少task_id")
                            continue
                        
                        # 先标记为已同步（对所有获取到的任务都发送update请求）
                        try:
                            await self._mark_task_synced(task_id, headers)
                            # 标记同步成功后，更新本地任务的synced状态
                            task_record = next((t for t in self.tasks if t.get("task_id") == task_id), None)
                            if task_record:
                                task_record["synced"] = True
                        except Exception as e:
                            self.logger.exception(f"标记{task_id}同步失败: {e}")
                        
                        # 再检查是否本地已存在（仅添加新任务）
                        existing = next((t for t in self.tasks if t.get("task_id") == task_id), None)
                        if not existing:
                            # 重新组织任务结构为本地存储格式
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
                            # 添加任务到本地列表（synced初始值根据接口返回）
                            self.tasks.append(local_task)
                            sync_count += 1
                            self.logger.info(f"添加新任务: {task_id} (类型: {task_type})")
                            
                            # 然后标记为已同步并更新端点状态
                            try:
                                await self._mark_task_synced(task_id, headers)
                                # 标记同步成功后，更新本地任务的synced状态
                                local_task["synced"] = True
                            except Exception as e:
                                self.logger.exception(f"标记{task_id}同步失败: {e}")
                    except Exception as e:
                        self.logger.exception(f"处理任务失败: {e}")
            
            if sync_count > 0:
                self._save_tasks()
                self.logger.info(f"同步了{sync_count}个新任务並更新了synced状态")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.exception(f"获取任务失败: {e}")
    
    async def _mark_task_synced(self, task_id: str, headers: dict):
        """将任务标记为已同步（发送update请求）"""
        try:
            params = {
                "type": "update",
                "task_id": task_id,
                "synced": True
            }
            
            # 详细日志模式：记录请求详情
            if self.logger.should_log_detail():
                self.logger.debug(f"标记任务同步 - URL: {self.task_center_url}")
                self.logger.debug(f"标记任务同步 - 请求参数: {params}")
                self.logger.debug(f"标记任务同步 - 请求头: {headers}")
            
            # 改为GET请求（webhook仅支持GET）
            resp = await fetch_json(
                self.task_center_url,
                method="GET",
                params=params,
                headers=headers
            )
            
            # 详细日志模式：记录完整响应
            if self.logger.should_log_detail():
                self.logger.debug(f"标记任务同步 - 响应: {resp}")
            
            self.logger.info(f"任务 {task_id} 标记为已同步")
        except Exception as e:
            self.logger.exception(f"标记任务同步失败 {task_id}: {e}")
    
    async def _execute_pending_tasks(self):
        """执行到期的待执行任务"""
        try:
            now = datetime.utcnow()
            executed_count = 0
            
            for task in self.tasks:
                try:
                    # 只处理未执行的任务
                    if task.get("status") != "pending":
                        continue
                    
                    # 检查执行时间
                    execution_time = task.get("execution_time") or task.get("created_at")
                    if not execution_time:
                        continue
                    
                    try:
                        # 解析时间字符串
                        if isinstance(execution_time, str):
                            # 移除Z后缀后解析
                            time_str = execution_time.rstrip("Z")
                            # 处理 ISO 8601 格式中的 +00:00
                            if "+" in time_str:
                                time_str = time_str.split("+")[0]
                            exec_time = datetime.fromisoformat(time_str)
                        else:
                            exec_time = datetime.fromtimestamp(execution_time)
                    except Exception as parse_e:
                        self.logger.debug(f"无法解析任务执行时间: {execution_time} - {parse_e}")
                        continue
                    
                    # 检查是否在过去5分钟内
                    time_diff = (now - exec_time).total_seconds()
                    if 0 <= time_diff <= 300:  # 0 - 5分钟
                        task_type = task.get("type", "unknown")
                        task_id = task.get("task_id", "unknown")
                        
                        try:
                            if task_type == "active_message":
                                await self._execute_active_message(task)
                                executed_count += 1
                            elif task_type == "local_storage":
                                await self._execute_local_storage(task)
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
    
    async def _execute_active_message(self, task: Dict[str, Any]):
        """执行主动消息任务"""
        task_id = task.get("task_id", "unknown")
        try:
            # 标记为运行中
            await self._update_task_status(task_id, "running")
            
            unified_msg_origin = task.get("unified_msg_origin")
            msg_type = task.get("message_type", "text")
            context = task.get("context", "")
            
            if not unified_msg_origin:
                raise ValueError("缺少unified_msg_origin")
            
            # 处理不同类型的消息
            try:
                if msg_type == "text":
                    await self.context.send_message(unified_msg_origin, self._build_message_chain(msg_type, context))
                elif msg_type in ["image", "voice", "video", "file"]:
                    # 如果是URL或base64，先保存到本地
                    local_path = await self._save_media_to_cache(context, msg_type)
                    await self.context.send_message(unified_msg_origin, self._build_message_chain(msg_type, local_path))
                else:
                    # 未知类型，按文本处理
                    await self.context.send_message(unified_msg_origin, self._build_message_chain("text", str(context)))
            except Exception as send_e:
                self.logger.exception(f"发送消息失败: {send_e}")
                raise
            
            # 标记为成功
            await self._update_task_status(task_id, "success", {"sent": True})
            self.logger.info(f"主动消息任务执行成功: {task_id}")
            
        except Exception as e:
            self.logger.exception(f"执行主动消息任务失败 {task_id}: {e}")
            try:
                await self._update_task_status(task_id, "failed", {"error": str(e)})
            except Exception as status_e:
                self.logger.exception(f"更新任务状态失败: {status_e}")
    
    async def _execute_local_storage(self, task: Dict[str, Any]):
        """执行本地存储任务"""
        task_id = task.get("task_id", "unknown")
        try:
            # 标记为运行中
            await self._update_task_status(task_id, "running")
            
            msg_type = task.get("message_type", "text")
            context = task.get("context", "")
            
            try:
                # 保存内容到本地
                local_path = await self._save_media_to_cache(context, msg_type)
            except Exception as save_e:
                self.logger.exception(f"保存文件失败: {save_e}")
                raise
            
            # 标记为成功
            await self._update_task_status(task_id, "success", {"saved_path": local_path})
            self.logger.info(f"本地存储任务执行成功: {task_id} -> {local_path}")
            
        except Exception as e:
            self.logger.exception(f"执行本地存储任务失败 {task_id}: {e}")
            try:
                await self._update_task_status(task_id, "failed", {"error": str(e)})
            except Exception as status_e:
                self.logger.exception(f"更新任务状态失败: {status_e}")
    
    async def _save_media_to_cache(self, content: str, media_type: str) -> str:
        """保存媒体文件到缓存目录，返回本地路径"""
        cache_type_dir = os.path.join(self.cache_dir, media_type)
        os.makedirs(cache_type_dir, exist_ok=True)
        
        try:
            # 检查是否是URL
            if content.startswith("http://") or content.startswith("https://"):
                return await self._download_and_save(content, cache_type_dir, media_type)
            # 检查是否是base64编码
            elif content.startswith("data:") or self._is_base64(content):
                return await self._decode_and_save_base64(content, cache_type_dir, media_type)
            else:
                # 如果是文本类型，直接保存
                if media_type == "text":
                    filename = f"{datetime.utcnow().timestamp()}.txt"
                    file_path = os.path.join(cache_type_dir, filename)
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    return file_path
                else:
                    # 其他类型无法处理，返回原内容
                    self.logger.warning(f"无法处理{media_type}类型的内容: {content[:50]}")
                    return content
        except Exception as e:
            self.logger.exception(f"保存媒体文件失败: {e}")
            raise
    
    async def _download_and_save(self, url: str, cache_dir: str, media_type: str) -> str:
        """从URL下载文件并保存到缓存"""
        try:
            # 详细日志模式：记录下载请求
            if self.logger.should_log_detail():
                self.logger.debug(f"下载媒体文件 - URL: {url}, 类型: {media_type}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        
                        # 详细日志模式：记录下载结果
                        if self.logger.should_log_detail():
                            self.logger.debug(f"下载媒体文件 - 响应状态: {resp.status}, 文件大小: {len(content)} bytes")
                        
                        # 根据Content-Type确定文件扩展名
                        content_type = resp.headers.get("content-type", "")
                        ext = self._get_extension_from_content_type(content_type, media_type)
                        
                        filename = f"{datetime.utcnow().timestamp()}{ext}"
                        file_path = os.path.join(cache_dir, filename)
                        
                        with open(file_path, "wb") as f:
                            f.write(content)
                        
                        self.logger.info(f"下载文件成功: {url} -> {file_path}")
                        return file_path
                    else:
                        raise Exception(f"下载失败: HTTP {resp.status}")
        except Exception as e:
            self.logger.exception(f"下载文件失败: {url}")
            raise
    
    async def _decode_and_save_base64(self, content: str, cache_dir: str, media_type: str) -> str:
        """解码base64内容并保存到缓存"""
        try:
            # 处理 data:image/png;base64, 格式
            if content.startswith("data:"):
                content = content.split(",", 1)[1]
            
            # 解码base64
            decoded = base64.b64decode(content)
            
            # 确定文件扩展名
            ext = self._get_extension_by_type(media_type)
            filename = f"{datetime.utcnow().timestamp()}{ext}"
            file_path = os.path.join(cache_dir, filename)
            
            with open(file_path, "wb") as f:
                f.write(decoded)
            
            self.logger.info(f"Base64解码保存成功: {file_path}")
            return file_path
        except Exception as e:
            self.logger.exception("Base64解码失败")
            raise
    
    def _is_base64(self, s: str) -> bool:
        """检查字符串是否是base64编码"""
        try:
            if isinstance(s, str):
                s_bytes = bytes(s, 'utf-8')
            elif isinstance(s, bytes):
                s_bytes = s
            else:
                return False
            return base64.b64encode(base64.b64decode(s_bytes)) == s_bytes
        except Exception:
            return False
    
    def _get_extension_from_content_type(self, content_type: str, default_type: str) -> str:
        """根据Content-Type获取文件扩展名"""
        mime_to_ext = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "audio/mpeg": ".mp3",
            "audio/wav": ".wav",
            "video/mp4": ".mp4",
            "video/webm": ".webm",
            "application/pdf": ".pdf",
        }
        
        for mime, ext in mime_to_ext.items():
            if mime in content_type:
                return ext
        
        return self._get_extension_by_type(default_type)
    
    def _get_extension_by_type(self, media_type: str) -> str:
        """根据媒体类型获取默认扩展名"""
        defaults = {
            "image": ".png",
            "voice": ".wav",
            "video": ".mp4",
            "file": "",
            "text": ".txt"
        }
        return defaults.get(media_type, "")
    
    def _build_message_chain(self, msg_type: str, content: str):
        """构建消息链"""
        from astrbot.api.event import MessageChain
        import astrbot.api.message_components as Comp
        
        mc = MessageChain()
        
        try:
            if msg_type == "text":
                mc = mc.message(content)
            elif msg_type == "image":
                if os.path.exists(content):
                    mc = mc.file_image(content)
                else:
                    mc = mc.message(content)
            elif msg_type == "voice":
                if os.path.exists(content):
                    mc = mc.message(Comp.Record(file=content, url=content))
                else:
                    mc = mc.message(content)
            elif msg_type == "video":
                if os.path.exists(content):
                    mc = mc.file_video(content)
                else:
                    mc = mc.message(content)
            elif msg_type == "file":
                if os.path.exists(content):
                    filename = os.path.basename(content)
                    mc = mc.message(Comp.File(file=content, name=filename))
                else:
                    mc = mc.message(content)
            else:
                mc = mc.message(str(content))
        except Exception as e:
            self.logger.exception(f"构建消息链失败: {e}")
            mc = MessageChain().message(str(content))
        
        return mc
    
    async def _update_task_status(self, task_id: str, status: str, result: Optional[dict] = None):
        """更新任务状态"""
        try:
            # 更新本地任务列表
            task = next((t for t in self.tasks if t.get("task_id") == task_id), None)
            if task:
                task["status"] = status
                task["updated_at"] = datetime.utcnow().isoformat() + "Z"
                if result:
                    task["result"] = result
                self._save_tasks()
            else:
                self.logger.warning(f"未找到任务 {task_id}")
            
            # 更新远程服务器
            if self.authorization:
                try:
                    headers = {"Authorization": self.authorization}
                    
                    params = {
                        "type": "update",
                        "task_id": task_id,
                        "status": status
                    }
                    if result:
                        params["result"] = result
                    
                    await fetch_json(self.task_center_url, method="GET", params=params, headers=headers)
                    self.logger.debug(f"任务 {task_id} 状态更新为 {status}")
                except Exception as remote_e:
                    self.logger.exception(f"更新远程任务状态失败 {task_id}: {remote_e}")
        except Exception as e:
            self.logger.exception(f"更新任务状态失败 {task_id}: {e}")
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        return next((t for t in self.tasks if t.get("task_id") == task_id), None)
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """获取所有任务"""
        return self.tasks.copy()
    
    def get_tasks_by_type(self, task_type: str) -> List[Dict[str, Any]]:
        """获取特定类型的任务"""
        return [t for t in self.tasks if t.get("type") == task_type]
