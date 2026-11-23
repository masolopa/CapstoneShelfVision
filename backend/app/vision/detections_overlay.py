"""Dibujo de productos (contorno verde) y espacios vacíos (contorno rojo), sin números."""
import cv2
import numpy as np

COLOR_PRODUCTO = (60, 220, 60)  # BGR, verde
COLOR_VACIO = (40, 40, 230)  # BGR, rojo
ROI_COLOR = (255, 200, 0)  # BGR, azul claro


def render_detections(img: np.ndarray, productos: list[dict], vacios: list[dict] | None = None,
                      roi_px: np.ndarray | None = None) -> bytes:
    canvas = img.copy()
    h, w = canvas.shape[:2]
    t = max(2, round(min(h, w) / 600))
    if roi_px is not None and len(roi_px) >= 3:
        cv2.polylines(canvas, [roi_px.astype(np.int32).reshape(-1, 1, 2)], True, ROI_COLOR, t, cv2.LINE_AA)
    for v in vacios or []:
        x1, y1, x2, y2 = (int(round(c)) for c in v["bbox"])
        cv2.rectangle(canvas, (x1, y1), (x2, y2), COLOR_VACIO, t + 1, cv2.LINE_AA)
    for p in productos:
        x1, y1, x2, y2 = (int(round(c)) for c in p["bbox"])
        cv2.rectangle(canvas, (x1, y1), (x2, y2), COLOR_PRODUCTO, t, cv2.LINE_AA)
    if roi_px is not None and len(roi_px) >= 3:
        # Recortar el dibujo al polígono real, no a su rectángulo envolvente.
        mask = np.zeros((h, w), dtype=np.uint8)
        points = np.rint(roi_px).astype(np.int32).reshape(-1, 1, 2)
        cv2.fillPoly(mask, [points], 255)
        canvas[mask == 0] = img[mask == 0]
        # El borde es una guía de interfaz; las detecciones quedan recortadas.
        cv2.polylines(canvas, [points], True, ROI_COLOR, t, cv2.LINE_AA)
    ok, buf = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise ValueError("No se pudo codificar la imagen procesada")
    return buf.tobytes()
