"""Pruebas reales PostgreSQL + HTTP. Nunca se ejecutan sobre REGOVA_BD."""
import hashlib
import json
import os
from pathlib import Path

import cv2
import numpy as np
import psycopg
import pytest
from fastapi.testclient import TestClient

from app.bootstrap import seed_local
from app.core.config import Settings
from app.core.database import Database
from app.core.security import COOKIE_NAME
from app.main import create_app
from app.services.storage import LocalStorage

PASSWORD = "PruebaApi-123456"
HEADERS = {"X-Regova-Request": "1"}


@pytest.fixture
def system(tmp_path):
    dsn = os.getenv("REGOVA_TEST_DSN")
    if not dsn:
        pytest.skip("Definir REGOVA_TEST_DSN para una base desechable terminada en _TEST")
    with psycopg.connect(dsn) as c:
        name = c.execute("SELECT current_database()").fetchone()[0]
        if not name.endswith("_TEST"):
            pytest.fail("Las pruebas solo pueden usar una base cuyo nombre termine en _TEST")
        # Instancia de prueba explícitamente dedicada; jamás usar REGOVA_BD.
        c.execute("TRUNCATE regova.sesiones,regova.eventos_auditoria,regova.alertas,regova.revisiones,regova.archivos_analisis,regova.resultados,regova.analisis,regova.imagenes,regova.configuraciones_vigentes,regova.configuraciones_analisis,regova.modelos_vision,regova.gondolas,regova.usuarios,regova.locales RESTART IDENTITY CASCADE")
    settings = Settings(dsn, tmp_path / "storage")
    db, storage = Database(dsn), LocalStorage(settings.storage_root)
    seed_local(db, storage, PASSWORD)
    app = create_app(settings)
    with TestClient(app) as client:
        yield app, client


def signin(client, username="ADM-001", password=PASSWORD):
    r = client.post("/api/auth/login", json={"username": username, "password": password}, headers=HEADERS)
    assert r.status_code == 200, r.text
    return r


def add_user(client, role):
    r = client.post("/api/users", json={"name": role, "password": PASSWORD, "role": role}, headers=HEADERS)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def picture():
    img = np.full((300, 400, 3), 230, np.uint8)
    img[:, :200] = np.random.default_rng(1).integers(0, 255, (300, 200, 3), dtype=np.uint8)
    return cv2.imencode(".png", img)[1].tobytes()


def analyze(client, pasillo, **opts):
    return client.post("/api/analyze", data={"pasillo": pasillo, "method": "heuristic", "capture_date": "2026-11-14T12:00", **opts},
                       files={"file": ("captura.png", picture(), "image/png")}, headers=HEADERS)


def test_auth_cookie_logout_and_no_plaintext(system):
    app, client = system
    assert client.get("/api/history").status_code == 401
    assert client.post("/api/auth/login", json={"username": "ADM-001", "password": PASSWORD}).status_code == 403
    assert client.post("/api/auth/login", json={"username": "ADM-001", "password": "incorrecta"}, headers=HEADERS).status_code == 401
    r = signin(client)
    assert "HttpOnly" in r.headers["set-cookie"]
    assert "password" not in r.json()
    assert client.get("/api/auth/me").json()["id"] == "ADM-001"
    with app.state.db.connection() as c:
        assert c.execute("SELECT password_hash FROM usuarios").fetchone()["password_hash"].startswith("$argon2")
        stored = c.execute("SELECT token_hash FROM sesiones").fetchone()["token_hash"]
        assert stored == hashlib.sha256(client.cookies[COOKIE_NAME].encode()).hexdigest()
    assert client.post("/api/auth/logout", headers=HEADERS).status_code == 204
    assert client.get("/api/history").status_code == 401


