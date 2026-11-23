"""Inferencia del detector YOLO de producto. Imprime JSON en stdout.

Corre en el entorno de entrenamiento (.venv-train), porque ahí están torch y ultralytics.
La app lo invoca como subproceso (app/vision/yolo_detector.py).

Salida: {"width": W, "height": H, "boxes": [[x1, y1, x2, y2, conf, clase], ...]} en píxeles de la imagen.
Clase 0 = producto, 1 = vacío (ver training/data/build_combined.py).

Uso:
  .venv-train/Scripts/python.exe -m training.infer_yolo --weights <best.pt> --image <archivo> --conf 0.25
"""
import argparse
import json
import sys
import os
from contextlib import redirect_stdout

with redirect_stdout(sys.stderr):
    from ultralytics import YOLO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--imgsz", type=int, default=1024)
    ap.add_argument("--device", default=os.environ.get("REGOVA_YOLO_DEVICE", "auto"))
    args = ap.parse_args()
    import torch
    device = ("0" if torch.cuda.is_available() else "cpu") if args.device == "auto" else args.device

    with redirect_stdout(sys.stderr):
        model = YOLO(args.weights)
        r = model.predict(args.image, imgsz=args.imgsz, conf=args.conf, device=device, verbose=False, max_det=1000)[0]
    h, w = r.orig_shape
    boxes = [[float(x) for x in (*xyxy, c, k)]
             for xyxy, c, k in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist(), r.boxes.cls.tolist())]
    json.dump({"width": int(w), "height": int(h), "boxes": boxes}, sys.stdout)


if __name__ == "__main__":
    main()
