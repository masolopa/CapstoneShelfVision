"""Estimación experimental de capacidad visible mediante rectángulos por fila.

No cambia la disponibilidad de superficie ni garantiza capacidad en profundidad.
"""
import math
import os
import numpy as np
import cv2

from app.vision.masks import Category
from app.shelf_rows import _columns


def _local_placements(free, boxes):
    """Referencia por sector con votos de las tres columnas más cercanas.

    Los productos apilados votan como una columna, para que muchas cajas pequeñas
    no dominen por cantidad. Los empates entre tamaños distintos quedan sin
    propuesta. No se achican referencias para hacerlas caber.
    """
    boxes = np.asarray(boxes, dtype=np.float64).reshape(-1, 4)
    columns = _columns(boxes)
    sizes = np.asarray([np.median(boxes[c, 2:] - boxes[c, :2], axis=0) for c in columns])
    centers = np.asarray([np.median((boxes[c, 0] + boxes[c, 2]) / 2) for c in columns])
    groups, assignments = [], np.zeros(len(columns), dtype=int)
    # Semillas grandes primero: no crear un tamaño intermedio entre botella y caja.
    for index in np.argsort(-sizes[:, 1]):
        found = next((i for i, g in enumerate(groups)
                      if np.all(np.maximum(sizes[index] / g['seed'], g['seed'] / sizes[index]) <= 1.45)), None)
        if found is None:
            found = len(groups)
            groups.append({'seed': sizes[index], 'members': []})
        groups[found]['members'].append(index)
        assignments[index] = found
    sectors = np.full(free.shape[1], -1, dtype=int)
    for x in range(free.shape[1]):
        nearest = np.argsort(np.abs(centers - x), kind='stable')[:3]
        votes = np.bincount(assignments[nearest], minlength=len(groups))
        winners = np.flatnonzero(votes == votes.max())
        if len(winners) == 1 and assignments[nearest[0]] == winners[0]:
            sectors[x] = winners[0]
    placements, references = [], []
    occupied = np.zeros(free.shape[1], dtype=bool)
    for group_id, group in enumerate(groups):
        size = np.median(sizes[group['members']], axis=0)
        width, height = (max(1, int(math.ceil(v))) for v in size)
        sector = sectors == group_id
        # La caja completa debe pertenecer al sector compatible, no solo su centro.
        candidates = _placements(free & sector[None, :] & ~occupied, width, height)
        for a, _, c, _ in candidates:
            occupied[a:c] = True
        placements.extend(candidates)
        references.append({'ancho_px': width, 'alto_px': height,
                           'columnas_referencia': len(group['members']),
                           'frentes_utiles': len(candidates),
                           'rango_x': [int(np.flatnonzero(sector)[0]), int(np.flatnonzero(sector)[-1])]
                           if sector.any() else None})
    return placements, references, int(np.count_nonzero(sectors < 0))


def _placements(free, width, height, limit=1000):
    """Coloca un frente por posición horizontal, dando prioridad a la parte baja.

    Se usa una imagen integral para comprobar todos los píxeles de cada posición.
    La selección es voraz y conservadora; no resuelve empaquetado óptimo.
    """
    h, w = free.shape
    if width < 1 or height < 1 or width > w or height > h:
        return []
    integral = cv2.integral(free.astype(np.uint8), sdepth=cv2.CV_32S)
    sums = (integral[height:, width:] - integral[:-height, width:]
            - integral[height:, :-width] + integral[:-height, :-width])
    valid = sums == width * height
    out = []
    for _ in range(limit):
        ys = np.flatnonzero(valid.any(axis=1))
        if not len(ys):
            break
        y = int(ys[-1])
        x = int(np.flatnonzero(valid[y])[0])
        out.append([x, y, x + width, y + height])
        # La misma posición horizontal solo admite un frente, a cualquier altura.
        valid[:, max(0, x - width + 1):x + width] = False
    return out


def detected_empty_surface(labels, empty_boxes):
    """Marca solo vacíos detectados dentro de la superficie útil sin producto."""
    result = labels.copy()
    result[labels == Category.EMPTY] = Category.UNKNOWN
    height, width = labels.shape
    for x1, y1, x2, y2 in empty_boxes:
        left, top = max(0, math.floor(x1)), max(0, math.floor(y1))
        right, bottom = min(width, math.ceil(x2)), min(height, math.ceil(y2))
        if right <= left or bottom <= top:
            continue
        patch = result[top:bottom, left:right]
        patch[labels[top:bottom, left:right] == Category.EMPTY] = Category.EMPTY
    return result


