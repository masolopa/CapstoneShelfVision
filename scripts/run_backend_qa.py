"""Prueba el backend en un PostgreSQL temporal; nunca usa la BD operativa."""
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import psycopg

root = Path(__file__).resolve().parents[1]
options = sorted(Path("C:/Program Files/PostgreSQL").glob("*/bin/postgres.exe"))
if not options:
    raise SystemExit("No se encontró PostgreSQL instalado en Program Files.")
pgbin = options[-1].parent
work = root / "work"
work.mkdir(exist_ok=True)
folder = Path(tempfile.mkdtemp(prefix="qa-postgres-", dir=work))
data = folder / "data"
flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
with socket.socket() as probe:
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
with (folder/"initdb.log").open("w") as log:
    subprocess.run([str(pgbin/"initdb.exe"),"-D",str(data),"-U","qa_owner","--auth=trust","--encoding=UTF8","--locale=C"],stdout=log,stderr=log,check=True,creationflags=flags)
base = f"host=127.0.0.1 port={port} user=qa_owner connect_timeout=2"
with (folder/"postgres.log").open("w") as log:
    process = subprocess.Popen([str(pgbin/"postgres.exe"),"-D",str(data),"-h","127.0.0.1","-p",str(port)],stdout=log,stderr=log,creationflags=flags)
    try:
        for attempt in range(30):
            try:
                with psycopg.connect(base+" dbname=postgres",autocommit=True) as c:
                    c.execute('CREATE DATABASE "REGOVA_QA_TEST"')
                break
            except psycopg.OperationalError:
                if process.poll() is not None:
                    raise RuntimeError("PostgreSQL no arrancó; consulta postgres.log.")
                time.sleep(.3)
        else:
            raise RuntimeError("PostgreSQL no respondió a tiempo.")
        dsn=base+" dbname=REGOVA_QA_TEST"
        with psycopg.connect(dsn,autocommit=True) as c:
            for name in ["000_esquema_inicial.sql","001_sesiones_api.sql","002_ubicacion_por_analisis.sql","003_recuperacion_acceso.sql"]:
                c.execute((root/"backend/migrations"/name).read_text(encoding="utf-8"))
        env=dict(os.environ,REGOVA_TEST_DSN=dsn)
        (root/"reports/qa").mkdir(parents=True,exist_ok=True)
        code=subprocess.run([sys.executable,"-m","pytest","backend/tests","-q","-p","no:cacheprovider","--basetemp",str(folder/"pytest"),"--junitxml","reports/qa/backend-junit.xml","--tb=short"],cwd=root,env=env,creationflags=flags).returncode
        print("Base de prueba aislada; no se utilizó REGOVA_BD. Evidencia: reports/qa/backend-junit.xml")
    finally:
        subprocess.run([str(pgbin/"pg_ctl.exe"),"-D",str(data),"-m","fast","-w","stop"],stdout=log,stderr=log,creationflags=flags)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=10)
raise SystemExit(code)
