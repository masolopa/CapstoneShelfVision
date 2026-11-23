"""Estado real del dataset y del entrenamiento. Solo lee archivos; no entrena nada.

Un checkpoint solo cuenta como válido si existe el archivo y el script de entrenamiento
lo registró en `data/training/status.json`. Sin esos dos elementos, el modelo sigue pendiente.
"""
import json, os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
RAW_IMAGES = os.path.join(DATA_DIR, "raw", "humans_in_the_loop", "images")
STATS = os.path.join(DATA_DIR, "processed", "stats.json")
TRAIN_STATUS = os.environ.get("REGOVA_TRAIN_STATUS", os.path.join(DATA_DIR, "training", "status.json"))


def _read_json(path):
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dataset_status():
    policy = _read_json(os.path.join(DATA_DIR, "yolo", "source_policy.json"))
    if policy:
        splits = {s: values["active"] for s, values in policy["datasets"]["combined"].items()}
        raw_images = sum(v["active"] + v["inactive"] for v in policy["datasets"]["combined"].values())
        return {"raw_images": raw_images, "prepared": True,
                "unique_images": sum(splits.values()), "splits": splits,
                "class_share_pct": None, "labels": {"producto": "Producto visible", "vacio": "Espacio vacío anotado"},
                "active_sources": policy["allowed_sources"], "disabled_sources": policy["disabled_sources"],
                "limitations": [policy["reason"], "Los splits son por imagen, no por sesión de captura."]}
    stats = _read_json(STATS)
    raw = len([n for n in os.listdir(RAW_IMAGES) if n.lower().endswith(".jpg")]) if os.path.isdir(RAW_IMAGES) else 0
    if stats is None:
        return {"raw_images": raw, "prepared": False, "unique_images": 0, "splits": None, "class_share_pct": None}
    px = stats["pixeles"]
    total = sum(px.values()) or 1
    return {
        "raw_images": raw,
        "prepared": True,
        "unique_images": stats["imagenes_unicas"],
        "splits": stats["splits"],
        "class_share_pct": {k: round(100 * v / total, 1) for k, v in px.items()},
        "labels": {"desconocido": "No se entrena sobre esta zona", "ocupado": "Producto", "estructural": "Etiqueta de precio"},
        "limitations": [
            "El dataset solo tiene cajas de producto y precio; no tiene espacio vacío anotado.",
            "Los splits son por imagen, no por supermercado ni por sesión de captura.",
        ],
    }


def training_status():
    st = _read_json(TRAIN_STATUS)
    if st is None:
        return {"ready": False, "checkpoint": None, "metrics": None,
                "reason": "Todavía no existe un entrenamiento registrado."}
    ckpt = st.get("checkpoint")
    valid = bool(ckpt) and os.path.isfile(os.path.join(DATA_DIR, "..", ckpt))
    return {"ready": valid, "checkpoint": ckpt if valid else None, "metrics": st.get("metrics") if valid else None,
            "reason": None if valid else st.get("reason", "El checkpoint registrado no existe en disco.")}
