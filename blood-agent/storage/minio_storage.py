from __future__ import annotations

import io
import json
import mimetypes
import os
from dataclasses import dataclass, field

from minio import Minio


@dataclass(frozen=True)
class MinioConfig:
    endpoint: str = field(default_factory=lambda: os.getenv("MINIO_ENDPOINT", "localhost:9000"))
    access_key: str = field(default_factory=lambda: os.getenv("MINIO_ACCESS_KEY", "minio"))
    secret_key: str = field(default_factory=lambda: os.getenv("MINIO_SECRET_KEY", "minio123"))
    secure: bool = field(default_factory=lambda: os.getenv("MINIO_SECURE", "false").lower() == "true")
    bronze_bucket: str = field(default_factory=lambda: os.getenv("MINIO_BUCKET", "bronze"))
    silver_bucket: str = field(default_factory=lambda: os.getenv("SILVER_BUCKET", "silver"))


def client(cfg: MinioConfig | None = None) -> Minio:
    cfg = cfg or MinioConfig()
    return Minio(cfg.endpoint, access_key=cfg.access_key, secret_key=cfg.secret_key, secure=cfg.secure)


def ensure_bucket(mc: Minio, bucket: str) -> None:
    if not mc.bucket_exists(bucket):
        mc.make_bucket(bucket)


def put_original(mc: Minio, bucket: str, filepath: str, doc_id: str) -> tuple[str, str, str, int]:
    _, ext = os.path.splitext(filepath)
    key = f"documents/{doc_id}/{doc_id}{ext}"
    ctype, _ = mimetypes.guess_type(filepath)
    ctype = ctype or "application/octet-stream"
    size = os.path.getsize(filepath)
    etag = mc.fput_object(bucket, key, filepath, content_type=ctype).etag
    return key, ctype, etag, size


def put_text(mc: Minio, bucket: str, doc_id: str, text: str) -> tuple[str, str | None]:
    key = f"documents/{doc_id}/{doc_id}.txt"
    data = text.encode("utf-8")
    etag = mc.put_object(
        bucket, key, io.BytesIO(data), length=len(data),
        content_type="text/plain; charset=utf-8"
    ).etag
    return key, etag

def put_anon_text(mc: Minio, bucket: str, doc_id: str, anon_text: str) -> tuple[str, str | None]:
    anon_key = f"documents/{doc_id}/anon_{doc_id}.txt"
    data = anon_text.encode("utf-8")
    etag = mc.put_object(
        bucket, anon_key, io.BytesIO(data), length=len(data),
        content_type="text/plain; charset=utf-8"
    ).etag
    return anon_key, etag


def put_json(mc: Minio, bucket: str, doc_id: str, obj: dict) -> str:
    key = f"documents/{doc_id}/{doc_id}.json"
    data = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    mc.put_object(
        bucket, key, io.BytesIO(data), length=len(data),
        content_type="application/json; charset=utf-8"
    )
    return key