def test_reponedor_cannot_analyze_change_settings_or_users(system):
    _, client = system
    signin(client)
    code, g = add_user(client, "reponedor"), "P-04"
    signin(client, code)
    assert analyze(client, g).status_code == 403
    assert client.put("/api/settings", json={"threshold": 40}, headers=HEADERS).status_code == 403
    assert client.get("/api/users").status_code == 403
    assert client.get("/api/alerts").status_code == 200


def test_supervisor_analysis_persists_raw_original_and_real_author(system):
    app, client = system
    signin(client)
    code, g = add_user(client, "supervisor"), "P-04"
    signin(client, code)
    response = analyze(client, g, reference="Reposición")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["author"] == code
    assert result["pasillo"] == g
    assert 0 <= result["availability_pct"] <= 100
    with app.state.db.connection() as c:
        row = c.execute("SELECT i.uri,a.estado,r.detalle FROM analisis a JOIN imagenes i ON i.id=a.imagen_id JOIN resultados r ON r.analisis_id=a.id").fetchone()
        assert app.state.storage.read(row["uri"]) == picture()
        assert row["estado"] == "exitoso"
        assert "original_jpg_b64" not in row["detalle"]
        assert "overlay_jpg_b64" not in row["detalle"]
    assert client.get(f"/api/analyze/{result['id']}").status_code == 200
    assert client.get(f"/api/analyze/{result['id']}/report.pdf").content.startswith(b"%PDF")
    assert client.get("/api/history").json()[0]["reference"] == "Reposición"
    assert client.get("/api/history").json()[0]["pasillo"] == g
    with app.state.db.connection() as c:
        assert c.execute("SELECT count(*) AS n FROM gondolas").fetchone()["n"] == 0
    assert client.get("/api/gondolas").status_code == 404
    assert client.get("/api/metrics").json()["total_analyses"] == 1
    assert client.post("/api/reports/grouped.pdf", json={"ids": [result["id"]]}, headers=HEADERS).content.startswith(b"%PDF")


def test_threshold_version_and_original_result_immutable(system):
    app, client = system
    signin(client)
    g = "P-04"
    response = analyze(client, g)
    assert response.status_code == 200, response.text
    rid = response.json()["id"]
    assert client.put("/api/settings", json={"threshold": 40, "low_threshold": 80}, headers=HEADERS).status_code == 200
    old = client.get(f"/api/analyze/{rid}").json()
    assert old["threshold"] == 30 and old["low_threshold"] == 70
    with app.state.db.connection() as c:
        assert c.execute("SELECT count(*) AS n FROM configuraciones_analisis").fetchone()["n"] == 2
    assert client.put("/api/settings", json={"threshold": 90, "low_threshold": 80}, headers=HEADERS).status_code == 422


def test_expired_suspended_session_and_protected_admin(system):
    app, client = system
    signin(client)
    code = add_user(client, "supervisor")
    assert client.delete("/api/users/ADM-001", headers=HEADERS).status_code == 403
    signin(client, code)
    with app.state.db.connection() as c:
        c.execute("UPDATE usuarios SET activo=false WHERE codigo=%s", (code,))
    assert client.get("/api/auth/me").status_code == 401
    signin(client)
    # La fecha de expiración sigue siendo posterior a la creación.
    with app.state.db.connection() as c:
        c.execute("UPDATE sesiones SET creada_en=current_timestamp-interval '2 days',expira_en=current_timestamp-interval '1 day'")
    assert client.get("/api/auth/me").status_code == 401


def test_invalid_image_geometry_origin_and_pasillo(system):
    _, client = system
    signin(client)
    g = "P-04"
    assert analyze(client, g, roi='[[0,0],[2,0],[1,1]]').status_code == 422
    assert analyze(client, g, roi='[[0,0],[1,1],[0,1],[1,0]]').status_code == 422
    assert analyze(client, "   ").status_code == 422
    assert client.put("/api/settings", json={"threshold": 35}, headers={**HEADERS, "Origin": "https://untrusted.example"}).status_code == 403
    r = client.post("/api/analyze", data={"pasillo": g, "method": "heuristic"}, files={"file": ("x.png", b"incorrecta", "image/png")}, headers=HEADERS)
    assert r.status_code == 422


