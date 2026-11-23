"""Motor de visión línea base con OpenCV (heurística, NO es IA entrenada).

Evidencia por píxel (dentro de la ROI):
  - ocupado: textura local alta o color saturado alto
  - vacío:   textura local baja Y color poco saturado
  - desconocido: evidencia intermedia (ninguna de las anteriores con claridad)
Exclusiones manuales y zonas con mala exposición se marcan como excluidas.
Limitación: un producto liso o de color neutro puede quedar como desconocido,
y un estante con textura puede contarse como ocupado. Ver docs/VISION_ENGINE.md.
"""
from dataclasses import dataclass, field
import cv2
import numpy as np

from app.vision.masks import Category, build_labels, count_categories, polygon_mask
from app.vision.preprocessing import PreprocessConfig, QualityReport, preprocess
from app.vision.regions import filter_detections

HEURISTIC_METHOD = "opencv-baseline"
YOLO_METHOD = "yolo-finetuned"


@dataclass
class BaselineParams:
    window: int = 15
    texture_low: float = 4.0      # por debajo: textura ausente
    texture_high: float = 12.0    # por encima: textura presente
    sat_low: int = 30
    sat_high: int = 60
    dark_low: int = 15
    dark_high: int = 245


@dataclass
class BaselineOutput:
    width: int
    height: int
    labels: np.ndarray
    areas: dict = field(default_factory=dict)
    quality: QualityReport | None = None
    method: str = "opencv-baseline"
    boxes: np.ndarray | None = None  # cajas de producto (YOLO), xyxy en píxeles
    confs: np.ndarray | None = None  # confianza de cada caja
    vacios: np.ndarray | None = None  # espacios vacíos detectados (YOLO), xyxy en píxeles
    vacios_confs: np.ndarray | None = None
    descartados: int = 0  # productos descartados por caer dentro de un vacío


def _evidence(img: np.ndarray, p: BaselineParams):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    sat = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[:, :, 1].astype(np.float32)
    k = p.window
    mean = cv2.blur(gray, (k, k))
    sq = cv2.blur(gray * gray, (k, k))
    std = np.sqrt(np.maximum(sq - mean * mean, 0))

    occ_score = np.maximum((std - p.texture_low) / (p.texture_high - p.texture_low),
                           (sat - p.sat_low) / (p.sat_high - p.sat_low))
    occupied = occ_score >= 1.0
    empty = (std < p.texture_low) & (sat < p.sat_low)
    bad_exposure = (gray < p.dark_low) | (gray > p.dark_high)
    return occupied & ~bad_exposure, empty & ~bad_exposure & ~occupied, bad_exposure


def analyze_pixels(img: np.ndarray, roi_mask: np.ndarray, exclude_mask: np.ndarray,
                   structural_mask: np.ndarray | None = None,
                   params: BaselineParams | None = None, quality: QualityReport | None = None) -> BaselineOutput:
    p = params or BaselineParams()
    occupied, empty, bad_exposure = _evidence(img, p)
    structural = structural_mask if structural_mask is not None else np.zeros(roi_mask.shape, np.uint8)
    excluded = (exclude_mask > 0) | bad_exposure
    labels = build_labels(roi_mask > 0, excluded, structural > 0, occupied, empty)
    return BaselineOutput(img.shape[1], img.shape[0], labels, count_categories(labels), quality)


UMBRAL_EN_VACIO = 0.6  # un producto cuya área está más de 60 % dentro de un vacío se descarta
AREA_MIN_REL = 0.1  # producto más pequeño que 10 % del área típica: ruido
# Sin límite superior: los paquetes grandes son productos reales (probado: un límite de 4x quitó cajas reales).


def filtrar_por_tamano(boxes, confs):
    """Quita cajas muy pequeñas comparadas con la mediana de la imagen (ruido)."""
    boxes = np.asarray(boxes, dtype=np.float64).reshape(-1, 4)
    if not len(boxes):
        return boxes, np.asarray(confs, dtype=np.float64)
    areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    tipica = float(np.median(areas))
    keep = areas >= AREA_MIN_REL * tipica
    return boxes[keep], np.asarray(confs, dtype=np.float64)[keep]


def filtrar_productos_en_vacio(prod_boxes, prod_confs, vacio_boxes, vacio_confs):
    """Quita productos casi completamente dentro de un espacio vacío (falsos positivos del detector)."""
    prod_boxes = np.asarray(prod_boxes, dtype=np.float64).reshape(-1, 4)
    if not len(prod_boxes) or not len(vacio_boxes):
        return prod_boxes, np.asarray(prod_confs, dtype=np.float64)
    vb = np.asarray(vacio_boxes, dtype=np.float64).reshape(-1, 4)
    keep = []
    for b in prod_boxes:
        area = max((b[2] - b[0]) * (b[3] - b[1]), 1e-6)
        ix1 = np.maximum(b[0], vb[:, 0]); iy1 = np.maximum(b[1], vb[:, 1])
        ix2 = np.minimum(b[2], vb[:, 2]); iy2 = np.minimum(b[3], vb[:, 3])
        inter = np.clip(ix2 - ix1, 0, None) * np.clip(iy2 - iy1, 0, None)
        keep.append(float(inter.max() / area) <= UMBRAL_EN_VACIO)
    keep = np.array(keep, dtype=bool)
    return prod_boxes[keep], np.asarray(prod_confs, dtype=np.float64)[keep]


