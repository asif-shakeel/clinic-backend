import os
import boto3
from botocore.config import Config

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["B2_ENDPOINT"],
    aws_access_key_id=os.environ["B2_KEY_ID"],
    aws_secret_access_key=os.environ["B2_APP_KEY"],
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},  # 🔴 REQUIRED FOR BACKBLAZE
    ),
)

BUCKET = os.environ["B2_BUCKET"]


def upload_file(local_path, remote_path):
    s3.upload_file(local_path, BUCKET, remote_path)


def download_file(remote_path, local_path):
    s3.download_file(BUCKET, remote_path, local_path)


def generate_signed_url(object_key: str, expires_seconds: int = 3600) -> str:
    return s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": BUCKET,
            "Key": object_key,
        },
        ExpiresIn=expires_seconds,
    )

def delete_file(remote_path):
    s3.delete_object(Bucket=BUCKET, Key=remote_path)
