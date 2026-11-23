"""Reglas compartidas de pertenencia y recorte a la región de análisis."""
import cv2
import numpy as np

from app.vision.masks import polygon_mask


def polygon_pixels(shape, polygon):
    h, w = shape[:2]
    return (np.asarray(polygon, dtype=np.float64) * [w - 1, h - 1]).astype(np.float32)


def centers_inside(boxes, shape, polygon):
    boxes = np.asarray(boxes, dtype=np.float64).reshape(-1, 4)
    if not polygon:
        return np.ones(len(boxes), dtype=bool)
    points = polygon_pixels(shape, polygon)
    centers = (boxes[:, :2] + boxes[:, 2:]) / 2
    return np.asarray([cv2.pointPolygonTest(points, (float(x), float(y)), False) >= 0
                       for x, y in centers], dtype=bool)


def filter_detections(boxes, confs, shape, polygon):
    boxes = np.asarray(boxes, dtype=np.float64).reshape(-1, 4)
    keep = centers_inside(boxes, shape, polygon)
    return boxes[keep], np.asarray(confs, dtype=np.float64)[keep]


def clip_spaces(spaces, shape, polygon, products):
    """Conserva solo intersecciones reales; limita cajas y frentes al ancho interior.

    El bbox resultante encierra la intersección. El renderer aplica además la
    máscara poligonal para no pintar fuera de regiones inclinadas o cóncavas.
    """
    if not polygon:
        return spaces
    mask = polygon_mask(shape[:2], polygon) > 0
    h, w = mask.shape
    typical = float(np.median([p['bbox'][2] - p['bbox'][0] for p in products])) if products else None
    result = []
    for space in spaces:
        a, b, c, d = space['bbox']
        x0, y0 = max(0, int(np.floor(a))), max(0, int(np.floor(b)))
        x1, y1 = min(w, int(np.ceil(c))), min(h, int(np.ceil(d)))
        if x1 <= x0 or y1 <= y0:
            continue
        intersection = mask[y0:y1, x0:x1]
        ys, xs = np.nonzero(intersection)
        if not len(xs):
            continue
        item = dict(space)
        item['bbox'] = [float(x0 + xs.min()), float(y0 + ys.min()),
                        float(x0 + xs.max() + 1), float(y0 + ys.max() + 1)]
        if typical and typical > 0:
            width_inside = int(np.count_nonzero(intersection.any(axis=0)))
            item['frentes_para_rellenar'] = max(1, int(round(width_inside / typical)))
        result.append(item)
    return result
