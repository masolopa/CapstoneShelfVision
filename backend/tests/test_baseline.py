import cv2, numpy as np
from app.vision.baseline import analyze_image_bytes

def _png(img):
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes()

def test_mitad_llena_mitad_vacia():
    rng = np.random.default_rng(0)
    img = np.full((300, 400, 3), 230, np.uint8)            # fondo liso claro
    noise = rng.integers(0, 255, (300, 200, 3), dtype=np.uint8)
    img[:, :200] = noise                                    # izquierda: textura (producto)
    _, out = analyze_image_bytes(_png(img))
    total = out.areas["occupied"] + out.areas["empty"]
    ratio = out.areas["occupied"] / total
    assert 0.40 < ratio < 0.60, ratio

def test_exclusion_no_cuenta():
    img = np.full((200, 200, 3), 230, np.uint8)
    _, out = analyze_image_bytes(_png(img), exclude_polygons=[[(0, 0), (0.5, 0), (0.5, 1), (0, 1)]])
    assert out.areas["excluded"] > 0
    assert out.areas["occupied"] == 0

def test_imagen_invalida():
    import pytest
    with pytest.raises(ValueError):
        analyze_image_bytes(b"no es imagen")
