"""Detector YOLOv8n de clase única `producto`, siguiendo la receta de REGOVA (configs/train_yolov8n.yaml).

Dataset: data/yolo/humans_in_the_loop (generado desde las cajas de Humans in the Loop).

Sin descargas automáticas:
  - `--weights yolov8n.yaml` (por defecto) construye la red desde cero.
  - `--weights yolov8n.pt` usaría pesos COCO de Ultralytics (AGPL-3.0). Requiere aprobación de descarga.
  - amp=False y plots=False: evitan que Ultralytics descargue yolo11n.pt (prueba de AMP) y fuentes.

Uso (desde backend/):
  .venv-train/Scripts/python.exe -m training.train_yolo --epochs 100 --name piloto_scratch
"""
import argparse
import os

from ultralytics import YOLO

from app.training import DATA_DIR
from training.preserve_checkpoint import PreserveCheckpointTrainer

DATA_YAML = os.path.join(DATA_DIR, "yolo", "combined", "data.yaml")  # producto + vacío (ver build_combined)
PROJECT = os.path.join(DATA_DIR, "training", "yolo_runs")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default="yolov8n.yaml", help="yolov8n.yaml = desde cero (sin descarga).")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=1024)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--name", default="piloto")
    ap.add_argument("--data", default=DATA_YAML)
    args = ap.parse_args()

    model = YOLO(args.weights)
    model.train(
        trainer=PreserveCheckpointTrainer,
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=0,
        workers=0,
        amp=False,
        plots=False,
        cache=False,
        single_cls=False,
        max_det=1000,
        iou=0.6,
        fliplr=0.5,
        flipud=0.0,
        mosaic=1.0,
        close_mosaic=10,
        patience=30,
        seed=42,
        deterministic=True,
        project=PROJECT,
        name=args.name,
        exist_ok=False,
    )
    metrics = model.val(data=args.data, split="test", imgsz=args.imgsz, batch=args.batch, device=0,
                        workers=0, plots=False, project=PROJECT, name=args.name + "_test", exist_ok=True)
    print("TEST mAP50 %.3f mAP50-95 %.3f precision %.3f recall %.3f" % (
        metrics.box.map50, metrics.box.map, metrics.box.mp, metrics.box.mr), flush=True)
    for idx, name in metrics.names.items():
        print("TEST clase %s mAP50 %.3f" % (name, metrics.box.ap50[list(metrics.ap_class_index).index(idx)]
                                             if idx in list(metrics.ap_class_index) else float("nan")), flush=True)


if __name__ == "__main__":
    main()
