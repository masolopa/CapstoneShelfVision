"""Preparación de datos nuevos; no importa SQLite ni usuarios del navegador."""
import hashlib
from pathlib import Path
from psycopg.types.json import Jsonb
from app.core.security import passwords
from app.repositories import audit


def seed_local(db, storage, admin_password, checkpoint=None, model_metrics=None):
    """Reejecutable: no cambia contraseñas, umbrales ni datos ya existentes."""
    encoded = passwords.hash(admin_password)
    model_file = None
    digest = None
    if checkpoint:
        content = Path(checkpoint).read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        # Una clave por contenido evita sobrescribir una versión anterior.
        key = f"modelos/yolo/{digest}/pesos.pt"
        target = storage.resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError("Los pesos locales no coinciden con su huella")
        else:
            with target.open("xb") as f:
                f.write(content)
        model_file = key
    with db.connection() as c:
        c.execute("INSERT INTO locales(codigo,nombre,direccion) VALUES('DEMO-RM-MAIPU','Local piloto Maipú (ficticio)','Maipú, Región Metropolitana, Chile') ON CONFLICT(codigo) DO NOTHING")
        local = c.execute("SELECT id FROM locales WHERE codigo='DEMO-RM-MAIPU'").fetchone()["id"]
        c.execute("SELECT pg_advisory_xact_lock(%s)", (local,))
        existing = c.execute("SELECT * FROM usuarios WHERE codigo='ADM-001'").fetchone()
        if existing and (existing["local_id"] != local or existing["rol"] != "administrador" or not existing["activo"] or existing["eliminado_en"]):
            raise ValueError("ADM-001 ya existe con una asignación incompatible; revisar antes de continuar")
        if not existing:
            admin = c.execute("INSERT INTO usuarios(local_id,codigo,nombre,password_hash,rol) VALUES(%s,'ADM-001','Administrador principal',%s,'administrador') RETURNING id", (local, encoded)).fetchone()["id"]
            audit(c, admin, "usuario.crear", "usuarios", admin, {"code": "ADM-001", "name": "Administrador principal", "role": "admin_principal"})
        else:
            admin = existing["id"]
        if not c.execute("SELECT 1 FROM configuraciones_vigentes WHERE local_id=%s", (local,)).fetchone():
            version = c.execute("SELECT coalesce(max(version),0)+1 AS n FROM configuraciones_analisis WHERE local_id=%s", (local,)).fetchone()["n"]
            config = c.execute("INSERT INTO configuraciones_analisis(local_id,version,umbral_critico,umbral_bajo,max_carga_mb,lado_minimo_px,creado_por) VALUES(%s,%s,30,70,10,200,%s) RETURNING id", (local, version, admin)).fetchone()["id"]
            c.execute("INSERT INTO configuraciones_vigentes(local_id,configuracion_id) VALUES(%s,%s)", (local, config))
        c.execute("INSERT INTO modelos_vision(nombre,version,metodo) VALUES('OpenCV baseline','regova-api-1','heuristic') ON CONFLICT(nombre,version) DO NOTHING")
        if model_file:
            c.execute("INSERT INTO modelos_vision(nombre,version,metodo,artefacto_uri,sha256,metricas) VALUES('Detector YOLO',%s,'yolo',%s,%s,%s) ON CONFLICT(nombre,version) DO NOTHING", ("sha256:"+digest[:48], model_file, digest, Jsonb(model_metrics or {})))
    return local
