"""Asistente de preparación PostgreSQL local. Contraseñas mediante getpass."""
import getpass
import json
import os
import secrets
from pathlib import Path
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from dotenv import dotenv_values
from app.bootstrap import seed_local
from app.core.config import BACKEND_ROOT
from app.core.database import Database
from app.services.storage import LocalStorage


def prepare(owner_password=None, owner_override=None):
    env_path = BACKEND_ROOT / ".env"
    previous = dict(dotenv_values(env_path)) if env_path.is_file() else {}
    dbname = previous.get("REGOVA_DB_NAME") or input("Base de datos [REGOVA_BD]: ").strip() or "REGOVA_BD"
    host = previous.get("REGOVA_DB_HOST") or "127.0.0.1"
    port = previous.get("REGOVA_DB_PORT") or "5432"
    owner = owner_override or input("Usuario propietario para preparar [postgres]: ").strip() or "postgres"
    owner_password = owner_password if owner_password is not None else getpass.getpass("Contraseña PostgreSQL del propietario (no se guardará): ")
    app_user = previous.get("REGOVA_DB_USER") or "regova_app"
    if app_user == owner:
        raise RuntimeError("Usa un rol de aplicación diferente del propietario de la base")
    app_password = previous.get("REGOVA_DB_PASSWORD") or secrets.token_urlsafe(36)
    with psycopg.connect(make_conninfo(host=host, port=port, dbname=dbname, user=owner, password=owner_password, connect_timeout=5), autocommit=True) as c:
        if not c.execute("SELECT to_regclass('regova.analisis')").fetchone()[0]:
            raise RuntimeError("Falta crear primero el esquema de REGOVA mediante el script SQL inicial")
        # La migración incluye su propia transacción y no modifica el historial legacy.
        for migration in ("001_sesiones_api.sql", "002_ubicacion_por_analisis.sql", "003_recuperacion_acceso.sql"):
            c.execute((BACKEND_ROOT / "migrations" / migration).read_text(encoding="utf-8"))
        with c.transaction():
            exists = c.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (app_user,)).fetchone()
            if not exists:
                c.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(app_user), sql.Literal(app_password)))
            elif not previous.get("REGOVA_DB_PASSWORD"):
                raise RuntimeError("El rol de aplicación ya existe. Configura su contraseña en backend/.env antes de repetir; no se cambió su contraseña.")
            privileges = c.execute("SELECT rolsuper,rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname=%s", (app_user,)).fetchone()
            if any(privileges):
                raise RuntimeError("El rol de aplicación debe carecer de permisos administrativos globales")
            role = sql.Identifier(app_user)
            c.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(dbname), role))
            c.execute(sql.SQL("GRANT USAGE ON SCHEMA regova TO {}").format(role))
            c.execute(sql.SQL("GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA regova TO {}").format(role))
            c.execute(sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA regova TO {}").format(role))
            c.execute(sql.SQL("GRANT UPDATE ON regova.usuarios,regova.gondolas,regova.analisis,regova.configuraciones_vigentes,regova.alertas TO {}").format(role))
            c.execute(sql.SQL("GRANT DELETE ON regova.sesiones,regova.recuperaciones_acceso TO {}").format(role))
    root = Path(previous.get("REGOVA_STORAGE_ROOT") or "storage")
    if not root.is_absolute():
        root = BACKEND_ROOT / root
    conninfo = make_conninfo(host=host, port=port, dbname=dbname, user=app_user, password=app_password, connect_timeout=5)
    # JSON quoted values son válidos para dotenv y conservan caracteres especiales.
    values = {**previous, "REGOVA_DB_HOST": host, "REGOVA_DB_PORT": port, "REGOVA_DB_NAME": dbname,
              "REGOVA_DB_USER": app_user, "REGOVA_DB_PASSWORD": app_password, "REGOVA_STORAGE_ROOT": str(root.resolve()),
              "REGOVA_COOKIE_SECURE": "false"}
    env_path.write_text("\n".join(f"{k}={json.dumps(v)}" for k,v in values.items() if v is not None)+"\n", encoding="utf-8")
    db = Database(conninfo)
    with db.connection() as c:
        existing = c.execute("SELECT 1 FROM usuarios WHERE codigo='ADM-001'").fetchone()
    if existing:
        admin_password = secrets.token_urlsafe(20)  # No se aplica a una cuenta ya existente.
        print("ADM-001 ya existe: se conservará su contraseña.")
    else:
        admin_password = getpass.getpass("Nueva contraseña para ADM-001 (mínimo 10 caracteres): ")
        confirm = getpass.getpass("Repite la contraseña de ADM-001: ")
        if len(admin_password) < 10 or admin_password != confirm:
            raise RuntimeError("Las contraseñas deben coincidir y tener al menos 10 caracteres")
    status = BACKEND_ROOT / "data/training/status.json"
    data = json.loads(status.read_text(encoding="utf-8")) if status.is_file() else {}
    checkpoint = (BACKEND_ROOT / data["checkpoint"]).resolve() if data.get("checkpoint") else None
    if checkpoint and not checkpoint.is_relative_to(BACKEND_ROOT):
        raise RuntimeError("Referencia de checkpoint fuera del backend")
    seed_local(db, LocalStorage(root), admin_password, checkpoint if checkpoint and checkpoint.is_file() else None, data.get("metrics"))
    print("Preparación terminada. Configuración privada guardada en backend/.env.")
    print("Inicia EJECUTAR.bat e ingresa como ADM-001. Crea usuarios y analiza indicando el pasillo de cada captura.")
    if not checkpoint or not checkpoint.is_file():
        print("No se encontró checkpoint YOLO: registra uno antes de analizar desde la interfaz.")


if __name__ == "__main__":
    try:
        prepare()
    except (RuntimeError, ValueError) as error:
        print(str(error))
        raise SystemExit(1)
    except psycopg.Error:
        print("No se pudo preparar PostgreSQL. Verifica base, propietario, contraseña y permisos. No compartas la contraseña en el chat.")
        raise SystemExit(1)