def apply_useful_space(result, labels, threshold, low_threshold=None):
    """Actualiza capacidad y marcas usando solo píxeles EMPTY de la región.

    Conserva las propuestas originales para trazabilidad. Una fila sin productos
    usa la mediana global y se identifica como referencia global estimada.
    """
    products = result['productos']
    if not products or not result['filas']:
        result['espacio_util'] = {'version': 1, 'evaluado': False,
                                 'motivo': 'Sin productos de referencia para estimar dimensiones.'}
        return result
    result['vacios_visuales'] = result['vacios']
    result['huecos_visuales'] = result['huecos']
    original_empty = result['vacios']
    result['vacios'], result['huecos'] = [], []
    h, w = labels.shape
    all_boxes = np.asarray([p['bbox'] for p in products])
    global_size = np.median(all_boxes[:, 2:] - all_boxes[:, :2], axis=0)
    available = labels == Category.EMPTY
    references = []
    for row in result['filas']:
        members = [p for p in products if p['fila'] == row['indice']]
        if members:
            boxes = np.asarray([p['bbox'] for p in members])
            size = np.median(boxes[:, 2:] - boxes[:, :2], axis=0)
            top, bottom = boxes[:, 1].min(), boxes[:, 3].max()
        else:
            size = global_size
            top, bottom = row['y_inicio'], row['y_fin']
        fw, fh = (max(1, int(math.ceil(v))) for v in size)
        top, bottom = max(0, int(math.floor(top))), min(h, int(math.ceil(bottom)))
        free = available[top:bottom]
        local = bool(members) and os.environ.get('REGOVA_LOCAL_REFERENCE', '1') != '0'
        if local:
            placements, sectors, ambiguous_width = _local_placements(free, boxes)
        else:
            placements = _placements(free, fw, fh)
            sectors, ambiguous_width = [], 0
        for a, b, c, d in placements:
            bbox = [a, b + top, c, d + top]
            available[b + top:d + top, a:c] = False
            cx, cy = (a + c) / 2, (b + d) / 2 + top
            detection = next((v for v in original_empty
                              if v['bbox'][0] <= cx <= v['bbox'][2]
                              and v['bbox'][1] <= cy <= v['bbox'][3]), None)
            item = {'fila': row['indice'], 'bbox': [float(v) for v in bbox],
                    'frentes_para_rellenar': 1, 'espacio_util': True}
            if detection is not None:
                item['confianza'] = detection.get('confianza')
                result['vacios'].append(item)
            else:
                result['huecos'].append(item)
        capacity = len(placements)
        row['frentes_libres_superficie'] = row['frentes_libres']
        row['frentes_totales_superficie'] = row['frentes_totales']
        row['frentes_libres'] = capacity
        row['frentes_totales'] = row['frentes_ocupados'] + capacity
        total = row['frentes_totales']
        occupancy = 100 * row['frentes_ocupados'] / total if total else 0
        row['ocupacion_pct'] = round(occupancy, 1)
        review = occupancy < low_threshold if low_threshold is not None else occupancy <= 70
        row['estado'] = 'REPONER' if occupancy <= threshold else ('REVISAR' if review else 'OK')
        references.append({'fila': row['indice'], 'ancho_px': fw, 'alto_px': fh,
                           'origen': 'sector' if local else ('fila' if members else 'global'),
                           'sectores': sectors, 'ancho_ambiguo_px': ambiguous_width,
                           'frentes_utiles': capacity})
    summary = result['resumen']
    summary['frentes_libres_superficie'] = summary['frentes_libres']
    summary['frentes_totales_superficie'] = summary['frentes_totales']
    summary['frentes_libres'] = sum(r['frentes_libres'] for r in result['filas'])
    summary['frentes_totales'] = sum(r['frentes_totales'] for r in result['filas'])
    total = summary['frentes_totales']
    summary['ocupacion_pct'] = round(100 * summary['frentes_ocupados'] / total, 1) if total else None
    summary['filas_reponer'] = sum(r['estado'] == 'REPONER' for r in result['filas'])
    summary['filas_revisar'] = sum(r['estado'] == 'REVISAR' for r in result['filas'])
    result['espacio_util'] = {'version': 2, 'evaluado': True, 'referencias': references,
                             'metodo': 'Tamaño por sector y voto de columnas cercanas sobre máscara vacía'}
    return result
