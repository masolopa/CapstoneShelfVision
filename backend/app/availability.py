"""Cálculo de disponibilidad sobre el área evaluable. Función pura, sin imagen.

evaluable = ocupada + vacía
disponibilidad = ocupada / evaluable * 100
espacio_vacío  = vacía   / evaluable * 100
Excluida, estructural y desconocida NO entran en el denominador.
Si evaluable == 0 se devuelve estado "no_evaluable" (nunca se divide entre cero).
"""
from dataclasses import dataclass

DEFAULT_THRESHOLD = 30.0
ROUND = 2
_TOL = 1e-6


class AvailabilityError(ValueError):
    pass


@dataclass(frozen=True)
class AreaBreakdown:
    occupied: float
    empty: float
    excluded: float = 0.0
    structural: float = 0.0
    unknown: float = 0.0
    total: float | None = None   # área total de la ROI, si se conoce


@dataclass(frozen=True)
class AvailabilityResult:
    status: str                  # "evaluable" | "no_evaluable"
    availability_pct: float | None
    empty_pct: float | None
    evaluable_area: float
    unknown_area: float
    structural_area: float
    excluded_area: float
    alert: bool
    criticality: str
    reason: str


def validate(areas: AreaBreakdown, threshold: float) -> None:
    fields = {"occupied": areas.occupied, "empty": areas.empty, "excluded": areas.excluded,
              "structural": areas.structural, "unknown": areas.unknown}
    for name, v in fields.items():
        if v < 0:
            raise AvailabilityError(f"El área '{name}' no puede ser negativa")
    if not 0 < threshold < 100:
        raise AvailabilityError("El umbral debe estar entre 0 y 100 (exclusivo)")
    if areas.total is not None:
        if areas.total <= 0:
            raise AvailabilityError("El área total debe ser mayor que cero")
        if sum(fields.values()) > areas.total * (1 + _TOL) + _TOL:
            raise AvailabilityError("La suma de categorías supera el área total (conteo doble o error)")


def compute_availability(areas: AreaBreakdown, threshold: float = DEFAULT_THRESHOLD, low_threshold: float | None = None) -> AvailabilityResult:
    validate(areas, threshold)
    if low_threshold is not None and not threshold < low_threshold <= 100:
        raise AvailabilityError('Los umbrales deben cumplir 0 < crítico < bajo <= 100')
    evaluable = areas.occupied + areas.empty
    base = dict(unknown_area=areas.unknown, structural_area=areas.structural, excluded_area=areas.excluded)
    if evaluable <= 0:
        return AvailabilityResult("no_evaluable", None, None, 0.0, alert=False, criticality="no_evaluable",
                                  reason="Área evaluable cero: no hay superficie analizable.", **base)

    availability = round(areas.occupied / evaluable * 100.0, ROUND)
    empty = round(100.0 - availability, ROUND)   # garantiza suma 100 tras redondeo
    if not (0.0 <= availability <= 100.0):
        raise AvailabilityError("Porcentaje fuera de rango 0-100")

    alert = availability <= threshold
    if low_threshold is not None:
        criticality = 'critica' if alert else ('baja' if availability < low_threshold else 'aceptable')
    elif availability <= threshold / 2:
        criticality = "critica"
    elif alert:
        criticality = "baja"
    else:
        criticality = "aceptable"
    reason = (f"Disponibilidad {availability}% <= umbral {threshold}%" if alert
              else f"Disponibilidad {availability}% > umbral {threshold}%")
    if areas.unknown > 0:
        reason += f". Hay {round(areas.unknown, 1)} px desconocidos que no se cuentan."
    return AvailabilityResult("evaluable", availability, empty, round(evaluable, ROUND), alert=alert,
                              criticality=criticality, reason=reason, **base)
