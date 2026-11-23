import os, tempfile, cv2, numpy as np
os.environ["SHELFVISION_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.vision import yolo_detector
from app.vision.baseline import analyze_boxes_pixels
from app.vision.masks import Category, polygon_mask

client = TestClient(app)
ROI = "[[0,0],[1,0],[1,1],[0,1]]"


def _img_bytes():
    img = np.full((300, 400, 3), 230, np.uint8)
    return cv2.imencode(".png", img)[1].tobytes()


def test_yolo_sin_roi_avisa_en_advertencias(monkeypatch):
    def fake(img, conf=0.25):
        return np.zeros((0, 4)), np.zeros(0)
    monkeypatch.setattr(yolo_detector, "detect_all", lambda img, conf=0.25: {"productos": fake(img), "vacios": (np.zeros((0, 4)), np.zeros(0))})
    r = client.post("/api/analyze", data={"method": "yolo"}, files={"file": ("g.png", _img_bytes(), "image/png")})
    assert r.status_code == 200
    assert any("Sin región" in w for w in r.json()["warnings"])


def test_metodo_desconocido_se_rechaza():
    r = client.post("/api/analyze", data={"method": "gpt"}, files={"file": ("g.png", _img_bytes(), "image/png")})
    assert r.status_code == 422


def test_yolo_usa_cajas_y_responde_metodo(monkeypatch):
    # Mitad izquierda ocupada por cajas, mitad derecha libre: disponibilidad ~50 %.
    def fake(img, conf=0.25):
        h, w = img.shape[:2]
        return np.array([[0, 0, w / 2, h]], dtype=np.float64), np.array([0.9])
    monkeypatch.setattr(yolo_detector, "detect_all", lambda img, conf=0.25: {"productos": fake(img), "vacios": (np.zeros((0, 4)), np.zeros(0))})
    r = client.post("/api/analyze", data={"method": "yolo", "roi": ROI},
                    files={"file": ("g.png", _img_bytes(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["method"] == "yolo-finetuned"
    assert abs(body["availability_pct"] - 50.0) < 2


def test_detector_no_disponible_da_503(monkeypatch):
    def fake(img, conf=0.25):
        raise yolo_detector.DetectorUnavailable("sin checkpoint")
    monkeypatch.setattr(yolo_detector, "detect_all", lambda img, conf=0.25: {"productos": fake(img), "vacios": (np.zeros((0, 4)), np.zeros(0))})
    r = client.post("/api/analyze", data={"method": "yolo", "roi": ROI},
                    files={"file": ("g.png", _img_bytes(), "image/png")})
    assert r.status_code == 503


def test_cajas_fuera_de_roi_no_ocupan_y_suelo_vacio_cuenta():
    img = np.zeros((100, 100, 3), np.uint8)
    roi = polygon_mask((100, 100), [[0, 0], [1, 0], [1, 0.5], [0, 0.5]])  # solo mitad superior
    zero = np.zeros((100, 100), np.uint8)
    boxes = np.array([[0, 0, 50, 50]], dtype=np.float64)  # caja en la esquina superior izquierda
    out = analyze_boxes_pixels(img, roi, zero, zero, boxes)
    assert out.areas["occupied"] == 50 * 50
    assert out.areas["empty"] == int((roi > 0).sum()) - 50 * 50
    assert out.labels[80, 80] == Category.OUTSIDE
