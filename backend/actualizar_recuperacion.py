"""Aplica la tabla de recuperación de acceso; conserva usuarios y contraseñas."""
import getpass
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from dotenv import dotenv_values
from app.core.config import BACKEND_ROOT


def main():
    values = dotenv_values(BACKEND_ROOT / ".env")
    if not values.get("REGOVA_DB_NAME"):
        raise ValueError("Falta la configuración del backend. Primero prepara PostgreSQL.")
    owner = input("Usuario propietario [postgres]: ").strip() or "postgres"
    password = getpass.getpass("Contraseña PostgreSQL del propietario: ")
    conninfo = make_conninfo(host=values.get("REGOVA_DB_HOST", "127.0.0.1"),
                            port=values.get("REGOVA_DB_PORT", "5432"),
                            dbname=values["REGOVA_DB_NAME"], user=owner, password=password, connect_timeout=5)
    with psycopg.connect(conninfo, autocommit=True) as c:
        c.execute((BACKEND_ROOT / "migrations/003_recuperacion_acceso.sql").read_text(encoding="utf-8"))
        c.execute(sql.SQL("GRANT SELECT,INSERT,DELETE ON regova.recuperaciones_acceso TO {}").format(sql.Identifier(values.get("REGOVA_DB_USER", "regova_app"))))
    print("Actualización terminada: recuperación de acceso por correo.")
    print("No se cambiaron cuentas ni contraseñas. Reinicia EJECUTAR.bat y actualiza el navegador con Ctrl+F5.")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        print(error)
        raise SystemExit(1)
    except psycopg.Error:
        print("No se pudo aplicar la actualización. Se revirtieron los cambios de esa transacción.")
        print("Revisa la contraseña del propietario y que la base corresponda al esquema inicial de REGOVA.")
        raise SystemExit(1)
    except (EOFError, KeyboardInterrupt):
        print("Operación cancelada.")
        raise SystemExit(1)
