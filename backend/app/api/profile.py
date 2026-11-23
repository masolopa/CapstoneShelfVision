from fastapi import APIRouter, Depends, HTTPException, Request
from app.api.schemas import EmailModel
from app.core.security import current_user, mutation_guard, verify_password
from app.repositories import audit

router = APIRouter(prefix="/api/auth")

class ProfileEmail(EmailModel):
    password: str

@router.put("/email", dependencies=[Depends(mutation_guard)], status_code=204)
def email(body: ProfileEmail, request: Request, actor=Depends(current_user)):
    with request.app.state.db.connection() as c:
        user = c.execute("SELECT * FROM usuarios WHERE id=%s FOR UPDATE", (actor["id"],)).fetchone()
        if not verify_password(body.password, user["password_hash"]):
            raise HTTPException(400, "La contraseña actual es incorrecta.")
        c.execute("UPDATE usuarios SET email=%s WHERE id=%s", (body.email, user["id"]))
        c.execute("DELETE FROM recuperaciones_acceso WHERE usuario_id=%s", (user["id"],))
        audit(c, user["id"], "usuario.actualizar_correo", "usuarios", user["id"])
