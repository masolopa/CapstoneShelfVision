"""Validación y preprocesamiento suave. Conserva la imagen original intacta."""
from dataclasses import dataclass, field
import cv2
import numpy as np

MAX_SIDE = 1280
MIN_SIDE = 200


@dataclass
class QualityReport:
    width: int
    height: int
    blur_score: float          # varianza del Laplaciano (más bajo = más borroso)
    mean_brightness: float
    clipped_dark_pct: float    # % de píxeles casi negros
    clipped_bright_pct: float  # % de píxeles casi blancos
    warnings: list = field(default_factory=list)


@dataclass
class PreprocessConfig:
    max_side: int = MAX_SIDE
    min_side: int = MIN_SIDE
    blur_threshold: float = 60.0
    dark_mean: float = 50.0
    bright_mean: float = 215.0
    clip_threshold_pct: float = 25.0


def check_quality(gray: np.ndarray, cfg: PreprocessConfig) -> QualityReport:
    h, w = gray.shape
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean = float(gray.mean())
    dark = float(np.mean(gray < 15) * 100)
    bright = float(np.mean(gray > 240) * 100)
    rep = QualityReport(w, h, round(blur, 2), round(mean, 2), round(dark, 2), round(bright, 2))
    if min(h, w) < cfg.min_side:
        rep.warnings.append("Imagen de baja resolución: el análisis puede no ser fiable.")
    if blur < cfg.blur_threshold:
        rep.warnings.append("Imagen borrosa: los bordes de los productos no son claros.")
    if mean < cfg.dark_mean or dark > cfg.clip_threshold_pct:
        rep.warnings.append("Imagen subexpuesta (muy oscura).")
    if mean > cfg.bright_mean or bright > cfg.clip_threshold_pct:
        rep.warnings.append("Imagen sobreexpuesta (reflejos o exceso de luz).")
    return rep


def preprocess(img_bgr: np.ndarray, cfg: PreprocessConfig | None = None):
    """Devuelve (imagen_procesada, reporte). La imagen se redimensiona solo si es muy grande.

    No se aplica suavizado agresivo para no borrar detalles de los productos.
    """
    cfg = cfg or PreprocessConfig()
    h, w = img_bgr.shape[:2]
    scale = min(1.0, cfg.max_side / max(h, w))
    work = img_bgr
    if scale < 1.0:
        work = cv2.resize(img_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
    return work, check_quality(gray, cfg)
