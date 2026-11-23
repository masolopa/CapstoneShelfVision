import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(StrictModel):
    username: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    # No normalizar espacios de una contraseña.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


def normalize_email(value):
    if value is None or not value.strip():
        return None
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValueError("Indica un correo electrónico válido.")
    return value


class EmailModel(StrictModel):
    email: str

    @model_validator(mode="after")
    def valid_email(self):
        self.email = normalize_email(self.email)
        if not self.email:
            raise ValueError("Indica tu correo electrónico.")
        return self


class ResetPassword(StrictModel):
    token: str = Field(min_length=32, max_length=128)
    password: str = Field(min_length=10, max_length=256)
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class UserCreate(StrictModel):
    email: str | None = None

    @model_validator(mode="after")
    def valid_email(self):
        self.email = normalize_email(self.email)
        return self

    name: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=10, max_length=256)
    role: Literal["admin_local", "supervisor", "reponedor"]

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class UserUpdate(StrictModel):
    email: str | None = None

    @model_validator(mode="after")
    def valid_email(self):
        self.email = normalize_email(self.email)
        return self

    role: Literal["admin_local", "supervisor", "reponedor"]
    active: bool


class SettingsUpdate(StrictModel):
    threshold: int | None = Field(None, ge=1, le=99)
    low_threshold: int | None = Field(None, ge=2, le=100)
    max_upload_mb: float | None = Field(None, gt=0, le=50)
    min_side_px: int | None = Field(None, ge=50, le=10000)


class MetadataUpdate(StrictModel):
    pasillo: str = Field(min_length=1, max_length=50)
    reference: str = Field(max_length=100)
    observations: str = Field(max_length=500)


class GroupedReports(StrictModel):
    ids: list[int] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def positive(self):
        if any(i < 1 for i in self.ids):
            raise ValueError("Los identificadores deben ser positivos")
        return self


class AlertUpdate(StrictModel):
    estado: Literal["en_atencion", "atendida", "descartada"]
    motivo: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def discard_reason_required(self):
        if self.estado == "descartada" and (not self.motivo or len(self.motivo) < 3):
            raise ValueError("Indica un motivo de al menos 3 caracteres para No procede.")
        if self.estado != "descartada" and self.motivo is not None:
            raise ValueError("El motivo de descarte solo corresponde a No procede.")
        return self


class ReviewCreate(StrictModel):
    decision: Literal["confirmado", "corregido", "descartado"]
    correccion: dict = Field(default_factory=dict)
    comentario: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def correction_required(self):
        if self.decision == "corregido" and not self.correccion:
            raise ValueError("Especifica la corrección")
        return self


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: int
    status: Literal["evaluable", "no_evaluable"]
    availability_pct: float | None
    empty_pct: float | None
    criticality: str
    threshold: float
    low_threshold: float
    filename: str
    pasillo: str
    created_at: str
    overlay_jpg_b64: str
