"""Detector YOLO de producto como subproceso del entorno de entrenamiento.

torch y ultralytics viven en `backend/.venv-train`, no en el entorno de la app. Por eso la app llama a
`training/infer_yolo.py` con ese Python. Cada llamada paga el arranque de torch (varios segundos).

Pesos: el checkpoint registrado en `data/training/status.json` (ver app/training.py).
Python: `SHELFVISION_TRAIN_PYTHON` si está definido; si no, `backend/.venv-train/Scripts/python.exe`.
"""
import json, os, subprocess, tempfile
from contextvars import ContextVar
ACTIVE_WEIGHTS = ContextVar("regova_active_weights", default=None)

import cv2
import numpy as np

from app.training import DATA_DIR, TRAIN_STATUS

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TIMEOUT_S = 120


class DetectorUnavailable(RuntimeError):
    pass


def _python() -> str:
    env = os.environ.get("SHELFVISION_TRAIN_PYTHON")
    if env:
        return env
    runtime = os.path.join(DATA_DIR, "training", "runtime.json")
    if os.path.isfile(runtime):
        with open(runtime, encoding="utf-8") as f:
            configured = json.load(f).get("train_python")
        if configured:
            return os.path.normpath(configured if os.path.isabs(configured) else os.path.join(BACKEND_DIR, configured))
    return os.path.join(BACKEND_DIR, ".venv-train", "Scripts", "python.exe")


def _weights() -> str:
    override = ACTIVE_WEIGHTS.get()
    if override:
        if not os.path.isfile(override):
            raise DetectorUnavailable("No se encontró la versión registrada del modelo")
        return override
    try:
        with open(TRAIN_STATUS, encoding="utf-8") as f:
            ckpt = json.load(f)["checkpoint"]
    except (OSError, KeyError, json.JSONDecodeError) as e:
        raise DetectorUnavailable("No hay un checkpoint registrado en data/training/status.json") from e
    path = os.path.join(BACKEND_DIR, ckpt)
    if not os.path.isfile(path):
        raise DetectorUnavailable(f"El checkpoint registrado no existe: {ckpt}")
    return path


PRODUCT_CLASS = 0  # 0 = producto
EMPTY_CLASS = 1  # 1 = vacío


def detect_all(img_bgr: np.ndarray, conf: float = 0.25) -> dict:
    """Productos y espacios vacíos en una sola inferencia.

    Devuelve {"productos": (cajas, confianzas), "vacios": (cajas, confianzas)}; cajas en píxeles de `img_bgr`.
    Lanza DetectorUnavailable si falta el Python de entrenamiento, el checkpoint o el subproceso falla.
    """
    python, weights = _python(), _weights()
    if not os.path.isfile(python):
        raise DetectorUnavailable(f"No se encontró el Python de entrenamiento: {python}")
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "imagen.jpg")
        cv2.imwrite(src, img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        cmd = [python, "-m", "training.infer_yolo", "--weights", weights, "--image", src, "--conf", str(conf)]
        try:
            runtime_env = os.environ.copy()
            config_dir = os.path.join(DATA_DIR, "training", "ultralytics_config")
            os.makedirs(config_dir, exist_ok=True)
            runtime_env.setdefault("YOLO_CONFIG_DIR", config_dir)
            proc = subprocess.run(cmd, cwd=BACKEND_DIR, capture_output=True, text=True, timeout=TIMEOUT_S,
                                  env=runtime_env)
        except subprocess.TimeoutExpired as e:
            raise DetectorUnavailable("El detector tardó demasiado") from e
    if proc.returncode != 0:
        raise DetectorUnavailable("Falló el detector: " + proc.stderr.strip().splitlines()[-1][:300])
    out = json.loads(proc.stdout)
    rows = np.asarray(out["boxes"], dtype=np.float64).reshape(-1, 6)
    h0, w0 = out["height"], out["width"]
    h1, w1 = img_bgr.shape[:2]
    # El detector trabaja sobre la foto original; la imagen analizada puede estar reducida.
    sx, sy = w1 / w0, h1 / h0

    def pick(cls):
        r = rows[rows[:, 5] == cls]
        return r[:, :4] * [sx, sy, sx, sy], r[:, 4]

    return {"productos": pick(PRODUCT_CLASS), "vacios": pick(EMPTY_CLASS)}


def detect_products(img_bgr: np.ndarray, conf: float = 0.25) -> tuple[np.ndarray, np.ndarray]:
    """Solo las cajas de producto (compatibilidad). Ver detect_all."""
    return detect_all(img_bgr, conf)["productos"]
