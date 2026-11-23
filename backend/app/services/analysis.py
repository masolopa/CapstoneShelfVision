"""Orquestación: entradas, evidencia, inferencia y finalización transaccional."""
import hashlib
import io
import logging
import math
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from psycopg.types.json import Jsonb

from app.repositories import audit, settings_row, settings_payload
from app.services.vision import process_image
from app.vision.yolo_detector import ACTIVE_WEIGHTS

logger = logging.getLogger(__name__)


def validate_polygons(opts):
    def polygon(points):
        if not isinstance(points, list) or not 3 <= len(points) <= 100:
            raise HTTPException(422, "Cada polígono necesita entre 3 y 100 vértices.")
        for p in points:
            if not isinstance(p, list) or len(p) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in p):
                raise HTTPException(422, "Las coordenadas deben estar entre 0 y 1.")
        if len({tuple(p) for p in points}) != len(points):
            raise HTTPException(422, "El polígono tiene vértices repetidos.")
        area = sum(points[i][0]*points[(i+1) % len(points)][1]-points[(i+1) % len(points)][0]*points[i][1] for i in range(len(points)))
        if abs(area) < 1e-8:
            raise HTTPException(422, "El polígono no tiene área evaluable.")
        def orient(a,b,c):
            return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        def on_segment(a,b,c):
            return abs(orient(a,b,c)) < 1e-10 and min(a[0],b[0]) <= c[0] <= max(a[0],b[0]) and min(a[1],b[1]) <= c[1] <= max(a[1],b[1])
        def intersect(a,b,c,d):
            x,y,z,w=orient(a,b,c),orient(a,b,d),orient(c,d,a),orient(c,d,b)
            return x*y < 0 and z*w < 0 or on_segment(a,b,c) or on_segment(a,b,d) or on_segment(c,d,a) or on_segment(c,d,b)
        for i in range(len(points)):
            for j in range(i+1, len(points)):
                if j == i+1 or i == 0 and j == len(points)-1:
                    continue
                if intersect(points[i], points[(i+1) % len(points)], points[j], points[(j+1) % len(points)]):
                    raise HTTPException(422, "El polígono se cruza consigo mismo.")
    if opts.get("roi") is not None:
        polygon(opts["roi"])
    for key in ("exclusions", "structural"):
        values = opts.get(key) or []
        if not isinstance(values, list) or len(values) > 32:
            raise HTTPException(422, "Demasiadas zonas dibujadas.")
        for points in values:
            polygon(points)


