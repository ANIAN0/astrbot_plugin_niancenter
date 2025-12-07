import os
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from astrbot.api.event import AstrMessageEvent
from astrbot.core.message.components import Plain, Image, Record, Video


class NoteManager:
    """灵感记录管理器"""
    
    def __init__(self, user_dir: str, logger):
        """
        初始化笔记管理器
        
        Args:
            user_dir: 用户目录路径
            logger: 日志记录器
        """
        self.user_dir = user_dir
        self.logger = logger
        self.notes_file = os.path.join(user_dir, "notes.json")
        self.notes_dir = os.path.join(user_dir, "notes")
        self.attachments_dir = os.path.join(user_dir, "attachments")
        
        # 确保目录存在
        os.makedirs(self.notes_dir, exist_ok=True)
        os.makedirs(self.attachments_dir, exist_ok=True)
        
        # 初始化notes.json
        self._init_notes_file()
    
    def _init_notes_file(self):
        """初始化notes.json文件"""
        if not os.path.exists(self.notes_file):
            initial_data = {
                "version": "1.0",
                "notes": []
            }
            with open(self.notes_file, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, ensure_ascii=False, indent=2)
    
    def _load_notes(self) -> Dict[str, Any]:
        """加载笔记数据"""
        try:
            with open(self.notes_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.logger.exception(f"加载笔记数据失败: {e}")
            return {"version": "1.0", "notes": []}
    
    def _save_notes(self, data: Dict[str, Any]):
        """保存笔记数据"""
        try:
            with open(self.notes_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.exception(f"保存笔记数据失败: {e}")
    
    def _generate_note_id(self) -> str:
        """生成唯一的笔记ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"nt_{timestamp}"
    
    def _generate_auto_keyword(self, content: str) -> str:
        """自动生成关键字（基于内容哈希）"""
        # 使用内容的前20个字符生成简短标识
        if len(content) > 20:
            preview = content[:20]
        else:
            preview = content
        # 生成哈希的前6位作为唯一标识
        hash_suffix = hashlib.md5(content.encode()).hexdigest()[:6]
        return f"{preview}_{hash_suffix}"
    
    def _parse_keywords(self, keyword_str: Optional[str]) -> List[str]:
        """解析关键字字符串为列表"""
        if not keyword_str:
            return []
        # 支持多种分隔符：空格、逗号、分号
        keywords = keyword_str.replace(",", " ").replace("，", " ").replace(";", " ").replace("；", " ")
        return [k.strip() for k in keywords.split() if k.strip()]
    
    def _save_text_to_group_file(self, group: str, content: str) -> str:
        """
        将文本内容追加到分组文件
        
        Returns:
            相对存储路径
        """
        # 使用年月作为子目录
        year_month = datetime.now().strftime("%Y-%m")
        group_dir = os.path.join(self.notes_dir, year_month)
        os.makedirs(group_dir, exist_ok=True)
        
        # 文件名使用分组名
        filename = f"{group}.md"
        file_path = os.path.join(group_dir, filename)
        
        # 追加内容 - 使用时间作为标题
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"\n## {timestamp}\n\n{content}\n\n---\n"
        
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(entry)
        
        # 返回相对路径
        return f"notes/{year_month}/{filename}"
    
    def _normalize_file_path(self, file_path: str) -> str:
        """
        规范化文件路径，处理 file:// 协议
        
        Args:
            file_path: 原始文件路径
            
        Returns:
            规范化后的本地文件路径
        """
        if not file_path:
            return file_path
        
        # 处理 file:// 协议
        if file_path.startswith('file://'):
            # 移除 file:// 前缀
            path = file_path[7:]  # 移除 'file://'
            
            # 处理 Windows 路径 (file:///C:/...)
            if len(path) > 2 and path[0] == '/' and path[2] == ':':
                path = path[1:]  # 移除开头的 /
            # 处理 Unix 路径 (file:///path/...)
            elif path.startswith('//'):
                path = path[1:]  # 保留一个 /
            
            return path
        
        return file_path
    
    def _save_media_file(self, file_path: str, content_type: str, note_id: str) -> str:
        """
        保存媒体文件（图片、视频、音频、文件）
        
        Args:
            file_path: 源文件路径
            content_type: 文件类型
            note_id: 笔记ID（用于命名）
            
        Returns:
            相对存储路径
        """
        import shutil
        
        # 规范化文件路径
        file_path = self._normalize_file_path(file_path)
        
        # 获取文件扩展名
        _, ext = os.path.splitext(file_path)
        
        # 生成新文件名：类型_noteID_时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_filename = f"{content_type}_{note_id}_{timestamp}{ext}"
        
        # 目标路径
        dest_path = os.path.join(self.attachments_dir, new_filename)
        
        # 复制文件
        shutil.copy2(file_path, dest_path)
        
        # 返回相对路径
        return f"attachments/{new_filename}"
    
    async def add_note(self, user_id: str, event: AstrMessageEvent, 
                       content: str, group: Optional[str] = None, 
                       keywords: Optional[str] = None) -> Dict[str, Any]:
        """
        添加新笔记
        
        Args:
            user_id: 用户ID
            event: 消息事件
            content: 笔记内容（文本部分）
            group: 分组名（可选）
            keywords: 关键字（可选）
            
        Returns:
            添加结果字典
        """
        try:
            # 解析消息链，提取内容
            message_chain = event.get_messages()
            
            # 默认分组
            if not group:
                group = "默认分组"
            
            # 解析关键字
            keyword_list = self._parse_keywords(keywords)
            
            # 生成笔记ID
            note_id = self._generate_note_id()
            
            # 确定内容类型和存储
            notes_data = self._load_notes()
            created_notes = []
            
            # 处理消息链中的各种类型
            has_text = False
            for component in message_chain:
                note_item = {
                    "note_id": note_id,
                    "user_id": user_id,
                    "group": group,
                    "keywords": keyword_list.copy(),
                    "created_at": datetime.utcnow().isoformat() + "Z"
                }
                
                if isinstance(component, Plain):
                    # 文本内容 - 过滤掉命令关键字、分组、关键字标记
                    text_content = component.text.strip()
                    if not text_content:
                        continue
                    
                    # 如果是命令行，过滤掉命令部分
                    if text_content.startswith("n记录") or text_content.startswith("/n记录"):
                        continue  # 命令行已经被 content 参数处理，跳过
                    
                    # 如果没有指定关键字，自动生成
                    if not keyword_list:
                        auto_kw = self._generate_auto_keyword(text_content)
                        note_item["keywords"].append(auto_kw)
                    
                    note_item["content_type"] = "text"
                    note_item["content"] = text_content
                    note_item["storage_path"] = self._save_text_to_group_file(group, text_content)
                    
                    notes_data["notes"].append(note_item)
                    created_notes.append(note_item)
                    has_text = True
                    
                elif isinstance(component, Image):
                    # 图片
                    if hasattr(component, 'file') and component.file:
                        note_item["content_type"] = "image"
                        note_item["content"] = "图片附件"
                        note_item["storage_path"] = self._save_media_file(component.file, "image", note_id)
                        
                        notes_data["notes"].append(note_item)
                        created_notes.append(note_item)
                
                elif isinstance(component, Video):
                    # 视频
                    if hasattr(component, 'file') and component.file:
                        note_item["content_type"] = "video"
                        note_item["content"] = "视频附件"
                        note_item["storage_path"] = self._save_media_file(component.file, "video", note_id)
                        
                        notes_data["notes"].append(note_item)
                        created_notes.append(note_item)
                
                elif isinstance(component, Record):
                    # 音频
                    if hasattr(component, 'file') and component.file:
                        note_item["content_type"] = "audio"
                        note_item["content"] = "音频附件"
                        note_item["storage_path"] = self._save_media_file(component.file, "audio", note_id)
                        
                        notes_data["notes"].append(note_item)
                        created_notes.append(note_item)
            
            # 如果没有提取到任何内容，使用传入的content参数
            if not created_notes and content:
                if not keyword_list:
                    auto_kw = self._generate_auto_keyword(content)
                    keyword_list.append(auto_kw)
                
                note_item = {
                    "note_id": note_id,
                    "user_id": user_id,
                    "group": group,
                    "keywords": keyword_list,
                    "content_type": "text",
                    "content": content,
                    "storage_path": self._save_text_to_group_file(group, content),
                    "created_at": datetime.utcnow().isoformat() + "Z"
                }
                
                notes_data["notes"].append(note_item)
                created_notes.append(note_item)
            
            # 保存数据
            self._save_notes(notes_data)
            
            return {
                "success": True,
                "note_count": len(created_notes),
                "notes": created_notes,
                "group": group
            }
            
        except Exception as e:
            self.logger.exception(f"添加笔记失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def search_notes(self, keywords: str) -> List[Dict[str, Any]]:
        """
        搜索笔记
        
        Args:
            keywords: 搜索关键字
            
        Returns:
            匹配的笔记列表
        """
        try:
            notes_data = self._load_notes()
            search_terms = self._parse_keywords(keywords)
            
            if not search_terms:
                return []
            
            results = []
            for note in notes_data.get("notes", []):
                # 检查关键字匹配
                note_keywords = note.get("keywords", [])
                content = note.get("content", "")
                
                # 匹配逻辑：任一搜索词在笔记关键字或内容中
                for term in search_terms:
                    if (any(term in kw for kw in note_keywords) or 
                        term in content):
                        results.append(note)
                        break
            
            return results
            
        except Exception as e:
            self.logger.exception(f"搜索笔记失败: {e}")
            return []
    
    def get_daily_notes(self, date_str: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取指定日期的笔记
        
        Args:
            date_str: 日期字符串（YYYY-MM-DD），默认为今天
            
        Returns:
            该日期的笔记列表
        """
        try:
            if not date_str:
                date_str = datetime.now().strftime("%Y-%m-%d")
            
            notes_data = self._load_notes()
            daily_notes = []
            
            for note in notes_data.get("notes", []):
                created_at = note.get("created_at", "")
                if created_at.startswith(date_str):
                    daily_notes.append(note)
            
            return daily_notes
            
        except Exception as e:
            self.logger.exception(f"获取每日笔记失败: {e}")
            return []
    
    def generate_daily_summary(self, date_str: Optional[str] = None) -> Optional[str]:
        """
        生成每日笔记汇总
        
        Args:
            date_str: 日期字符串（YYYY-MM-DD），默认为今天
            
        Returns:
            汇总文件路径
        """
        try:
            if not date_str:
                date_str = datetime.now().strftime("%Y-%m-%d")
            
            daily_notes = self.get_daily_notes(date_str)
            
            if not daily_notes:
                return None
            
            # 生成Markdown内容
            md_content = f"# {date_str} 笔记汇总\n\n"
            md_content += f"**总计**: {len(daily_notes)} 条记录\n\n"
            
            # 按分组整理
            groups = {}
            for note in daily_notes:
                group = note.get("group", "默认分组")
                if group not in groups:
                    groups[group] = []
                groups[group].append(note)
            
            # 生成分组内容
            for group, notes in groups.items():
                md_content += f"\n## {group}\n\n"
                for note in notes:
                    content_type = note.get("content_type", "text")
                    content = note.get("content", "")
                    keywords = ", ".join(note.get("keywords", []))
                    created_at = note.get("created_at", "")
                    
                    # 使用时间作为标题
                    time_str = created_at[:19].replace("T", " ") if created_at else "未知时间"
                    md_content += f"### {time_str}\n\n"
                    
                    if keywords:
                        md_content += f"**关键字**: {keywords}\n\n"
                    md_content += f"**类型**: {content_type}\n\n"
                    
                    if content_type == "text":
                        md_content += f"{content}\n\n"
                    else:
                        storage_path = note.get("storage_path", "")
                        md_content += f"**文件路径**: `{storage_path}`\n\n"
                    
                    md_content += "---\n\n"
            
            # 保存汇总文件
            summary_dir = os.path.join(self.notes_dir, "summaries")
            os.makedirs(summary_dir, exist_ok=True)
            
            summary_file = os.path.join(summary_dir, f"{date_str}.md")
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(md_content)
            
            return summary_file
            
        except Exception as e:
            self.logger.exception(f"生成每日汇总失败: {e}")
            return None
