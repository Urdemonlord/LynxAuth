from __future__ import annotations

import hashlib
import io
import os
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image


@dataclass
class BackendInfo:
    mode: str
    provider: str
    reason: str | None = None


class FaceRecognizer:
    """Real face recognizer with InsightFace primary backend and deterministic fallback.

    Phase 2 behavior:
    - decodes image bytes into RGB ndarray
    - prefers InsightFace FaceAnalysis when dependency/model are available
    - falls back to deterministic 512-dim embedding when InsightFace is unavailable
    - can be configured to fail on invalid image bytes for stricter API behavior
    """

    def __init__(
        self,
        *,
        force_fallback: bool = False,
        fail_on_invalid_image: bool = False,
        det_size: tuple[int, int] | None = None,
    ) -> None:
        self._force_fallback = force_fallback
        self._fail_on_invalid_image = fail_on_invalid_image
        self._det_size = det_size or (640, 640)
        self._analysis_app: Any | None = None
        self._backend = self._build_backend()

    def backend_info(self) -> dict[str, str | None]:
        return {
            "mode": self._backend.mode,
            "provider": self._backend.provider,
            "reason": self._backend.reason,
        }

    def extract_embedding(self, image_bytes: bytes) -> list[float]:
        image = self._decode_image(image_bytes)

        if self._backend.mode == "insightface":
            faces = self._analysis_app.get(image)
            if not faces:
                raise ValueError("no face detected in image")

            best_face = max(faces, key=lambda face: self._face_area(face.bbox))
            embedding = np.asarray(best_face.embedding, dtype=np.float32)
            if embedding.shape[0] != 512:
                raise ValueError(f"unexpected embedding length: {embedding.shape[0]}")
            return embedding.astype(float).tolist()

        return self._fallback_embedding(image)

    def _build_backend(self) -> BackendInfo:
        if self._force_fallback:
            return BackendInfo(mode="fallback", provider="deterministic", reason="force_fallback enabled")

        try:
            import insightface
            from insightface.app import FaceAnalysis

            providers = [provider.strip() for provider in os.environ.get("INFERENCE_PROVIDERS", "CPUExecutionProvider").split(",") if provider.strip()]
            self._analysis_app = FaceAnalysis(providers=providers)
            self._analysis_app.prepare(ctx_id=0, det_size=self._det_size)
            return BackendInfo(mode="insightface", provider=providers[0], reason=None)
        except Exception as err:
            self._analysis_app = None
            return BackendInfo(mode="fallback", provider="deterministic", reason=str(err))

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

    @staticmethod
    def _fallback_embedding(image: np.ndarray) -> list[float]:
        digest = hashlib.sha256(image.tobytes()).digest()
        base = list(digest)
        values: list[float] = []
        while len(values) < 512:
            values.extend((byte / 255.0) for byte in base)
        return values[:512]

    @staticmethod
    def _face_area(bbox: Any) -> float:
        x1, y1, x2, y2 = bbox
        return max(0.0, float(x2 - x1)) * max(0.0, float(y2 - y1))
