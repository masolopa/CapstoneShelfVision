"""Preparación inicial y arranque guiado. No instala programas del sistema."""
import argparse
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
URL = "http://127.0.0.1:8011"
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / "data/training/ultralytics_config"))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "data/training/mpl_config"))


def run(command, **kwargs):
    subprocess.run([str(v) for v in command], check=True, cwd=ROOT, **kwargs)


def python_for(name):
    return ROOT / name / "Scripts/python.exe"


def environment_ok(name, modules):
    exe = python_for(name)
    if not exe.is_file():
        return False
    result = subprocess.run([str(exe), "-c", "import sys; assert sys.version_info[:2]==(3,13); " + "; ".join("import " + m for m in modules)],
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0


def prepare_environment(name, modules):
    if environment_ok(name, modules):
        print(f"[OK] Entorno {name} disponible.", flush=True)
        return False
    path = ROOT / name
    if path.exists():
        backups = ROOT / "backups/entornos"
        backups.mkdir(parents=True, exist_ok=True)
        target = backups / (name.lstrip('.') + '-' + str(time.time_ns()))
        if not path.resolve().is_relative_to(ROOT) or not target.resolve().is_relative_to(ROOT):
            raise RuntimeError("Ruta de entorno fuera del proyecto")
        path.rename(target)  # Respaldo reversible; no borra el entorno anterior.
    print(f"Preparando {name}; requiere internet en esta primera instalación…", flush=True)
    run([sys.executable, "-m", "venv", path])
    return True


def pg_bin():
    path = shutil.which("pg_restore")
    if path:
        return Path(path).parent
    folder = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "PostgreSQL"
    options = sorted((p for p in folder.glob("*/bin") if (p / "pg_restore.exe").is_file()),
                     key=lambda p: int(p.parent.name) if p.parent.name.isdigit() else 0, reverse=True)
    if not options:
        raise RuntimeError("Falta PostgreSQL. Instala PostgreSQL 18 para Windows antes de preparar este equipo.")
    return options[0]


def prepare_database():
    # Imports después de preparar .venv. No se necesita guardar la clave del propietario.
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    from dotenv import dotenv_values
    import preparar_local

    binaries = pg_bin()
    env_path = ROOT / ".env"
    values = dict(dotenv_values(env_path)) if env_path.is_file() else {}
    # El despliegue preparado por este acceso es local. No reutilizar rutas personales.
    values.update(REGOVA_DB_HOST="127.0.0.1", REGOVA_DB_PORT=values.get("REGOVA_DB_PORT") or "5432",
                  REGOVA_DB_NAME=values.get("REGOVA_DB_NAME") or "REGOVA_BD", REGOVA_STORAGE_ROOT="./storage")
    owner = input("Usuario propietario de PostgreSQL [postgres]: ").strip() or "postgres"
    password = getpass.getpass("Contraseña PostgreSQL de este equipo: ")
    common = dict(host=values["REGOVA_DB_HOST"], port=values["REGOVA_DB_PORT"], user=owner, password=password, connect_timeout=5)
    name = values["REGOVA_DB_NAME"]
    with psycopg.connect(make_conninfo(dbname="postgres", **common), autocommit=True) as c:
        exists = c.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone()
        if not exists:
            c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    with psycopg.connect(make_conninfo(dbname=name, **common), autocommit=True) as c:
        installed = bool(c.execute("SELECT to_regclass('regova.analisis')").fetchone()[0])
        nonempty = c.execute("SELECT count(*) FROM pg_class cl JOIN pg_namespace n ON n.oid=cl.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%' AND cl.relkind='r'").fetchone()[0]
    if not installed and nonempty:
        raise RuntimeError("La base existe con otras tablas. No se sobrescribirá; revisar su contenido.")
    if not installed:
        dumps = sorted((ROOT / "backups/postgresql").glob("*.dump"), key=lambda p: p.stat().st_mtime_ns, reverse=True)
        if dumps:
            print("Restaurando el respaldo operacional; conserva usuarios y sus contraseñas…", flush=True)
            env = os.environ.copy()
            env["PGPASSWORD"] = password
            run([binaries / "pg_restore.exe", "-h", common["host"], "-p", common["port"], "-U", owner,
                 "-d", name, "--no-owner", "--no-privileges", "--single-transaction", "--exit-on-error", dumps[0]], env=env)
            with psycopg.connect(make_conninfo(dbname=name, **common), autocommit=True) as c:
                c.execute("DELETE FROM regova.sesiones")
        else:
            with psycopg.connect(make_conninfo(dbname=name, **common), autocommit=True) as c:
                c.execute((ROOT / "migrations/000_esquema_inicial.sql").read_text(encoding="utf-8"))
    else:
        print("[OK] Base existente: se conserva sin restaurar encima.", flush=True)
    history_script = ROOT / "migrations/historico/01_Conservar_Historial_PostgreSQL.sql"
    if history_script.is_file():
        with psycopg.connect(make_conninfo(dbname=name, **common), autocommit=True) as c:
            if not c.execute("SELECT to_regclass('regova_legacy.analisis')").fetchone()[0]:
                c.execute(history_script.read_text(encoding="utf-8"))
    env_path.write_text("\n".join(f"{k}={json.dumps(v)}" for k,v in values.items() if v is not None)+"\n", encoding="utf-8")
    preparar_local.prepare(owner_password=password, owner_override=owner)


def preflight(check_model=True):
    if not (ROOT / ".env").is_file():
        raise RuntimeError("Falta la configuración. Ejecuta PREPARAR_EQUIPO.bat una vez antes de iniciar.")
    if not (PROJECT / "dist/index.html").is_file():
        raise RuntimeError("Falta el frontend compilado en dist. Usa una copia completa de Regova.")
    if not environment_ok(".venv-train", ("torch", "ultralytics")):
        raise RuntimeError("El entorno del detector no está disponible. Ejecuta PREPARAR_EQUIPO.bat.")
    from app.core.config import load_settings
    from app.core.database import Database
    from app.services.storage import LocalStorage
    cfg = load_settings()
    with Database(cfg.conninfo).connection() as c:
        if not c.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='regova' AND table_name='analisis' AND column_name='pasillo'").fetchone():
            raise RuntimeError("Falta actualizar el esquema de ubicación por pasillo.")
        if not c.execute("SELECT to_regclass('regova.sesiones')").fetchone()["to_regclass"]:
            raise RuntimeError("Falta preparar las sesiones de la API.")
        model = c.execute("SELECT artefacto_uri,sha256 FROM modelos_vision WHERE metodo='yolo' ORDER BY id DESC LIMIT 1").fetchone()
    if not model:
        raise RuntimeError("No hay un modelo YOLO registrado. Ejecuta PREPARAR_EQUIPO.bat.")
    weights = LocalStorage(cfg.storage_root).resolve(model["artefacto_uri"])
    import hashlib
    if not weights.is_file() or hashlib.sha256(weights.read_bytes()).hexdigest() != model["sha256"]:
        raise RuntimeError("Faltan los pesos del modelo o su huella no coincide. Revisa que storage se haya copiado completo.")
    print("[OK] PostgreSQL, esquema, frontend y pesos del modelo.", flush=True)
    if check_model:
        run([python_for(".venv-train"), "-c", "import sys,torch; from ultralytics import YOLO; YOLO(sys.argv[1]); print('[OK] Detector cargado. Dispositivo: '+('GPU' if torch.cuda.is_available() else 'CPU'))", weights])


def start():
    preflight()
    try:
        with urllib.request.urlopen(URL + "/api/health", timeout=2) as response:
            health = json.load(response)
    except OSError:
        health = None
    pilot = os.environ.get("REGOVA_SURFACE_PILOT") == "1"
    if health is not None:
        if pilot:
            raise RuntimeError("Regova ya está en ejecución. Detén el servidor con Ctrl+C en su consola y vuelve a abrir INICIAR_PILOTO_SUPERFICIE.bat.")
        if health.get("service") != "regova" or health.get("version") != "1.1.0":
            raise RuntimeError("El puerto 8011 está ocupado por otra aplicación o una versión anterior. Cierra su consola y vuelve a iniciar.")
        webbrowser.open(URL)
        print("Regova ya estaba encendido. Se abrió el navegador.")
        return
    env = os.environ.copy()
    env["SHELFVISION_TRAIN_PYTHON"] = str(python_for(".venv-train"))
    env["YOLO_CONFIG_DIR"] = str(ROOT / "data/training/ultralytics_config")
    env["MPLCONFIGDIR"] = str(ROOT / "data/training/mpl_config")
    print("Iniciando Regova. Mantén esta ventana abierta mientras lo usas.", flush=True)
    if pilot:
        print("Piloto de superficie activo. Marca la región de análisis y ejecuta un análisis nuevo.", flush=True)
    process = subprocess.Popen([str(python_for(".venv")), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8011", "--workers", "1"], cwd=ROOT, env=env)
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise RuntimeError("La API no pudo iniciar. Revisa el mensaje que aparece arriba.")
            try:
                with urllib.request.urlopen(URL + "/api/ready", timeout=2) as r:
                    if r.status == 200:
                        webbrowser.open(URL)
                        print("REGOVA LISTO. Puedes presentar desde el navegador.", flush=True)
                        process.wait()
                        return
            except OSError:
                time.sleep(.5)
        raise RuntimeError("La API no quedó lista a tiempo. Revisa su salida en esta ventana.")
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=15)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("preparar", "configurar", "comprobar", "iniciar"))
    mode = parser.parse_args().mode
    if mode == "preparar":
        if sys.version_info[:2] != (3,13):
            raise RuntimeError("Instala Python 3.13 de 64 bits para recrear los entornos comprobados de Regova.")
        pg_bin()
        if prepare_environment(".venv", ("fastapi","psycopg","pwdlib","reportlab","cv2","dotenv","PIL")):
            run([python_for(".venv"), "-m", "pip", "install", "--disable-pip-version-check", "--no-deps", "-r", ROOT / "requirements-app.lock.txt"])
        if prepare_environment(".venv-train", ("torch","ultralytics")):
            run([python_for(".venv-train"), "-m", "pip", "install", "torch==2.6.0", "torchvision==0.21.0", "--index-url", "https://download.pytorch.org/whl/cpu"])
            run([python_for(".venv-train"), "-m", "pip", "install", "ultralytics==8.3.159", "numpy==2.2.6", "opencv-python==4.12.0.88", "pillow==11.2.1"])
        for name in (".venv", ".venv-train"):
            run([python_for(name), "-m", "pip", "check"])
        run([python_for(".venv"), __file__, "configurar"])
    elif mode == "configurar":
        prepare_database()
        preflight()
        print("Equipo preparado. Realiza un ensayo de análisis antes de la presentación.")
    elif mode == "comprobar":
        preflight()
    else:
        start()


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("Operación cancelada.")
        raise SystemExit(1)
    except Exception as error:
        # No imprimir DSN, contraseñas ni configuración privada.
        print("\nNO SE PUDO COMPLETAR: " + (str(error) if isinstance(error, RuntimeError) else type(error).__name__))
        print("Conserva este mensaje para revisarlo; no necesitas escribir comandos.")
        raise SystemExit(1)
