import json
import os
from aiohttp import web
from .core.request import fetch_json


class HttpServer:
    def __init__(self, host: str, port: int, config_path: str, unified_store, handler, logger):
        self.host = host
        self.port = port
        self.config_path = config_path
        self.unified_store = unified_store
        self.handler = handler
        self.logger = logger
        self._runner = None

    async def start(self):
        app = web.Application()

        async def get_config(request):
            try:
                if os.path.exists(self.config_path):
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                else:
                    cfg = {}
                return web.json_response(cfg)
            except Exception:
                return web.json_response({})

        async def test_api(request):
            try:
                data = await request.json()
            except Exception:
                return web.json_response({"error": "invalid json"}, status=400)

            rule_index = data.get("rule_index")
            if rule_index is not None:
                try:
                    # ensure handler config is loaded
                    try:
                        self.handler._load_config()
                    except Exception:
                        pass
                    rules = getattr(self.handler, "_config", {}).get("rules", [])
                    rule = rules[int(rule_index)]
                    url = rule.get("url")
                    method = (rule.get("method") or "GET").upper()
                    params = rule.get("params") or {}
                    headers = rule.get("headers")
                except Exception:
                    return web.json_response({"error": "invalid rule_index"}, status=400)
            else:
                url = data.get("url")
                method = (data.get("method") or "GET").upper()
                params = data.get("params") or {}
                headers = data.get("headers")

            if not url:
                return web.json_response({"error": "url required"}, status=400)

            try:
                resp = await fetch_json(url, method=method, params=params, headers=headers)
                if isinstance(resp, (dict, list)):
                    return web.json_response({"ok": True, "response": resp})
                else:
                    return web.json_response({"ok": True, "response": str(resp)})
            except Exception:
                self.logger.exception("test_api 调用失败")
                return web.json_response({"ok": False, "error": "request failed"}, status=500)

        async def update_config(request):
            try:
                data = await request.json()
            except Exception:
                return web.json_response({"error": "invalid json"}, status=400)
            try:
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                # notify handler to reload
                try:
                    self.handler._load_config()
                except Exception:
                    pass
                return web.json_response({"ok": True})
            except Exception:
                return web.json_response({"ok": False}, status=500)

        async def send_message(request):
            # 仅支持 unified_msg_origin 方式
            try:
                data = await request.json()
            except Exception:
                return web.json_response({"error": "invalid json"}, status=400)
            unified = data.get("unified_msg_origin")
            msg_type = data.get("type", "text")
            content = data.get("content")
            if not unified or not content:
                return web.json_response({"error": "unified_msg_origin and content required"}, status=400)

            # 调用 handler 发送（直接使用 context.send_message）
            try:
                # build MessageChain via handler utilities
                await self.handler.send_proactive(unified, msg_type, content)
                return web.json_response({"ok": True})
            except Exception:
                self.logger.exception("主动发送失败")
                return web.json_response({"ok": False}, status=500)

        async def list_unified(request):
            return web.json_response(self.unified_store.all())

        async def delete_unified(request):
            try:
                data = await request.json()
            except Exception:
                return web.json_response({"error": "invalid json"}, status=400)
            key = data.get("key")
            if not key:
                return web.json_response({"error": "key required"}, status=400)
            ok = self.unified_store.delete(key)
            return web.json_response({"ok": ok})

        app.router.add_get("/get_config", get_config)
        app.router.add_post("/update_config", update_config)
        app.router.add_post("/test_api", test_api)
        app.router.add_post("/send_message", send_message)
        app.router.add_get("/list_unified", list_unified)
        app.router.add_post("/delete_unified", delete_unified)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, int(self.port))
        await site.start()
        self._runner = runner
        self.logger.info("HTTP server started on port %s", self.port)

    async def stop(self):
        try:
            if self._runner:
                await self._runner.cleanup()
        except Exception:
            pass
