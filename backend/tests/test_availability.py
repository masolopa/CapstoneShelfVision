import pytest
from app.availability import AreaBreakdown, compute_availability, AvailabilityError

def A(o, e, x=0, s=0):
    return AreaBreakdown(occupied=o, empty=e, excluded=x, structural=s)

def test_todo_ocupado():
    r = compute_availability(A(100, 0))
    assert r.availability_pct == 100 and r.empty_pct == 0 and not r.alert

def test_todo_vacio():
    r = compute_availability(A(0, 100))
    assert r.availability_pct == 0 and r.empty_pct == 100 and r.alert

def test_50_por_ciento():
    r = compute_availability(A(50, 50))
    assert r.availability_pct == 50 and r.empty_pct == 50 and not r.alert

def test_30_exacto_alerta():
    assert compute_availability(A(30, 70)).alert is True

def test_29_alerta():
    r = compute_availability(A(29, 71))
    assert r.alert and r.criticality in ("baja", "critica")

def test_excluidas_no_suman_al_denominador():
    r = compute_availability(A(50, 50, x=200, s=100))
    assert r.availability_pct == 50 and r.evaluable_area == 100

def test_disponibilidad_mas_vacio_es_100():
    r = compute_availability(A(37, 63, x=10, s=5))
    assert round(r.availability_pct + r.empty_pct, 2) == 100

def test_division_por_cero_da_no_evaluable():
    r = compute_availability(A(0, 0, x=50))
    assert r.status == "no_evaluable" and r.availability_pct is None and not r.alert

def test_valores_negativos():
    with pytest.raises(AvailabilityError):
        compute_availability(A(-1, 10))

def test_umbral_invalido():
    with pytest.raises(AvailabilityError):
        compute_availability(A(10, 10), threshold=100)

def test_desconocido_no_cuenta_ni_como_vacio_ni_como_ocupado():
    r = compute_availability(AreaBreakdown(occupied=50, empty=50, unknown=400))
    assert r.availability_pct == 50 and r.empty_pct == 50 and r.unknown_area == 400

def test_estructural_no_entra_en_denominador():
    r = compute_availability(AreaBreakdown(occupied=20, empty=80, structural=300))
    assert r.availability_pct == 20 and r.evaluable_area == 100

def test_suma_supera_total():
    with pytest.raises(AvailabilityError):
        compute_availability(AreaBreakdown(occupied=60, empty=60, total=100))

def test_suma_igual_total_ok():
    r = compute_availability(AreaBreakdown(occupied=40, empty=30, excluded=20, structural=10, total=100))
    assert r.availability_pct == 57.14 and round(r.availability_pct + r.empty_pct, 2) == 100

def test_negativo_desconocido():
    with pytest.raises(AvailabilityError):
        compute_availability(AreaBreakdown(occupied=1, empty=1, unknown=-3))

@pytest.mark.parametrize("occ,emp", [(1, 2), (7, 3), (333, 667), (1, 999999)])
def test_redondeo_suma_100(occ, emp):
    r = compute_availability(AreaBreakdown(occupied=occ, empty=emp))
    assert round(r.availability_pct + r.empty_pct, 2) == 100
