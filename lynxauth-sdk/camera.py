from __future__ import annotations

from pathlib import Path


def is_hardware_camera(device_path: str) -> bool:
    """Best-effort Linux hardware camera guard.

    Scaffold behavior: device path must live under /dev and must not look like
    a common loopback / virtual camera path.
    """

    blocked_markers = ("loopback", "obs", "virtual")
    normalized = device_path.lower()
    return normalized.startswith("/dev/") and not any(marker in normalized for marker in blocked_markers)


def ensure_camera_device(device_path: str) -> Path:
    path = Path(device_path)
    if not is_hardware_camera(device_path):
        raise ValueError(f"blocked non-hardware camera path: {device_path}")
    return path
