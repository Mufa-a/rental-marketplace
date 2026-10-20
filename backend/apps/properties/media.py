"""Listing media: allowed file types, size limits and the Cloudflare R2 helpers the media endpoints share."""
import logging

import boto3
from botocore.config import Config
from django.conf import settings

logger = logging.getLogger(__name__)

IMAGE_TYPES = {"image/jpeg": {".jpg", ".jpeg"}, "image/png": {".png"}, "image/webp": {".webp"}}
VIDEO_TYPES = {"video/mp4": {".mp4", ".m4v"}, "video/webm": {".webm"}, "video/quicktime": {".mov"}}
ALLOWED_TYPES = {**IMAGE_TYPES, **VIDEO_TYPES}


def is_video_type(content_type: str) -> bool:
    return content_type in VIDEO_TYPES


def max_bytes_for(content_type: str) -> int:
    return settings.MEDIA_MAX_VIDEO_BYTES if is_video_type(content_type) else settings.MEDIA_MAX_IMAGE_BYTES


def r2_configured() -> bool:
    return all((
        settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, settings.AWS_STORAGE_BUCKET_NAME,
        settings.AWS_S3_ENDPOINT_URL, settings.R2_PUBLIC_BASE_URL,
    ))


def r2_client():
    return boto3.client(
        "s3", endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name="auto", config=Config(signature_version="s3v4"),
    )


def delete_object(asset_key: str) -> None:
    """Best-effort removal of an uploaded file.

    Used when a registration is refused (so a rejected upload does not sit in the bucket) and when a
    photo or video is removed. A failure is logged, never raised: the database row is the source of
    truth, and a leftover object is only wasted storage.
    """
    if not r2_configured():
        return
    try:
        r2_client().delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=asset_key)
    except Exception:
        logger.warning("Could not delete R2 object %s", asset_key, exc_info=True)