def analyze_boxes_pixels(img: np.ndarray, roi_mask: np.ndarray, exclude_mask: np.ndarray,
                         structural_mask: np.ndarray, boxes: np.ndarray,
                         quality: QualityReport | None = None, confs: np.ndarray | None = None) -> BaselineOutput:
    """Ocupación con cajas de producto del detector YOLO.

    Píxel ocupado = dentro de una caja de producto. Píxel vacío = dentro de la ROI, fuera de cajas.
    Por eso la ROI es obligatoria: sin ella, el suelo y el techo contarían como espacio vacío.
    """
    h, w = img.shape[:2]
    occupied = np.zeros((h, w), dtype=bool)
    for x1, y1, x2, y2 in boxes:
        occupied[max(0, int(y1)):min(h, int(np.ceil(y2))), max(0, int(x1)):min(w, int(np.ceil(x2)))] = True
    inside = roi_mask > 0
    empty = inside & ~occupied
    labels = build_labels(inside, exclude_mask > 0, structural_mask > 0, occupied, empty)
    out = BaselineOutput(w, h, labels, count_categories(labels), quality, method=YOLO_METHOD,
                         boxes=boxes.reshape(-1, 4), confs=confs)
    return out


def analyze_image_bytes(image_bytes: bytes, roi_polygon=None, exclude_polygons=None,
                        structural_polygons=None, params: BaselineParams | None = None,
                        preprocess_cfg: PreprocessConfig | None = None, method: str = "heuristic"):
    """Analiza una imagen. ``method``: ``heuristic`` (OpenCV) o ``yolo`` (detector entrenado, requiere ROI).

    Sin ROI con ``yolo``, la imagen completa cuenta como región: piso y techo quedan como vacío.
    Se añade una advertencia de calidad. Lanza ``DetectorUnavailable`` si el detector falla.
    """
    if method not in ("heuristic", "yolo"):
        raise ValueError("Método de análisis no válido")
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    raw = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if raw is None:
        raise ValueError("No se pudo decodificar la imagen")
    img, quality = preprocess(raw, preprocess_cfg)
    h, w = img.shape[:2]
    roi = polygon_mask((h, w), roi_polygon) if roi_polygon else np.full((h, w), 255, np.uint8)
    excl = np.zeros((h, w), np.uint8)
    for poly in exclude_polygons or []:
        excl |= polygon_mask((h, w), poly)
    struct = np.zeros((h, w), np.uint8)
    for poly in structural_polygons or []:
        struct |= polygon_mask((h, w), poly)
    if method == "yolo":
        from app.vision.yolo_detector import detect_products  # import tardío: el detector es opcional
        if not roi_polygon:
            quality.warnings.append("Sin región de estantes: el piso y el techo cuentan como espacio vacío. "
                                    "Marca los estantes para un resultado fiable.")
        from app.vision.yolo_detector import detect_all
        det = detect_all(img)
        # Filtrar antes de comparar tamaños y solapes: el exterior no debe influir.
        if roi_polygon:
            det = {name: filter_detections(*values, img.shape, roi_polygon)
                   for name, values in det.items()}
        boxes, confs = filtrar_productos_en_vacio(*det["productos"], *det["vacios"])
        boxes, confs = filtrar_por_tamano(boxes, confs)
        out = analyze_boxes_pixels(img, roi, excl, struct, boxes, quality, confs)
        out.vacios, out.vacios_confs = det["vacios"]
        out.descartados = det["productos"][0].shape[0] - len(boxes)  # en vacío y por tamaño
    else:
        out = analyze_pixels(img, roi, excl, struct, params, quality)
    return img, out


COLORS = {  # BGR
    Category.EXCLUDED: (128, 128, 128),   # gris
    Category.EMPTY: (0, 0, 220),          # rojo (vacío)
    Category.OCCUPIED: (0, 200, 0),       # verde (ocupado)
    Category.STRUCTURAL: (220, 100, 0),   # azul
    Category.UNKNOWN: (0, 220, 230),      # amarillo
}


def render_overlay(img: np.ndarray, out: BaselineOutput) -> bytes:
    overlay = img.copy()
    for cat, color in COLORS.items():
        overlay[out.labels == cat] = color
    blended = cv2.addWeighted(img, 0.55, overlay, 0.45, 0)
    ok, buf = cv2.imencode(".jpg", blended, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise ValueError("No se pudo codificar la imagen procesada")
    return buf.tobytes()
