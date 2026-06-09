from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


@dataclass
class BackendInfo:
    mode: str
    provider: str
    reason: str | None = None
    model_path: str | None = None


@dataclass
class PreprocessConfig:
    width: int = 224
    height: int = 224
    mean: tuple[float, float, float] = (0.485, 0.456, 0.406)
    std: tuple[float, float, float] = (0.229, 0.224, 0.225)
    rescale_factor: float = 1.0 / 255.0


class DeepfakeDetector:
    """Real deepfake detector loader with ONNX primary backend and safe fallback.

    Expected real-model path:
    - `DEEPFAKE_MODEL_PATH`
    - defaults to `inference-worker/models/efficientnet_b0_ffpp.onnx`

    If the ONNX model is unavailable, detector falls back to a strict heuristic so
    the rest of the pipeline stays testable while clearly exposing fallback mode.
    """

    def __init__(
        self,
        *,
        model_path: str | None = None,
        threshold: float | None = None,
        force_fallback: bool = False,
        fail_on_invalid_image: bool = False,
    ) -> None:
        self._model_path = model_path or os.environ.get(
            "DEEPFAKE_MODEL_PATH",
            str(Path(__file__).resolve().parents[1] / "models" / "deepfake_vit_int8.onnx"),
        )
        self._threshold = threshold if threshold is not None else float(os.environ.get("DEEPFAKE_THRESHOLD", "0.5"))
        self._force_fallback = force_fallback
        self._fail_on_invalid_image = fail_on_invalid_image
        self._session: Any | None = None
        self._input_name: str | None = None
        self._preprocess = self._load_preprocess_config(Path(self._model_path))
        self._backend = self._build_backend()

    def backend_info(self) -> dict[str, str | None]:
        return {
            "mode": self._backend.mode,
            "provider": self._backend.provider,
            "reason": self._backend.reason,
            "model_path": self._backend.model_path,
        }

    def is_fake(self, image_bytes: bytes) -> bool:
        image = self._decode_image(image_bytes)

        if self._backend.mode == "onnx":
            tensor = self._preprocess_for_model(image)
            output = self._session.run(None, {self._input_name: tensor})[0]
            fake_probability = self._extract_fake_probability(output)
            return fake_probability >= self._threshold

        payload = image_bytes.lower()
        grayscale = image.mean(axis=2)
        low_variance = float(np.std(grayscale)) < 2.0
        tiny_image = image.shape[0] < 64 or image.shape[1] < 64
        if not payload:
            return True
        return low_variance or tiny_image or b"deepfake" in payload

    def _build_backend(self) -> BackendInfo:
        if self._force_fallback:
            return BackendInfo(mode="fallback", provider="heuristic", reason="force_fallback enabled", model_path=self._model_path)

        model_file = Path(self._model_path)
        if not model_file.exists():
            return BackendInfo(mode="fallback", provider="heuristic", reason="model file not found", model_path=self._model_path)

        try:
            import onnxruntime as ort

            providers = [provider.strip() for provider in os.environ.get("INFERENCE_PROVIDERS", "CPUExecutionProvider").split(",") if provider.strip()]
            self._session = ort.InferenceSession(str(model_file), providers=providers)
            self._input_name = self._session.get_inputs()[0].name
            return BackendInfo(mode="onnx", provider=providers[0], reason=None, model_path=self._model_path)
        except Exception as err:
            self._session = None
            self._input_name = None
            return BackendInfo(mode="fallback", provider="heuristic", reason=str(err), model_path=self._model_path)

    def _decode_image(self, image_bytes: bytes) -> np.ndarray:
        if not image_bytes:
            raise ValueError("empty image payload")
        try:
            with Image.open(io.BytesIO(image_bytes)) as image:
                rgb = image.convert("RGB")
                return np.array(rgb)
        except Exception as err:
            if self._fail_on_invalid_image:
                raise ValueError("invalid image bytes") from err
            raise ValueError("invalid image bytes") from err

    def _preprocess_for_model(self, image: np.ndarray) -> np.ndarray:
        resized = Image.fromarray(image).resize((self._preprocess.width, self._preprocess.height))
        array = np.asarray(resized, dtype=np.float32) * self._preprocess.rescale_factor
        normalized = (array - np.array(self._preprocess.mean, dtype=np.float32)) / np.array(self._preprocess.std, dtype=np.float32)
        chw = np.transpose(normalized, (2, 0, 1))
        return np.expand_dims(chw, axis=0).astype(np.float32)

    @staticmethod
    def _extract_fake_probability(output: Any) -> float:
        array = np.asarray(output, dtype=np.float32).squeeze()
        if array.ndim == 0:
            return float(array)
        if array.shape[0] == 1:
            return float(array[0])
        logits = np.exp(array - np.max(array))
        probabilities = logits / logits.sum()
        return float(probabilities[-1])

    @staticmethod
    def _load_preprocess_config(model_path: Path) -> PreprocessConfig:
        config_path = model_path.with_name("preprocessor_config.json")
        if not config_path.exists():
            return PreprocessConfig()

        try:
            data = json.loads(config_path.read_text())
        except Exception:
            return PreprocessConfig()

        size = data.get("size") or {}
        if isinstance(size, int):
            width = height = int(size)
        else:
            width = int(size.get("width", size.get("shortest_edge", 224)))
            height = int(size.get("height", size.get("shortest_edge", 224)))

        mean = DeepfakeDetector._triple(data.get("image_mean"), (0.485, 0.456, 0.406))
        std = DeepfakeDetector._triple(data.get("image_std"), (0.229, 0.224, 0.225))
        rescale_factor = float(data.get("rescale_factor", 1.0 / 255.0))
        return PreprocessConfig(width=width, height=height, mean=mean, std=std, rescale_factor=rescale_factor)

    @staticmethod
    def _triple(value: Any, default: tuple[float, float, float]) -> tuple[float, float, float]:
        if isinstance(value, (list, tuple)) and len(value) == 3:
            return (float(value[0]), float(value[1]), float(value[2]))
        if isinstance(value, (int, float)):
            scalar = float(value)
            return (scalar, scalar, scalar)
        return default
