from typing import Any, Tuple, List

def collect_components(ev: Any) -> Tuple[List[str], List[str], List[str], List[str]]:
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
