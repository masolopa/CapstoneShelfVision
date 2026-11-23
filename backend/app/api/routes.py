"""Contrato HTTP. Las reglas y la persistencia residen fuera de las rutas."""
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import Response as BinaryResponse
from starlette.concurrency import run_in_threadpool

from app.api.schemas import (AlertUpdate, AnalysisResponse, GroupedReports, Login,
                             MetadataUpdate, ReviewCreate, SettingsUpdate, UserCreate, UserUpdate)
from app.core.security import (COOKIE_NAME, DUMMY_HASH, current_user, mutation_guard,
                               public_user, require_roles, token_hash, verify_password)
from app.report import build_pdf, build_grouped_pdf
from app.repositories import audit
from app import training

from app.api.schemas import EmailModel, ResetPassword
from app.services.recovery import request_recovery, reset_password

router = APIRouter(prefix="/api")
reader = Depends(current_user)
writer = Depends(require_roles("administrador", "supervisor"))
admin = Depends(require_roles("administrador"))
mutating = [Depends(mutation_guard)]


@router.get("/health", tags=["Estado"])
def health():
    return {"status": "ok", "service": "regova", "version": "1.1.0", "detector": "opencv/yolo", "model_ml": "consultar /api/training/status"}


@router.get("/ready", tags=["Estado"])
def ready(request: Request):
    with request.app.state.db.connection() as c:
        tables = c.execute("SELECT to_regclass('regova.sesiones') IS NOT NULL AS sessions, EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='regova' AND table_name='analisis' AND column_name='pasillo') AS location").fetchone()
    if not all(tables.values()):
        raise HTTPException(503, "Falta aplicar la preparación de la base de datos.")
    return {"status": "ready", "database": "postgresql"}


@router.post("/auth/login", dependencies=mutating, tags=["Autenticación"])
def login(body: Login, request: Request, response: Response):
    limiter = request.app.state.login_limiter
    key = request.client.host if request.client else "local"
    limiter.check(key)
    with request.app.state.db.connection() as c:
        user = c.execute("""SELECT u.*, l.codigo AS local_codigo,l.activo AS local_activo FROM usuarios u
          JOIN locales l ON l.id=u.local_id WHERE upper(u.codigo)=upper(%s) OR lower(u.email)=lower(%s) LIMIT 1""",
          (body.username.strip(), body.username.strip())).fetchone()
        valid = verify_password(body.password, user["password_hash"] if user else DUMMY_HASH)
        if not user or not valid or not user["activo"] or user["eliminado_en"] or not user["local_activo"]:
            raise HTTPException(401, "Usuario o contraseña incorrectos.")
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(hours=request.app.state.settings.session_hours)
        old = request.cookies.get(COOKIE_NAME)
        if old:
            c.execute("DELETE FROM sesiones WHERE token_hash=%s", (token_hash(old),))
        c.execute("DELETE FROM sesiones WHERE expira_en<=current_timestamp")
        c.execute("INSERT INTO sesiones(token_hash,usuario_id,expira_en) VALUES(%s,%s,%s)", (token_hash(token), user["id"], expires))
        audit(c, user["id"], "sesion.iniciar", "usuarios", user["id"])
    limiter.clear(key)
    response.set_cookie(COOKIE_NAME, token, max_age=request.app.state.settings.session_hours*3600,
                        httponly=True, secure=request.app.state.settings.cookie_secure, samesite="strict", path="/api")
    response.headers["Cache-Control"] = "no-store"
    return public_user(user)


@router.post("/auth/recovery", dependencies=mutating, tags=["Autenticación"])
def recover(body: EmailModel, request: Request):
    request.app.state.recovery_limiter.check(request.client.host if request.client else "local")
    return request_recovery(request.app.state.db, request.app.state.settings, body.email)


@router.post("/auth/reset-password", dependencies=mutating, status_code=204, tags=["Autenticación"])
def reset(body: ResetPassword, request: Request):
    request.app.state.recovery_limiter.check(request.client.host if request.client else "local")
    reset_password(request.app.state.db, body.token, body.password)


@router.get("/auth/me", tags=["Autenticación"])
def me(user=reader):
    return public_user(user)


@router.post("/auth/logout", dependencies=mutating, status_code=204, tags=["Autenticación"])
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        with request.app.state.db.connection() as c:
            c.execute("DELETE FROM sesiones WHERE token_hash=%s", (token_hash(token),))
    response.delete_cookie(COOKIE_NAME, path="/api", secure=request.app.state.settings.cookie_secure, httponly=True, samesite="strict")


@router.get("/users", tags=["Usuarios"])
def users(request: Request, user=admin):
    return request.app.state.repo.list_users(user)


@router.get("/users/activity", tags=["Usuarios"])
def activity(request: Request, user=admin):
    return request.app.state.repo.user_activity(user)


@router.post("/users", dependencies=mutating, status_code=201, tags=["Usuarios"])
def create_user(body: UserCreate, request: Request, user=admin):
    return request.app.state.repo.create_user(user, body)


@router.patch("/users/{code}", dependencies=mutating, status_code=204, tags=["Usuarios"])
def change_user(code: str, body: UserUpdate, request: Request, user=admin):
    request.app.state.repo.change_user(user, code, body)


@router.delete("/users/{code}", dependencies=mutating, status_code=204, tags=["Usuarios"])
def delete_user(code: str, request: Request, user=admin):
    request.app.state.repo.change_user(user, code)


@router.get("/settings", tags=["Configuración"])
def settings(request: Request, user=reader):
    return request.app.state.repo.settings(user)


@router.put("/settings", dependencies=mutating, tags=["Configuración"])
def save_settings(body: SettingsUpdate, request: Request, user=admin):
    return request.app.state.repo.update_settings(user, body.model_dump(exclude_none=True))


