"""Persistencia mínima con SQLite (historial y configuración).

Los overlays se guardan como archivos JPG en `overlays/` junto a la base de datos,
no dentro del JSON del resultado. Los análisis antiguos que aún tienen el overlay
en `result_json` siguen funcionando.
"""
import base64, json, os, sqlite3, threading
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.environ.get("SHELFVISION_DB", os.path.join(os.path.dirname(__file__), "..", "data", "shelfvision.db"))
OVERLAY_DIR = os.path.join(os.path.dirname(os.path.abspath(DB_PATH)), "overlays")
_lock = threading.Lock()

DEFAULT_SETTINGS = {"threshold": 30.0, "max_upload_mb": 10, "min_side_px": 200, "low_threshold": 70}


@contextmanager
def _conn():
    """Abre una conexión, confirma o revierte la transacción y SIEMPRE la cierra."""
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, filename TEXT,
            availability_pct REAL, empty_pct REAL, evaluable_area REAL, alert INTEGER,
            criticality TEXT, threshold REAL, result_json TEXT)""")
        if 'deleted_at' not in {row[1] for row in c.execute('PRAGMA table_info(analyses)')}:
            c.execute('ALTER TABLE analyses ADD COLUMN deleted_at TEXT')
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        with c:
            yield c
    finally:
        c.close()


def _overlay_path(analysis_id):
    return os.path.join(OVERLAY_DIR, f"{analysis_id}.jpg")


def save_analysis(filename, result, threshold, overlay_jpg: bytes):
    stored = {k: v for k, v in result.items() if k not in ("overlay_jpg_b64", "original_jpg_b64")}
    with _lock, _conn() as c:
        cur = c.execute(
            "INSERT INTO analyses (created_at, filename, availability_pct, empty_pct, evaluable_area, alert, criticality, threshold, result_json) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), filename, result["availability_pct"], result["empty_pct"],
             result["evaluable_area"], int(result["alert"]), result["criticality"], threshold, json.dumps(stored)))
        analysis_id = cur.lastrowid
        original = result.get("original_jpg_b64")
        if original:
            os.makedirs(OVERLAY_DIR, exist_ok=True)
            with open(os.path.join(OVERLAY_DIR, f"{analysis_id}_original.jpg"), "wb") as f:
                f.write(base64.b64decode(original))
        # Se escribe dentro de la transacción: si falla, la fila no queda confirmada.
        os.makedirs(OVERLAY_DIR, exist_ok=True)
        with open(_overlay_path(analysis_id), "wb") as f:
            f.write(overlay_jpg)
    return analysis_id


def get_analysis(analysis_id):
    with _lock, _conn() as c:
        row = c.execute("SELECT * FROM analyses WHERE id=? AND deleted_at IS NULL", (analysis_id,)).fetchone()
    if not row:
        return None
    data = json.loads(row["result_json"])
    data.update({"id": row["id"], "created_at": row["created_at"], "filename": row["filename"]})
    path = _overlay_path(row["id"])
    if os.path.exists(path):
        with open(path, "rb") as f:
            data["overlay_jpg_b64"] = base64.b64encode(f.read()).decode()
    original = os.path.join(OVERLAY_DIR, f"{analysis_id}_original.jpg")
    if os.path.isfile(original):
        with open(original, "rb") as f:
            data["original_jpg_b64"] = base64.b64encode(f.read()).decode()
    return data


def list_history(limit=50):
    with _lock, _conn() as c:
        rows = c.execute("SELECT id, created_at, filename, availability_pct, empty_pct, alert, criticality, result_json "
                         "FROM analyses WHERE deleted_at IS NULL ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    result=[]
    for row in rows:
        item=dict(row)
        metadata=json.loads(item.pop('result_json'))
        item['reference']=metadata.get('reference','')
        result.append(item)
    return result


def metrics():
    with _lock, _conn() as c:
        row = c.execute("SELECT COUNT(*) n, AVG(availability_pct) av, AVG(empty_pct) ev, SUM(alert) al FROM analyses WHERE deleted_at IS NULL").fetchone()
    n = row["n"] or 0
    return {"total_analyses": n,
            "avg_availability_pct": round(row["av"], 2) if n else None,
            "avg_empty_pct": round(row["ev"], 2) if n else None,
            "alerts": int(row["al"] or 0)}


def get_settings():
    with _lock, _conn() as c:
        rows = c.execute("SELECT key, value FROM settings").fetchall()
    s = dict(DEFAULT_SETTINGS)
    for r in rows:
        s[r["key"]] = json.loads(r["value"])
    # Upgrade legacy settings without changing already saved analyses.
    s['threshold']=max(1,min(99,round(s['threshold'])))
    s['low_threshold']=max(s['threshold']+1,min(100,round(s.get('low_threshold',70))))
    return s


def update_settings(new):
    with _lock, _conn() as c:
        for k, v in new.items():
            c.execute("INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                      (k, json.dumps(v)))
    return get_settings()


def update_analysis_metadata(analysis_id, changes):
    with _lock, _conn() as c:
        row=c.execute('SELECT result_json FROM analyses WHERE id=? AND deleted_at IS NULL',(analysis_id,)).fetchone()
        if not row:
            return None
        data=json.loads(row['result_json'])
        data.update({key:value for key,value in changes.items() if key in ('reference','observations')})
        data['updated_at']=datetime.now(timezone.utc).isoformat()
        c.execute('UPDATE analyses SET result_json=? WHERE id=?',(json.dumps(data),analysis_id))
    return get_analysis(analysis_id)


def delete_analysis(analysis_id):
    # Logical deletion preserves the original evidence and avoids destructive file operations.
    with _lock, _conn() as c:
        changed=c.execute('UPDATE analyses SET deleted_at=? WHERE id=? AND deleted_at IS NULL',
                          (datetime.now(timezone.utc).isoformat(),analysis_id)).rowcount
    return bool(changed)
