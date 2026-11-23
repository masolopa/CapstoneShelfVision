"""Acceso PostgreSQL. Todas las consultas de operación se limitan por local."""
import base64
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import HTTPException
from psycopg.types.json import Jsonb
from app.core.security import passwords, public_user


def audit(conn, actor, action, entity, entity_id, detail=None):
    conn.execute("INSERT INTO eventos_auditoria(actor_id,accion,entidad,entidad_id,detalle) VALUES(%s,%s,%s,%s,%s)",
                 (actor, action, entity, entity_id, Jsonb(detail or {})))


def settings_row(conn, local_id):
    row = conn.execute("""SELECT c.* FROM configuraciones_vigentes v
      JOIN configuraciones_analisis c ON c.id=v.configuracion_id AND c.local_id=v.local_id
      WHERE v.local_id=%s""", (local_id,)).fetchone()
    if not row:
        raise HTTPException(409, "Falta configurar los umbrales del local. Ejecuta la preparación inicial.")
    return row


def settings_payload(row):
    return {"threshold": float(row["umbral_critico"]), "low_threshold": float(row["umbral_bajo"]),
            "max_upload_mb": float(row["max_carga_mb"]), "min_side_px": row["lado_minimo_px"]}


class Repository:
    def __init__(self, db, storage):
        self.db, self.storage = db, storage

    def settings(self, user):
        with self.db.connection() as c:
            return settings_payload(settings_row(c, user["local_id"]))

    def update_settings(self, user, changes):
        with self.db.connection() as c:
            c.execute("SELECT pg_advisory_xact_lock(%s)", (user["local_id"],))
            old = settings_row(c, user["local_id"])
            merged = {**settings_payload(old), **changes}
            if merged["threshold"] >= merged["low_threshold"]:
                raise HTTPException(422, "El umbral crítico debe ser menor que el umbral bajo.")
            row = c.execute("""INSERT INTO configuraciones_analisis(local_id,version,umbral_critico,umbral_bajo,max_carga_mb,lado_minimo_px,creado_por)
              VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
              (user["local_id"], old["version"]+1, merged["threshold"], merged["low_threshold"], merged["max_upload_mb"], merged["min_side_px"], user["id"])).fetchone()
            c.execute("UPDATE configuraciones_vigentes SET configuracion_id=%s WHERE local_id=%s", (row["id"], user["local_id"]))
            audit(c, user["id"], "configuracion.crear_version", "configuraciones_analisis", row["id"])
            return settings_payload(row)

    def list_users(self, user):
        with self.db.connection() as c:
            rows = c.execute("""SELECT u.*, l.codigo AS local_codigo FROM usuarios u JOIN locales l ON l.id=u.local_id
              WHERE u.local_id=%s AND u.eliminado_en IS NULL ORDER BY u.id""", (user["local_id"],)).fetchall()
            return [public_user(r) for r in rows]

    def create_user(self, user, body):
        role = {"admin_local": "administrador", "supervisor": "supervisor", "reponedor": "reponedor"}[body.role]
        if user["codigo"] != "ADM-001" and role == "administrador":
            raise HTTPException(403, "Solo la cuenta principal puede crear administradores.")
        name = body.name.strip()
        if not name:
            raise HTTPException(422, "Indica el nombre del usuario.")
        encoded = passwords.hash(body.password)
        with self.db.connection() as c:
            row = c.execute("""INSERT INTO usuarios(local_id,codigo,nombre,password_hash,rol,email)
              VALUES(%s,%s,%s,%s,%s,%s) RETURNING *""",
              (user["local_id"], "USR-"+uuid4().hex[:10].upper(), name, encoded, role, body.email)).fetchone()
            audit(c, user["id"], "usuario.crear", "usuarios", row["id"], {"name": name, "role": body.role, "code": row["codigo"]})
            return public_user({**row, "local_codigo": user["local_codigo"]})

    def change_user(self, user, code, body=None):
        with self.db.connection() as c:
            target = c.execute("SELECT * FROM usuarios WHERE codigo=%s AND local_id=%s AND eliminado_en IS NULL FOR UPDATE", (code, user["local_id"])).fetchone()
            if not target:
                raise HTTPException(404, "No se encontró la cuenta.")
            if code == "ADM-001" or target["id"] == user["id"]:
                raise HTTPException(403, "No puedes modificar esta cuenta desde esta operación.")
            if user["codigo"] != "ADM-001" and (target["rol"] == "administrador" or (body and body.role == "admin_local")):
                raise HTTPException(403, "No tienes jerarquía para modificar esta cuenta.")
            if body is None:
                c.execute("UPDATE usuarios SET activo=false,eliminado_en=current_timestamp WHERE id=%s", (target["id"],))
                action = "usuario.eliminar"
            else:
                role = {"admin_local": "administrador", "supervisor": "supervisor", "reponedor": "reponedor"}[body.role]
                c.execute("UPDATE usuarios SET rol=%s,activo=%s WHERE id=%s", (role, body.active, target["id"]))
                if "email" in body.model_fields_set:
                    c.execute("UPDATE usuarios SET email=%s WHERE id=%s", (body.email, target["id"]))
                    c.execute("DELETE FROM recuperaciones_acceso WHERE usuario_id=%s", (target["id"],))
                action = "usuario.editar"
            # Revocar sesiones también al cambiar rol o suspender.
            c.execute("DELETE FROM sesiones WHERE usuario_id=%s", (target["id"],))
            audit(c, user["id"], action, "usuarios", target["id"], {"name": target["nombre"], "code": code})

    def user_activity(self, user):
        with self.db.connection() as c:
            rows = c.execute("""SELECT e.*, u.codigo AS actor_codigo FROM eventos_auditoria e
              JOIN usuarios u ON u.id=e.actor_id WHERE u.local_id=%s AND e.entidad='usuarios'
              ORDER BY e.id DESC LIMIT 200""", (user["local_id"],)).fetchall()
            return [{"id": r["detalle"].get("code", str(r["entidad_id"])), "name": r["detalle"].get("name", ""),
                     "role": r["detalle"].get("role", "supervisor"), "action": r["accion"],
                     "timestamp": r["creado_en"].isoformat(), "actorId": r["actor_codigo"]} for r in rows]

    def analysis(self, user, analysis_id, images=True):
        with self.db.connection() as c:
            row = c.execute("""SELECT a.*, r.detalle, i.nombre_original, i.uri AS original_uri,
              u.codigo AS autor_codigo FROM analisis a
              JOIN resultados r ON r.analisis_id=a.id JOIN imagenes i ON i.id=a.imagen_id
              JOIN usuarios u ON u.id=a.ejecutado_por
              WHERE a.id=%s AND a.local_id=%s AND a.eliminado_en IS NULL""", (analysis_id, user["local_id"])).fetchone()
            if not row:
                raise HTTPException(404, "Análisis no encontrado.")
            overlay = c.execute("SELECT uri FROM archivos_analisis WHERE analisis_id=%s AND tipo='overlay' ORDER BY id LIMIT 1", (analysis_id,)).fetchone()
        data = {**row["detalle"], "id": row["id"], "created_at": row["creado_en"].isoformat(),
                "filename": row["nombre_original"], "reference": row["referencia"], "observations": row["observaciones"],
                "pasillo": row["pasillo"], "author": row["autor_codigo"]}
        if images:
            if not overlay:
                raise HTTPException(409, "Falta la referencia de la imagen procesada.")
            data["overlay_jpg_b64"] = base64.b64encode(self.storage.read(overlay["uri"])).decode()
            # La evidencia original conserva su formato; la vista usa JPEG por compatibilidad.
            import cv2
            import numpy as np
            original = cv2.imdecode(np.frombuffer(self.storage.read(row["original_uri"]), np.uint8), cv2.IMREAD_COLOR)
            if original is None:
                raise HTTPException(409, "No se pudo leer el original conservado.")
            data["original_jpg_b64"] = base64.b64encode(cv2.imencode(".jpg", original)[1]).decode()
        return data

    def history(self, user, limit, before_id=None):
        with self.db.connection() as c:
            rows = c.execute("""SELECT a.id,a.creado_en,i.nombre_original,a.referencia,r.disponibilidad_pct,
              r.estado_operacional,r.detalle,a.pasillo FROM analisis a JOIN resultados r ON r.analisis_id=a.id
              JOIN imagenes i ON i.id=a.imagen_id
              WHERE a.local_id=%s AND a.eliminado_en IS NULL AND (%s::bigint IS NULL OR a.id<%s)
              ORDER BY a.id DESC LIMIT %s""", (user["local_id"], before_id, before_id, limit)).fetchall()
            return [{"id": r["id"], "created_at": r["creado_en"].isoformat(), "filename": r["nombre_original"],
                     "reference": r["referencia"], "availability_pct": r["disponibilidad_pct"],
                     "empty_pct": r["detalle"].get("empty_pct"), "alert": int(bool(r["detalle"].get("alert"))),
                     "criticality": r["estado_operacional"], "pasillo": r["pasillo"]} for r in rows]

    def metrics(self, user):
        with self.db.connection() as c:
            row = c.execute("""SELECT count(*) AS total_analyses,round(avg(r.disponibilidad_pct),2) AS avg_availability_pct,
              round(avg((r.detalle->>'empty_pct')::numeric),2) AS avg_empty_pct,
              count(*) FILTER(WHERE (r.detalle->>'alert')::boolean) AS alerts
              FROM analisis a JOIN resultados r ON r.analisis_id=a.id WHERE a.local_id=%s AND a.eliminado_en IS NULL""", (user["local_id"],)).fetchone()
            return row

    def change_analysis(self, user, analysis_id, metadata=None):
        with self.db.connection() as c:
            row = c.execute("SELECT id FROM analisis WHERE id=%s AND local_id=%s AND eliminado_en IS NULL FOR UPDATE", (analysis_id, user["local_id"])).fetchone()
            if not row:
                raise HTTPException(404, "Análisis no encontrado.")
            if metadata is None:
                c.execute("UPDATE analisis SET eliminado_en=current_timestamp WHERE id=%s", (analysis_id,))
            else:
                c.execute("UPDATE analisis SET pasillo=%s,referencia=%s,observaciones=%s WHERE id=%s", (metadata.pasillo, metadata.reference, metadata.observations, analysis_id))
            audit(c, user["id"], "analisis.eliminar" if metadata is None else "analisis.editar", "analisis", analysis_id)

    def alerts(self, user):
        with self.db.connection() as c:
            return c.execute("""SELECT al.id,al.analisis_id,al.motivo,al.estado,al.creada_en,al.cerrada_en,
              a.pasillo,a.referencia,u.codigo AS responsable, reviewer.codigo AS revisado_por,
              closure.detalle->>'motivo' AS motivo_cierre FROM alertas al
              JOIN analisis a ON a.id=al.analisis_id
              LEFT JOIN usuarios u ON u.id=al.responsable_id
              LEFT JOIN usuarios reviewer ON reviewer.id=al.cerrada_por
              LEFT JOIN LATERAL (SELECT e.detalle FROM eventos_auditoria e
                WHERE e.entidad='alertas' AND e.entidad_id=al.id AND e.accion='alerta.descartada'
                ORDER BY e.id DESC LIMIT 1) closure ON true
              WHERE a.local_id=%s AND a.eliminado_en IS NULL ORDER BY al.id DESC LIMIT 200""", (user["local_id"],)).fetchall()

    def attend_alert(self, user, alert_id, state, reason=None):
        role = user.get("rol")
        if state not in ("en_atencion", "atendida", "descartada"):
            raise HTTPException(422, "Estado de alerta no válido.")
        if role not in ("reponedor", "supervisor", "administrador") or (state != "descartada" and role != "reponedor"):
            raise HTTPException(403, "Acción no permitida para este rol.")
        reason = reason.strip() if reason else None
        if state == "descartada" and (not reason or not 3 <= len(reason) <= 1000):
            raise HTTPException(422, "Indica un motivo válido para No procede.")
        with self.db.connection() as c:
            alert = c.execute("""SELECT al.* FROM alertas al JOIN analisis a ON a.id=al.analisis_id
              WHERE al.id=%s AND a.local_id=%s AND a.eliminado_en IS NULL FOR UPDATE OF al""", (alert_id, user["local_id"])).fetchone()
            if not alert:
                raise HTTPException(404, "Alerta no encontrada.")
            if alert["estado"] in ("atendida", "descartada"):
                raise HTTPException(409, "La alerta ya está cerrada.")
            if alert["responsable_id"] not in (None, user["id"]) and not (state == "descartada" and role in ("supervisor", "administrador")):
                raise HTTPException(409, "La alerta está asignada a otra persona.")
            closed = state in ("atendida", "descartada")
            responsible = (alert["responsable_id"] if state == "descartada" else user["id"])
            c.execute("""UPDATE alertas SET estado=%s,responsable_id=%s,cerrada_por=%s,cerrada_en=%s WHERE id=%s""",
                      (state, responsible, user["id"] if closed else None,
                       datetime.now(timezone.utc) if closed else None, alert_id))
            audit(c, user["id"], "alerta."+state, "alertas", alert_id,
                  {"motivo": reason} if state == "descartada" else None)


    def review(self, user, analysis_id, body):
        with self.db.connection() as c:
            r = c.execute("""SELECT r.id FROM resultados r JOIN analisis a ON a.id=r.analisis_id
              WHERE a.id=%s AND a.local_id=%s AND a.eliminado_en IS NULL""", (analysis_id, user["local_id"])).fetchone()
            if not r:
                raise HTTPException(404, "Resultado no encontrado.")
            row = c.execute("""INSERT INTO revisiones(resultado_id,analisis_id,revisor_id,decision,correccion,comentario)
              VALUES(%s,%s,%s,%s,%s,%s) RETURNING id""", (r["id"], analysis_id, user["id"], body.decision, Jsonb(body.correccion), body.comentario)).fetchone()
            audit(c, user["id"], "resultado.revisar", "revisiones", row["id"])
            return row


    def reviews(self, user, analysis_id):
        with self.db.connection() as c:
            result = c.execute("""SELECT r.id FROM resultados r JOIN analisis a ON a.id=r.analisis_id
              WHERE a.id=%s AND a.local_id=%s AND a.eliminado_en IS NULL""", (analysis_id, user["local_id"])).fetchone()
            if not result:
                raise HTTPException(404, "Resultado no encontrado.")
            return c.execute("""SELECT r.id,r.decision,r.correccion,r.comentario,r.creado_en,
              u.codigo AS revisor_codigo,u.nombre AS revisor_nombre
              FROM revisiones r JOIN usuarios u ON u.id=r.revisor_id
              WHERE r.resultado_id=%s ORDER BY r.creado_en DESC,r.id DESC""", (result["id"],)).fetchall()
