"""Categorías de superficie y construcción de máscaras mutuamente excluyentes.

Cada píxel recibe exactamente una etiqueta. Precedencia:
  fuera de ROI > excluido > estructural > evidencia (ocupado / vacío / desconocido).
"""
from enum import IntEnum
import numpy as np
import cv2


class Category(IntEnum):
    OUTSIDE = -1      # fuera de la región de interés
    EXCLUDED = 0      # no evaluable (obstrucción, reflejo, mala captura)
    EMPTY = 1         # espacio utilizable sin producto
    OCCUPIED = 2      # producto
    STRUCTURAL = 3    # elemento de la góndola, no almacenable
    UNKNOWN = 4       # evidencia insuficiente: NUNCA se cuenta como vacío ni como ocupado


CATEGORY_NAMES = {c.value: c.name.lower() for c in Category}


def polygon_mask(shape_hw, polygon_norm):
    """Convierte un polígono con coordenadas normalizadas (0-1) en máscara uint8."""
    h, w = shape_hw
    mask = np.zeros((h, w), dtype=np.uint8)
    if not polygon_norm:
        return mask
    if len(polygon_norm) < 3:
        raise ValueError("Un polígono necesita al menos 3 puntos")
    for x, y in polygon_norm:
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise ValueError("Coordenadas de polígono fuera del rango 0-1")
    pts = np.array([[int(round(x * (w - 1))), int(round(y * (h - 1)))] for x, y in polygon_norm], dtype=np.int32)
    cv2.fillPoly(mask, [pts], 255)
    return mask


def build_labels(roi: np.ndarray, excluded: np.ndarray, structural: np.ndarray,
                 occupied_evidence: np.ndarray, empty_evidence: np.ndarray) -> np.ndarray:
    """Combina máscaras booleanas en una sola matriz de etiquetas (int8).

    Cualquier píxel de la ROI sin evidencia clara queda como UNKNOWN.
    """
    labels = np.full(roi.shape, Category.OUTSIDE, dtype=np.int8)
    inside = roi.astype(bool)
    labels[inside] = Category.UNKNOWN
    labels[inside & empty_evidence] = Category.EMPTY
    labels[inside & occupied_evidence] = Category.OCCUPIED
    labels[inside & structural.astype(bool)] = Category.STRUCTURAL
    labels[inside & excluded.astype(bool)] = Category.EXCLUDED
    return labels


def count_categories(labels: np.ndarray) -> dict:
    return {name: int(np.sum(labels == cat)) for cat, name in
            ((Category.OCCUPIED, "occupied"), (Category.EMPTY, "empty"), (Category.EXCLUDED, "excluded"),
             (Category.STRUCTURAL, "structural"), (Category.UNKNOWN, "unknown"))}
