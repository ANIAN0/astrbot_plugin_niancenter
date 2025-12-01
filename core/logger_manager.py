import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional


class LoggerManager:
    """管理插件的本地日志记录"""
    
    def __init__(self, plugin_dir: str, config: dict):
        self.plugin_dir = plugin_dir
        self.config = config
        self.logs_dir = os.path.join(plugin_dir, "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        
        self.logger = None
        self.file_handler = None
        self.enable_file_logging = config.get("enable_logging", True)
    
    def setup_file_logging(self, log_level: str = "INFO", max_size_mb: int = 10, backup_count: int = 5):
        """设置文件日志"""
        if not self.enable_file_logging:
            return
        
        try:
            # 创建logger
            self.logger = logging.getLogger("niancenter_plugin")
            self.logger.setLevel(getattr(logging, log_level, logging.INFO))
            
            # 清除已有的处理器
            for handler in self.logger.handlers[:]:
                self.logger.removeHandler(handler)
            
            # 创建日志文件路径
            log_file = os.path.join(self.logs_dir, "niancenter.log")
            
            # 创建旋转文件处理器
            max_bytes = max_size_mb * 1024 * 1024 if max_size_mb > 0 else 0
            self.file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes if max_bytes > 0 else 10485760,  # 默认10MB
                backupCount=backup_count,
                encoding="utf-8"
            )
            self.file_handler.setLevel(getattr(logging, log_level, logging.INFO))
            
            # 创建格式器
            formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            self.file_handler.setFormatter(formatter)
            
            # 添加处理器
            self.logger.addHandler(self.file_handler)
            
        except Exception as e:
            print(f"设置文件日志失败: {e}")
    
    def log(self, message: str, level: str = "INFO"):
        """记录日志"""
        if self.logger is None:
            return
        
        try:
            log_func = getattr(self.logger, level.lower(), self.logger.info)
            log_func(message)
        except Exception as e:
            print(f"记录日志失败: {e}")
    
    def get_recent_logs(self, lines: int = 100) -> str:
        """获取最近的日志内容"""
        try:
            log_file = os.path.join(self.logs_dir, "niancenter.log")
            if not os.path.exists(log_file):
                return "暂无日志文件"
            
            with open(log_file, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
            
            # 获取最后N行
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return "".join(recent_lines)
        except Exception as e:
            return f"获取日志失败: {e}"
    
    def close(self):
        """关闭日志"""
        if self.file_handler:
            self.file_handler.close()
            if self.logger:
                self.logger.removeHandler(self.file_handler)
