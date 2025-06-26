"""
S3-compatible storage backend (AWS S3, MinIO, etc.)
"""
from typing import AsyncIterator, Dict, Any, List
import os
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError
import aioboto3

from storage.base import StorageBackend


class S3StorageBackend(StorageBackend):
    """Storage backend for S3-compatible services."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Extract configuration
        self.endpoint = config.get("endpoint", "https://s3.amazonaws.com")
        self.region = config.get("region", "us-east-1")
        self.bucket = config.get("bucket")
        self.access_key = config.get("access_key") or os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_key = config.get("secret_key") or os.getenv("AWS_SECRET_ACCESS_KEY")
        self.path_style = config.get("path_style", False)
        self.verify_ssl = config.get("verify_ssl", True)
        
        if not self.bucket:
            raise ValueError("S3 backend requires 'bucket' configuration")
        
        # Create session
        self.session = aioboto3.Session(
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
        )
        
        # S3 configuration
        self.s3_config = {
            "endpoint_url": self.endpoint if self.endpoint != "https://s3.amazonaws.com" else None,
            "use_ssl": self.endpoint.startswith("https"),
            "verify": self.verify_ssl,
            "region_name": self.region,
        }
        
        if self.path_style:
            self.s3_config["config"] = boto3.session.Config(
                s3={"addressing_style": "path"}
            )
    
    async def exists(self, path: str) -> bool:
        """Check if object exists in S3."""
        async with self.session.client("s3", **self.s3_config) as s3:
            try:
                await s3.head_object(Bucket=self.bucket, Key=path)
                return True
            except ClientError as e:
                if e.response["Error"]["Code"] == "404":
                    return False
                raise
    
    async def read(self, path: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Read object from S3 in chunks."""
        async with self.session.client("s3", **self.s3_config) as s3:
            try:
                response = await s3.get_object(Bucket=self.bucket, Key=path)
                
                async with response["Body"] as stream:
                    while True:
                        chunk = await stream.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
                        
            except ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchKey":
                    raise FileNotFoundError(f"Object not found: {path}")
                raise
    
    async def write(self, path: str, content: AsyncIterator[bytes]) -> int:
        """Write content to S3 using multipart upload for large files."""
        async with self.session.client("s3", **self.s3_config) as s3:
            # For small files, use simple upload
            # For large files, use multipart upload
            chunks = []
            total_size = 0
            
            async for chunk in content:
                chunks.append(chunk)
                total_size += len(chunk)
                
                # If accumulated size > 100MB, switch to multipart
                if total_size > 100 * 1024 * 1024:
                    return await self._multipart_upload(s3, path, chunks, content)
            
            # Simple upload for small files
            data = b"".join(chunks)
            await s3.put_object(
                Bucket=self.bucket,
                Key=path,
                Body=data,
            )
            
            return total_size
    
    async def _multipart_upload(
        self,
        s3_client,
        path: str,
        initial_chunks: List[bytes],
        content: AsyncIterator[bytes]
    ) -> int:
        """Handle multipart upload for large files."""
        # Initiate multipart upload
        response = await s3_client.create_multipart_upload(
            Bucket=self.bucket,
            Key=path,
        )
        upload_id = response["UploadId"]
        
        parts = []
        part_number = 1
        total_size = 0
        current_chunk = b"".join(initial_chunks)
        
        try:
            # Upload initial chunks
            if len(current_chunk) >= 5 * 1024 * 1024:  # 5MB minimum part size
                response = await s3_client.upload_part(
                    Bucket=self.bucket,
                    Key=path,
                    PartNumber=part_number,
                    UploadId=upload_id,
                    Body=current_chunk,
                )
                parts.append({
                    "ETag": response["ETag"],
                    "PartNumber": part_number,
                })
                total_size += len(current_chunk)
                part_number += 1
                current_chunk = b""
            
            # Continue with remaining content
            async for chunk in content:
                current_chunk += chunk
                
                if len(current_chunk) >= 5 * 1024 * 1024:
                    response = await s3_client.upload_part(
                        Bucket=self.bucket,
                        Key=path,
                        PartNumber=part_number,
                        UploadId=upload_id,
                        Body=current_chunk,
                    )
                    parts.append({
                        "ETag": response["ETag"],
                        "PartNumber": part_number,
                    })
                    total_size += len(current_chunk)
                    part_number += 1
                    current_chunk = b""
            
            # Upload final part if any
            if current_chunk:
                response = await s3_client.upload_part(
                    Bucket=self.bucket,
                    Key=path,
                    PartNumber=part_number,
                    UploadId=upload_id,
                    Body=current_chunk,
                )
                parts.append({
                    "ETag": response["ETag"],
                    "PartNumber": part_number,
                })
                total_size += len(current_chunk)
            
            # Complete multipart upload
            await s3_client.complete_multipart_upload(
                Bucket=self.bucket,
                Key=path,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
            
            return total_size
            
        except Exception:
            # Abort multipart upload on error
            await s3_client.abort_multipart_upload(
                Bucket=self.bucket,
                Key=path,
                UploadId=upload_id,
            )
            raise
    
    async def delete(self, path: str) -> bool:
        """Delete object from S3."""
        async with self.session.client("s3", **self.s3_config) as s3:
            try:
                await s3.delete_object(Bucket=self.bucket, Key=path)
                return True
            except ClientError:
                return False
    
    async def list(self, prefix: str) -> List[str]:
        """List objects with given prefix."""
        objects = []
        
        async with self.session.client("s3", **self.s3_config) as s3:
            paginator = s3.get_paginator("list_objects_v2")
            
            async for page in paginator.paginate(
                Bucket=self.bucket,
                Prefix=prefix,
            ):
                if "Contents" in page:
                    for obj in page["Contents"]:
                        objects.append(obj["Key"])
        
        return objects
    
    async def stat(self, path: str) -> Dict[str, Any]:
        """Get object metadata."""
        async with self.session.client("s3", **self.s3_config) as s3:
            try:
                response = await s3.head_object(Bucket=self.bucket, Key=path)
                
                return {
                    "size": response["ContentLength"],
                    "modified": response["LastModified"].timestamp(),
                    "etag": response.get("ETag", "").strip('"'),
                    "content_type": response.get("ContentType"),
                    "metadata": response.get("Metadata", {}),
                }
            except ClientError as e:
                if e.response["Error"]["Code"] == "404":
                    raise FileNotFoundError(f"Object not found: {path}")
                raise
    
    async def move(self, src: str, dst: str) -> bool:
        """Move object within S3."""
        async with self.session.client("s3", **self.s3_config) as s3:
            try:
                # Copy object
                await s3.copy_object(
                    Bucket=self.bucket,
                    CopySource={"Bucket": self.bucket, "Key": src},
                    Key=dst,
                )
                
                # Delete original
                await s3.delete_object(Bucket=self.bucket, Key=src)
                
                return True
            except ClientError:
                return False
    
    async def copy(self, src: str, dst: str) -> bool:
        """Copy object within S3."""
        async with self.session.client("s3", **self.s3_config) as s3:
            try:
                await s3.copy_object(
                    Bucket=self.bucket,
                    CopySource={"Bucket": self.bucket, "Key": src},
                    Key=dst,
                )
                return True
            except ClientError:
                return False
    
    async def get_url(self, path: str, expires: int = 3600) -> str:
        """Generate presigned URL for direct access."""
        async with self.session.client("s3", **self.s3_config) as s3:
            url = await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": path},
                ExpiresIn=expires,
            )
            return url
    
    async def get_status(self) -> Dict[str, Any]:
        """Get backend status information."""
        async with self.session.client("s3", **self.s3_config) as s3:
            try:
                # Get bucket location
                location = await s3.get_bucket_location(Bucket=self.bucket)
                
                # Get bucket versioning
                versioning = await s3.get_bucket_versioning(Bucket=self.bucket)
                
                # Get approximate object count (first page only for performance)
                response = await s3.list_objects_v2(
                    Bucket=self.bucket,
                    MaxKeys=1000,
                )
                
                return {
                    "bucket": self.bucket,
                    "region": location.get("LocationConstraint") or "us-east-1",
                    "versioning": versioning.get("Status", "Disabled"),
                    "object_count": response.get("KeyCount", 0),
                    "is_truncated": response.get("IsTruncated", False),
                }
            except Exception as e:
                return {
                    "error": str(e),
                }