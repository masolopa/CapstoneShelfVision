import base64, json, os, sqlite3, tempfile, cv2, numpy as np
os.environ["SHELFVISION_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
from fastapi.testclient import TestClient
from app import store
from app.main import app

client = TestClient(app)

def _img_bytes():
    img = np.full((300, 400, 3), 230, np.uint8)
    img[:, :200] = np.random.default_rng(1).integers(0, 255, (300, 200, 3), dtype=np.uint8)
    return cv2.imencode(".png", img)[1].tobytes()

def _analyze():
    r = client.post("/api/analyze", files={"file": ("g.png", _img_bytes(), "image/png")})
    assert r.status_code == 200
    return r.json()

def test_overlay_se_guarda_como_archivo_fuera_del_json():
    body = _analyze()
    rid = body["id"]
    with sqlite3.connect(store.DB_PATH) as c:
        (raw,) = c.execute("SELECT result_json FROM analyses WHERE id=?", (rid,)).fetchone()
    assert "overlay_jpg_b64" not in json.loads(raw)
    assert os.path.isfile(os.path.join(store.OVERLAY_DIR, f"{rid}.jpg"))

def test_get_devuelve_el_mismo_overlay_que_la_respuesta():
    body = _analyze()
    stored = client.get(f"/api/analyze/{body['id']}").json()
    assert stored["overlay_jpg_b64"] == body["overlay_jpg_b64"]
    assert base64.b64decode(stored["overlay_jpg_b64"])[:2] == b"\xff\xd8"

def test_analisis_antiguo_con_overlay_en_json_sigue_legible():
    legacy = {"status": "evaluable", "availability_pct": 50.0, "empty_pct": 50.0, "evaluable_area": 10.0,
              "alert": False, "criticality": "aceptable", "overlay_jpg_b64": "AAAA"}
    with store._conn() as c:
        cur = c.execute("INSERT INTO analyses (created_at, filename, availability_pct, empty_pct, evaluable_area, "
                        "alert, criticality, threshold, result_json) VALUES ('t','old.png',50,50,10,0,'aceptable',30,?)",
                        (json.dumps(legacy),))
        rid = cur.lastrowid
    assert store.get_analysis(rid)["overlay_jpg_b64"] == "AAAA"