@router.post("/analyze", dependencies=mutating, response_model=AnalysisResponse, tags=["Análisis"])
async def analyze(request: Request, file: Annotated[UploadFile, File()],
                  pasillo: Annotated[str, Form(min_length=1, max_length=50)],
                  method: Annotated[str, Form()] = "yolo",
                  filas: Annotated[int | None, Form(ge=1, le=20)] = None,
                  capture_date: Annotated[str, Form(max_length=64)] = "",
                  reference: Annotated[str, Form(max_length=100)] = "",
                  observations: Annotated[str, Form(max_length=500)] = "",
                  roi: Annotated[str | None, Form(max_length=10000)] = None,
                  exclusions: Annotated[str | None, Form(max_length=100000)] = None,
                  structural: Annotated[str | None, Form(max_length=100000)] = None,
                  user=writer):
    if method not in ("heuristic", "yolo"):
        raise HTTPException(422, "Método inválido.")
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(415, "Usa imágenes JPG, PNG o WEBP.")
    limits = await run_in_threadpool(request.app.state.repo.settings, user)
    maximum = int(limits["max_upload_mb"]*1024*1024)
    try:
        content = await file.read(maximum+1)
    finally:
        await file.close()
    if len(content) > maximum:
        raise HTTPException(413, "La imagen supera el tamaño permitido.")
    try:
        geometry = {"roi": json.loads(roi) if roi else None, "exclusions": json.loads(exclusions) if exclusions else [], "structural": json.loads(structural) if structural else []}
    except (ValueError, TypeError):
        raise HTTPException(422, "Las zonas dibujadas no son JSON válido.")
    opts = {**geometry, "method": method, "filas": filas, "capture_date": capture_date, "reference": reference, "observations": observations}
    filename = (file.filename or "imagen").replace("\\", "/").split("/")[-1][:255]
    new_id = await run_in_threadpool(request.app.state.analysis.execute, user, content, filename, file.content_type, pasillo, opts)
    return await run_in_threadpool(request.app.state.repo.analysis, user, new_id)


@router.get("/history", tags=["Análisis"])
def history(request: Request, limit: int = Query(50, ge=1, le=200), before_id: int | None = Query(None, gt=0), user=reader):
    return request.app.state.repo.history(user, limit, before_id)


@router.get("/dashboard/history", tags=["Panel"])
def dashboard_history(request: Request, limit: int = Query(200, ge=1, le=200), user=reader):
    live = [{**r, "origin": "live"} for r in request.app.state.repo.history(user, limit)]
    archive = request.app.state.historical.summaries(user)
    return sorted(live + archive, key=lambda r: (r["created_at"], r["id"]), reverse=True)[:limit]


@router.get("/dashboard/historical/{legacy_id}/report.pdf", tags=["Panel"])
def historical_report(legacy_id: int, request: Request, user=reader):
    result = request.app.state.historical.report_data(user, legacy_id)
    return BinaryResponse(build_pdf(result), media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="historico_prueba_{legacy_id}.pdf"'})


@router.get("/metrics", tags=["Análisis"])
def metrics(request: Request, user=reader):
    return request.app.state.repo.metrics(user)


@router.get("/analyze/{analysis_id}", response_model=AnalysisResponse, tags=["Análisis"])
def analysis(analysis_id: int, request: Request, user=reader):
    return request.app.state.repo.analysis(user, analysis_id)


@router.patch("/analyze/{analysis_id}", dependencies=mutating, response_model=AnalysisResponse, tags=["Análisis"])
def metadata(analysis_id: int, body: MetadataUpdate, request: Request, user=writer):
    request.app.state.repo.change_analysis(user, analysis_id, body)
    return request.app.state.repo.analysis(user, analysis_id)


@router.delete("/analyze/{analysis_id}", dependencies=mutating, status_code=204, tags=["Análisis"])
def delete_analysis(analysis_id: int, request: Request, user=admin):
    request.app.state.repo.change_analysis(user, analysis_id)


@router.post("/analyze/{analysis_id}/reviews", dependencies=mutating, status_code=201, tags=["Revisiones"])
def review(analysis_id: int, body: ReviewCreate, request: Request, user=writer):
    return request.app.state.repo.review(user, analysis_id, body)


@router.get("/analyze/{analysis_id}/report.pdf", tags=["Reportes"])
def report(analysis_id: int, request: Request, user=reader):
    result = request.app.state.repo.analysis(user, analysis_id)
    return BinaryResponse(build_pdf(result), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="reporte_{analysis_id}.pdf"'})


@router.post("/reports/grouped.pdf", dependencies=mutating, tags=["Reportes"])
def grouped(body: GroupedReports, request: Request, user=reader):
    results = [request.app.state.repo.analysis(user, i) for i in dict.fromkeys(body.ids)]
    return BinaryResponse(build_grouped_pdf(results), media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="regova_reportes.pdf"'})


@router.get("/alerts", tags=["Alertas"])
def alerts(request: Request, user=reader):
    return request.app.state.repo.alerts(user)


@router.patch("/alerts/{alert_id}", dependencies=mutating, status_code=204, tags=["Alertas"])
def attend(alert_id: int, body: AlertUpdate, request: Request, user=Depends(require_roles("reponedor", "supervisor", "administrador"))):
    request.app.state.repo.attend_alert(user, alert_id, body.estado, body.motivo)


@router.get("/training/status", tags=["Detector"])
def training_status(user=reader):
    return {"dataset": training.dataset_status(), "modelo": training.training_status()}


@router.get("/analyze/{analysis_id}/reviews", tags=["Revisiones"])
def reviews(analysis_id: int, request: Request, user=writer):
    return request.app.state.repo.reviews(user, analysis_id)
