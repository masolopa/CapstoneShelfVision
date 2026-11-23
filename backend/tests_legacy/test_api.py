import os, tempfile, cv2, numpy as np
os.environ["SHELFVISION_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def _img_bytes(fill=230, noisy=False):
    img = np.full((300, 400, 3), fill, np.uint8)
    if noisy:
        img[:, :200] = np.random.default_rng(1).integers(0, 255, (300, 200, 3), dtype=np.uint8)
    return cv2.imencode(".png", img)[1].tobytes()

def test_health():
    assert client.get("/api/health").json()["status"] == "ok"

def test_analyze_ok_y_historial():
    r = client.post("/api/analyze", files={"file": ("g.png", _img_bytes(noisy=True), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["availability_pct"] <= 100
    assert round(body["availability_pct"] + body["empty_pct"], 1) == 100
    assert client.get(f"/api/analyze/{body['id']}").status_code == 200
    assert any(h["id"] == body["id"] for h in client.get("/api/history").json())

def test_tipo_no_permitido():
    r = client.post("/api/analyze", files={"file": ("x.gif", b"GIF89a", "image/gif")})
    assert r.status_code == 415

def test_imagen_corrupta():
    r = client.post("/api/analyze", files={"file": ("x.png", b"basura", "image/png")})
    assert r.status_code == 422

def test_settings_y_umbral_invalido():
    assert client.put("/api/settings", json={"threshold": 45}).json()["threshold"] == 45
    assert client.put("/api/settings", json={"threshold": 150}).status_code == 422
    client.put("/api/settings", json={"threshold": 30})

def test_no_existe():
    assert client.get("/api/analyze/999999").status_code == 404

def test_metrics():
    m = client.get("/api/metrics").json()
    assert m["total_analyses"] >= 1

def test_reporte_pdf():
    r = client.post("/api/analyze", files={"file": ("g.png", _img_bytes(noisy=True), "image/png")})
    rid = r.json()["id"]
    pdf = client.get(f"/api/analyze/{rid}/report.pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"

def test_reporte_no_existe():
    assert client.get("/api/analyze/999999/report.pdf").status_code == 404

def test_analisis_con_estructural_y_resultado_completo():
    struct = '[[[0.5,0],[1,0],[1,1],[0.5,1]]]'
    r = client.post("/api/analyze", data={"structural": struct},
                    files={"file": ("g.png", _img_bytes(noisy=True), "image/png")})
    assert r.status_code == 200
    b = r.json()
    assert b["status"] == "evaluable" and b["structural_area"] > 0
    assert "areas_px" in b and "unknown" in b["areas_px"] and isinstance(b["warnings"], list)

def test_poligono_invalido_en_api():
    r = client.post("/api/analyze", data={"roi": "[[[0,0],[2,0],[1,1]]]"},
                    files={"file": ("g.png", _img_bytes(), "image/png")})
    assert r.status_code == 422

def test_roi_malformado_no_da_500():
    r = client.post("/api/analyze", data={"roi": "[1,2,3]"},
                    files={"file": ("g.png", _img_bytes(), "image/png")})
    assert r.status_code == 422
