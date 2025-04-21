import boto3
import os
from urllib.parse import urlparse
from app.config import settings

s3 = boto3.client('s3',
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION
)

def fetch(loc):
    if loc.local_path:
        return loc.local_path
    if loc.s3_path:
        p = urlparse(loc.s3_path)
        out = f"/tmp/{os.path.basename(p.path)}"
        s3.download_file(p.netloc, p.path.lstrip('/'), out)
        return out
    raise ValueError("Invalid location")

def upload(local, loc):
    if loc.s3_path:
        p = urlparse(loc.s3_path)
        s3.upload_file(local, p.netloc, p.path.lstrip('/'))