def test_local_isolation(system):
    app, client = system
    signin(client)
    g = "P-04"
    result = analyze(client, g)
    assert result.status_code == 200, result.text
    with app.state.db.connection() as c:
        local = c.execute("INSERT INTO locales(codigo,nombre) VALUES('OTRO','Otro') RETURNING id").fetchone()["id"]
        from app.core.security import passwords
        c.execute("INSERT INTO usuarios(local_id,codigo,nombre,password_hash,rol) VALUES(%s,'OTRO-SUP','Otro',%s,'supervisor')", (local, passwords.hash(PASSWORD)))
    signin(client, "OTRO-SUP")
    assert client.get("/api/history").json() == []
    assert client.get(f"/api/analyze/{result.json()['id']}").status_code == 404
    assert analyze(client, g).status_code == 409  # No hay configuración en el otro local.


def test_failure_keeps_original_and_failed_state(system, monkeypatch):
    app, client = system
    signin(client)
    g = "P-04"
    def fail(*args, **kwargs):
        raise RuntimeError("fallo de prueba")
    monkeypatch.setattr("app.services.analysis.process_image", fail)
    assert analyze(client, g).status_code == 500
    with app.state.db.connection() as c:
        row = c.execute("SELECT estado,error_detalle FROM analisis").fetchone()
        assert row["estado"] == "fallido" and row["error_detalle"] == "RuntimeError"
        assert c.execute("SELECT count(*) AS n FROM resultados").fetchone()["n"] == 0
        key = c.execute("SELECT uri FROM imagenes").fetchone()["uri"]
        assert app.state.storage.read(key) == picture()


def test_alert_attendance_and_review_do_not_change_prediction(system):
    app, client = system
    signin(client)
    code = add_user(client, "reponedor")
    g = "P-04"
    assert client.put("/api/settings", json={"threshold": 98, "low_threshold": 99}, headers=HEADERS).status_code == 200
    r = analyze(client, g)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    assert client.post(f"/api/analyze/{rid}/reviews", json={"decision": "confirmado"}, headers=HEADERS).status_code == 201
    alerts = client.get("/api/alerts").json()
    assert len(alerts) == 1
    alert_id = alerts[0]["id"]
    assert client.patch(f"/api/alerts/{alert_id}", json={"estado": "atendida"}, headers=HEADERS).status_code == 403
    signin(client, code)
    assert client.patch(f"/api/alerts/{alert_id}", json={"estado": "en_atencion"}, headers=HEADERS).status_code == 204
    assert client.patch(f"/api/alerts/{alert_id}", json={"estado": "atendida"}, headers=HEADERS).status_code == 204
    assert client.patch(f"/api/alerts/{alert_id}", json={"estado": "atendida"}, headers=HEADERS).status_code == 409
    assert client.get(f"/api/analyze/{rid}").json()["availability_pct"] == r.json()["availability_pct"]


def test_storage_rejects_traversal_and_no_secret_in_api_docs(system):
    app, client = system
    for key in ("../secret", "C:/Windows/test", "originales/../../test", "originales\\test"):
        with pytest.raises(ValueError):
            app.state.storage.resolve(key)
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/ready").status_code == 200
    assert "/api/auth/login" in client.get("/api/openapi.json").json()["paths"]


