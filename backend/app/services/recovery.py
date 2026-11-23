"""Recuperación por correo: tokens de 30 minutos, huellas y consumo atómico."""
import logging
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from fastapi import HTTPException
from app.core.security import token_hash, passwords
from app.repositories import audit

logger = logging.getLogger("regova.recovery")

MESSAGE = "Si el correo está asociado a una cuenta activa, recibirás tu ID y las instrucciones de recuperación."


def send_recovery(settings, email, code, token):
    if settings.smtp_security not in ("starttls", "ssl"):
        raise ValueError("Configura SMTP con starttls o ssl.")
    message = EmailMessage()
    message["Subject"] = "REGOVA: recuperación de acceso"
    message["From"] = settings.smtp_from
    message["To"] = email
    link = settings.public_url.rstrip("/") + "/#recuperar=" + token
    message.set_content(f"Tu ID de usuario es: {code}\nTambién puedes ingresar con tu correo.\n\nPara establecer una contraseña nueva, abre este enlace:\n{link}\n\nVence en 30 minutos y solo puede usarse una vez. Si no lo solicitaste, ignora este mensaje.")
    client = smtplib.SMTP_SSL if settings.smtp_security == "ssl" else smtplib.SMTP
    with client(settings.smtp_host, settings.smtp_port, timeout=15, **({"context": ssl.create_default_context()} if settings.smtp_security == "ssl" else {})) as smtp:
        if settings.smtp_security == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)


def request_recovery(db, settings, email):
    if not settings.smtp_host or not settings.smtp_from:
        raise HTTPException(503, "La recuperación por correo aún no está configurada. Contacta al administrador.")
    # Bloquear al usuario serializa solicitudes y cambios de contraseña.
    with db.connection() as c:
        user = c.execute("""SELECT u.* FROM usuarios u JOIN locales l ON l.id=u.local_id
            WHERE lower(u.email)=%s AND u.activo AND u.eliminado_en IS NULL AND l.activo FOR UPDATE OF u""", (email,)).fetchone()
        if not user:
            return {"message": MESSAGE}
        recent = c.execute("SELECT 1 FROM recuperaciones_acceso WHERE usuario_id=%s AND creada_en>current_timestamp-interval '2 minutes'", (user["id"],)).fetchone()
        if recent:
            return {"message": MESSAGE}
        token = secrets.token_urlsafe(32)
        c.execute("DELETE FROM recuperaciones_acceso WHERE usuario_id=%s OR expira_en<=current_timestamp", (user["id"],))
        c.execute("INSERT INTO recuperaciones_acceso(token_hash,usuario_id,email,expira_en) VALUES(%s,%s,%s,%s)",
                  (token_hash(token), user["id"], email, datetime.now(timezone.utc)+timedelta(minutes=30)))
        # No registrar el token ni devolverlo al navegador que solicitó el correo.
        try:
            send_recovery(settings, email, user["codigo"], token)
        except (OSError, smtplib.SMTPException, ValueError):
            # Misma respuesta para evitar revelar qué correos existen; rollback permite reintentar.
            logger.error("No se pudo entregar un correo de recuperación. Revisa la configuración SMTP.")
            c.rollback()
            return {"message": MESSAGE}
        audit(c, user["id"], "usuario.solicitar_recuperacion", "usuarios", user["id"])
    return {"message": MESSAGE}


def reset_password(db, token, password):
    encoded = passwords.hash(password)
    with db.connection() as c:
        candidate = c.execute("SELECT usuario_id FROM recuperaciones_acceso WHERE token_hash=%s", (token_hash(token),)).fetchone()
        if not candidate:
            raise HTTPException(400, "El enlace es inválido o venció. Solicita uno nuevo.")
        user = c.execute("""SELECT u.* FROM usuarios u JOIN locales l ON l.id=u.local_id
            WHERE u.id=%s AND u.activo AND u.eliminado_en IS NULL AND l.activo FOR UPDATE OF u""", (candidate["usuario_id"],)).fetchone()
        valid = c.execute("""DELETE FROM recuperaciones_acceso WHERE token_hash=%s AND expira_en>current_timestamp
            AND lower(email)=lower(%s) RETURNING usuario_id""", (token_hash(token), user["email"] if user else "")).fetchone()
        if not user or not valid:
            raise HTTPException(400, "El enlace es inválido o venció. Solicita uno nuevo.")
        c.execute("UPDATE usuarios SET password_hash=%s WHERE id=%s", (encoded, user["id"]))
        c.execute("DELETE FROM sesiones WHERE usuario_id=%s", (user["id"],))
        c.execute("DELETE FROM recuperaciones_acceso WHERE usuario_id=%s", (user["id"],))
        audit(c, user["id"], "usuario.restablecer_password", "usuarios", user["id"])
