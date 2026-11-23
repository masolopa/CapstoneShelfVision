"""Entrenamiento de segmentación con SegFormer-B0 sobre data/processed/masks.

Clases de la máscara (ver training/data/build_masks.py):
  0 = desconocido, 1 = ocupado (producto), 2 = estructural (precio)

Modos para los píxeles desconocidos (`--unknown`):
  ignore      : no entran en la pérdida ni en las métricas (2 clases de salida).
  background  : se tratan como clase de fondo (3 clases de salida).
                Esto ASUME que lo no etiquetado no es producto. Decisión pendiente.

Pesos iniciales (`--pretrained`):
  Por defecto la red empieza con pesos aleatorios. Los pesos preentrenados de NVIDIA
  (nvidia/mit-b0) tienen licencia NO comercial (solo investigación o evaluación).
  No se descargan sin aprobación.

Solo se registra un checkpoint en data/training/status.json con `--register`.
Uso (desde backend/):
  .venv-train/Scripts/python.exe -m training.train --epochs 30 --unknown ignore
"""
import argparse, json, os, random, time
import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from transformers import SegformerConfig, SegformerForSemanticSegmentation

from training.data.build_masks import MASKS, SPLITS, SRC
from app.training import TRAIN_STATUS, DATA_DIR

RAW_IMAGES = os.path.join(SRC, "images")
RUNS = os.path.join(DATA_DIR, "training", "runs")
IGNORE = 255
SIZE = 512
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
CLASS_NAMES = {0: "ocupado", 1: "estructural"}


def read_split(part, limit=None):
    with open(os.path.join(SPLITS, part + ".txt"), encoding="utf-8") as f:
        names = [line.strip() for line in f if line.strip()]
    return names[:limit] if limit else names


class ShelfDataset(Dataset):
    def __init__(self, names, unknown, augment=False):
        self.names, self.unknown, self.augment = names, unknown, augment

    def __len__(self):
        return len(self.names)

    def __getitem__(self, i):
        name = self.names[i]
        img = cv2.imread(os.path.join(RAW_IMAGES, name + ".jpg"))[:, :, ::-1]
        mask = cv2.imread(os.path.join(MASKS, name + ".png"), cv2.IMREAD_GRAYSCALE)
        img = cv2.resize(img, (SIZE, SIZE), interpolation=cv2.INTER_AREA)
        mask = cv2.resize(mask, (SIZE, SIZE), interpolation=cv2.INTER_NEAREST)
        if self.augment and random.random() < 0.5:
            img, mask = img[:, ::-1], mask[:, ::-1]
        label = np.full(mask.shape, IGNORE, np.uint8)
        label[mask == 1] = 0                       # ocupado
        label[mask == 2] = 1                       # estructural
        if self.unknown == "background":
            label[mask == 0] = 2                   # fondo
        x = (img.astype(np.float32) / 255.0 - MEAN) / STD
        return torch.from_numpy(x.transpose(2, 0, 1).copy()), torch.from_numpy(label.astype(np.int64))


def build_model(num_labels, pretrained):
    if pretrained:
        return SegformerForSemanticSegmentation.from_pretrained(
            pretrained, num_labels=num_labels, ignore_mismatched_sizes=True)
    # SegFormer-B0: hidden_sizes/depths del paper; pesos aleatorios.
    cfg = SegformerConfig(num_channels=3, num_encoder_blocks=4, depths=[2, 2, 2, 2],
                          sr_ratios=[8, 4, 2, 1], hidden_sizes=[32, 64, 160, 256],
                          patch_sizes=[7, 3, 3, 3], strides=[4, 2, 2, 2],
                          num_attention_heads=[1, 2, 5, 8], mlp_ratios=[4, 4, 4, 4],
                          decoder_hidden_size=256, num_labels=num_labels)
    return SegformerForSemanticSegmentation(cfg)


def logits_to_size(logits, size):
    return F.interpolate(logits, size=size, mode="bilinear", align_corners=False)


