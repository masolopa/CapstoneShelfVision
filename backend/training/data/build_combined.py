"""Dataset combinado para YOLOv8: clases 0 = producto, 1 = vacío.

Fuentes (licencias según su metadata):
  - Humans in the Loop (CC0 1.0): data/yolo/humans_in_the_loop        -> producto
  - Retail Shelf Detection (CC BY 4.0): data/external/dataset2        -> product=0, empty=1
  - retail-shelf-object-detection (Public Domain): data/external/dataset3 -> object=0, empty=1
CE+S (CC BY 4.0): clase 0 = huecos vacíos (confirmado visualmente, no en documentación).

Duplicados exactos (mismo SHA-256) se descartan. Se conservan las particiones de cada fuente.
Salida: data/yolo/combined/ con data.yaml y resumen.json.

Uso (desde backend/):
  .venv-train/Scripts/python.exe -m training.data.build_combined
"""
import glob, hashlib, json, os, shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
OUT = os.path.join(ROOT, "yolo", "combined")
# (etiqueta, carpeta, nombres de clase en la fuente en orden de índice, mapa nombre -> clase destino)
SOURCES = [
    ("hitl", os.path.join(ROOT, "yolo", "humans_in_the_loop"), ["producto"], {"producto": 0}),
    ("rsd", os.path.join(ROOT, "external", "dataset2", "Retail Shelf Detection.v1i.yolov8"),
     ["empty", "product"], {"product": 0, "empty": 1}),
    ("cese", os.path.join(ROOT, "external", "ce-s"), ["0"], {"0": 1}),  # CE+S: clase 0 = huecos (vacío), verificado visualmente
    ("rsod", os.path.join(ROOT, "external", "dataset3",
                          "retail-shelf-object-detection.v2-test-tommy-version.yolov8"),
     ["empty", "object"], {"object": 0, "empty": 1}),
]
# Temporary source policy: only sources annotating both product and empty.
# Keep partial sources documented above, but do not silently re-enable them.
DISABLED_SOURCES = [source for source in SOURCES if source[0] not in ("rsd", "rsod")]
SOURCES = [source for source in SOURCES if source[0] in ("rsd", "rsod")]
SPLIT_DIRS = {"train": ["train"], "val": ["valid", "val"], "test": ["test"]}


def apply_saved_corrections(output=OUT, verify_only=False):
    """Reapply CVAT labels after rebuilding; never copy training edits into test."""
    correction_root = os.path.join(ROOT, "corrections", "cvat_revision")
    manifest = os.path.join(correction_root, "manifest.json")
    if not os.path.isfile(manifest):
        return 0
    with open(manifest, encoding="utf-8") as f:
        labels = json.load(f)["label_sha256"]
    applied = 0
    for name, expected_hash in labels.items():
        source = os.path.join(correction_root, "labels", name)
        if sha(source) != expected_hash:
            raise ValueError(f"Correction integrity mismatch: {name}")
        target = os.path.join(output, "labels", "train", name)
        if not verify_only and os.path.isfile(target):
            shutil.copyfile(source, target)
            applied += 1
    return applied


def find_split_dir(src, names):
    """Devuelve (carpeta de imágenes, carpeta de etiquetas) para una partición.

    Acepta dos layouts: <src>/<parte>/images y <src>/images/<parte> (como Humans in the Loop).
    """
    for n in names:
        if os.path.isdir(os.path.join(src, n, "images")):
            return os.path.join(src, n, "images"), os.path.join(src, n, "labels")
        if os.path.isdir(os.path.join(src, "images", n)):
            return os.path.join(src, "images", n), os.path.join(src, "labels", n)
    return None, None


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    # Refuse an invalid correction store before replacing any existing dataset.
    apply_saved_corrections(verify_only=True)
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    seen, stats = {}, {"duplicados": 0}
    for tag, src, src_names, mapping in SOURCES:
        remap = {i: mapping[n] for i, n in enumerate(src_names) if n in mapping}
        for dst_part, aliases in SPLIT_DIRS.items():
            img_dir, lbl_dir = find_split_dir(src, aliases)
            if img_dir is None:
                continue
            os.makedirs(os.path.join(OUT, "images", dst_part), exist_ok=True)
            os.makedirs(os.path.join(OUT, "labels", dst_part), exist_ok=True)
            for img in sorted(glob.glob(os.path.join(img_dir, "*"))):
                h = sha(img)
                if h in seen:
                    stats["duplicados"] += 1
                    continue
                base, ext = os.path.splitext(os.path.basename(img))
                name = f"{tag}_{base}"
                seen[h] = name
                shutil.copy(img, os.path.join(OUT, "images", dst_part, name + ext))
                lines = []
                lbl = os.path.join(lbl_dir, base + ".txt")
                if os.path.isfile(lbl):
                    for ln in open(lbl, encoding="utf-8"):
                        p = ln.split()
                        if len(p) != 5:
                            continue
                        c = int(float(p[0]))
                        if c in remap:
                            lines.append(f"{remap[c]} {' '.join(p[1:])}")
                with open(os.path.join(OUT, "labels", dst_part, name + ".txt"), "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + ("\n" if lines else ""))
                key = f"{tag}/{dst_part}"
                stats[key] = stats.get(key, 0) + 1
    stats["correcciones_cvat_aplicadas"] = apply_saved_corrections()
    with open(os.path.join(OUT, "data.yaml"), "w", encoding="utf-8") as f:
        f.write(f"path: {OUT.replace(os.sep, '/')}\ntrain: images/train\nval: images/val\ntest: images/test\n"
                "nc: 2\nnames:\n  0: producto\n  1: vacio\n")
    with open(os.path.join(OUT, "resumen.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
