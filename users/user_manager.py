import os
import json
import re
import hashlib
import random
import string
from datetime import datetime
from typing import Any

class UsersManager:
    def __init__(self, data_dir: str, logger, plugin_config: dict):
        self.data_dir = data_dir  # 数据目录
        self.logger = logger
        self.plugin_config = plugin_config or {}
        # 用户数据存储在数据目录下
        self.user_data_dir = os.path.join(data_dir, "users")
        os.makedirs(self.user_data_dir, exist_ok=True)

    def _derive_user_id(self, event: Any) -> str:
        uid = None
        try:
            if hasattr(event, "get_sender_id"):
                sid = event.get_sender_id()
                if sid is not None:
                    uid = f"u_{sid}"
        except Exception:
            uid = None
        if not uid:
            # fallback: use session_id or random
            session_id = getattr(event, "session_id", None)
            if session_id:
                uid = f"u_{session_id}"
            else:
                uid = f"u_{int(datetime.utcnow().timestamp())}{random.randint(10,99)}"
        return uid

    def _gen_secret_plain(self, length: int = 4) -> str:
        chars = string.ascii_letters + string.digits
        return "".join(random.choice(chars) for _ in range(length))

    def _encrypt_secret(self, plain: str) -> str:
        return hashlib.sha256(plain.encode("utf-8")).hexdigest()

    def _user_dir(self, user_id: str) -> str:
        d = os.path.join(self.user_data_dir, user_id)
        os.makedirs(d, exist_ok=True)
        return d
    
    def user_exists(self, user_id: str) -> bool:
        """
        检查用户是否存在
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户是否已创建
        """
        user_dir = os.path.join(self.user_data_dir, user_id)
        cfg_path = os.path.join(user_dir, "config.json")
        return os.path.exists(cfg_path)

    async def create_user(self, event: Any) -> bool:
        try:
            user_id = self._derive_user_id(event)
            sender_name = None
            try:
                if hasattr(event, "get_sender_name"):
                    sender_name = event.get_sender_name()
            except Exception:
                sender_name = None
            unified_msg_origin = getattr(event, "unified_msg_origin", None) or f"{user_id}_默认"

            secret_plain = self._gen_secret_plain(4)
            encrypted_secret = self._encrypt_secret(secret_plain)

            user_dir = self._user_dir(user_id)
            cfg_path = os.path.join(user_dir, "config.json")

            config_obj = {
                "version": "1.0",
                "user_id": user_id,
                "qq_number": str(getattr(event, "qq_number", "")),
                "username": sender_name or str(getattr(event, "username", "")) or user_id,
                "encrypted_secret": encrypted_secret,
                "unified_msg_origin": unified_msg_origin,
                "last_sync_time": datetime.utcnow().isoformat() + "Z",
                "settings": {
                    "daily_reminder_time": "08:00",
                    "afternoon_reminder_time": "14:00",
                    "summary_generation_time": "22:00"
                }
            }

            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(config_obj, f, ensure_ascii=False, indent=2)

            task_center_entry = self.plugin_config.get("task_center_entry_url", "")
            self.logger.info(f"用户创建成功: {user_id} -> {cfg_path}")
            await event.send(event.plain_result(f"✓ 用户创建成功\n密钥: {secret_plain}\n任务中心入口: {task_center_entry}"))
            return True
        except Exception as e:
            self.logger.exception(f"创建用户失败: {e}")
            try:
                await event.send(event.plain_result("✗ 创建用户失败"))
            except Exception:
                pass
            return False

    async def change_password(self, event: Any) -> bool:
        try:
            message_str = getattr(event, "message_str", "") or ""
            # 提取新密钥: 去除关键字"n修改密码"后的内容
            if "n修改密码" in message_str:
                new_secret = message_str.replace("n修改密码", "", 1).strip()
            else:
                # 若关键词大小写或其他变体
                new_secret = message_str
            # 校验格式
            if not re.fullmatch(r"[A-Za-z0-9]{1,16}", new_secret or ""):
                await event.send(event.plain_result("✗ 密钥格式错误（仅英文数字，最长16位）"))
                return False
            # 根据 sender 派生用户目录
            user_id = self._derive_user_id(event)
            unified_msg_origin = getattr(event, "unified_msg_origin", None)
            user_dir = self._user_dir(user_id)
            cfg_path = os.path.join(user_dir, "config.json")
            if not os.path.exists(cfg_path):
                await event.send(event.plain_result("✗ 用户不存在，请先 /n登录 创建用户"))
                return False
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            # 使用 unified_msg_origin 校验
            if not unified_msg_origin or unified_msg_origin != cfg.get("unified_msg_origin"):
                await event.send(event.plain_result("✗ 会话校验失败，请在绑定的会话中修改密码"))
                return False
            # 更新密钥
            cfg["encrypted_secret"] = self._encrypt_secret(new_secret)
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            await event.send(event.plain_result("✓ 密钥修改成功"))
            return True
        except Exception as e:
            self.logger.exception(f"修改密码失败: {e}")
            try:
                await event.send(event.plain_result("✗ 修改密码失败"))
            except Exception:
                pass
            return False
