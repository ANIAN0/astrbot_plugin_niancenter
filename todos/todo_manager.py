import os
import json
import re
import uuid
import shutil
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


class TodoManager:
    """待办管理器"""
    
    def __init__(self, user_data_dir: str, logger):
        """
        初始化待办管理器
        
        Args:
            user_data_dir: 用户数据目录
            logger: 日志记录器
        """
        self.user_data_dir = user_data_dir
        self.logger = logger
    
    def _get_todos_file(self, user_id: str) -> str:
        """获取用户的待办文件路径"""
        user_dir = os.path.join(self.user_data_dir, user_id)
        os.makedirs(user_dir, exist_ok=True)
        return os.path.join(user_dir, "todos.json")
    
    def _load_todos(self, user_id: str) -> Dict:
        """加载用户的待办数据"""
        todos_file = self._get_todos_file(user_id)
        if not os.path.exists(todos_file):
            return {
                "version": "1.0",
                "todos": []
            }
        
        try:
            with open(todos_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"加载待办文件失败: {e}")
            return {
                "version": "1.0",
                "todos": []
            }
    
    def _save_todos(self, user_id: str, todos_data: Dict) -> bool:
        """保存用户的待办数据"""
        try:
            todos_file = self._get_todos_file(user_id)
            with open(todos_file, "w", encoding="utf-8") as f:
                json.dump(todos_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"保存待办文件失败: {e}")
            return False
    
    def _generate_todo_id(self) -> str:
        """生成唯一的待办ID"""
        return f"td_{uuid.uuid4().hex[:8]}"
    
    def _generate_follow_up_id(self) -> str:
        """生成唯一的跟进ID"""
        return f"fu_{uuid.uuid4().hex[:8]}"
    
    def _parse_time(self, time_str: str) -> Optional[datetime]:
        """
        解析时间字符串
        
        支持格式:
        - "今日" -> 今天18:00
        - "今日 HH:MM" -> 今天指定时间
        - "明日" -> 明天18:00
        - "明日 HH:MM" -> 明天指定时间
        - "MM-DD HH:MM" -> 具体日期时间
        - "MM-DD" -> 具体日期18:00
        
        Args:
            time_str: 时间字符串
            
        Returns:
            解析后的datetime对象，解析失败返回None
        """
        if not time_str:
            return None
        
        time_str = time_str.strip()
        now = datetime.now()
        
        self.logger.info(f"[时间解析] 输入: '{time_str}', 当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 处理"今日 HH:MM" 或 "今日HH:MM"（空格可选）
        match = re.match(r'^今日\s*(\d{1,2}):(\d{1,2})$', time_str)
        if match:
            hour, minute = map(int, match.groups())
            try:
                result = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                self.logger.info(f"[时间解析] 匹配'今日 HH:MM': {result.strftime('%Y-%m-%d %H:%M:%S')}")
                # 如果指定的时间已经过了，保持今天（不跳到明天）
                return result
            except ValueError:
                return None
        
        # 处理"今日"（默认18:00）
        if time_str == "今日":
            result = now.replace(hour=18, minute=0, second=0, microsecond=0)
            self.logger.info(f"[时间解析] 匹配'今日': {result.strftime('%Y-%m-%d %H:%M:%S')}")
            return result
        
        # 处理"明日 HH:MM" 或 "明日HH:MM"（空格可选）
        match = re.match(r'^明日\s*(\d{1,2}):(\d{1,2})$', time_str)
        if match:
            hour, minute = map(int, match.groups())
            try:
                tomorrow = now + timedelta(days=1)
                result = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
                return result
            except ValueError:
                return None
        
        # 处理"明日"（默认18:00）
        if time_str == "明日":
            tomorrow = now + timedelta(days=1)
            return tomorrow.replace(hour=18, minute=0, second=0, microsecond=0)
        
        # 处理具体日期格式: MM-DD HH:MM 或 MM-DD
        # 匹配 MM-DD HH:MM
        match = re.match(r'^(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})$', time_str)
        if match:
            month, day, hour, minute = map(int, match.groups())
            try:
                # 使用当前年份
                result = now.replace(month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0)
                # 如果日期已过，使用明年
                if result < now:
                    result = result.replace(year=now.year + 1)
                return result
            except ValueError:
                return None
        
        # 匹配 MM-DD（默认18:00）
        match = re.match(r'^(\d{1,2})-(\d{1,2})$', time_str)
        if match:
            month, day = map(int, match.groups())
            try:
                result = now.replace(month=month, day=day, hour=18, minute=0, second=0, microsecond=0)
                if result < now:
                    result = result.replace(year=now.year + 1)
                return result
            except ValueError:
                return None
        
        return None
    
    def _get_next_display_id(self, todos_data: Dict) -> int:
        """获取下一个可用的显示ID"""
        todos = todos_data.get("todos", [])
        if not todos:
            return 1
        
        # 获取所有进行中的待办的最大display_id
        max_id = 0
        for todo in todos:
            if todo.get("status") == "进行中":
                display_id = todo.get("display_id", 0)
                max_id = max(max_id, display_id)
        
        return max_id + 1
    
    def get_active_todos(self, user_id: str) -> List[Dict]:
        """
        获取用户所有进行中的待办
        
        Args:
            user_id: 用户ID
            
        Returns:
            进行中的待办列表
        """
        todos_data = self._load_todos(user_id)
        todos = todos_data.get("todos", [])
        
        # 只返回进行中的待办
        active_todos = [t for t in todos if t.get("status") == "进行中"]
        
        # 按display_id排序
        active_todos.sort(key=lambda x: x.get("display_id", 0))
        
        return active_todos
    
    def get_todo_by_display_id(self, user_id: str, display_id: int) -> Optional[Dict]:
        """
        通过显示ID获取待办
        
        Args:
            user_id: 用户ID
            display_id: 显示ID
            
        Returns:
            待办对象，未找到返回None
        """
        active_todos = self.get_active_todos(user_id)
        for todo in active_todos:
            if todo.get("display_id") == display_id:
                return todo
        return None
    
    def add_todo(self, user_id: str, content: str, estimated_time_str: Optional[str] = None) -> Dict:
        """
        添加新待办
        
        Args:
            user_id: 用户ID
            content: 待办内容
            estimated_time_str: 预计完成时间字符串（今日/明日/具体日期）
            
        Returns:
            包含操作结果的字典
        """
        try:
            # 解析预计完成时间
            if estimated_time_str:
                estimated_time = self._parse_time(estimated_time_str)
            else:
                # 默认为明日18:00
                tomorrow = datetime.now() + timedelta(days=1)
                estimated_time = tomorrow.replace(hour=18, minute=0, second=0, microsecond=0)
            
            if not estimated_time:
                return {
                    "success": False,
                    "error": f"时间格式错误: {estimated_time_str}"
                }
            
            # 加载待办数据
            todos_data = self._load_todos(user_id)
            
            # 创建新待办
            todo_id = self._generate_todo_id()
            display_id = self._get_next_display_id(todos_data)
            now = datetime.utcnow()
            
            new_todo = {
                "todo_id": todo_id,
                "user_id": user_id,
                "display_id": display_id,
                "content": content,
                "status": "进行中",
                "created_at": now.isoformat() + "Z",
                "estimated_finish_time": estimated_time.isoformat() + "Z",
                "finished_at": None,
                "reminded_at": [],
                "follow_ups": []
            }
            
            # 添加到列表
            todos_data["todos"].append(new_todo)
            
            # 保存
            if not self._save_todos(user_id, todos_data):
                return {
                    "success": False,
                    "error": "保存失败"
                }
            
            return {
                "success": True,
                "todo_id": todo_id,
                "display_id": display_id,
                "estimated_time": estimated_time.strftime("%Y-%m-%d %H:%M")
            }
            
        except Exception as e:
            self.logger.exception(f"添加待办失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def close_todo(self, user_id: str, display_id: int) -> Dict:
        """
        关闭待办
        
        Args:
            user_id: 用户ID
            display_id: 显示ID
            
        Returns:
            包含操作结果的字典
        """
        try:
            # 加载待办数据
            todos_data = self._load_todos(user_id)
            todos = todos_data.get("todos", [])
            
            # 查找待办
            found = False
            for todo in todos:
                if todo.get("display_id") == display_id and todo.get("status") == "进行中":
                    # 更新状态
                    todo["status"] = "已完成"
                    todo["finished_at"] = datetime.utcnow().isoformat() + "Z"
                    found = True
                    break
            
            if not found:
                return {
                    "success": False,
                    "error": f"未找到序号为 {display_id} 的进行中待办"
                }
            
            # 保存
            if not self._save_todos(user_id, todos_data):
                return {
                    "success": False,
                    "error": "保存失败"
                }
            
            return {
                "success": True,
                "display_id": display_id
            }
            
        except Exception as e:
            self.logger.exception(f"关闭待办失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _normalize_file_path(self, file_path: str) -> str:
        """规范化文件路径，处理 file:// 协议"""
        if not file_path:
            return file_path
        
        # 处理 file:// 协议
        if file_path.startswith('file://'):
            path = file_path[7:]  # 移除 'file://'
            # 处理 Windows 路径 (file:///C:/...)
            if len(path) > 2 and path[0] == '/' and path[2] == ':':
                path = path[1:]  # 移除开头的 /
            # 处理 Unix 路径 (file:///path/...)
            elif path.startswith('//'):
                path = path[1:]  # 保留一个 /
            return path
        
        return file_path
    
    def _save_media_file(self, file_path: str, content_type: str, follow_up_id: str, user_id: str) -> str:
        """
        保存多媒体文件
        
        Args:
            file_path: 源文件路径
            content_type: 内容类型
            follow_up_id: 跟进 ID
            user_id: 用户 ID
            
        Returns:
            相对存储路径
        """
        # 规范化文件路径
        file_path = self._normalize_file_path(file_path)
        
        # 获取文件扩展名
        _, ext = os.path.splitext(file_path)
        
        # 生成新文件名：类型_followUpID_时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_filename = f"{content_type}_{follow_up_id}_{timestamp}{ext}"
        
        # 目标路径：用户目录/todo_attachments/
        user_dir = os.path.join(self.user_data_dir, user_id)
        attachments_dir = os.path.join(user_dir, "todo_attachments")
        os.makedirs(attachments_dir, exist_ok=True)
        
        dest_path = os.path.join(attachments_dir, new_filename)
        
        # 复制文件
        shutil.copy2(file_path, dest_path)
        
        # 返回相对路径
        return f"todo_attachments/{new_filename}"
    
    def add_follow_up(self, user_id: str, display_id: int, event: Any, content: str) -> Dict:
        """
        添加待办跟进
        
        Args:
            user_id: 用户ID
            display_id: 待办显示ID
            event: 消息事件（用于获取多媒体文件）
            content: 跟进文本内容
            
        Returns:
            包含操作结果的字典
        """
        try:
            # 加载待办数据
            todos_data = self._load_todos(user_id)
            todos = todos_data.get("todos", [])
            
            # 查找待办
            target_todo = None
            for todo in todos:
                if todo.get("display_id") == display_id and todo.get("status") == "进行中":
                    target_todo = todo
                    break
            
            if not target_todo:
                return {
                    "success": False,
                    "error": f"未找到序号为 {display_id} 的进行中待办"
                }
            
            # 解析消息链，提取内容
            message_chain = event.get_messages()
            follow_ups = []
            
            # 导入消息类型
            try:
                from astrbot.api.event import Plain, Image, Video, Record
            except ImportError:
                # 如果无法导入，定义简单的类型检查
                Plain = type('Plain', (), {})
                Image = type('Image', (), {})
                Video = type('Video', (), {})
                Record = type('Record', (), {})
            
            # 处理消息链中的各种类型
            for component in message_chain:
                follow_up_id = self._generate_follow_up_id()
                follow_up_item = {
                    "follow_up_id": follow_up_id,
                    "created_at": datetime.utcnow().isoformat() + "Z"
                }
                
                if isinstance(component, Plain):
                    # 文本内容
                    text_content = component.text.strip()
                    if not text_content:
                        continue
                    
                    # 过滤命令行
                    if text_content.startswith("n跟进") or text_content.startswith("/n跟进"):
                        continue
                    
                    follow_up_item["type"] = "text"
                    follow_up_item["content"] = text_content
                    follow_ups.append(follow_up_item)
                    
                elif isinstance(component, Image):
                    # 图片
                    if hasattr(component, 'file') and component.file:
                        follow_up_item["type"] = "image"
                        follow_up_item["content"] = "图片附件"
                        follow_up_item["storage_path"] = self._save_media_file(
                            component.file, "image", follow_up_id, user_id
                        )
                        follow_ups.append(follow_up_item)
                
                elif isinstance(component, Video):
                    # 视频
                    if hasattr(component, 'file') and component.file:
                        follow_up_item["type"] = "video"
                        follow_up_item["content"] = "视频附件"
                        follow_up_item["storage_path"] = self._save_media_file(
                            component.file, "video", follow_up_id, user_id
                        )
                        follow_ups.append(follow_up_item)
                
                elif isinstance(component, Record):
                    # 音频
                    if hasattr(component, 'file') and component.file:
                        follow_up_item["type"] = "audio"
                        follow_up_item["content"] = "音频附件"
                        follow_up_item["storage_path"] = self._save_media_file(
                            component.file, "audio", follow_up_id, user_id
                        )
                        follow_ups.append(follow_up_item)
            
            # 如果没有提取到内容，使用传入的content参数
            if not follow_ups and content:
                follow_up_id = self._generate_follow_up_id()
                follow_ups.append({
                    "follow_up_id": follow_up_id,
                    "type": "text",
                    "content": content,
                    "created_at": datetime.utcnow().isoformat() + "Z"
                })
            
            # 添加到待办的 follow_ups 列表
            if "follow_ups" not in target_todo:
                target_todo["follow_ups"] = []
            target_todo["follow_ups"].extend(follow_ups)
            
            # 保存
            if not self._save_todos(user_id, todos_data):
                return {
                    "success": False,
                    "error": "保存失败"
                }
            
            return {
                "success": True,
                "follow_up_count": len(follow_ups),
                "display_id": display_id
            }
            
        except Exception as e:
            self.logger.exception(f"添加跟进失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def list_todos(self, user_id: str) -> List[Dict]:
        """
        查询用户的所有进行中的待办
        
        Args:
            user_id: 用户ID
            
        Returns:
            进行中的待办列表，按 display_id 排序
        """
        return self.get_active_todos(user_id)
