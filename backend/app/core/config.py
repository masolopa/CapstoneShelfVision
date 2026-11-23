"""Configuración explícita del despliegue local. No crea tablas al arrancar."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo

BACKEND_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    conninfo: str
    storage_root: Path
    origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173", "http://127.0.0.1:8011", "http://localhost:8011")
    cookie_secure: bool = False  # Solo HTTP local. Activar al desplegar HTTPS.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_security: str = "starttls"
    public_url: str = "http://127.0.0.1:8011"
    session_hours: int = 8
    model_max_pixels: int = 40_000_000


def load_settings() -> Settings:
    load_dotenv(BACKEND_ROOT / ".env", override=False)
    root = Path(os.getenv("REGOVA_STORAGE_ROOT", "storage"))
    if not root.is_absolute():
        root = BACKEND_ROOT / root
    return Settings(
        conninfo=make_conninfo(
            host=os.getenv("REGOVA_DB_HOST", "127.0.0.1"),
            port=os.getenv("REGOVA_DB_PORT", "5432"),
            dbname=os.getenv("REGOVA_DB_NAME", "REGOVA_BD"),
            user=os.getenv("REGOVA_DB_USER", "regova_app"),
            password=os.getenv("REGOVA_DB_PASSWORD", ""),
            connect_timeout=5,
            application_name="regova_api",
        ),
        storage_root=root.resolve(),
        smtp_host=os.getenv("REGOVA_SMTP_HOST", ""),
        smtp_port=int(os.getenv("REGOVA_SMTP_PORT", "587")),
        smtp_user=os.getenv("REGOVA_SMTP_USER", ""),
        smtp_password=os.getenv("REGOVA_SMTP_PASSWORD", ""),
        smtp_from=os.getenv("REGOVA_SMTP_FROM", ""),
        smtp_security=os.getenv("REGOVA_SMTP_SECURITY", "starttls"),
        public_url=os.getenv("REGOVA_PUBLIC_URL", "http://127.0.0.1:8011"),
        origins=tuple(s.strip() for s in os.getenv("REGOVA_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:8011,http://localhost:8011").split(",") if s.strip()),
        cookie_secure=os.getenv("REGOVA_COOKIE_SECURE", "false").lower() == "true",
    )
