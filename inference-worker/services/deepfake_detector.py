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


class DeepfakeDetector:
    """Dual-model deepfake detector.

    Primary: ViT (dima806/deepfake_vs_real_image_detection) — pretrained ONNX.
        Best at faceswap artifacts (FaceForensics++ training).
    Secondary: EfficientNet-B0 ONNX — for general deepfake detection.
        WARNING: must be fine-tuned. An untrained export gives ~0.5 random output.
        When efficientnet output is reliably trained, it's weighted 0.4 in ensemble.
        Otherwise falls back to ViT-only scoring.

    ArcFace detection confidence (from FaceRecognizer) adds synthetic/AI face detection
    as a separate signal outside this class.
    """

    def __init__(
        self,
        *,
        vit_model_path: str | None = None,
        enet_model_path: str | None = None,
        threshold: float | None = None,
        force_fallback: bool = False,
    ) -> None:
        self._vit_path = vit_model_path or os.environ.get(
            "DEEPFAKE_MODEL_PATH",
            str(Path(__file__).resolve().parents[1] / "models" / "deepfake_vit_int8.onnx"),
        )
        self._enet_path = enet_model_path or os.environ.get(
            "EFFICIENTNET_MODEL_PATH",
            str(Path(__file__).resolve().parents[1] / "models" / "efficientnet_b0_fp32.onnx"),
        )
        self._threshold = threshold if threshold is not None else float(os.environ.get("DEEPFAKE_THRESHOLD", "0.5"))
        self._force_fallback = force_fallback

        self._vit_session: Any | None = None
        self._vit_input_name: str | None = None
        self._vit_backend = self._build_model("vit", self._vit_path)

        self._enet_session: Any | None = None
        self._enet_input_name: str | None = None
        self._enet_backend = self._build_model("enet", self._enet_path)

    def vit_backend_info(self) -> dict[str, str | None]:
        return {
            "mode": self._vit_backend.mode,
            "provider": self._vit_backend.provider,
            "reason": self._vit_backend.reason,
            "model_path": self._vit_backend.model_path,
        }

    def enet_backend_info(self) -> dict[str, str | None]:
        return {
            "mode": self._enet_backend.mode,
            "provider": self._enet_backend.provider,
            "reason": self._enet_backend.reason,
            "model_path": self._enet_backend.model_path,
        }

    def is_fake(self, image_bytes: bytes) -> bool:
        """Combined detection — returns True if image is likely fake."""
        scores = self.get_scores(image_bytes)
        combined = scores["combined"]

        if combined >= self._threshold:
            return True
        if scores["vit_prob"] >= 0.7:
            return True
        if scores["enet_prob"] >= 0.7:
            return True

        # Pure fallback when no models available
        if self._vit_backend.mode == "fallback" and self._enet_backend.mode == "fallback":
            return self._fallback_detect(image_bytes)

        return False

    def get_scores(self, image_bytes: bytes) -> dict[str, float]:
        """Return per-model probabilities for diagnostics."""
        image = self._decode_image(image_bytes)

        vit_prob = self._model_score(image, "vit")
        enet_prob = self._model_score(image, "enet")

        # EfficientNet untrained check: if it always outputs ~0.5, ignore it
        # A properly trained model will show meaningful variation
        if abs(enet_prob - 0.5) < 0.05:
            enet_prob = 0.0  # untrained — don't use

        vit_weight = 0.6
        enet_weight = 0.4
        if enet_prob == 0.0:
            combined = vit_prob  # ViT-only
        else:
            combined = vit_prob * vit_weight + enet_prob * enet_weight

        return {"vit_prob": vit_prob, "enet_prob": enet_prob, "combined": combined}

    def _model_score(self, image: np.ndarray, model_type: str) -> float:
        if model_type == "vit" and self._vit_backend.mode == "onnx":
            tensor = self._preprocess_vit(image)
            out = self._vit_session.run(None, {self._vit_input_name: tensor})[0]
            return self._extract_probability(out)

        if model_type == "enet" and self._enet_backend.mode == "onnx":
            tensor = self._preprocess_enet(image)
            out = self._enet_session.run(None, {self._enet_input_name: tensor})[0]
            return self._extract_probability(out)

        return 0.0

    def _build_model(self, name: str, path: str) -> BackendInfo:
        if self._force_fallback:
            return BackendInfo(mode="fallback", provider="heuristic", reason=f"{name}: forced", model_path=path)

        f = Path(path)
        if not f.exists():
            return BackendInfo(mode="fallback", provider="heuristic", reason=f"{name}: file not found", model_path=path)

        try:
            import onnxruntime as ort
            providers = [p.strip() for p in os.environ.get("INFERENCE_PROVIDERS", "CPUExecutionProvider").split(",") if p.strip()]
            session = ort.InferenceSession(str(f), providers=providers)
            input_name = session.get_inputs()[0].name

            if name == "vit":
                self._vit_session = session
                self._vit_input_name = input_name
            else:
                self._enet_session = session
                self._enet_input_name = input_name

            return BackendInfo(mode="onnx", provider=providers[0], reason=None, model_path=path)
        except Exception as err:
            return BackendInfo(mode="fallback", provider="heuristic", reason=f"{name}: {err}", model_path=path)

    @staticmethod
    def _decode_image(image_bytes: bytes) -> np.ndarray:
        if not image_bytes:
            raise ValueError("empty image payload")
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                return np.array(img.convert("RGB"))
        except Exception as err:
            raise ValueError("invalid image bytes") from err

    def _preprocess_vit(self, image: np.ndarray) -> np.ndarray:
        # ViT model uses its own preprocessor_config.json
        from pathlib import Path as P
        cfg = P(self._vit_path).with_name("preprocessor_config.json")
        if cfg.exists():
            data = json.loads(cfg.read_text())
            sz = data.get("size") or {}
            w = int(sz.get("width", sz.get("shortest_edge", 224))) if not isinstance(sz, int) else int(sz)
            h = int(sz.get("height", sz.get("shortest_edge", 224))) if not isinstance(sz, int) else int(sz)
            mean = self._triple(data.get("image_mean"), (0.485, 0.456, 0.406))
            std = self._triple(data.get("image_std"), (0.229, 0.224, 0.225))
            scale = float(data.get("rescale_factor", 1.0 / 255.0))
        else:
            w = h = 224
            mean = (0.485, 0.456, 0.406)
            std = (0.229, 0.224, 0.225)
            scale = 1.0 / 255.0

        resized = Image.fromarray(image).resize((w, h))
        arr = np.asarray(resized, dtype=np.float32) * scale
        norm = (arr - np.array(mean, dtype=np.float32)) / np.array(std, dtype=np.float32)
        return np.expand_dims(np.transpose(norm, (2, 0, 1)), 0).astype(np.float32)

    @staticmethod
    def _preprocess_enet(image: np.ndarray) -> np.ndarray:
        # EfficientNet: 224x224, ImageNet normalize (mean, std)
        resized = Image.fromarray(image).resize((224, 224))
        arr = np.asarray(resized, dtype=np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        norm = (arr - mean) / std
        return np.expand_dims(np.transpose(norm, (2, 0, 1)), 0).astype(np.float32)

    @staticmethod
    def _extract_probability(output: Any) -> float:
        arr = np.asarray(output, dtype=np.float32).squeeze()
        if arr.ndim == 0:
            return float(arr)
        if arr.shape[0] == 1:
            return float(arr[0])
        # Multi-class: softmax + take last class
        logits = arr - np.max(arr)
        probs = np.exp(logits) / np.sum(np.exp(logits))
        return float(probs[-1])

    def _fallback_detect(self, image_bytes: bytes) -> bool:
        image = self._decode_image(image_bytes)
        gray = image.mean(axis=2)
        if float(np.std(gray)) < 2.0:
            return True
        if image.shape[0] < 64 or image.shape[1] < 64:
            return True
        payload = image_bytes.lower()
        if not payload:
            return True
        return b"deepfake" in payload

    @staticmethod
    def _triple(v: Any, d: tuple[float, float, float]) -> tuple[float, float, float]:
        if isinstance(v, (list, tuple)) and len(v) == 3:
            return (float(v[0]), float(v[1]), float(v[2]))
        if isinstance(v, (int, float)):
            return (float(v),) * 3
        return d
