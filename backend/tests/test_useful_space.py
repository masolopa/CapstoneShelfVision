import cv2
import numpy as np
from app.vision.useful_space import _placements, _local_placements, apply_useful_space
from app.vision.masks import Category
from app.services.vision import process_image
from app.vision import yolo_detector


def test_detected_empty_surface_uses_lower_shelves_and_respects_masks():
    from app.vision.useful_space import detected_empty_surface

    labels = np.full((8, 8), Category.EMPTY, np.int8)
    labels[0, :] = Category.OUTSIDE
    labels[4, :] = Category.STRUCTURAL
    labels[5, 0] = Category.EXCLUDED
    labels[5, 1] = Category.OCCUPIED

    result = detected_empty_surface(labels, [[-1, 4, 4, 8]])

    assert result[6, 2] == Category.EMPTY
    assert result[2, 2] == result[6, 5] == Category.UNKNOWN
    assert result[0, 0] == Category.OUTSIDE
    assert result[4, 2] == Category.STRUCTURAL
    assert result[5, 0] == Category.EXCLUDED
    assert result[5, 1] == Category.OCCUPIED
    assert not np.any(detected_empty_surface(labels, []) == Category.EMPTY)


def test_slivers_are_not_a_useful_front():
    free = np.zeros((60, 100), bool)
    free[:, 20:29] = True
    free[:, 60:69] = True
    assert _placements(free, 20, 50) == []


def test_width_alone_is_not_enough():
    assert _placements(np.ones((30, 100), bool), 20, 50) == []


def test_fits_exactly_and_counts_without_overlap():
    places = _placements(np.ones((50, 60), bool), 20, 50)
    assert len(places) == 3
    occupied = np.zeros((50, 60), bool)
    for a, b, c, d in places:
        assert not occupied[b:d, a:c].any()
        occupied[b:d, a:c] = True


def test_vertical_room_does_not_add_fronts():
    free = np.ones((100, 60), bool)
    assert _placements(free, 20, 50) == [
        [0, 50, 20, 100], [20, 50, 40, 100], [40, 50, 60, 100],
    ]


def test_real_gap_above_product_is_kept():
    products = [
        {'fila': 1, 'bbox': [0, 50, 20, 100]},
        {'fila': 1, 'bbox': [20, 0, 40, 50]},
    ]
    row = {'indice': 1, 'frentes_libres': 2, 'frentes_totales': 4,
           'frentes_ocupados': 2, 'y_inicio': 0, 'y_fin': 100}
    result = {'productos': products, 'filas': [row], 'vacios': [], 'huecos': [],
              'resumen': {'frentes_libres': 2, 'frentes_totales': 4, 'frentes_ocupados': 2}}
    labels = np.full((100, 60), Category.EMPTY, np.int8)
    labels[50:, :20] = Category.OCCUPIED
    labels[:50, 20:40] = Category.OCCUPIED

    apply_useful_space(result, labels, 30)

    assert row['frentes_libres'] == 3
    assert [0, 0, 20, 50] in [h['bbox'] for h in result['huecos']]


def test_polygon_and_structures_cannot_be_crossed():
    free = np.ones((50, 60), bool)
    free[:, 25:35] = False
    places = _placements(free, 30, 50)
    assert places == []


def test_disconnected_pixels_do_not_make_a_slot():
    free = np.indices((80, 80)).sum(axis=0) % 2 == 0
    assert _placements(free, 10, 10) == []


def test_mixed_row_never_uses_small_boxes_in_bottle_sector():
    tall = [[x, 70, x + 20, 170] for x in (10, 40, 70)]
    small = [[x, y, x + 20, y + 20] for x in (180, 210, 240)
             for y in (90, 110, 130, 150)]
    boxes = np.array(tall + small, dtype=float)
    free = np.ones((170, 280), bool)
    for a, b, c, d in boxes.astype(int):
        free[b:d, a:c] = False
    placements, refs, _ = _local_placements(free, boxes)
    assert placements
    # El aire sobre las botellas no admite otra botella de 100px de altura.
    assert not any(a < 90 and d - b < 100 for a, b, c, d in placements)
    assert any(a >= 180 and d - b == 20 for a, b, c, d in placements)
    assert sorted(r['columnas_referencia'] for r in refs) == [3, 3]
    for a, b, c, d in placements:
        assert free[b:d, a:c].all()


def test_ambiguous_sizes_do_not_force_a_smaller_reference():
    boxes = np.array([[10, 50, 30, 150], [110, 130, 130, 150.]])
    placements, _, ambiguous = _local_placements(np.ones((150, 160), bool), boxes)
    assert placements == []
    assert ambiguous == 160


def test_single_tall_column_is_not_overruled_by_small_neighbours():
    boxes = np.array([[10, 70, 30, 170], [100, 150, 120, 170], [130, 150, 150, 170.]])
    placements, _, _ = _local_placements(np.ones((170, 180), bool), boxes)
    assert not any(a < 30 and d - b < 100 for a, b, c, d in placements)


