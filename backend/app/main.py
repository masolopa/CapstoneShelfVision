"""Aplicación FastAPI de REGOVA: fábrica, middleware y registro de rutas."""
import logging
import time
from uuid import uuid4
from pathlib import Path
import psycopg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.api.routes import router
from app.core.config import load_settings
from app.core.database import Database
from app.core.security import LoginLimiter
from app.repositories import Repository
from app.services.analysis import AnalysisService
from app.services.storage import LocalStorage
from app.services.historical import HistoricalArchive

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("regova.api")


def create_app(settings=None):
    settings = settings or load_settings()
    application = FastAPI(title="REGOVA API", version="1.1.0",
        description="API local de monitoreo de góndolas. Sesiones, roles, evidencia y trazabilidad en PostgreSQL.",
        docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    application.state.settings = settings
    application.state.db = Database(settings.conninfo)
    application.state.storage = LocalStorage(settings.storage_root)
    application.state.historical = HistoricalArchive(application.state.storage)
    application.state.repo = Repository(application.state.db, application.state.storage)
    application.state.analysis = AnalysisService(application.state.db, application.state.storage, settings)
    application.state.login_limiter = LoginLimiter()
    application.state.recovery_limiter = LoginLimiter()
    application.add_middleware(CORSMiddleware, allow_origins=list(settings.origins), allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type", "X-Regova-Request"])

    @application.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = uuid4().hex
        request.state.request_id = request_id
        started = time.monotonic()
        length = request.headers.get("content-length", "0")
        if length.isdigit() and int(length) > 52*1024*1024:
            return JSONResponse({"detail": "La solicitud supera el tamaño permitido."}, status_code=413)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        logger.info("request=%s method=%s path=%s status=%s ms=%s", request_id, request.method,
            request.url.path, response.status_code, round((time.monotonic()-started)*1000))
        return response

    @application.exception_handler(psycopg.IntegrityError)
    async def integrity_error(request: Request, error):
        logger.warning("Conflicto de integridad request=%s sqlstate=%s", getattr(request.state,"request_id",""), error.sqlstate)
        return JSONResponse({"detail": "Los datos entran en conflicto con un registro o una regla de la base."}, status_code=409)

    @application.exception_handler(psycopg.OperationalError)
    async def database_unavailable(request: Request, error):
        logger.error("Base no disponible request=%s", getattr(request.state,"request_id",""))
        return JSONResponse({"detail": "No se pudo conectar con PostgreSQL. Revisa la configuración local del backend."}, status_code=503)

    @application.exception_handler(FileNotFoundError)
    async def missing_evidence(request: Request, error):
        logger.error("Archivo ausente request=%s", getattr(request.state,"request_id",""))
        return JSONResponse({"detail": "No se encontró un archivo de evidencia. Revisa el almacenamiento del servidor."}, status_code=409)

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, error):
        logger.exception("Error no controlado request=%s", getattr(request.state,"request_id",""))
        return JSONResponse({"detail": "Error interno. Consulta el registro del servidor con el identificador de solicitud."}, status_code=500)

    from app.api.profile import router as profile_router
    application.include_router(profile_router)
    application.include_router(router)
    dist = Path(__file__).resolve().parents[2] / "dist"
    if dist.is_dir():
        application.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return application


app = create_app()
