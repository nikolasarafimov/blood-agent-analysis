from __future__ import annotations

import io
import json
import math
import mimetypes
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Tuple

from minio import Minio
from minio.deleteobjects import DeleteObject
from minio.error import S3Error
from PIL import Image

_DOC_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_SUFFIX_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_DELETE_PREFIX_RE = re.compile(r"^documents/[A-Za-z0-9_-]{1,128}/$")


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _positive_env_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _validate_doc_id(doc_id: str) -> str:
    if not isinstance(doc_id, str) or not _DOC_ID_RE.fullmatch(doc_id):
        raise ValueError("Invalid document identifier")
    return doc_id


def _read_limit() -> int:
    return _positive_env_int("MAX_STORAGE_READ_MB", 32) * 1024 * 1024


def _reject_json_constant(value: str) -> None:
    raise ValueError("Non-finite JSON constants are not allowed")


def _finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("Non-finite JSON numbers are not allowed")
    return parsed


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON keys are not allowed")
        result[key] = value
    return result


@dataclass(frozen=True)
class MinioConfig:
    endpoint: str = field(
        default_factory=lambda: os.getenv("MINIO_ENDPOINT", "localhost:9000")
    )
    access_key: str = field(
        default_factory=lambda: os.getenv("MINIO_ACCESS_KEY", "minio")
    )
    secret_key: str = field(
        default_factory=lambda: os.getenv("MINIO_SECRET_KEY", "minio123")
    )
    secure: bool = field(
        default_factory=lambda: _env_flag("MINIO_SECURE", default=False)
    )
    bronze_bucket: str = field(
        default_factory=lambda: os.getenv(
            "MINIO_BRONZE_BUCKET",
            os.getenv("MINIO_BUCKET", "bronze"),
        )
    )
    silver_bucket: str = field(
        default_factory=lambda: os.getenv(
            "MINIO_SILVER_BUCKET",
            os.getenv("SILVER_BUCKET", "silver"),
        )
    )

    def __post_init__(self) -> None:
        for name in (
            "endpoint",
            "access_key",
            "secret_key",
            "bronze_bucket",
            "silver_bucket",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} cannot be empty")
            object.__setattr__(self, name, value.strip())

        if (
            "://" in self.endpoint
            or "/" in self.endpoint
            or "\\" in self.endpoint
            or any(char.isspace() for char in self.endpoint)
        ):
            raise ValueError(
                "MINIO_ENDPOINT must be a host with optional port, without a scheme or path"
            )


def client(cfg: Optional[MinioConfig] = None) -> Minio:
    resolved = cfg or MinioConfig()
    return Minio(
        resolved.endpoint,
        access_key=resolved.access_key,
        secret_key=resolved.secret_key,
        secure=resolved.secure,
    )


def ensure_bucket(mc: Minio, bucket: str) -> None:
    if not isinstance(bucket, str) or not bucket.strip():
        raise ValueError("bucket cannot be empty")
    bucket = bucket.strip()
    if mc.bucket_exists(bucket):
        return
    try:
        mc.make_bucket(bucket)
    except S3Error as exc:
        if exc.code != "BucketAlreadyOwnedByYou":
            raise


def put_original(
    mc: Minio,
    bucket: str,
    filepath: str,
    doc_id: str,
) -> Tuple[str, str, str, int]:
    _validate_doc_id(doc_id)
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {filepath}")

    size = path.stat().st_size
    if size == 0:
        raise ValueError("Input document is empty")
    if size > _positive_env_int("MAX_UPLOAD_MB", 20) * 1024 * 1024:
        raise ValueError("Input document exceeds maximum allowed size")

    ensure_bucket(mc, bucket)
    extension = path.suffix.lower()
    key = f"documents/{doc_id}/{doc_id}{extension}"

    content_type, _ = mimetypes.guess_type(str(path))
    content_type = content_type or "application/octet-stream"

    result = mc.fput_object(
        bucket_name=bucket,
        object_name=key,
        file_path=str(path),
        content_type=content_type,
    )

    return key, content_type, result.etag, size


def put_text(
    mc: Minio,
    bucket: str,
    doc_id: str,
    text: str,
) -> Tuple[str, Optional[str]]:
    _validate_doc_id(doc_id)
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    data = text.encode("utf-8")
    if len(data) > _read_limit():
        raise ValueError("Extracted text exceeds the storage size limit")

    ensure_bucket(mc, bucket)
    key = f"documents/{doc_id}/{doc_id}.txt"

    result = mc.put_object(
        bucket_name=bucket,
        object_name=key,
        data=io.BytesIO(data),
        length=len(data),
        content_type="text/plain; charset=utf-8",
    )

    return key, result.etag


