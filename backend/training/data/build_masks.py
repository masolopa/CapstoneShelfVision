"""Convierte las cajas de Humans in the Loop en máscaras de segmentación y crea los splits.

Clases de salida (valor del píxel en el PNG):
  0 = desconocido (no se entrena sobre él)
  1 = ocupado (caja `Product`)
  2 = estructural (caja `Price`, etiqueta de precio en la góndola)

Limitación: el dataset no tiene anotaciones de espacio vacío. Por eso lo que no está
dentro de una caja NO se marca como vacío, sino como desconocido.

Uso (desde backend/):
  .venv/Scripts/python.exe -m training.data.build_masks
"""
import csv, json, os, random
import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
SRC = os.path.join(ROOT, "raw", "humans_in_the_loop")
MASKS = os.path.join(ROOT, "processed", "masks")
SPLITS = os.path.join(ROOT, "splits")
CLASS_VALUE = {"Product": 1, "Price": 2}
SEED = 42
VAL_N, TEST_N = 7, 7


def load_unique_images():
    """Devuelve los nombres sin duplicados exactos (se conserva el primero por hash)."""
    seen, names = set(), []
    with open(os.path.join(SRC, "manifest.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["sha256"] in seen:
                continue
            seen.add(row["sha256"])
            names.append(row["imagen"])
    return names


def build_mask(name):
    ann = json.load(open(os.path.join(SRC, "annotations", name + ".json"), encoding="utf-8"))
    h, w = ann["size"]["height"], ann["size"]["width"]
    mask = np.zeros((h, w), np.uint8)
    # Primero productos, luego precios encima (los precios son estructurales).
    for cls in ("Product", "Price"):
        for obj in ann["objects"]:
            if obj["classTitle"] != cls:
                continue
            (x1, y1), (x2, y2) = obj["points"]["exterior"]
            cv2.rectangle(mask, (int(x1), int(y1)), (int(x2), int(y2)), CLASS_VALUE[cls], thickness=-1)
    return mask


def split(names):
    rng = random.Random(SEED)
    shuffled = sorted(names)
    rng.shuffle(shuffled)
    test = shuffled[:TEST_N]
    val = shuffled[TEST_N:TEST_N + VAL_N]
    train = shuffled[TEST_N + VAL_N:]
    return {"train": sorted(train), "val": sorted(val), "test": sorted(test)}


def main():
    os.makedirs(MASKS, exist_ok=True)
    os.makedirs(SPLITS, exist_ok=True)
    names = load_unique_images()
    counts = {0: 0, 1: 0, 2: 0}
    for name in names:
        mask = build_mask(name)
        cv2.imwrite(os.path.join(MASKS, name.replace(".jpg", ".png")), mask)
        for v in counts:
            counts[v] += int(np.sum(mask == v))
    parts = split(names)
    for part, items in parts.items():
        with open(os.path.join(SPLITS, part + ".txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(i.replace(".jpg", "") for i in items) + "\n")
    total = sum(counts.values())
    stats = {
        "imagenes_unicas": len(names),
        "splits": {k: len(v) for k, v in parts.items()},
        "pixeles": {"desconocido": counts[0], "ocupado": counts[1], "estructural": counts[2]},
    }
    with open(os.path.join(ROOT, "processed", "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print("imagenes unicas", len(names))
    print("splits", {k: len(v) for k, v in parts.items()})
    print("pixeles", {"desconocido": counts[0], "ocupado": counts[1], "estructural": counts[2]})
    print("proporcion ocupado %.1f%% estructural %.1f%% desconocido %.1f%%" % (
        100 * counts[1] / total, 100 * counts[2] / total, 100 * counts[0] / total))


if __name__ == "__main__":
    main()