def test_bootstrap_model_version_and_reexecution_preserve_account(system, tmp_path):
    app, client = system
    checkpoint = tmp_path / "fake_checkpoint.pt"
    checkpoint.write_bytes(b"modelo de prueba no ejecutable")
    seed_local(app.state.db, app.state.storage, "OtraContrasena-123", checkpoint)
    seed_local(app.state.db, app.state.storage, "OtraContrasena-123", checkpoint)
    signin(client)  # Se conserva la contraseña original, no la de la reejecución.
    with app.state.db.connection() as c:
        row = c.execute("SELECT * FROM modelos_vision WHERE metodo='yolo'").fetchone()
        assert len(row["version"]) <= 60
        assert row["sha256"] == hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        assert c.execute("SELECT count(*) AS n FROM modelos_vision WHERE metodo='yolo'").fetchone()["n"] == 1
    app.state.storage.resolve(row["artefacto_uri"]).write_bytes(b"pesos alterados")
    g = "P-04"
    assert analyze(client, g, method="yolo").status_code == 503


def test_pasillo_required_normalized_and_editable_without_catalog(system):
    app, client = system
    signin(client)
    missing = client.post("/api/analyze", data={"method": "heuristic"}, files={"file": ("x.png", picture(), "image/png")}, headers=HEADERS)
    assert missing.status_code == 422
    assert analyze(client, " ").status_code == 422
    assert analyze(client, "P" * 51).status_code == 422
    response = analyze(client, "  P-06  ")
    assert response.status_code == 200, response.text
    original = response.json()
    assert original["pasillo"] == "P-06"
    changed = client.patch(f"/api/analyze/{original['id']}", json={"pasillo": "P-07", "reference": "Snacks, lado derecho", "observations": "Corrección de ubicación"}, headers=HEADERS)
    assert changed.status_code == 200, changed.text
    assert changed.json()["pasillo"] == "P-07"
    assert changed.json()["availability_pct"] == original["availability_pct"]
    assert client.get("/api/history").json()[0]["pasillo"] == "P-07"
    with app.state.db.connection() as c:
        assert c.execute("SELECT count(*) AS n FROM gondolas").fetchone()["n"] == 0


def test_historical_dashboard_readonly_pdf_and_local_isolation(system):
    app, client = system
    signin(client)
    result = analyze(client, "P-01")
    assert result.status_code == 200, result.text
    b = result.json()
    with app.state.db.connection() as c:
        overlay = c.execute("SELECT uri FROM archivos_analisis WHERE analisis_id=%s", (b["id"],)).fetchone()["uri"]
        alerts_before = c.execute("SELECT count(*) AS n FROM alertas").fetchone()["n"]
    old_result = {k: v for k, v in b.items() if k not in ("original_jpg_b64", "overlay_jpg_b64", "low_threshold")}
    index = app.state.storage.resolve("historico/indice.json")
    index.parent.mkdir(parents=True)
    index.write_text(json.dumps({"analyses": [{"legacy_id": 1, "created_at": "2026-10-30T12:00:00+00:00",
      "filename": "historica.jpg", "availability_pct": b["availability_pct"], "empty_pct": b["empty_pct"],
      "alert": 1, "criticality": b["criticality"], "overlay_uri": overlay, "original_uri": None, "result": old_result}]}), encoding="utf-8")
    panel = client.get("/api/dashboard/history").json()
    assert len(panel) == 2
    archived = next(r for r in panel if r["origin"] == "historical_test")
    assert archived["id"] == -1 and archived["pasillo"] is None
    assert client.get("/api/dashboard/historical/1/report.pdf").content.startswith(b"%PDF")
    assert len(client.get("/api/history").json()) == 1
    with app.state.db.connection() as c:
        assert c.execute("SELECT count(*) AS n FROM analisis").fetchone()["n"] == 1
        assert c.execute("SELECT count(*) AS n FROM alertas").fetchone()["n"] == alerts_before
        local = c.execute("INSERT INTO locales(codigo,nombre) VALUES('OTRO','Otro local') RETURNING id").fetchone()["id"]
        from app.core.security import passwords
        c.execute("INSERT INTO usuarios(local_id,codigo,nombre,password_hash,rol) VALUES(%s,'EXTERNO','Otro',%s,'supervisor')", (local, passwords.hash(PASSWORD)))
    signin(client, "EXTERNO")
    assert client.get("/api/dashboard/history").json() == []
    assert client.get("/api/dashboard/historical/1/report.pdf").status_code == 404


