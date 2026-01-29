from __future__ import annotations

import mimetypes
import os
from typing import Optional

from minio import Minio
from PIL import Image
from pdf2image import convert_from_path

from storage.minio_storage import MinioConfig, put_preview_image


def _pdf_first_page_image(pdf_path: str, dpi: int = 160) -> Optional[Image.Image]:
    poppler_bin = os.getenv("POPPLER_PATH") or None
    images = convert_from_path(
        pdf_path,
        dpi=dpi,
        poppler_path=poppler_bin,
        first_page=1,
        last_page=1,
    )
    if not images:
        return None
    img = images[0]
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def create_preview_and_store(mc: Minio, cfg: MinioConfig, doc_id: str, filepath: str) -> Optional[str]:
    mime, _ = mimetypes.guess_type(filepath)

    if mime and "pdf" in mime.lower():
        img = _pdf_first_page_image(filepath, dpi=160)
        if img is None:
            return None
        return put_preview_image(mc, cfg.bronze_bucket, doc_id, img)

    try:
        with Image.open(filepath) as opened:
            img = opened.convert("RGB") if opened.mode != "RGB" else opened.copy()
    except Exception:
        return None

    return put_preview_image(mc, cfg.bronze_bucket, doc_id, img)