import json
import os
from typing import Dict, List, Any


class DataViewer:
    """用于查看和管理本地数据"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir  # 数据目录
        self.tasks_file = os.path.join(data_dir, "tasks", "tasks.json")
        self.unified_store_file = os.path.join(data_dir, "unified_store.json")
    
    def get_tasks_summary(self) -> Dict[str, Any]:
        """获取任务列表摘要"""
        try:
            if not os.path.exists(self.tasks_file):
                return {
                    "total": 0,
                    "tasks": [],
                    "status_distribution": {}
                }
            
            with open(self.tasks_file, "r", encoding="utf-8") as f:
                tasks = json.load(f)
            
            if not isinstance(tasks, list):
                return {
                    "total": 0,
                    "tasks": [],
                    "error": "任务文件格式错误"
                }
            
            # 统计各状态任务数
            status_dist = {}
            for task in tasks:
                status = task.get("status", "unknown")
                status_dist[status] = status_dist.get(status, 0) + 1
            
            # 按类型分类
            task_types = {}
            for task in tasks:
                task_type = task.get("type", "unknown")
                if task_type not in task_types:
                    task_types[task_type] = []
                task_types[task_type].append({
                    "id": task.get("task_id", "N/A"),
                    "status": task.get("status", "N/A"),
                    "type": task_type,
                    "created_at": task.get("created_at", "N/A"),
                    "scheduled_time": task.get("scheduled_time", "N/A")
                })
            
            return {
                "total": len(tasks),
                "status_distribution": status_dist,
                "task_types": {k: len(v) for k, v in task_types.items()},
                "tasks": task_types,
                "recent_tasks": tasks[-10:] if len(tasks) > 10 else tasks
            }
        except Exception as e:
            return {
                "total": 0,
                "tasks": [],
                "error": str(e)
            }
    
    def get_unified_origins_summary(self) -> Dict[str, Any]:
        """获取用户映射摘要"""
        try:
            if not os.path.exists(self.unified_store_file):
                return {
                    "total": 0,
                    "origins": {},
                    "message": "暂无用户映射数据"
                }
            
            with open(self.unified_store_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if not isinstance(data, dict):
                return {
                    "total": 0,
                    "origins": {},
                    "error": "映射文件格式错误"
                }
            
            return {
                "total": len(data),
                "origins": data,
                "message": f"已保存 {len(data)} 个用户映射"
            }
        except Exception as e:
            return {
                "total": 0,
                "origins": {},
                "error": str(e)
            }
    
    def get_tasks_details(self, task_id: str = None) -> Dict[str, Any]:
        """获取任务详细信息"""
        try:
            if not os.path.exists(self.tasks_file):
                return {"error": "任务文件不存在"}
            
            with open(self.tasks_file, "r", encoding="utf-8") as f:
                tasks = json.load(f)
            
            if task_id:
                # 获取特定任务
                for task in tasks:
                    if task.get("task_id") == task_id:
                        return {"task": task}
                return {"error": f"未找到任务: {task_id}"}
            else:
                # 获取所有任务（分页）
                return {
                    "total": len(tasks),
                    "tasks": tasks
                }
        except Exception as e:
            return {"error": str(e)}
    
    def get_unified_origins_details(self, key: str = None) -> Dict[str, Any]:
        """获取用户映射详细信息"""
        try:
            if not os.path.exists(self.unified_store_file):
                return {"error": "映射文件不存在"}
            
            with open(self.unified_store_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if key:
                # 获取特定映射
                if key in data:
                    return {
                        "key": key,
                        "unified_msg_origin": data[key]
                    }
                return {"error": f"未找到映射: {key}"}
            else:
                # 获取所有映射
                return {
                    "total": len(data),
                    "mappings": data
                }
        except Exception as e:
            return {"error": str(e)}
    
    def export_tasks_as_json(self) -> str:
        """导出任务为JSON字符串"""
        try:
            if not os.path.exists(self.tasks_file):
                return json.dumps([])
            
            with open(self.tasks_file, "r", encoding="utf-8") as f:
                tasks = json.load(f)
            
            return json.dumps(tasks, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    def export_origins_as_json(self) -> str:
        """导出用户映射为JSON字符串"""
        try:
            if not os.path.exists(self.unified_store_file):
                return json.dumps({})
            
            with open(self.unified_store_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
