import os
from pathlib import Path


class LocalStore:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    async def save_bytes(self, data: bytes, filename: str) -> str:
        path = Path(self.base_dir) / filename
        with open(path, "wb") as f:
            f.write(data)
        return str(path)

    async def cleanup(self, path: str):
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
