from __future__ import annotations

import io
import json
import mimetypes
import os
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

from minio import Minio
from minio.deleteobjects import DeleteObject
from PIL import Image


@dataclass(frozen=True)
class MinioConfig:
    endpoint: str = field(default_factory=lambda: os.getenv("MINIO_ENDPOINT", "localhost:9000"))
    access_key: str = field(default_factory=lambda: os.getenv("MINIO_ACCESS_KEY", "minio"))
    secret_key: str = field(default_factory=lambda: os.getenv("MINIO_SECRET_KEY", "minio123"))
    secure: bool = field(default_factory=lambda: os.getenv("MINIO_SECURE", "false").lower() == "true")

    # NOTE: These env var names should match your docker-compose.yml
    bronze_bucket: str = field(default_factory=lambda: os.getenv("MINIO_BRONZE_BUCKET", os.getenv("MINIO_BUCKET", "bronze")))
    silver_bucket: str = field(default_factory=lambda: os.getenv("MINIO_SILVER_BUCKET", os.getenv("SILVER_BUCKET", "silver")))


def client(cfg: Optional[MinioConfig] = None) -> Minio:
    cfg = cfg or MinioConfig()
    return Minio(cfg.endpoint, access_key=cfg.access_key, secret_key=cfg.secret_key, secure=cfg.secure)


def ensure_bucket(mc: Minio, bucket: str) -> None:
    if not mc.bucket_exists(bucket):
        mc.make_bucket(bucket)


def put_original(mc: Minio, bucket: str, filepath: str, doc_id: str) -> Tuple[str, str, str, int]:
    ensure_bucket(mc, bucket)
    _, ext = os.path.splitext(filepath)
    key = f"documents/{doc_id}/{doc_id}{ext}"
    ctype, _ = mimetypes.guess_type(filepath)
    ctype = ctype or "application/octet-stream"
    size = os.path.getsize(filepath)

    etag = mc.fput_object(bucket, key, filepath, content_type=ctype).etag
    return key, ctype, etag, size


def put_text(mc: Minio, bucket: str, doc_id: str, text: str) -> Tuple[str, Optional[str]]:
    ensure_bucket(mc, bucket)
    key = f"documents/{doc_id}/{doc_id}.txt"
    data = (text or "").encode("utf-8")

    etag = mc.put_object(
        bucket_name=bucket,
        object_name=key,
        data=io.BytesIO(data),
        length=len(data),
        content_type="text/plain; charset=utf-8",
    ).etag
    return key, etag


def put_anon_text(mc: Minio, bucket: str, doc_id: str, anon_text: str) -> Tuple[str, Optional[str]]:
    ensure_bucket(mc, bucket)
    key = f"documents/{doc_id}/anon_{doc_id}.txt"
    data = (anon_text or "").encode("utf-8")

    etag = mc.put_object(
        bucket_name=bucket,
        object_name=key,
        data=io.BytesIO(data),
        length=len(data),
        content_type="text/plain; charset=utf-8",
    ).etag
    return key, etag


def put_json(mc: Minio, bucket: str, doc_id: str, obj: Any, suffix: str = "") -> str:
    ensure_bucket(mc, bucket)
    name = f"{doc_id}.json" if not suffix else f"{doc_id}_{suffix}.json"
    key = f"documents/{doc_id}/{name}"
    data = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")

    mc.put_object(
        bucket_name=bucket,
        object_name=key,
        data=io.BytesIO(data),
        length=len(data),
        content_type="application/json; charset=utf-8",
    )
    return key


def get_json(mc: Minio, bucket: str, key: str) -> Any:
    resp = mc.get_object(bucket, key)
    try:
        raw = resp.read()
    finally:
        resp.close()
        resp.release_conn()

    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Failed to parse JSON from {bucket}/{key}: {e}") from e


def get_text_object(mc: Minio, bucket: str, key: str) -> str:
    resp = mc.get_object(bucket, key)
    try:
        data = resp.read()
    finally:
        resp.close()
        resp.release_conn()
    return data.decode("utf-8", errors="ignore")


def put_preview_image(mc: Minio, bucket: str, doc_id: str, image: Image.Image) -> str:
    ensure_bucket(mc, bucket)
    key = f"documents/{doc_id}/preview.jpg"
    buf = io.BytesIO()

    img = image.convert("RGB") if image.mode != "RGB" else image
    img.save(buf, format="JPEG", quality=85)
    payload = buf.getvalue()

    mc.put_object(
        bucket_name=bucket,
        object_name=key,
        data=io.BytesIO(payload),
        length=len(payload),
        content_type="image/jpeg",
    )
    return key


def list_prefix(mc: Minio, bucket: str, prefix: str) -> List[str]:
    return [o.object_name for o in mc.list_objects(bucket, prefix=prefix, recursive=True)]


def delete_prefix(mc: Minio, bucket: str, prefix: str) -> None:
    objs = list_prefix(mc, bucket, prefix)
    if not objs:
        return

    errors = mc.remove_objects(bucket, (DeleteObject(name) for name in objs))
    for err in errors:
        raise RuntimeError(f"Failed deleting {bucket}/{err.object_name}: {err.message}")
