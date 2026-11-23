"""Almacenamiento local privado: claves generadas por el servidor."""
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def resolve(self, key: str) -> Path:
        relative = Path(key)
        if relative.is_absolute() or ".." in relative.parts or ":" in key or "\\" in key:
            raise ValueError("Referencia de archivo inválida")
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError("Referencia fuera del almacenamiento")
        return path

    def put(self, content: bytes, folder: str, extension: str) -> dict:
        date = datetime.now(timezone.utc)
        key = f"{folder}/{date:%Y/%m}/{uuid4().hex}.{extension}"
        path = self.resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as stream:
                stream.write(content)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return {"uri": key, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}

    def read(self, key):
        return self.resolve(key).read_bytes()

    def remove(self, key):
        self.resolve(key).unlink(missing_ok=True)
