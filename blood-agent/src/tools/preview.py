from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Optional

from minio import Minio
from pdf2image import convert_from_path
from PIL import Image, ImageOps

from storage.minio_storage import MinioConfig, put_preview_image


_SUPPORTED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"
}


def _positive_env_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _is_pdf(filepath: str) -> bool:
    return Path(filepath).suffix.lower() == ".pdf"


def _validate_preview_source(filepath: str) -> Path:
    path = Path(filepath)

    if not path.is_file():
        raise FileNotFoundError(
            f"Preview source file not found: {filepath}"
        )

    if path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
        raise ValueError("Unsupported preview source type")

    size = path.stat().st_size

    if size == 0:
        raise ValueError("Preview source file is empty")

    max_bytes = (
        _positive_env_int("MAX_UPLOAD_MB", 20)
        * 1024
        * 1024
    )

    if size > max_bytes:
        raise ValueError(
            "Preview source file exceeds maximum allowed size"
        )

    return path


def _check_image_size(image: Image.Image) -> None:
    width, height = image.size

    max_pixels = _positive_env_int(
        "MAX_OCR_IMAGE_PIXELS",
        40_000_000,
    )

    if (
        width < 1
        or height < 1
        or width * height > max_pixels
    ):
        raise ValueError(
            "Preview image exceeds the allowed dimensions"
        )


def _clean_rgb_preview(
    image: Image.Image,
) -> Image.Image:
    _check_image_size(image)

    corrected = ImageOps.exif_transpose(image)

    try:
        max_side = _positive_env_int(
            "MAX_PREVIEW_DIMENSION",
            2000,
        )

        corrected.thumbnail(
            (max_side, max_side),
            Image.Resampling.LANCZOS,
        )

        has_alpha = (
            corrected.mode in {"RGBA", "LA"}
            or (
                corrected.mode == "P"
                and "transparency" in corrected.info
            )
        )

        if has_alpha:
            rgba = corrected.convert("RGBA")

            try:
                preview = Image.new(
                    "RGB",
                    rgba.size,
                    "white",
                )

                alpha = rgba.getchannel("A")

                try:
                    preview.paste(
                        rgba,
                        mask=alpha,
                    )
                finally:
                    alpha.close()

                return preview

            finally:
                rgba.close()

        rgb = corrected.convert("RGB")

        try:
            preview = Image.new(
                "RGB",
                rgb.size,
                "white",
            )

            preview.paste(rgb)
            return preview

        finally:
            rgb.close()

    finally:
        corrected.close()


def _pdf_first_page_image(
    pdf_path: str,
    dpi: int = 160,
) -> Optional[Image.Image]:
    images = convert_from_path(
        pdf_path,
        dpi=dpi,
        poppler_path=(
            os.getenv("POPPLER_PATH")
            or None
        ),
        first_page=1,
        last_page=1,
        thread_count=1,
        size=_positive_env_int(
            "MAX_PREVIEW_DIMENSION",
            2000,
        ),
        timeout=_positive_env_int(
            "PDF_RENDER_TIMEOUT_SECONDS",
            60,
        ),
    )

    if not images:
        return None

    try:
        return _clean_rgb_preview(
            images[0]
        )

    finally:
        for image in images:
            image.close()


def _image_preview(filepath: str) -> Image.Image:
    with warnings.catch_warnings():
        warnings.simplefilter(
            "error",
            Image.DecompressionBombWarning,
        )

        with Image.open(filepath) as opened:
            return _clean_rgb_preview(
                opened
            )


def create_preview_and_store(
    mc: Minio,
    cfg: MinioConfig,
    doc_id: str,
    filepath: str,
) -> Optional[str]:
    path = _validate_preview_source(
        filepath
    )

    if _is_pdf(str(path)):
        image = _pdf_first_page_image(
            str(path),
            dpi=160,
        )

        if image is None:
            return None

    else:
        image = _image_preview(
            str(path)
        )

    try:
        return put_preview_image(
            mc,
            cfg.bronze_bucket,
            doc_id,
            image,
        )

    finally:
        image.close()