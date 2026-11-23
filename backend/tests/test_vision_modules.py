import cv2, numpy as np, pytest
from app.vision.masks import Category, build_labels, polygon_mask, count_categories
from app.vision.preprocessing import preprocess, PreprocessConfig
from app.vision.baseline import analyze_image_bytes

def _png(img):
    return cv2.imencode(".png", img)[1].tobytes()

def _textured(h=300, w=400, seed=0):
    return np.random.default_rng(seed).integers(0, 255, (h, w, 3), dtype=np.uint8)

# --- máscaras: exclusividad y precedencia ---
def test_precedencia_excluido_sobre_estructural_y_evidencia():
    roi = np.ones((4, 4), np.uint8)
    excl = np.zeros((4, 4), bool); excl[0, :] = True
    struct = np.zeros((4, 4), bool); struct[1, :] = True
    occ = np.ones((4, 4), bool)
    emp = np.zeros((4, 4), bool)
    lab = build_labels(roi, excl, struct, occ, emp)
    assert (lab[0] == Category.EXCLUDED).all()
    assert (lab[1] == Category.STRUCTURAL).all()
    assert (lab[2] == Category.OCCUPIED).all()

def test_fuera_de_roi_no_cuenta():
    roi = np.zeros((4, 4), np.uint8); roi[:2] = 1
    lab = build_labels(roi, np.zeros((4, 4), bool), np.zeros((4, 4), bool),
                       np.ones((4, 4), bool), np.zeros((4, 4), bool))
    c = count_categories(lab)
    assert c["occupied"] == 8 and c["unknown"] == 0 and (lab[2:] == Category.OUTSIDE).all()

def test_sin_evidencia_es_desconocido():
    lab = build_labels(np.ones((3, 3), np.uint8), np.zeros((3, 3), bool), np.zeros((3, 3), bool),
                       np.zeros((3, 3), bool), np.zeros((3, 3), bool))
    assert count_categories(lab)["unknown"] == 9

def test_poligono_fuera_de_rango():
    with pytest.raises(ValueError):
        polygon_mask((10, 10), [(0, 0), (1.5, 0), (1, 1)])

def test_poligono_muy_corto():
    with pytest.raises(ValueError):
        polygon_mask((10, 10), [(0, 0), (1, 1)])

# --- preprocesamiento: calidad de imagen ---
def test_imagen_borrosa_se_advierte():
    img = np.full((300, 400, 3), 128, np.uint8)  # sin bordes
    _, q = preprocess(img)
    assert any("borrosa" in w for w in q.warnings)

def test_imagen_oscura_se_advierte():
    img = np.full((300, 400, 3), 10, np.uint8)
    _, q = preprocess(img)
    assert any("subexpuesta" in w for w in q.warnings)

def test_imagen_sobreexpuesta_se_advierte():
    img = np.full((300, 400, 3), 252, np.uint8)
    _, q = preprocess(img)
    assert any("sobreexpuesta" in w for w in q.warnings)

def test_imagen_nitida_sin_advertencias_de_exposicion():
    img = _textured()
    _, q = preprocess(img)
    assert not any("expuesta" in w for w in q.warnings)

def test_redimensiona_imagen_grande():
    img = np.zeros((2000, 3000, 3), np.uint8)
    out, _ = preprocess(img, PreprocessConfig(max_side=1000))
    assert max(out.shape[:2]) == 1000

# --- motor completo con polígonos ---
def test_estructural_se_excluye_del_denominador():
    img = np.full((300, 400, 3), 230, np.uint8)
    img[:, :200] = _textured()[:, :200]
    struct = [[(0.5, 0), (1, 0), (1, 1), (0.5, 1)]]  # mitad derecha estructural
    _, out = analyze_image_bytes(_png(img), structural_polygons=struct)
    assert out.areas["structural"] > 0
    assert out.areas["occupied"] > 0
    assert out.areas["occupied"] + out.areas["empty"] + out.areas["unknown"] + out.areas["excluded"] + out.areas["structural"] == 300 * 400

def test_roi_limita_el_analisis():
    img = np.full((300, 400, 3), 230, np.uint8)
    roi = [(0, 0), (0.5, 0), (0.5, 1), (0, 1)]  # un solo polígono
    _, out = analyze_image_bytes(_png(img), roi_polygon=roi)
    total = sum(out.areas.values())
    assert abs(total - (300 * 400) / 2) < 300 * 400 * 0.02

def test_no_hay_conteo_doble():
    img = _textured()
    excl = [[(0, 0), (0.6, 0), (0.6, 1), (0, 1)]]
    struct = [[(0.4, 0), (1, 0), (1, 1), (0.4, 1)]]
    _, out = analyze_image_bytes(_png(img), exclude_polygons=excl, structural_polygons=struct)
    assert sum(out.areas.values()) <= 300 * 400
