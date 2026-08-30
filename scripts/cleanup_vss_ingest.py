#!/usr/bin/env python3
"""
Reset VSS ingest storage: empty S3 buckets and drop VastDB tables.

Usage:
  python cleanup_vss_ingest.py --confirm \\
    --endpoint http://<vip> \\
    --access-key <key> --secret-key <secret> \\
    --s3-bucket video-uploads --s3-bucket my-bucket-segments \\
    --vastdb-bucket processed-videos-db \\
    --vastdb-schema processed-videos-schema

  # Drop one table only:
  python cleanup_vss_ingest.py --confirm ... \\
    --vastdb-table processed-videos-collection
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Iterable, List

import boto3
import vastdb
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

DELETE_BATCH_SIZE = 1000


def _normalize_endpoint(endpoint: str) -> str:
    endpoint = endpoint.strip()
    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"http://{endpoint}"
    return endpoint.rstrip("/")


def _s3_client(endpoint: str, access_key: str, secret_key: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        verify=False,
    )


def _list_all_keys(s3, bucket: str) -> List[str]:
    keys: List[str] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        keys.extend(obj["Key"] for obj in page.get("Contents", []))
    return keys


def _delete_keys(s3, bucket: str, keys: Iterable[str]) -> int:
    deleted = 0
    batch: List[dict] = []
    for key in keys:
        batch.append({"Key": key})
        if len(batch) >= DELETE_BATCH_SIZE:
            s3.delete_objects(Bucket=bucket, Delete={"Objects": batch, "Quiet": True})
            deleted += len(batch)
            batch = []
    if batch:
        s3.delete_objects(Bucket=bucket, Delete={"Objects": batch, "Quiet": True})
        deleted += len(batch)
    return deleted


def cleanup_s3_buckets(
    endpoint: str,
    access_key: str,
    secret_key: str,
    buckets: List[str],
) -> None:
    s3 = _s3_client(endpoint, access_key, secret_key)
    for bucket in buckets:
        log.info("S3: listing objects in s3://%s/", bucket)
        try:
            keys = _list_all_keys(s3, bucket)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchBucket", "404"):
                log.warning("S3: bucket not found, skipping: %s", bucket)
                continue
            raise

        if not keys:
            log.info("S3: bucket already empty: %s", bucket)
            continue

        log.info("S3: deleting %d object(s) from %s", len(keys), bucket)
        deleted = _delete_keys(s3, bucket, keys)
        log.info("S3: deleted %d object(s) from %s", deleted, bucket)


def cleanup_vastdb_tables(
    endpoint: str,
    access_key: str,
    secret_key: str,
    vastdb_bucket: str,
    vastdb_schema: str,
    tables: List[str] | None,
) -> None:
    session = vastdb.connect(
        endpoint=endpoint,
        access=access_key,
        secret=secret_key,
        ssl_verify=False,
    )

    with session.transaction() as tx:
        bucket = tx.bucket(vastdb_bucket)
        schema = bucket.schema(vastdb_schema, fail_if_missing=False)
        if schema is None:
            log.warning(
                "VastDB: schema not found: %s/%s",
                vastdb_bucket,
                vastdb_schema,
            )
            return

        if tables:
            target_tables = tables
        else:
            target_tables = schema.tablenames()
            log.info(
                "VastDB: dropping all %d table(s) in %s/%s",
                len(target_tables),
                vastdb_bucket,
                vastdb_schema,
            )

        if not target_tables:
            log.info("VastDB: no tables to drop in %s/%s", vastdb_bucket, vastdb_schema)
            return

        for name in target_tables:
            table = schema.table(name, fail_if_missing=False)
            if table is None:
                log.warning("VastDB: table not found, skipping: %s", name)
                continue
            log.info("VastDB: dropping table %s/%s/%s", vastdb_bucket, vastdb_schema, name)
            table.drop()
            log.info("VastDB: dropped %s", name)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean S3 buckets and drop VastDB tables before a new VSS ingest.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required. Acknowledge destructive cleanup.",
    )
    parser.add_argument(
        "--endpoint",
        required=True,
        help="VIP / S3 / VastDB endpoint (e.g. http://10.0.0.1 or https://vip.example)",
    )
    parser.add_argument("--access-key", required=True, help="S3 and VastDB access key")
    parser.add_argument("--secret-key", required=True, help="S3 and VastDB secret key")
    parser.add_argument(
        "--s3-bucket",
        action="append",
        default=[],
        dest="s3_buckets",
        metavar="BUCKET",
        help="S3 bucket to empty (repeatable)",
    )
    parser.add_argument("--vastdb-bucket", help="VastDB database bucket name")
    parser.add_argument("--vastdb-schema", help="VastDB schema name")
    parser.add_argument(
        "--vastdb-table",
        action="append",
        default=[],
        dest="vastdb_tables",
        metavar="TABLE",
        help="Drop only this table (repeatable). Omit to drop all tables in the schema.",
    )
    parser.add_argument(
        "--skip-s3",
        action="store_true",
        help="Only run VastDB cleanup",
    )
    parser.add_argument(
        "--skip-vastdb",
        action="store_true",
        help="Only run S3 cleanup",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.confirm:
        log.error("Refusing to run without --confirm")
        return 1

    endpoint = _normalize_endpoint(args.endpoint)
    has_s3 = bool(args.s3_buckets) and not args.skip_s3
    has_vdb = bool(args.vastdb_bucket or args.vastdb_schema or args.vastdb_tables) and not args.skip_vastdb

    if args.vastdb_tables and (not args.vastdb_bucket or not args.vastdb_schema):
        log.error("--vastdb-table requires --vastdb-bucket and --vastdb-schema")
        return 1
    if (args.vastdb_bucket or args.vastdb_schema) and not (args.vastdb_bucket and args.vastdb_schema):
        log.error("--vastdb-bucket and --vastdb-schema must be provided together")
        return 1

    if not has_s3 and not has_vdb:
        log.error("Nothing to do: pass --s3-bucket and/or --vastdb-bucket + --vastdb-schema")
        return 1

    if has_s3:
        cleanup_s3_buckets(endpoint, args.access_key, args.secret_key, args.s3_buckets)

    if has_vdb:
        tables = args.vastdb_tables or None
        cleanup_vastdb_tables(
            endpoint,
            args.access_key,
            args.secret_key,
            args.vastdb_bucket,
            args.vastdb_schema,
            tables,
        )

    log.info("Cleanup complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