def test_row_dimensions_are_local():
    products = [{'fila': 1, 'bbox': [0, 0, 20, 40]},
                {'fila': 2, 'bbox': [0, 50, 40, 90]}]
    rows = [{'indice': i + 1, 'frentes_libres': 4, 'frentes_totales': 5,
             'frentes_ocupados': 1, 'y_inicio': i * 50, 'y_fin': (i+1)*50}
            for i in range(2)]
    result = {'productos': products, 'filas': rows, 'vacios': [], 'huecos': [],
              'resumen': {'frentes_libres': 8, 'frentes_totales': 10, 'frentes_ocupados': 2}}
    labels = np.full((100, 100), Category.EMPTY, np.int8)
    labels[:40, :20] = Category.OCCUPIED
    labels[50:90, :40] = Category.OCCUPIED
    apply_useful_space(result, labels, 30, 70)
    assert [r['frentes_libres'] for r in rows] == [4, 1]
    assert result['resumen']['frentes_libres'] == 5
    assert result['espacio_util']['referencias'][1]['ancho_px'] == 40


def test_missing_reference_is_explicit():
    result = {'productos': [], 'filas': [], 'vacios': [], 'huecos': []}
    apply_useful_space(result, np.ones((10, 10), np.int8), 30)
    assert result['espacio_util']['evaluado'] is False


def test_experiment_does_not_change_surface_or_product_count(monkeypatch):
    def detect(img, conf=.25):
        return {'productos': (np.array([[20, 40, 60, 240], [70, 40, 110, 240.]]), np.array([.9, .9])),
                'vacios': (np.array([[60, 40, 70, 240.]]), np.array([.8]))}
    monkeypatch.setattr(yolo_detector, 'detect_all', detect)
    data = cv2.imencode('.png', np.full((300, 400, 3), 100, np.uint8))[1].tobytes()
    opts = {'method': 'yolo', 'roi': [[.05, .1], [.28, .1], [.28, .85], [.05, .85]], 'filas': 1}
    settings = {'threshold': 30, 'low_threshold': 70, 'min_side_px': 200}
    monkeypatch.setenv('REGOVA_SURFACE_PILOT', '0')
    monkeypatch.setenv('REGOVA_USEFUL_SPACE', '0')
    before, _ = process_image(data, opts, settings)
    monkeypatch.setenv('REGOVA_USEFUL_SPACE', '1')
    after, _ = process_image(data, opts, settings)
    assert before['availability_pct'] == after['surface_availability_pct']
    assert after['availability_pct'] == 100
    assert after['empty_pct'] == 0
    assert after['availability_basis'] == 'useful_fronts'
    assert after['useful_free_fronts'] == 0
    assert not after['alert']
    assert before['conteo']['resumen']['productos'] == after['conteo']['resumen']['productos'] == 2
    assert after['conteo']['resumen']['frentes_libres'] == 0
    assert after['conteo']['vacios'] == after['conteo']['huecos'] == []
    assert after['conteo']['vacios_visuales']


def test_surface_pilot_alerts_for_review_without_reclassifying_unknown(monkeypatch):
    def detect(img, conf=.25):
        return {'productos': (np.array([[20, 20, 90, 260.]]), np.array([.9])),
                'vacios': (np.empty((0, 4)), np.empty(0))}

    monkeypatch.setattr(yolo_detector, 'detect_all', detect)
    monkeypatch.delenv('REGOVA_SURFACE_PILOT', raising=False)
    data = cv2.imencode('.png', np.full((300, 400, 3), 100, np.uint8))[1].tobytes()
    opts = {'method': 'yolo', 'roi': [[0, 0], [1, 0], [1, 1], [0, 1]], 'filas': 1}
    settings = {'threshold': 30, 'low_threshold': 70, 'min_side_px': 200}
    result, _ = process_image(data, opts, settings)

    assert result['alert'] and result['alert_basis'] == 'product_coverage_review'
    assert result['reason'].startswith('Revisar góndola')
    assert result['requires_review']
    assert result['availability_pct'] > 30 >= result['alert_product_coverage_pct']
    assert result['areas_px']['unknown'] > 0
    areas = result['areas_px']
    assert result['alert_product_coverage_pct'] == round(
        100 * areas['occupied'] / (areas['occupied'] + areas['empty'] + areas['unknown']), 2
    )
    result, _ = process_image(data, opts, {**settings, 'threshold': 10})
    assert not result['alert']


def test_useful_capacity_drives_percentage_alert_and_pdf(monkeypatch):
    def detect(img, conf=.25):
        return {'productos': (np.array([[20, 40, 60, 240.]]), np.array([.9])),
                'vacios': (np.empty((0, 4)), np.empty(0))}
    monkeypatch.setattr(yolo_detector, 'detect_all', detect)
    monkeypatch.setenv('REGOVA_SURFACE_PILOT', '0')
    monkeypatch.setenv('REGOVA_USEFUL_SPACE', '1')
    data = cv2.imencode('.png', np.full((300, 400, 3), 100, np.uint8))[1].tobytes()
    settings = {'threshold': 30, 'low_threshold': 70, 'min_side_px': 200}
    result, _ = process_image(data, {'method': 'yolo', 'roi': [[0, 0], [1, 0], [1, 1], [0, 1]], 'filas': 1}, settings)
    occupied, free = result['useful_occupied_fronts'], result['useful_free_fronts']
    assert free > 0
    assert result['availability_pct'] == round(100 * occupied / (occupied + free), 2)
    assert result['empty_pct'] == round(100 - result['availability_pct'], 2)
    assert result['alert'] and result['criticality'] == 'critica'
    assert len(result['conteo']['vacios']) + len(result['conteo']['huecos']) == free
    from app.report import build_pdf
    result.update(id=0, filename='prueba.png')
    assert build_pdf(result).startswith(b'%PDF')
