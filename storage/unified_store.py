import json
import os
from typing import Any, Dict, Optional


class UnifiedStore:
    def __init__(self, path: str):
        self.path = path
        self._store: Dict[str, Any] = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    try:
                        self._store = json.load(f)
                    except Exception:
                        self._store = {}
            else:
                self._store = {}
        except Exception:
            self._store = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._store, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    def set(self, key: str, value: Any) -> None:
        self._store[str(key)] = value
        self._save()

    def delete(self, key: str) -> bool:
        if str(key) in self._store:
            del self._store[str(key)]
            self._save()
            return True
        return False

    def all(self) -> Dict[str, Any]:
        return dict(self._store)
