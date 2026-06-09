from __future__ import annotations

import mimetypes
from pathlib import Path


def guess_image_mime(path: str | Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "image/jpeg"