@torch.no_grad()
def evaluate(model, loader, num_labels, device):
    model.eval()
    cm = np.zeros((num_labels, num_labels), np.int64)
    for x, y in loader:
        logits = logits_to_size(model(pixel_values=x.to(device)).logits, y.shape[-2:])
        pred = logits.argmax(1).cpu().numpy()
        gt = y.numpy()
        valid = gt != IGNORE
        idx = gt[valid] * num_labels + pred[valid]
        cm += np.bincount(idx, minlength=num_labels * num_labels).reshape(num_labels, num_labels)
    model.train()
    iou = {}
    for c in range(num_labels):
        inter = cm[c, c]
        union = cm[c, :].sum() + cm[:, c].sum() - inter
        iou[c] = float(inter / union) if union else None
    valid_ious = [v for v in iou.values() if v is not None]
    return {"miou": float(np.mean(valid_ious)) if valid_ious else None,
            "pixel_acc": float(np.trace(cm) / max(cm.sum(), 1)),
            "iou_por_clase": {CLASS_NAMES.get(c, "fondo"): v for c, v in iou.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--lr", type=float, default=6e-5)
    ap.add_argument("--unknown", choices=["ignore", "background"], default="ignore")
    ap.add_argument("--pretrained", default=None, help="Id de Hugging Face. Requiere aprobación de licencia.")
    ap.add_argument("--limit", type=int, default=None, help="Usa solo las primeras N imágenes de cada split (prueba).")
    ap.add_argument("--max-steps", type=int, default=None)
    ap.add_argument("--run", default=None)
    ap.add_argument("--register", action="store_true")
    args = ap.parse_args()

    random.seed(42)
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    num_labels = 2 if args.unknown == "ignore" else 3
    run = args.run or time.strftime("run_%Y%m%d_%H%M%S")
    out_dir = os.path.join(RUNS, run)
    os.makedirs(out_dir, exist_ok=True)

    train_ds = ShelfDataset(read_split("train", args.limit), args.unknown, augment=True)
    val_ds = ShelfDataset(read_split("val", args.limit), args.unknown)
    test_ds = ShelfDataset(read_split("test", args.limit), args.unknown)
    train_dl = DataLoader(train_ds, batch_size=args.batch, shuffle=True, num_workers=0)
    val_dl = DataLoader(val_ds, batch_size=args.batch, num_workers=0)
    test_dl = DataLoader(test_ds, batch_size=args.batch, num_workers=0)

    model = build_model(num_labels, args.pretrained).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda")
    ce = torch.nn.CrossEntropyLoss(ignore_index=IGNORE)

    log, best, step = [], None, 0
    print(f"run={run} device={device} labels={num_labels} train={len(train_ds)} val={len(val_ds)} test={len(test_ds)}", flush=True)
    for epoch in range(1, args.epochs + 1):
        t0, losses = time.time(), []
        for x, y in train_dl:
            x, y = x.to(device), y.to(device)
            with torch.autocast(device_type=device, dtype=torch.float16, enabled=device == "cuda"):
                logits = logits_to_size(model(pixel_values=x).logits, y.shape[-2:])
                loss = ce(logits.float(), y)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            losses.append(loss.item())
            step += 1
            if args.max_steps and step >= args.max_steps:
                break
        val = evaluate(model, val_dl, num_labels, device)
        entry = {"epoch": epoch, "loss": float(np.mean(losses)), "val": val, "segundos": round(time.time() - t0, 1)}
        log.append(entry)
        print(json.dumps(entry, ensure_ascii=False), flush=True)
        if val["miou"] is not None and (best is None or val["miou"] > best["miou"]):
            best = {"epoch": epoch, "miou": val["miou"]}
            torch.save(model.state_dict(), os.path.join(out_dir, "best.pt"))
        if args.max_steps and step >= args.max_steps:
            break

    model.load_state_dict(torch.load(os.path.join(out_dir, "best.pt"), map_location=device))
    test = evaluate(model, test_dl, num_labels, device)
    metrics = {"run": run, "unknown": args.unknown, "pretrained": args.pretrained, "best": best,
               "test": test, "historial": log}
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print("test", json.dumps(test, ensure_ascii=False), flush=True)

    if args.register:
        os.makedirs(os.path.dirname(TRAIN_STATUS), exist_ok=True)
        rel = os.path.relpath(os.path.join(out_dir, "best.pt"), os.path.join(DATA_DIR, ".."))
        status = {"checkpoint": rel.replace(os.sep, "/"), "run": run,
                  "metrics": {"miou_val": best["miou"], "test_miou": test["miou"], "test_pixel_acc": test["pixel_acc"]}}
        with open(TRAIN_STATUS, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
        print("registrado", TRAIN_STATUS, flush=True)


if __name__ == "__main__":
    main()
