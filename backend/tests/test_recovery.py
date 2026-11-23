from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.api.schemas import EmailModel, UserCreate, ResetPassword
from app.services.recovery import send_recovery, request_recovery, reset_password, MESSAGE
from app.core.security import token_hash


def test_email_validation_and_password_spaces():
    assert EmailModel(email=" A@EXAMPLE.COM ").email == "a@example.com"
    for email in ("bad", "a@b", "a\n@b.cl", ""):
        with pytest.raises(ValidationError):
            EmailModel(email=email)
    assert UserCreate(name="Test", password="0123456789", role="reponedor").email is None
    assert ResetPassword(token="x"*43, password=" 0123456789 ").password == " 0123456789 "


def test_smtp_tls_message_contains_id_and_fragment_link():
    settings = SimpleNamespace(smtp_security="starttls", smtp_host="smtp.example.com", smtp_port=587,
        smtp_user="sender", smtp_password="secret", smtp_from="sender@example.com", public_url="http://localhost:8011")
    with patch("app.services.recovery.smtplib.SMTP") as factory:
        send_recovery(settings, "worker@example.com", "USR-123", "test-token")
        smtp = factory.return_value.__enter__.return_value
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("sender", "secret")
        message = smtp.send_message.call_args.args[0]
        assert "USR-123" in message.get_content()
        assert "/#recuperar=test-token" in message.get_content()


class FakeDB:
    def __init__(self, rows):
        self.conn = MagicMock()
        self.conn.execute.side_effect = [SimpleNamespace(fetchone=lambda row=row: row) for row in rows]
    @contextmanager
    def connection(self):
        yield self.conn


def test_unknown_email_generic_response_and_no_send():
    db = FakeDB([None])
    with patch("app.services.recovery.send_recovery") as send:
        assert request_recovery(db, SimpleNamespace(smtp_host="smtp", smtp_from="a@b.cl"), "a@b.cl") == {"message": MESSAGE}
        send.assert_not_called()


def test_reset_invalid_or_expired_token_never_updates_password():
    for rows in ([None], [{"usuario_id": 1}, {"id": 1, "email": "a@b.cl"}, None]):
        db = FakeDB(rows)
        with pytest.raises(HTTPException) as error:
            reset_password(db, "x"*43, "NewPassword123")
        assert error.value.status_code == 400
        assert not any("UPDATE usuarios" in call.args[0] for call in db.conn.execute.call_args_list)


def test_reset_consumes_token_revokes_sessions_and_audits():
    db = FakeDB([{"usuario_id": 1}, {"id": 1, "email": "a@b.cl"}, {"usuario_id": 1}, None, None, None, None])
    reset_password(db, "x"*43, "NewPassword123")
    calls = db.conn.execute.call_args_list
    assert calls[0].args[1] == (token_hash("x"*43),)
    assert "expira_en>current_timestamp" in calls[2].args[0]
    assert calls[3].args[1][0].startswith("$argon2")
    assert "DELETE FROM sesiones" in calls[4].args[0]
    assert "DELETE FROM recuperaciones_acceso" in calls[5].args[0]
    assert "INSERT INTO eventos_auditoria" in calls[6].args[0]
