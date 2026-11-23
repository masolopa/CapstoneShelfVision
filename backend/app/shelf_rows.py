"""Conteo de productos y frentes por fila a partir de las cajas del detector.

Definiciones (todas en píxeles de la imagen analizada):

* **Producto**: una caja del detector cuyo centro está dentro de la región de análisis.
* **Fila**: un estante. Si el usuario indica cuántos estantes hay (`filas`), la región se divide en
  bandas iguales. Si no, las filas se forman agrupando cajas por altura; un estante vacío no genera
  cajas, así que sin `filas` no se puede ver como fila vacía.
* **Frente**: columna de productos de una fila. Cajas que se solapan horizontalmente (por ejemplo,
  latas apiladas) cuentan como un solo frente.
* **Frentes totales** de una fila: ancho útil de la región / ancho típico de frente (mediana de la imagen).
* **Frentes libres** = frentes totales - frentes ocupados (mínimo 0). Es una estimación: depende del
  ancho de frente que se haya medido.

Estado por fila:
* ``REPONER``: ocupación de frentes <= umbral (por defecto 30 %).
* ``REVISAR``: entre el umbral y 70 %.
* ``OK``: más de 70 %.

Esto no identifica marcas ni SKU: el detector solo distingue producto de no producto. El pedido
se expresa en frentes, y el administrador lo traduce a productos concretos.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

import numpy as np

REVISAR_LIMIT = 70.0
OVERLAP = 0.5  # solape horizontal (fracción del más angosto) para considerar que dos cajas son el mismo frente


@dataclass
class Row:
    indice: int  # 1 = fila superior
    productos: int
    frentes_ocupados: int
    frentes_totales: int
    frentes_libres: int
    ocupacion_pct: float
    estado: str
    confianza_media: float | None
    y_inicio: float
    y_fin: float
    cajas: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ocupacion_pct"] = round(self.ocupacion_pct, 1)
        if self.confianza_media is not None:
            d["confianza_media"] = round(self.confianza_media, 1)
        return d


def _columns(boxes: np.ndarray) -> list[list[int]]:
    """Agrupa cajas (N, 4) xyxy en frentes: índices por columna, de izquierda a derecha."""
    if not len(boxes):
        return []
    order = np.argsort(boxes[:, 0] + boxes[:, 2])
    cols: list[list[int]] = []
    for i in order:
        placed = False
        for col in cols:
            ov = [min(boxes[i, 2], boxes[j, 2]) - max(boxes[i, 0], boxes[j, 0])
                  >= OVERLAP * min(boxes[i, 2] - boxes[i, 0], boxes[j, 2] - boxes[j, 0]) for j in col]
            if any(ov):
                col.append(int(i))
                placed = True
                break
        if not placed:
            cols.append([int(i)])
    return sorted(cols, key=lambda c: float(boxes[c, 0].min()))


def _row_bands(cy: np.ndarray, heights: np.ndarray, filas: int | None, y0: float, y1: float) -> list[list[int]]:
    """Asigna cada caja a una fila. Devuelve listas de índices, de arriba hacia abajo."""
    if filas:
        edges = np.linspace(y0, y1, filas + 1)
        bands = [[] for _ in range(filas)]
        for i, y in enumerate(cy):
            k = int(np.clip(np.searchsorted(edges, y, side="right") - 1, 0, filas - 1))
            bands[k].append(i)
        return bands
    if not len(cy):
        return []
    # Productos apilados quedan separados ~1 altura de caja; un estante, bastante más. Umbral: 1,5 alturas.
    gap_limit = 1.5 * float(np.median(heights))
    order = np.argsort(cy)
    rows: list[list[int]] = [[int(order[0])]]
    for prev, cur in zip(order[:-1], order[1:]):
        if cy[cur] - cy[prev] > gap_limit:
            rows.append([])
        rows[-1].append(int(cur))
    return rows


def analyze_rows(boxes: np.ndarray, confs: np.ndarray | None, region: tuple[float, float, float, float],
                 inside: np.ndarray, filas: int | None = None, umbral: float = 30.0, low_threshold: float | None = None) -> dict:
    """Filas, frentes y totales dentro de ``region`` = (x0, y0, x1, y1) en píxeles.

    ``inside``: máscara booleana de las cajas que cuentan (centro dentro de la región).
    """
    x0, y0, x1, y1 = region
    boxes = np.asarray(boxes, dtype=np.float64).reshape(-1, 4)
    idx = np.where(inside)[0]
    b = boxes[idx]
    c = confs[idx] if confs is not None else None
    width = max(x1 - x0, 1.0)
    if not len(b):
        return {"filas": [], "resumen": _summary([], width, umbral, 0), "productos": [], "huecos": []}

    cy = (b[:, 1] + b[:, 3]) / 2
    heights = b[:, 3] - b[:, 1]
    widths = b[:, 2] - b[:, 0]
    typical_frente = float(np.median(widths))
    bands = _row_bands(cy, heights, filas, y0, y1)

    rows: list[Row] = []
    n_bands = len(bands)
    for k, members in enumerate(bands):
        if not members:
            if filas:  # fila definida por el usuario sin productos
                rows.append(_row(k, [], b, c, idx, width, typical_frente, umbral, y0, y1, n_bands, low_threshold))
            continue
        rows.append(_row(k, members, b, c, idx, width, typical_frente, umbral, y0, y1, n_bands, low_threshold))
    productos = []
    n = 0
    for r in rows:
        ordenadas = sorted(r.cajas, key=lambda i: boxes[i, 0])  # de izquierda a derecha
        for pos, i in enumerate(ordenadas, start=1):
            n += 1
            productos.append({
                "id": n,
                "fila": r.indice,
                "posicion": pos,
                "bbox": [float(v) for v in boxes[i]],
                "confianza": round(float(confs[i]) * 100, 1) if confs is not None else None,
            })
    filas_dict = [r.to_dict() for r in rows]
    return {"filas": filas_dict, "resumen": _summary(rows, width, umbral, len(b)),
            "productos": productos,
            "huecos": huecos_por_fila(filas_dict, boxes, region, typical_frente)}


def _row(k, members, b, c, idx, width, typical_frente, umbral, y0, y1, n_bands, low_threshold=None) -> Row:
    sub = b[members] if members else np.zeros((0, 4))
    cols = _columns(sub)
    # Mismo ancho de frente para todas las filas: así los totales son comparables entre estantes.
    frente = typical_frente
    totales = max(1, int(round(width / max(frente, 1.0))))
    ocupados = len(cols)
    libres = max(0, totales - ocupados)
    ocup = min(100.0, 100.0 * ocupados / totales)
    below_sufficient = ocup < low_threshold if low_threshold is not None else ocup <= REVISAR_LIMIT
    estado = "REPONER" if ocup <= umbral else ("REVISAR" if below_sufficient else "OK")
    conf = float(np.mean(c[members])) * 100 if c is not None and members else None
    band_h = (y1 - y0) / max(n_bands, 1)
    return Row(
        indice=k + 1,
        productos=len(members),
        frentes_ocupados=ocupados,
        frentes_totales=totales,
        frentes_libres=libres,
        ocupacion_pct=ocup,
        estado=estado,
        confianza_media=conf,
        y_inicio=float(y0 + k * band_h),
        y_fin=float(y0 + (k + 1) * band_h),
        cajas=[int(idx[m]) for m in members],
    )


def _summary(rows: list[Row], width: float, umbral: float, n_productos: int) -> dict:
    totales = sum(r.frentes_totales for r in rows)
    ocupados = sum(r.frentes_ocupados for r in rows)
    libres = sum(r.frentes_libres for r in rows)
    return {
        "productos": n_productos,
        "filas": len(rows),
        "frentes_totales": totales,
        "frentes_ocupados": ocupados,
        "frentes_libres": libres,
        "ocupacion_pct": round(100.0 * ocupados / totales, 1) if totales else None,
        "filas_reponer": sum(1 for r in rows if r.estado == "REPONER"),
        "filas_revisar": sum(1 for r in rows if r.estado == "REVISAR"),
        "umbral_pct": umbral,
    }


def vacios_detalle(vacios: np.ndarray, confs: np.ndarray | None, productos: list[dict]) -> list[dict]:
    """Espacios vacíos detectados, con frentes estimados para rellenar (ancho / ancho típico de frente)."""
    v = np.asarray(vacios, dtype=np.float64).reshape(-1, 4)
    if not len(v):
        return []
    frente = float(np.median([p["bbox"][2] - p["bbox"][0] for p in productos])) if productos else None
    out = []
    for i, b in enumerate(v):
        ancho = b[2] - b[0]
        frentes = max(1, int(round(ancho / frente))) if frente else None
        out.append({
            "bbox": [float(x) for x in b],
            "confianza": round(float(confs[i]) * 100, 1) if confs is not None else None,
            "frentes_para_rellenar": frentes,
        })
    return out


def huecos_por_fila(rows: list[dict], boxes: np.ndarray, region: tuple[float, float, float, float],
                    frente: float, min_frentes: float = 0.6) -> list[dict]:
    """Huecos libres dentro de cada fila: tramos de la región sin productos, de al menos ``min_frentes`` frentes.

    ``rows``: filas ya calculadas (con ``cajas`` y ``y_inicio``/``y_fin`` si existen).
    La franja vertical de cada fila es la de sus productos; una fila sin productos usa su banda definida.
    """
    x0, _, x1, _ = region
    boxes = np.asarray(boxes, dtype=np.float64).reshape(-1, 4)
    out = []
    for r in rows:
        if r["cajas"]:
            sub = boxes[r["cajas"]]
            ya, yb = float(sub[:, 1].min()), float(sub[:, 3].max())
            spans = sorted(zip(sub[:, 0], sub[:, 2]))
        else:
            if "y_inicio" not in r:
                continue
            ya, yb = r["y_inicio"], r["y_fin"]
            spans = []
        cursor = x0
        gaps = []
        for a, b in spans:
            if a > cursor:
                gaps.append((cursor, a))
            cursor = max(cursor, b)
        if cursor < x1:
            gaps.append((cursor, x1))
        for a, b in gaps:
            ancho = b - a
            if ancho >= min_frentes * frente:
                out.append({
                    "fila": r["indice"],
                    "bbox": [float(a), float(ya), float(b), float(yb)],
                    "frentes_para_rellenar": max(1, int(round(ancho / frente))),
                })
    return out