class AnalysisService:
    def __init__(self, db, storage, settings):
        self.db, self.storage, self.settings = db, storage, settings
        self.slot = threading.BoundedSemaphore(1)

    def execute(self, user, content, filename, mime, pasillo, opts):
        if not self.slot.acquire(blocking=False):
            raise HTTPException(429, "Hay otro análisis en curso. Intenta nuevamente al finalizar.")
        try:
            return self._execute(user, content, filename, mime, pasillo, opts)
        finally:
            self.slot.release()

    def _execute(self, user, content, filename, mime, pasillo, opts):
        pasillo = pasillo.strip()
        if not pasillo or len(pasillo) > 50:
            raise HTTPException(422, "Indica un pasillo de hasta 50 caracteres.")
        validate_polygons(opts)
        capture = None
        if opts.get("capture_date"):
            try:
                capture = datetime.fromisoformat(opts["capture_date"])
                if capture.tzinfo is None:
                    capture = capture.replace(tzinfo=ZoneInfo("America/Santiago"))
            except ValueError:
                raise HTTPException(422, "Fecha de captura inválida.")
        with self.db.connection() as c:
            config = settings_row(c, user["local_id"])
            model = c.execute("SELECT * FROM modelos_vision WHERE metodo=%s ORDER BY id DESC LIMIT 1", (opts["method"],)).fetchone()
            if not model:
                raise HTTPException(409, "Falta registrar la versión del detector. Ejecuta la preparación inicial.")
        limits = settings_payload(config)
        if not content or len(content) > limits["max_upload_mb"] * 1024 * 1024:
            raise HTTPException(413, "La imagen está vacía o supera el tamaño permitido.")
        try:
            with Image.open(io.BytesIO(content)) as image:
                width, height = image.size
                formats = {"JPEG": ("image/jpeg", "jpg"), "PNG": ("image/png", "png"), "WEBP": ("image/webp", "webp")}
                actual = formats.get(image.format)
                if not actual or actual[0] != mime:
                    raise HTTPException(415, "El contenido no corresponde a un JPG, PNG o WEBP válido.")
                if width*height > self.settings.model_max_pixels:
                    raise HTTPException(413, "La imagen tiene demasiados píxeles (máximo 40 megapíxeles).")
                if min(width, height) < limits["min_side_px"]:
                    raise HTTPException(422, "Imagen demasiado pequeña para analizar.")
                image.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise HTTPException(422, "No se pudo validar la imagen.")
        weights = None
        if opts["method"] == "yolo":
            weights = self.storage.resolve(model["artefacto_uri"])
            if not weights.is_file() or hashlib.sha256(weights.read_bytes()).hexdigest() != model["sha256"]:
                raise HTTPException(503, "Los pesos del modelo no están disponibles o no coinciden con su versión registrada.")
        original = self.storage.put(content, "originales", actual[1])
        try:
            with self.db.connection() as c:
                image_id = c.execute("""INSERT INTO imagenes(local_id,cargada_por,uri,nombre_original,mime,sha256,bytes,ancho_px,alto_px,capturada_en)
                  VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                  (user["local_id"], user["id"], original["uri"], filename, mime, original["sha256"], original["bytes"], width, height, capture)).fetchone()["id"]
                analysis_id = c.execute("""INSERT INTO analisis(imagen_id,pasillo,local_id,ejecutado_por,configuracion_id,modelo_id,estado,referencia,observaciones,parametros,iniciado_en)
                  VALUES(%s,%s,%s,%s,%s,%s,'procesando',%s,%s,%s,current_timestamp) RETURNING id""",
                  (image_id, pasillo, user["local_id"], user["id"], config["id"], model["id"], opts["reference"], opts["observations"], Jsonb({**opts, "code_version": "regova-api-1"}))).fetchone()["id"]
                audit(c, user["id"], "analisis.iniciar", "analisis", analysis_id)
        except BaseException:
            self.storage.remove(original["uri"])
            raise
        overlay_file = None
        try:
            token = ACTIVE_WEIGHTS.set(str(weights) if weights else None)
            try:
                result, overlay = process_image(content, opts, limits)
            finally:
                ACTIVE_WEIGHTS.reset(token)
            overlay_file = self.storage.put(overlay, "procesadas", "jpg")
            stored = {k: v for k, v in result.items() if k not in ("overlay_jpg_b64", "original_jpg_b64")}
            with self.db.connection() as c:
                rid = c.execute("""INSERT INTO resultados(analisis_id,disponibilidad_pct,estado_operacional,requiere_revision,area_evaluable_px,detalle)
                  VALUES(%s,%s,%s,%s,%s,%s) RETURNING id""",
                  (analysis_id, result["availability_pct"], result["criticality"], result.get("requires_review", bool(result["warnings"])), result["evaluable_area"], Jsonb(stored))).fetchone()["id"]
                c.execute("INSERT INTO archivos_analisis(analisis_id,tipo,uri,sha256,bytes) VALUES(%s,'overlay',%s,%s,%s)",
                          (analysis_id, overlay_file["uri"], overlay_file["sha256"], overlay_file["bytes"]))
                if result["alert"]:
                    c.execute("INSERT INTO alertas(resultado_id,analisis_id,motivo) VALUES(%s,%s,%s)", (rid, analysis_id, result["reason"] or "Disponibilidad crítica"))
                c.execute("UPDATE analisis SET estado='exitoso',finalizado_en=current_timestamp,duracion_ms=%s WHERE id=%s", (round(result["inference_seconds"]*1000), analysis_id))
                audit(c, user["id"], "analisis.finalizar", "analisis", analysis_id)
            return analysis_id
        except Exception as error:
            if overlay_file:
                self.storage.remove(overlay_file["uri"])
            logger.exception("Falló el análisis id=%s", analysis_id)
            with self.db.connection() as c:
                c.execute("UPDATE analisis SET estado='fallido',finalizado_en=current_timestamp,error_detalle=%s WHERE id=%s", (type(error).__name__, analysis_id))
                audit(c, user["id"], "analisis.fallar", "analisis", analysis_id, {"error_type": type(error).__name__})
            if isinstance(error, HTTPException):
                # No propagar rutas internas ni stderr del detector.
                raise HTTPException(error.status_code, "No se pudo completar el análisis. Verifica la imagen y la disponibilidad del detector.")
            raise HTTPException(500, "No se pudo completar el análisis. Revisa el registro del servidor.")
