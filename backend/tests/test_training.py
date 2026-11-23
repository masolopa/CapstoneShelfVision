from app import training

def test_training_status_sin_checkpoint_no_declara_modelo(monkeypatch, tmp_path):
    monkeypatch.setattr(training, "TRAIN_STATUS", str(tmp_path / "no_existe.json"))
    body = training.training_status()
    assert body["ready"] is False
    assert body["checkpoint"] is None
    assert body["metrics"] is None

def test_training_status_dataset_refleja_stats():
    d = training.dataset_status()
    assert d["raw_images"] >= 0 and isinstance(d["prepared"], bool)
    if d["prepared"]:
        assert sum(d["splits"].values()) == d["unique_images"]
