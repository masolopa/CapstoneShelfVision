import numpy as np
from app.shelf_rows import analyze_rows


def _grid(rows, cols, box_w=50, box_h=60, gap_y=200, x0=100):
    """Cajas en una cuadrícula: `rows` filas con `cols[i]` productos cada una."""
    boxes = []
    for r, n in enumerate(cols):
        y = 100 + r * gap_y
        for c in range(n):
            x = x0 + c * (box_w + 10)
            boxes.append([x, y, x + box_w, y + box_h])
    return np.array(boxes, dtype=np.float64)


def _run(boxes, region=(0, 0, 1000, 800), filas=None):
    x0, y0, x1, y1 = region
    cx = (boxes[:, 0] + boxes[:, 2]) / 2
    cy = (boxes[:, 1] + boxes[:, 3]) / 2
    inside = (cx >= x0) & (cx <= x1) & (cy >= y0) & (cy <= y1)
    confs = np.full(len(boxes), 0.8)
    return analyze_rows(boxes, confs, region, inside, filas=filas, umbral=30.0)


def test_cuenta_productos_y_filas_automaticas():
    res = _run(_grid(3, [5, 3, 1]))
    assert res["resumen"]["productos"] == 9
    assert res["resumen"]["filas"] == 3
    assert [f["productos"] for f in res["filas"]] == [5, 3, 1]


def test_frentes_ocupados_y_libres_por_fila():
    res = _run(_grid(2, [4, 2]))
    fila1, fila2 = res["filas"]
    assert fila1["frentes_ocupados"] == 4
    assert fila2["frentes_ocupados"] == 2
    assert fila2["frentes_libres"] > fila1["frentes_libres"]


def test_fila_con_pocos_productos_se_marca_reponer():
    res = _run(_grid(2, [10, 1]))
    assert res["filas"][1]["estado"] == "REPONER"
    assert res["filas"][0]["estado"] == "REVISAR"  # 10 de 20 frentes, entre 30 % y 70 %
    assert res["resumen"]["filas_reponer"] == 1


def test_productos_apilados_cuentan_como_un_frente():
    boxes = np.array([[100, 100, 150, 160], [100, 170, 150, 230], [100, 240, 150, 300]], dtype=np.float64)
    res = _run(boxes)
    assert res["resumen"]["productos"] == 3
    assert len(res["filas"]) == 1
    assert res["filas"][0]["frentes_ocupados"] == 1


def test_filas_indicadas_por_el_usuario_muestran_fila_vacia():
    boxes = _grid(1, [4])  # solo la fila superior tiene productos
    res = _run(boxes, region=(0, 0, 1000, 800), filas=3)
    assert len(res["filas"]) == 3
    assert res["filas"][0]["productos"] == 4
    assert res["filas"][2]["productos"] == 0
    assert res["filas"][2]["estado"] == "REPONER"


def test_sin_productos_no_inventa_filas():
    res = _run(np.zeros((0, 4)))
    assert res["filas"] == []
    assert res["resumen"]["productos"] == 0
    assert res["resumen"]["ocupacion_pct"] is None