def put_anon_text(
    mc: Minio,
    bucket: str,
    doc_id: str,
    anon_text: str,
) -> Tuple[str, Optional[str]]:
    _validate_doc_id(doc_id)
    if not isinstance(anon_text, str):
        raise TypeError("anon_text must be a string")

    data = anon_text.encode("utf-8")
    if len(data) > _read_limit():
        raise ValueError("Anonymized text exceeds the storage size limit")

    ensure_bucket(mc, bucket)
    key = f"documents/{doc_id}/anon_{doc_id}.txt"

    result = mc.put_object(
        bucket_name=bucket,
        object_name=key,
        data=io.BytesIO(data),
        length=len(data),
        content_type="text/plain; charset=utf-8",
    )

    return key, result.etag


def put_json(
    mc: Minio,
    bucket: str,
    doc_id: str,
    obj: Any,
    suffix: str = "",
) -> str:
    _validate_doc_id(doc_id)
    if not isinstance(suffix, str):
        raise ValueError("Invalid JSON filename suffix")

    clean_suffix = suffix.strip()
    if clean_suffix and not _SUFFIX_RE.fullmatch(clean_suffix):
        raise ValueError("Invalid JSON filename suffix")

    try:
        serialized = json.dumps(
            obj,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Object cannot be serialized to valid JSON") from exc

    data = serialized.encode("utf-8")
    if len(data) > _read_limit():
        raise ValueError("JSON content exceeds the storage size limit")

    ensure_bucket(mc, bucket)
    filename = (
        f"{doc_id}_{clean_suffix}.json"
        if clean_suffix
        else f"{doc_id}.json"
    )
    key = f"documents/{doc_id}/{filename}"

    mc.put_object(
        bucket_name=bucket,
        object_name=key,
        data=io.BytesIO(data),
        length=len(data),
        content_type="application/json; charset=utf-8",
    )
    return key


def _read_object_limited(mc: Minio, bucket: str, key: str) -> bytes:
    response = mc.get_object(bucket_name=bucket, object_name=key)
    try:
        data = response.read(_read_limit() + 1)
        if len(data) > _read_limit():
            raise ValueError(
                "Stored object exceeds the maximum allowed read size"
            )
        return data
    finally:
        response.close()
        response.release_conn()


def get_json(mc: Minio, bucket: str, key: str) -> Any:
    try:
        text = _read_object_limited(
            mc,
            bucket,
            key,
        ).decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("Stored JSON is not valid UTF-8") from exc

    try:
        return json.loads(
            text,
            parse_constant=_reject_json_constant,
            parse_float=_finite_json_float,
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (json.JSONDecodeError, ValueError, OverflowError) as exc:
        raise ValueError("Stored object contains invalid JSON") from exc


def get_text_object(mc: Minio, bucket: str, key: str) -> str:
    try:
        return _read_object_limited(
            mc,
            bucket,
            key,
        ).decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("Stored text is not valid UTF-8") from exc


def put_preview_image(
    mc: Minio,
    bucket: str,
    doc_id: str,
    image: Image.Image,
) -> str:
    _validate_doc_id(doc_id)

    width, height = image.size
    max_pixels = _positive_env_int("MAX_OCR_IMAGE_PIXELS", 40_000_000)

    if width < 1 or height < 1 or width * height > max_pixels:
        raise ValueError("Preview image exceeds allowed dimensions")

    prepared = image.convert("RGB")
    try:
        buffer = io.BytesIO()
        prepared.save(
            buffer,
            format="JPEG",
            quality=85,
            optimize=True,
        )
        payload = buffer.getvalue()
    finally:
        prepared.close()

    ensure_bucket(mc, bucket)
    key = f"documents/{doc_id}/preview.jpg"

    mc.put_object(
        bucket_name=bucket,
        object_name=key,
        data=io.BytesIO(payload),
        length=len(payload),
        content_type="image/jpeg",
    )
    return key


def list_prefix(mc: Minio, bucket: str, prefix: str) -> List[str]:
    if not isinstance(prefix, str) or not prefix:
        raise ValueError("Object prefix cannot be empty")

    return [
        obj.object_name
        for obj in mc.list_objects(
            bucket_name=bucket,
            prefix=prefix,
            recursive=True,
        )
        if obj.object_name
    ]


def delete_prefix(mc: Minio, bucket: str, prefix: str) -> None:
    if not isinstance(prefix, str) or not _DELETE_PREFIX_RE.fullmatch(prefix):
        raise ValueError(
            "Document deletion requires a full documents/<doc_id>/ prefix"
        )

    def objects_to_delete():
        for obj in mc.list_objects(
            bucket_name=bucket,
            prefix=prefix,
            recursive=True,
        ):
            if obj.object_name and obj.object_name.startswith(prefix):
                yield DeleteObject(obj.object_name)

    errors = mc.remove_objects(
        bucket_name=bucket,
        delete_object_list=objects_to_delete(),
    )

    failed = 0
    for _error in errors:
        failed += 1

    if failed:
        raise RuntimeError(
            f"Failed to delete {failed} document storage objects"
        )