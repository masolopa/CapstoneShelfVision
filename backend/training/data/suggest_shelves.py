"""Sugerencias de líneas de estante para corregir a mano en CVAT o Label Studio.

Usa el detector clásico de bandejas de REGOVA (regova.vision.shelf_levels). Es un punto de partida:
en fotos tomadas de lado detecta pocas líneas, así que hay que revisar cada imagen.

Salidas (en data/shelves/):
  suggestions/<imagen>.json  líneas en píxeles de la imagen original: [[x1, y1, x2, y2], ...]
  previews/<imagen>.jpg      la misma imagen con las líneas dibujadas, para revisar rápido

Requiere el paquete regova instalado en el Python que se use para correrlo.
Uso (desde backend/):
  <python con regova>  -m training.data.suggest_shelves
"""
import csv, json, os
import cv2
import numpy as np

from regova.vision.shelf_levels import detect_shelf_levels
from training.data.build_masks import SRC, ROOT

OUT = os.path.join(ROOT, "shelves")
SUG = os.path.join(OUT, "suggestions")
PRV = os.path.join(OUT, "previews")


def unique_names():
    seen, names = set(), []
    with open(os.path.join(SRC, "manifest.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["sha256"] in seen:
                continue
            seen.add(row["sha256"])
            names.append(row["imagen"])
    return names


def shelf_lines_px(img, layout):
    """Convierte cada línea del marco enderezado a segmentos en píxeles de la imagen original."""
    h, w = img.shape[:2]
    lines = []
    for y in layout.shelf_lines:
        xs, ys = layout.unrectify(np.array([0.0, 1.0]), np.array([y, y]))
        lines.append([float(xs[0] * w), float(ys[0] * h), float(xs[1] * w), float(ys[1] * h)])
    return lines


def main():
    os.makedirs(SUG, exist_ok=True)
    os.makedirs(PRV, exist_ok=True)
    total = 0
    for imagen in unique_names():
        src = os.path.join(SRC, "images", imagen)
        img = cv2.imread(src)
        layout = detect_shelf_levels(img)
        lines = shelf_lines_px(img, layout)
        total += len(lines)
        name = os.path.splitext(imagen)[0]
        with open(os.path.join(SUG, name + ".json"), "w", encoding="utf-8") as f:
            json.dump({"image": imagen, "size": [img.shape[1], img.shape[0]], "lines_px": lines}, f, indent=2)
        canvas = img.copy()
        t = max(3, round(min(img.shape[:2]) / 250))
        for x1, y1, x2, y2 in lines:
            cv2.line(canvas, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), t, cv2.LINE_AA)
        cv2.imwrite(os.path.join(PRV, name + ".jpg"), canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    print("imagenes", len(unique_names()), "lineas sugeridas", total)


if __name__ == "__main__":
    main()
