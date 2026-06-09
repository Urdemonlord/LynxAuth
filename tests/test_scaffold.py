from pathlib import Path
import importlib.util
import io
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_prd_and_readme_exist():
    assert (ROOT / "docs/PRD.md").exists()
    assert (ROOT / "README.md").exists()


def test_sdk_camera_guard_blocks_virtual_devices():
    camera = load_module("camera_module", ROOT / "lynxauth-sdk/camera.py")
    assert camera.is_hardware_camera("/dev/video0") is True
    assert camera.is_hardware_camera("/dev/virtual-camera0") is False


def test_worker_embedding_is_stable_length_512():
    recognizer_module = load_module("face_recognizer_module", ROOT / "inference-worker/services/face_recognizer.py")
    recognizer = recognizer_module.FaceRecognizer(force_fallback=True)

    image = Image.new("RGB", (8, 8), color=(120, 30, 200))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    embedding = recognizer.extract_embedding(buffer.getvalue())
    assert len(embedding) == 512
    assert all(isinstance(item, float) for item in embedding)
