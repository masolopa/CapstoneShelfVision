"""Historial de prueba preservado: solo lectura y separado de la operación nueva."""
import base64
import json
from fastapi import HTTPException


class HistoricalArchive:
    def __init__(self, storage):
        self.storage = storage
        self._stamp = None
        self._rows = []

    def records(self, user):
        # Este respaldo procede exclusivamente del local piloto.
        if user["local_codigo"] != "DEMO-RM-MAIPU":
            return []
        path = self.storage.resolve("historico/indice.json")
        if not path.is_file():
            return []
        stamp = path.stat().st_mtime_ns
        if stamp != self._stamp:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._rows = data["analyses"]
            self._stamp = stamp
        return self._rows

    def summaries(self, user):
        return [{"id": -r["legacy_id"], "created_at": r["created_at"], "filename": r["filename"],
                 "reference": r["result"].get("reference", ""), "pasillo": None,
                 "availability_pct": r["availability_pct"], "empty_pct": r["empty_pct"],
                 "alert": int(bool(r["alert"])), "criticality": r["criticality"],
                 "origin": "historical_test", "legacy_id": r["legacy_id"]} for r in self.records(user)]

    def report_data(self, user, legacy_id):
        row = next((r for r in self.records(user) if r["legacy_id"] == legacy_id), None)
        if not row:
            raise HTTPException(404, "Registro histórico no encontrado.")
        result = {**row["result"], "id": f"H-{legacy_id}", "filename": row["filename"],
                  "created_at": row["created_at"], "pasillo": "No registrado (histórico de prueba)",
                  "observations": "Histórico de prueba importado. Autor y versión exacta del modelo no registrados. "
                    + ("Fotografía original no disponible. " if not row.get("original_uri") else "")
                    + ("Segundo umbral no registrado. " if row["result"].get("low_threshold") is None else "")
                    + row["result"].get("observations", ""),
                  "overlay_jpg_b64": base64.b64encode(self.storage.read(row["overlay_uri"])).decode()}
        return result
