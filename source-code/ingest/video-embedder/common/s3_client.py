import logging
from urllib.parse import urlparse

import boto3


class S3Client:
    """Minimal S3 client for downloading segment videos."""

    def __init__(self, settings):
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3endpoint,
            aws_access_key_id=settings.s3accesskey,
            aws_secret_access_key=settings.s3secretkey,
            verify=False,
        )

    def download_from_uri(self, source_uri: str) -> bytes:
        parsed = urlparse(source_uri)
        if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
            raise ValueError(f"Invalid S3 URI: {source_uri}")
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        logging.info(f"[S3] Downloading s3://{bucket}/{key}")
        response = self.client.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read()
        logging.info(f"[S3] Downloaded {len(content)} bytes")
        return content