# QA integration extension: only the explicitly configured disposable _TEST database.
def recovery_token(app, client, monkeypatch):
    from dataclasses import replace
    captured = []
    app.state.settings = replace(app.state.settings, smtp_host="smtp.test", smtp_from="qa@example.test")
    monkeypatch.setattr("app.services.recovery.send_recovery", lambda settings, email, code, token: captured.append(token))
    signin(client)
    assert client.put("/api/auth/email", json={"email":"qa@example.test","password":PASSWORD}, headers=HEADERS).status_code == 204
    response = client.post("/api/auth/recovery", json={"email":"qa@example.test"}, headers=HEADERS)
    assert response.status_code == 200 and len(captured) == 1
    return captured[0]


def test_qa_recovery_single_use_revokes_sessions_persists_hash(system, monkeypatch):
    app, client = system
    token = recovery_token(app, client, monkeypatch)
    with app.state.db.connection() as c:
        stored = c.execute("SELECT token_hash FROM recuperaciones_acceso").fetchone()["token_hash"]
        assert stored == hashlib.sha256(token.encode()).hexdigest()
    new_password = "NuevaClaveQA12345"
    assert client.post("/api/auth/reset-password", json={"token":token,"password":new_password}, headers=HEADERS).status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/reset-password", json={"token":token,"password":new_password}, headers=HEADERS).status_code == 400
    assert client.post("/api/auth/login", json={"username":"ADM-001","password":PASSWORD}, headers=HEADERS).status_code == 401
    assert signin(client,password=new_password).status_code == 200
    from app.core.security import verify_password
    with app.state.db.connection() as c:
        encoded = c.execute("SELECT password_hash FROM usuarios WHERE codigo='ADM-001'").fetchone()["password_hash"]
        assert encoded.startswith("$argon2") and verify_password(new_password,encoded)


def test_qa_recovery_expired_token_and_short_password_rejected(system, monkeypatch):
    app, client = system
    token = recovery_token(app, client, monkeypatch)
    assert client.post("/api/auth/reset-password", json={"token":token,"password":"corta"}, headers=HEADERS).status_code == 422
    with app.state.db.connection() as c:
        c.execute("UPDATE recuperaciones_acceso SET creada_en=current_timestamp-interval '2 hours', expira_en=current_timestamp-interval '1 hour'")
    assert client.post("/api/auth/reset-password", json={"token":token,"password":"NuevaClaveQA12345"}, headers=HEADERS).status_code == 400
    assert signin(client).status_code == 200


def test_qa_recovery_concurrent_token_only_one_change(system, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi import HTTPException
    from app.services.recovery import reset_password
    app, client = system
    token = recovery_token(app, client, monkeypatch)
    barrier = Barrier(2)
    def attempt(index):
        barrier.wait(timeout=10)
        try:
            reset_password(app.state.db, token, f"ConcurrenciaQA{index}12345")
            return 204
        except HTTPException as error:
            return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt,[1,2])) == [204,400]


def test_qa_two_workers_cannot_claim_same_alert(system):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi import HTTPException
    app, client = system
    signin(client)
    codes = [add_user(client,"reponedor") for _ in range(2)]
    assert client.put("/api/settings",json={"threshold":98,"low_threshold":99},headers=HEADERS).status_code == 200
    assert analyze(client,"QA-P01").status_code == 200
    alert_id = client.get("/api/alerts").json()[0]["id"]
    with app.state.db.connection() as c:
        users = [c.execute("SELECT * FROM usuarios WHERE codigo=%s",(code,)).fetchone() for code in codes]
    barrier = Barrier(2)
    def claim(user):
        barrier.wait(timeout=10)
        try:
            app.state.repo.attend_alert(user,alert_id,"en_atencion")
            return 204
        except HTTPException as error:
            return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(claim,users)) == [204,409]
    with app.state.db.connection() as c:
        assert c.execute("SELECT responsable_id FROM alertas WHERE id=%s",(alert_id,)).fetchone()["responsable_id"] in [u["id"] for u in users]


