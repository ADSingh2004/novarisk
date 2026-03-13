from __future__ import annotations

import os
from pathlib import Path


def _require_boto3():
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError

        return boto3, BotoCoreError, ClientError
    except Exception as exc:
        raise RuntimeError("boto3 is not installed. Run pip install boto3.") from exc


def s3_bucket_name() -> str | None:
    bucket = os.getenv("NOVARISK_S3_BUCKET", "").strip()
    return bucket or None


def s3_delivery_enabled() -> bool:
    return s3_bucket_name() is not None


def upload_compliance_pack(zip_path: str, site_id: str) -> dict[str, object]:
    bucket = s3_bucket_name()
    if not bucket:
        raise RuntimeError("NOVARISK_S3_BUCKET is not configured.")

    boto3, BotoCoreError, ClientError = _require_boto3()
    region = os.getenv("AWS_REGION", "eu-north-1")
    key_prefix = os.getenv("NOVARISK_S3_PREFIX", "compliance-packs").strip("/")
    expires_in = int(os.getenv("NOVARISK_S3_URL_EXPIRES_SECONDS", "900"))
    file_name = Path(zip_path).name
    object_key = f"{key_prefix}/{site_id}/{file_name}"

    client = boto3.client("s3", region_name=region)

    try:
        client.upload_file(
            Filename=zip_path,
            Bucket=bucket,
            Key=object_key,
            ExtraArgs={"ContentType": "application/zip"},
        )
        presigned_url = client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": object_key},
            ExpiresIn=expires_in,
        )
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"S3 upload/presign failed: {exc}") from exc

    return {
        "bucket": bucket,
        "object_key": object_key,
        "download_url": presigned_url,
        "expires_in_seconds": expires_in,
    }