import cv2
import numpy as np
import pytest

from app.vision import yolo_detector
from app.vision.baseline import analyze_image_bytes
from app.vision.regions import centers_inside, clip_spaces, polygon_pixels
from app.vision.detections_overlay import render_detections
from app.services.vision import _conteo, process_image


ROI = [[0.1, 0.1], [0.6, 0.1], [0.6, 0.9], [0.1, 0.9]]


@pytest.fixture(autouse=True)
def isolate_region_filter(monkeypatch):
    monkeypatch.setenv('REGOVA_SURFACE_PILOT', '0')
    monkeypatch.setenv('REGOVA_USEFUL_SPACE', '0')


def image_bytes():
    return cv2.imencode('.png', np.full((300, 400, 3), 100, np.uint8))[1].tobytes()


def fake_detector(img, conf=0.25):
    return {'productos': (np.array([[60, 60, 100, 110], [300, 60, 340, 110.]]), np.array([.9, .8])),
            'vacios': (np.array([[120, 150, 160, 200], [280, 150, 360, 200.]]), np.array([.8, .7]))}


@pytest.mark.parametrize('roi,expected', [(ROI, 1), (None, 2)])
def test_roi_filters_both_classes_without_disabling_full_image(monkeypatch, roi, expected):
    monkeypatch.setattr(yolo_detector, 'detect_all', fake_detector)
    img, out = analyze_image_bytes(image_bytes(), roi_polygon=roi, method='yolo')
    assert len(out.boxes) == len(out.vacios) == expected
    assert out.confs.tolist() == ([.9] if roi else [.9, .8])
    result = _conteo(img, out, roi, 2, 30, 70)
    assert result['resumen']['productos'] == expected
    assert result['resumen']['vacios_detectados'] == expected
    if roi is None:
        assert result['huecos'] == []
        assert any('Sin región' in w for w in out.quality.warnings)


def test_outside_empty_cannot_remove_inside_product(monkeypatch):
    def det(img, conf=.25):
        return {'productos': (np.array([[200, 100, 230, 150.]]), np.array([.9])),
                'vacios': (np.array([[190, 90, 390, 180.]]), np.array([.9]))}
    monkeypatch.setattr(yolo_detector, 'detect_all', det)
    _, out = analyze_image_bytes(image_bytes(), roi_polygon=ROI, method='yolo')
    assert len(out.boxes) == 1
    assert len(out.vacios) == 0


def test_outside_large_products_do_not_change_size_filter(monkeypatch):
    def det(img, conf=.25):
        return {'productos': (np.array([[60, 60, 70, 70], [260, 0, 390, 290], [250, 0, 399, 299.]]), np.array([.9]*3)),
                'vacios': (np.empty((0, 4)), np.empty(0))}
    monkeypatch.setattr(yolo_detector, 'detect_all', det)
    _, out = analyze_image_bytes(image_bytes(), roi_polygon=ROI, method='yolo')
    assert len(out.boxes) == 1


def test_concave_roi_rejects_center_in_bounding_rectangle_but_outside_polygon():
    polygon = [[0, 0], [1, 0], [1, .3], [.3, .3], [.3, 1], [0, 1]]
    boxes = np.array([[5, 60, 15, 80], [60, 60, 80, 80.]])
    assert centers_inside(boxes, (100, 100), polygon).tolist() == [True, False]
    spaces = [{'bbox': [60, 60, 80, 80], 'frentes_para_rellenar': 3},
              {'bbox': [0, 60, 80, 80], 'frentes_para_rellenar': 8}]
    clipped = clip_spaces(spaces, (100, 100), polygon, [{'bbox': [0, 0, 10, 10]}])
    assert len(clipped) == 1
    assert clipped[0]['bbox'][2] <= 31
    assert clipped[0]['frentes_para_rellenar'] == 3


def test_slanted_roi_clips_rendering_at_actual_polygon(monkeypatch):
    polygon = [[.1, .1], [.9, .1], [.6, .9], [.4, .9]]
    img = np.full((300, 400, 3), 100, np.uint8)
    captured = {}
    def encode(ext, canvas, params):
        captured['canvas'] = canvas.copy()
        return True, np.array([1], np.uint8)
    monkeypatch.setattr(cv2, 'imencode', encode)
    render_detections(img, [{'bbox': [0, 0, 399, 299]}], [{'bbox': [0, 240, 399, 270]}],
                      polygon_pixels(img.shape, polygon))
    mask = np.zeros(img.shape[:2], np.uint8)
    cv2.fillPoly(mask, [np.rint(polygon_pixels(img.shape, polygon)).astype(np.int32)], 255)
    outside = cv2.dilate(mask, np.ones((11, 11), np.uint8)) == 0
    assert np.array_equal(captured['canvas'][outside], img[outside])
    assert np.any(captured['canvas'][240, 190] != img[240, 190])


def test_process_image_returns_consistent_counts_and_surfaces(monkeypatch):
    monkeypatch.setattr(yolo_detector, 'detect_all', fake_detector)
    settings = {'min_side_px': 200, 'threshold': 30, 'low_threshold': 70}
    result, overlay = process_image(image_bytes(), {'method': 'yolo', 'roi': ROI, 'filas': 2}, settings)
    assert result['conteo']['resumen']['productos'] == 1
    assert result['conteo']['resumen']['vacios_detectados'] == 1
    assert result['availability_pct'] + result['empty_pct'] == 100
    assert result['method'] == 'yolo-finetuned'
    assert overlay[:2] == b'\xff\xd8'


def test_no_roi_keeps_unclipped_drawing(monkeypatch):
    img = np.full((100, 100, 3), 100, np.uint8)
    captured = {}
    def encode(ext, canvas, params):
        captured['canvas'] = canvas.copy()
        return True, np.array([1], np.uint8)
    monkeypatch.setattr(cv2, 'imencode', encode)
    render_detections(img, [{'bbox': [70, 70, 90, 90]}])
    assert not np.array_equal(captured['canvas'], img)
