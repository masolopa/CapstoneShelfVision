"""Argon2 y sesiones opacas: solo se conserva la huella del token."""
import hashlib
import secrets
import threading
import time
from collections import OrderedDict
from typing import Annotated
from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import APIKeyCookie
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(32))
COOKIE_NAME = "regova_session"
cookie_scheme = APIKeyCookie(name=COOKIE_NAME, auto_error=False)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_password(value: str, encoded: str) -> bool:
    try:
        return passwords.verify(value, encoded)
    except (ValueError, TypeError, UnknownHashError):
        return False


class LoginLimiter:
    """Límite local por cliente; al reiniciar se limpia. Un proceso para el MVP."""
    def __init__(self):
        self.entries = OrderedDict()
        self.lock = threading.Lock()

    def check(self, key):
        with self.lock:
            now = time.monotonic()
            old = self.entries.get(key, (0, now))
            count = old[0] if now - old[1] < 300 else 0
            if count >= 10:
                raise HTTPException(429, "Demasiados intentos. Espera cinco minutos.")
            self.entries[key] = (count + 1, old[1] if count else now)
            self.entries.move_to_end(key)
            while len(self.entries) > 5000:
                self.entries.popitem(last=False)

    def clear(self, key):
        with self.lock:
            self.entries.pop(key, None)


def mutation_guard(request: Request, x_regova_request: Annotated[str | None, Header(alias="X-Regova-Request")] = None):
    # La cabecera exige una petición explícita de la aplicación (también en login).
    if x_regova_request != "1":
        raise HTTPException(403, "Solicitud no autorizada.")
    origin = request.headers.get("origin")
    if origin and origin not in request.app.state.settings.origins:
        raise HTTPException(403, "Origen no autorizado.")


def current_user(request: Request, token: str | None = Depends(cookie_scheme)):
    if not token or len(token) > 128:
        raise HTTPException(401, "Inicia sesión para continuar.")
    with request.app.state.db.connection() as conn:
        user = conn.execute("""SELECT u.*, l.codigo AS local_codigo FROM sesiones s
          JOIN usuarios u ON u.id=s.usuario_id JOIN locales l ON l.id=u.local_id
          WHERE s.token_hash=%s AND s.expira_en>current_timestamp
          AND u.activo AND u.eliminado_en IS NULL AND l.activo""", (token_hash(token),)).fetchone()
    if not user:
        raise HTTPException(401, "Tu sesión expiró o la cuenta está desactivada.")
    return user


def require_roles(*roles):
    def dependency(user=Depends(current_user)):
        if user["rol"] not in roles:
            raise HTTPException(403, "No tienes permiso para esta operación.")
        return user
    return dependency


def public_user(user):
    role = "admin_principal" if user["codigo"] == "ADM-001" else {"administrador": "admin_local", "supervisor": "supervisor", "reponedor": "reponedor"}[user["rol"]]
    return {"id": user["codigo"], "name": user["nombre"], "email": user.get("email") or "", "role": role,
            "roleLabel": {"administrador": "Administrador", "supervisor": "Supervisor", "reponedor": "Reponedor"}[user["rol"]],
            "scope": "local", "branch": user["local_codigo"], "active": user["activo"]}
