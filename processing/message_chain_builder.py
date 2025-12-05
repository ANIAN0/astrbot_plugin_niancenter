import os
from astrbot.api.event import MessageChain
import astrbot.api.message_components as Comp

class MessageChainBuilder:
    def __init__(self, logger):
        self.logger = logger

    def build(self, msg_type: str, content: str):
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
