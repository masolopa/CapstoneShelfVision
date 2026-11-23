import io
import json
from pathlib import Path
import pytest
import equipo


def test_preparation_preserves_broken_environment_instead_of_deleting(tmp_path, monkeypatch):
    monkeypatch.setattr(equipo, "ROOT", tmp_path)
    folder = tmp_path / ".venv"
    folder.mkdir()
    (folder / "conservar.txt").write_text("referencia")
    monkeypatch.setattr(equipo, "environment_ok", lambda *args: False)
    commands = []
    monkeypatch.setattr(equipo, "run", lambda command: commands.append(command))
    assert equipo.prepare_environment(".venv", ("fastapi",)) is True
    assert len(list((tmp_path / "backups/entornos").glob("*/conservar.txt"))) == 1
    assert commands[0][1:3] == ["-m", "venv"]


def test_preparation_reuses_valid_environment_without_installing(monkeypatch):
    monkeypatch.setattr(equipo, "environment_ok", lambda *args: True)
    monkeypatch.setattr(equipo, "run", lambda *args: pytest.fail("No instalar sobre un entorno válido"))
    assert equipo.prepare_environment(".venv", ("fastapi",)) is False


def test_start_reuses_current_server_without_starting_another(monkeypatch):
    monkeypatch.setattr(equipo, "preflight", lambda: None)
    monkeypatch.setattr(equipo.urllib.request, "urlopen", lambda *args, **kwargs: io.BytesIO(json.dumps({"service": "regova", "version": "1.1.0"}).encode()))
    opened = []
    monkeypatch.setattr(equipo.webbrowser, "open", opened.append)
    monkeypatch.setattr(equipo.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("No duplicar servidor"))
    equipo.start()
    assert opened == [equipo.URL]


def test_start_detects_old_server_without_killing_it(monkeypatch):
    monkeypatch.setattr(equipo, "preflight", lambda: None)
    monkeypatch.setattr(equipo.urllib.request, "urlopen", lambda *args, **kwargs: io.BytesIO(json.dumps({"service": "regova", "version": "1.0.0"}).encode()))
    with pytest.raises(RuntimeError, match="versión anterior"):
        equipo.start()
