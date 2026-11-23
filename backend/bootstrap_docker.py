"""Inicializa la base y registra los pesos para un despliegue Docker."""
import json
import os
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from app.bootstrap import seed_local
from app.core.config import BACKEND_ROOT, load_settings
from app.core.database import Database
from app.services.storage import LocalStorage


def main(checkpoint=Path("/checkpoint/pesos.pt")):
    admin_password = os.environ["REGOVA_ADMIN_PASSWORD"]
    if len(admin_password) < 10:
        raise ValueError("REGOVA_ADMIN_PASSWORD debe tener al menos 10 caracteres")
    if not checkpoint.is_file():
        raise FileNotFoundError("REGOVA_CHECKPOINT debe apuntar a un archivo de pesos .pt")

    settings = load_settings()
    admin_conn = conninfo_to_dict(settings.conninfo)
    role = sql.Identifier(admin_conn["user"])
    app_password = sql.Literal(admin_conn["password"])
    admin_conn.update(user="postgres", password=os.environ["POSTGRES_PASSWORD"])
    with psycopg.connect(**admin_conn, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(801100)")
        if not conn.execute("SELECT to_regclass('regova.analisis')").fetchone()[0]:
            conn.execute((BACKEND_ROOT / "migrations/000_esquema_inicial.sql").read_text(encoding="utf-8"))
        # Estas migraciones se pueden reaplicar y tienen sus propias transacciones.
        for migration in sorted((BACKEND_ROOT / "migrations").glob("00[1-9]_*.sql")):
            conn.execute(migration.read_text(encoding="utf-8"))
        with conn.transaction():
            if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (os.environ["REGOVA_DB_USER"],)).fetchone():
                conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(role, app_password))
            for grant in (
                "GRANT USAGE ON SCHEMA regova TO {}",
                "GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA regova TO {}",
                "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA regova TO {}",
                "GRANT UPDATE ON regova.usuarios,regova.gondolas,regova.analisis,regova.configuraciones_vigentes,regova.alertas TO {}",
                "GRANT DELETE ON regova.sesiones,regova.recuperaciones_acceso TO {}",
            ):
                conn.execute(sql.SQL(grant).format(role))
        db = Database(settings.conninfo)
        storage = LocalStorage(settings.storage_root)
        seed_local(db, storage, admin_password, checkpoint)
        with db.connection() as app_conn:
            model = app_conn.execute(
                "SELECT artefacto_uri, metricas FROM modelos_vision WHERE metodo='yolo' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        status = storage.root / "model-status.json"
        temporary = status.with_suffix(".tmp")
        temporary.write_text(json.dumps({
            "checkpoint": str(storage.resolve(model["artefacto_uri"])),
            "metrics": model["metricas"] or None,
        }), encoding="utf-8")
        temporary.replace(status)


if __name__ == "__main__":
    main()
