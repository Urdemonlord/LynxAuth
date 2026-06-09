from pathlib import Path
import importlib.util
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_face_recognizer_exposes_backend_info_for_fallback_mode():
    module = load_module("face_recognizer_phase2", ROOT / "inference-worker/services/face_recognizer.py")
    recognizer = module.FaceRecognizer(force_fallback=True)
    info = recognizer.backend_info()

    assert info["mode"] == "fallback"
    assert "reason" in info


def test_deepfake_detector_exposes_backend_info_for_missing_model():
    module = load_module("deepfake_detector_phase2", ROOT / "inference-worker/services/deepfake_detector.py")
    detector = module.DeepfakeDetector(model_path=str(ROOT / "inference-worker/models/missing-model.onnx"))
    info = detector.backend_info()

    assert info["mode"] == "fallback"
    assert info["model_path"].endswith("missing-model.onnx")


def test_real_inference_components_reject_invalid_image_bytes():
    recognizer_module = load_module("face_recognizer_phase2_invalid", ROOT / "inference-worker/services/face_recognizer.py")
    detector_module = load_module("deepfake_detector_phase2_invalid", ROOT / "inference-worker/services/deepfake_detector.py")

    recognizer = recognizer_module.FaceRecognizer(force_fallback=False, fail_on_invalid_image=True)
    detector = detector_module.DeepfakeDetector(force_fallback=False, fail_on_invalid_image=True)

    try:
        recognizer.extract_embedding(b"not-an-image")
        raise AssertionError("expected ValueError for recognizer invalid image")
    except ValueError:
        pass

    try:
        detector.is_fake(b"not-an-image")
        raise AssertionError("expected ValueError for detector invalid image")
    except ValueError:
        pass


def test_deepfake_detector_uses_sidecar_preprocessor_config_when_present(tmp_path):
    module = load_module("deepfake_detector_phase25_sidecar", ROOT / "inference-worker/services/deepfake_detector.py")

    model_path = tmp_path / "model.onnx"
    model_path.write_bytes(b"fake-onnx-placeholder")
    (tmp_path / "preprocessor_config.json").write_text(
        json.dumps(
            {
                "image_mean": [0.5, 0.5, 0.5],
                "image_std": [0.5, 0.5, 0.5],
                "size": {"height": 224, "width": 224},
            }
        )
    )

    detector = module.DeepfakeDetector(model_path=str(model_path), force_fallback=True)
    image = np.full((32, 32, 3), 128, dtype=np.uint8)
    tensor = detector._preprocess_for_model(image)

    assert tensor.shape == (1, 3, 224, 224)
    assert abs(float(tensor[0, 0, 0, 0]) - 0.0039215686) < 1e-4