def test_qa_suspended_account_cannot_use_existing_recovery(system, monkeypatch):
    app, client = system
    token = recovery_token(app, client, monkeypatch)
    with app.state.db.connection() as c:
        c.execute("UPDATE usuarios SET activo=false WHERE codigo='ADM-001'")
    assert client.post("/api/auth/reset-password", json={"token":token,"password":"NuevaClaveQA12345"}, headers=HEADERS).status_code == 400


def test_qa_worker_cannot_edit_users_directly(system):
    _, client = system
    signin(client)
    code = add_user(client,"reponedor")
    signin(client,code)
    assert client.patch("/api/users/ADM-001",json={"role":"reponedor","active":True},headers=HEADERS).status_code == 403
    assert client.delete("/api/users/ADM-001",headers=HEADERS).status_code == 403


def test_discard_requires_reason_records_actor_and_does_not_change_prediction(system):
    app, client = system
    signin(client)
    code = add_user(client, "reponedor")
    client.put("/api/settings", json={"threshold": 98, "low_threshold": 99}, headers=HEADERS)
    prediction = analyze(client, "P-NP").json()
    alert_id = client.get("/api/alerts").json()[0]["id"]
    signin(client, code)
    for reason in (None, "   ", "x", "x" * 1001):
        payload = {"estado": "descartada", "motivo": reason}
        assert client.patch(f"/api/alerts/{alert_id}", json=payload, headers=HEADERS).status_code == 422
    reason = "Producto no apilable; no corresponde reposición."
    assert client.patch(f"/api/alerts/{alert_id}", json={"estado":"descartada","motivo":reason}, headers=HEADERS).status_code == 204
    item = client.get("/api/alerts").json()[0]
    assert item["estado"] == "descartada" and item["motivo_cierre"] == reason
    assert item["revisado_por"] == code and item["cerrada_en"]
    assert client.patch(f"/api/alerts/{alert_id}", json={"estado":"en_atencion"}, headers=HEADERS).status_code == 409
    assert client.get(f"/api/analyze/{prediction['id']}").json()["availability_pct"] == prediction["availability_pct"]


def test_supervisor_discards_another_workers_alert_but_cannot_attend(system):
    app, client = system
    signin(client)
    worker = add_user(client, "reponedor")
    other = add_user(client, "reponedor")
    supervisor = add_user(client, "supervisor")
    client.put("/api/settings", json={"threshold":98,"low_threshold":99}, headers=HEADERS)
    analyze(client, "P-NP")
    alert_id = client.get("/api/alerts").json()[0]["id"]
    signin(client, worker)
    assert client.patch(f"/api/alerts/{alert_id}",json={"estado":"en_atencion"},headers=HEADERS).status_code == 204
    signin(client, other)
    payload = {"estado":"descartada","motivo":"No es apilable"}
    assert client.patch(f"/api/alerts/{alert_id}",json=payload,headers=HEADERS).status_code == 409
    signin(client, supervisor)
    assert client.patch(f"/api/alerts/{alert_id}",json={"estado":"atendida"},headers=HEADERS).status_code == 403
    assert client.patch(f"/api/alerts/{alert_id}",json=payload,headers=HEADERS).status_code == 204
    item = client.get("/api/alerts").json()[0]
    assert item["responsable"] == worker and item["revisado_por"] == supervisor


