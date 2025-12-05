import os
from typing import Any, Tuple, List
from astrbot.api.event import MessageChain
from astrbot.core.message.components import Plain, Image, Video, Record

class RuleProcessor:
    def __init__(self, logger, unified_store, config: dict, keywords_config: dict, cache_utils, context):
        self.logger = logger
        self.unified_store = unified_store
        self.config = config or {}
        self.keywords_config = keywords_config or {}
        self.cache_utils = cache_utils
        self.context = context

    async def handle(self, event: Any) -> bool:
        message_str = getattr(event, "message_str", "") or ""
        if not message_str:
            return False
        # 规则列表
        rules = self.config.get("rules", [])
        for rule in rules:
            keywords = rule.get("keywords", [])
            if isinstance(keywords, str):
                keywords = [keywords]
            if any(k in message_str for k in keywords):
                # 记录 unified 映射
                try:
                    umo = getattr(event, "unified_msg_origin", None)
                    unified_value = None
                    if isinstance(umo, str):
                        unified_value = umo
                    elif isinstance(umo, dict) and isinstance(umo.get("unified_msg_origin"), str):
                        unified_value = umo.get("unified_msg_origin")
                    store_key = None
                    try:
                        if hasattr(event, "get_sender_id"):
                            sid = event.get_sender_id()
                            if sid is not None:
                                store_key = str(sid)
                    except Exception:
                        store_key = None
                    if not store_key:
                        try:
                            sname = event.get_sender_name()
                            if sname:
                                store_key = str(sname)
                        except Exception:
                            store_key = None
                    if not store_key and unified_value:
                        store_key = unified_value
                    if store_key and unified_value:
                        self.unified_store.set(store_key, unified_value)
                except Exception:
                    self.logger.exception("记录 unified 失败")

                # 构造请求
                url = rule.get("url")
                method = (rule.get("method") or "GET").upper()
                request_params = {}
                texts, images, videos, records = self._collect_components(event)
                matched_keyword = None
                for k in (keywords if isinstance(keywords, (list, tuple)) else [keywords]):
                    if k and k in message_str:
                        matched_keyword = k
                        break
                body_fields = rule.get("body_fields")
                if body_fields and isinstance(body_fields, list):
                    for fld in body_fields:
                        fname = fld.get("name")
                        ftype = (fld.get("type") or "text").lower()
                        if not fname:
                            continue
                        if ftype == "text":
                            if matched_keyword:
                                proc = message_str.replace(matched_keyword, "", 1).lstrip()
                            else:
                                proc = message_str
                            value = proc if proc else ",".join(t.strip() for t in texts if t and t.strip())
                            request_params[fname] = value
                        elif ftype == "image":
                            request_params[fname] = ",".join(images)
                        elif ftype == "video":
                            request_params[fname] = ",".join(videos)
                        elif ftype in ("record", "voice"):
                            request_params[fname] = ",".join(records)
                        else:
                            request_params[fname] = ",".join(texts) if texts else message_str
                else:
                    request_params = rule.get("params") or {}
                    if rule.get("pass_event"):
                        request_params.update({
                            "session_id": getattr(event, "session_id", None),
                            "message_id": getattr(event, "message_id", None),
                            "message_str": getattr(event, "message_str", None),
                            "timestamp": getattr(event, "timestamp", None),
                        })

                # 调用外部 API
                from ..api.request import fetch_json
                try:
                    resp = await fetch_json(url, method=method, params=request_params, headers=rule.get("headers"))
                except Exception:
                    self.logger.exception("外部接口失败")
                    await event.send(event.plain_result(rule.get("on_error") or "接口调用失败"))
                    event.stop_event()
                    return True

                # 回复
                reply_type = rule.get("reply_type", "text")
                if reply_type == "text":
                    content = rule.get("text_template") or str(resp)
                    chain = [Plain(content)]
                    await event.send(event.chain_result(chain))
                    event.stop_event()
                    return True
                elif reply_type == "image":
                    image_path = rule.get("image_path") or resp
                    if isinstance(resp, str) and not os.path.exists(str(image_path)):
                        image_path = await self.cache_utils.cache_media(str(resp), "image")
                    if isinstance(image_path, str) and os.path.exists(image_path):
                        chain = [Image.fromFileSystem(str(image_path))]
                        await event.send(event.chain_result(chain))
                    else:
                        await event.send(event.image_result(image_path))
                    event.stop_event()
                    return True
                elif reply_type == "video":
                    video_path = rule.get("video_path") or resp
                    if isinstance(resp, str) and not os.path.exists(str(video_path)):
                        video_path = await self.cache_utils.cache_media(str(resp), "video")
                    if isinstance(video_path, str) and os.path.exists(video_path):
                        chain = [Video.fromFileSystem(str(video_path))]
                        await event.send(event.chain_result(chain))
                    else:
                        if hasattr(event, "video_result"):
                            await event.send(event.video_result(video_path))
                        else:
                            await event.send(event.plain_result(f"[视频] {video_path}"))
                    event.stop_event()
                    return True
                elif reply_type == "voice":
                    voice_path = rule.get("voice_path") or resp
                    if isinstance(resp, str) and not os.path.exists(str(voice_path)):
                        voice_path = await self.cache_utils.cache_media(str(resp), "voice")
                    if isinstance(voice_path, str) and os.path.exists(voice_path):
                        chain = [Record(file=voice_path, url=voice_path)]
                        await event.send(event.chain_result(chain))
                    else:
                        await event.send(event.plain_result(f"[语音] {voice_path}"))
                    event.stop_event()
                    return True
                elif reply_type == "file":
                    file_path = rule.get("file_path") or resp
                    if isinstance(resp, str) and not os.path.exists(str(file_path)):
                        file_path = await self.cache_utils.cache_media(str(resp), "file")
                    if isinstance(file_path, str) and os.path.exists(file_path):
                        from astrbot.api.message_components import File
                        filename = os.path.basename(file_path)
                        chain = [File(file=file_path, name=filename)]
                        await event.send(event.chain_result(chain))
                    else:
                        await event.send(event.plain_result(f"[文件] {file_path}"))
                    event.stop_event()
                    return True
                else:
                    await event.send(event.plain_result(str(resp)))
                    event.stop_event()
                    return True
        return False

    def _collect_components(self, ev: Any) -> Tuple[List[str], List[str], List[str], List[str]]:
        texts, images, videos, records = [], [], [], []
        comps = None
        try:
            if hasattr(ev, "get_messages") and callable(ev.get_messages):
                comps = ev.get_messages()
        except Exception:
            comps = None
        if comps is None:
            try:
                mo = getattr(ev, "message_obj", None)
                if mo is not None and hasattr(mo, "message"):
                    comps = mo.message
            except Exception:
                comps = None
        if comps is None:
            try:
                comps = getattr(ev, "message", None)
            except Exception:
                comps = None
        message_str_all = getattr(ev, "message_str", "") or ""
        if not comps:
            if message_str_all:
                texts = [message_str_all]
            return texts, images, videos, records
        for c in comps:
            try:
                c_cls = c.__class__.__name__.lower()
            except Exception:
                c_cls = ""
            txt = None
            if hasattr(c, "text"):
                txt = getattr(c, "text")
            elif hasattr(c, "content"):
                txt = getattr(c, "content")
            elif hasattr(c, "data"):
                txt = getattr(c, "data")
            img = None
            if hasattr(c, "url"):
                img = getattr(c, "url")
            elif hasattr(c, "file"):
                img = getattr(c, "file")
            elif hasattr(c, "path"):
                img = getattr(c, "path")
            vid = None
            if hasattr(c, "url") and "video" in c_cls:
                vid = getattr(c, "url")
            elif hasattr(c, "file") and "video" in c_cls:
                vid = getattr(c, "file")
            if txt is not None and isinstance(txt, str) and txt:
                texts.append(txt)
            elif img is not None:
                images.append(str(img))
            elif vid is not None:
                videos.append(str(vid))
            else:
                if "image" in c_cls and hasattr(c, "url"):
                    images.append(str(getattr(c, "url")))
                elif "video" in c_cls and hasattr(c, "url"):
                    videos.append(str(getattr(c, "url")))
        return texts, images, videos, records
