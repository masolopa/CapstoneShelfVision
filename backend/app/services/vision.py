"""Procesamiento de visión sin acceso a base de datos ni sesiones."""
import base64, time, os
from fastapi import HTTPException
from app.availability import AreaBreakdown, compute_availability
from app.vision.baseline import analyze_image_bytes, render_overlay
from app.vision.yolo_detector import DetectorUnavailable
from app.shelf_rows import analyze_rows, vacios_detalle
from app.vision.detections_overlay import render_detections
import cv2
import numpy as np
from app.vision.preprocessing import PreprocessConfig
from app.vision.regions import centers_inside, polygon_pixels, clip_spaces
from app.vision.useful_space import apply_useful_space, detected_empty_surface
from app.vision.masks import count_categories



def process_image(data, opts, s):
    roi_poly=opts.get("roi")
    excl=opts.get("exclusions")
    struct=opts.get("structural")
    method=opts["method"]
    filas=opts.get("filas")
    capture_date=opts.get("capture_date", "")
    reference=opts.get("reference", "")
    observations=opts.get("observations", "")
    t0 = time.time()
    try:
        img, out = analyze_image_bytes(data, roi_poly, excl, struct,
                                       preprocess_cfg=PreprocessConfig(min_side=s["min_side_px"]),
                                       method=method)
    except DetectorUnavailable as e:
        raise HTTPException(503, f"Detector YOLO no disponible: {e}")
    except (ValueError, TypeError, IndexError, KeyError) as e:
        raise HTTPException(422, f"Polígono o imagen no válidos: {e}")
    if min(img.shape[:2]) < s["min_side_px"]:
        raise HTTPException(422, "Imagen demasiado pequeña para analizar")
    use_surface = os.environ.get('REGOVA_SURFACE_PILOT', '1') != '0' and bool(roi_poly) and out.boxes is not None
    conteo = _conteo(img, out, roi_poly, filas, s["threshold"], s["low_threshold"], use_fronts=not use_surface)
    if use_surface:
        out.labels = detected_empty_surface(out.labels, out.vacios)
        out.areas = count_categories(out.labels)
    c = out.areas
    areas = AreaBreakdown(occupied=c["occupied"], empty=c["empty"], excluded=c["excluded"],
                          structural=c["structural"], unknown=c["unknown"])
    try:
        res = compute_availability(areas, s["threshold"], s["low_threshold"])
    except ValueError as e:
        raise HTTPException(422, str(e))
    if use_surface:
        overlay = render_overlay(img, out)
    elif conteo is not None:
        roi_px = polygon_pixels(img.shape, roi_poly) if roi_poly else None
        overlay = render_detections(img, conteo["productos"], conteo["vacios"] + conteo["huecos"], roi_px)
    else:
        overlay = render_overlay(img, out)
    q = out.quality
    result = {
        "status": res.status, "availability_pct": res.availability_pct, "empty_pct": res.empty_pct,
        "evaluable_area": res.evaluable_area, "unknown_area": res.unknown_area,
        "structural_area": res.structural_area, "excluded_area": res.excluded_area,
        "alert": res.alert, "criticality": res.criticality, "reason": res.reason,
        "threshold": s["threshold"], "low_threshold": s["low_threshold"], "classification_version": 2, "excluded_px": c["excluded"],
        "areas_px": c, "warnings": q.warnings if q else [],
        "quality": {"blur_score": q.blur_score, "mean_brightness": q.mean_brightness} if q else None,
        "inference_seconds": round(time.time() - t0, 3), "method": out.method,
        "perspective_corrected": False,
        "overlay_jpg_b64": base64.b64encode(overlay).decode(),
        "conteo": conteo,
    }
    if use_surface:
        result['requires_review'] = bool(result['warnings'])
        eligible = c['occupied'] + c['empty'] + c['unknown']
        if eligible:
            detected_share = 100 * c['occupied'] / eligible
            result['alert_product_coverage_pct'] = round(detected_share, 2)
            if c['unknown'] and detected_share <= s['threshold'] and not result['alert']:
                reason = (
                    f"Revisar góndola: producto detectado en {detected_share:.2f}% de la región útil, "
                    f"igual o por debajo del umbral crítico ({s['threshold']}%). "
                    "La señal incluye la superficie desconocida al evaluar cuánto espacio quedó sin producto detectado."
                )
                result.update(alert=True, criticality='critica', reason=reason,
                              alert_basis='product_coverage_review', requires_review=True)
                result['warnings'].append(reason)
    result['availability_basis'] = 'surface'
    result['surface_availability_pct'] = res.availability_pct
    result['surface_empty_pct'] = res.empty_pct
    if conteo and conteo.get('espacio_util', {}).get('evaluado'):
        counts = conteo['resumen']
        useful = compute_availability(AreaBreakdown(occupied=counts['frentes_ocupados'],
                                      empty=counts['frentes_libres']),
                                      s['threshold'], s['low_threshold'])
        result.update(availability_basis='useful_fronts', availability_pct=useful.availability_pct,
                      empty_pct=useful.empty_pct, status=useful.status, alert=useful.alert,
                      criticality=useful.criticality,
                      reason='Ocupación útil estimada por frentes. ' + useful.reason,
                      useful_occupied_fronts=counts['frentes_ocupados'],
                      useful_free_fronts=counts['frentes_libres'])
    original = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    result.update({"capture_date": capture_date, "reference": reference, "observations": observations, "requested_shelves": filas,
                   "original_jpg_b64": base64.b64encode(cv2.imencode(".jpg", original)[1]).decode()})
    return result, overlay


def _conteo(img, out, roi_poly, filas, umbral, low_threshold=None, *, use_fronts=True):
    """Productos y frentes por fila. Solo con el detector YOLO (las cajas no existen con la heurística)."""
    if out.boxes is None:
        return None
    h, w = img.shape[:2]
    if roi_poly:
        pts = polygon_pixels(img.shape, roi_poly)
        x0, y0 = pts.min(axis=0)
        x1, y1 = pts.max(axis=0)
    else:
        pts = None
        x0, y0, x1, y1 = 0.0, 0.0, float(w), float(h)
    inside = centers_inside(out.boxes, img.shape, roi_poly)
    res = analyze_rows(out.boxes, out.confs, (float(x0), float(y0), float(x1), float(y1)), inside,
                       filas=filas, umbral=umbral, low_threshold=low_threshold)
    if low_threshold is not None:
        res["resumen"]["low_threshold"] = low_threshold
    res["vacios"] = vacios_detalle(out.vacios, out.vacios_confs, res["productos"]) if out.vacios is not None else []
    if roi_poly:
        res["vacios"] = clip_spaces(res["vacios"], img.shape, roi_poly, res["productos"])
        res["huecos"] = clip_spaces(res["huecos"], img.shape, roi_poly, res["productos"])
    if not roi_poly:  # sin región marcada, los huecos mezclarían suelo y paredes con estantes
        res["huecos"] = []
    if use_fronts and roi_poly and os.environ.get("REGOVA_USEFUL_SPACE", "1") != "0":
        res = apply_useful_space(res, out.labels, umbral, low_threshold)
    res["resumen"]["vacios_detectados"] = len(res["vacios"])
    res["resumen"]["frentes_para_rellenar_vacios"] = sum(v["frentes_para_rellenar"] or 0 for v in res["vacios"])
    res["resumen"]["productos_descartados"] = out.descartados
    res["resumen"]["huecos_detectados"] = len(res["huecos"])
    res["resumen"]["frentes_para_rellenar_huecos"] = sum(h["frentes_para_rellenar"] for h in res["huecos"])
    return res