def test_no_procede_admin_and_local_isolation(system):
    app, client = system
    signin(client)
    client.put("/api/settings", json={"threshold":98,"low_threshold":99}, headers=HEADERS)
    analyze(client, "P-NP")
    alert_id = client.get("/api/alerts").json()[0]["id"]
    from fastapi import HTTPException
    with app.state.db.connection() as c:
        user = dict(c.execute("SELECT * FROM usuarios WHERE codigo='ADM-001'").fetchone())
    user["local_id"] = -1
    with pytest.raises(HTTPException) as error:
        app.state.repo.attend_alert(user,alert_id,"descartada","No procede aquí")
    assert error.value.status_code == 404
    assert client.patch(f"/api/alerts/{alert_id}",json={"estado":"descartada","motivo":"Obstrucción en zona útil"},headers=HEADERS).status_code == 204
    assert client.get("/api/alerts").json()[0]["revisado_por"] == "ADM-001"

@pytest.mark.parametrize("role", ["administrador", "supervisor"])
def test_cu08_review_history_preserves_result_and_alerts(system, role):
    app, client = system
    signin(client)
    if role == "supervisor":
        signin(client, add_user(client, role))
    response = analyze(client, "CU08")
    assert response.status_code == 200, response.text
    original = response.json()
    rid = original["id"]
    url = f"/api/analyze/{rid}/reviews"
    alerts = client.get("/api/alerts").json()
    assert client.get(url).json() == []
    for decision in ("confirmado", "corregido", "descartado"):
        correction = {"descripcion": "Disponibilidad verificada manualmente", "availability_pct": 0} if decision == "corregido" else {}
        created = client.post(url, json={"decision": decision, "correccion": correction, "comentario": "Prueba CU08"}, headers=HEADERS)
        assert created.status_code == 201, created.text
        history = client.get(url)
        assert history.status_code == 200, history.text
        latest = history.json()[0]
        assert latest["id"] == created.json()["id"]
        assert latest["decision"] == decision
        assert latest["correccion"] == correction
        assert latest["revisor_codigo"]
        assert latest["revisor_nombre"]
        assert latest["creado_en"]
    assert len(client.get(url).json()) == 3
    assert client.get(f"/api/analyze/{rid}").json() == original
    assert client.get("/api/alerts").json() == alerts
    with app.state.db.connection() as c:
        assert c.execute("SELECT count(*) AS n FROM eventos_auditoria WHERE accion='resultado.revisar'").fetchone()["n"] == 3
    worker = None
    if role == "administrador":
        worker = add_user(client, "reponedor")
    if worker:
        signin(client, worker)
        assert client.get(url).status_code == 403
        assert client.post(url, json={"decision":"confirmado"}, headers=HEADERS).status_code == 403


def test_cu08_invalid_missing_and_other_local(system):
    app, client = system
    signin(client)
    rid = analyze(client, "CU08").json()["id"]
    url = f"/api/analyze/{rid}/reviews"
    for body in ({"decision":"otro"}, {"decision":"corregido"}, {"decision":"confirmado", "comentario":"x" * 1001}):
        assert client.post(url, json=body, headers=HEADERS).status_code == 422
    assert client.get("/api/analyze/99999/reviews").status_code == 404
    from app.core.security import passwords
    with app.state.db.connection() as c:
        local = c.execute("INSERT INTO locales(codigo,nombre) VALUES('CU08-OTRO','Otro') RETURNING id").fetchone()["id"]
        c.execute("INSERT INTO usuarios(local_id,codigo,nombre,password_hash,rol) VALUES(%s,'CU08-EXT','Externo',%s,'supervisor')", (local, passwords.hash(PASSWORD)))
    signin(client, "CU08-EXT")
    assert client.get(url).status_code == 404
    assert client.post(url, json={"decision":"confirmado"}, headers=HEADERS).status_code == 404
    signin(client)
    assert client.delete(f"/api/analyze/{rid}", headers=HEADERS).status_code == 204
    assert client.get(url).status_code == 404
    assert client.post(url, json={"decision":"confirmado"}, headers=HEADERS).status_code == 404
