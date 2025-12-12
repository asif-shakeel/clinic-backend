import os
import boto3

session = boto3.session.Session()
s3 = session.client(
    service_name="s3",
    endpoint_url=os.environ["B2_ENDPOINT"],
    aws_access_key_id=os.environ["B2_KEY_ID"],
    aws_secret_access_key=os.environ["B2_APP_KEY"],
)

BUCKET = os.environ["B2_BUCKET"]


def upload_file(local_path, remote_path):
    s3.upload_file(local_path, BUCKET, remote_path)


def download_file(remote_path, local_path):
    s3.download_file(BUCKET, remote_path, local_path)
