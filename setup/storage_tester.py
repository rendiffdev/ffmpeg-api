"""
Storage backend connection testing utilities
"""
import os
import subprocess
import tempfile
from typing import Dict, Any, Optional
import boto3
from rich.console import Console

console = Console()


class StorageTester:
    """Test connections to various storage backends."""
    
    def test_s3(self, endpoint: str, bucket: str, access_key: str, 
                secret_key: str, region: str = "us-east-1") -> bool:
        """Test S3 connection."""
        try:
            if endpoint == "https://s3.amazonaws.com":
                s3_client = boto3.client(
                    's3',
                    region_name=region,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key
                )
            else:
                s3_client = boto3.client(
                    's3',
                    endpoint_url=endpoint,
                    region_name=region,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key
                )
            
            # Try to list objects in bucket
            s3_client.head_bucket(Bucket=bucket)
            return True
            
        except Exception as e:
            console.print(f"[red]S3 connection failed: {e}[/red]")
            return False
    
    def test_minio(self, endpoint: str, bucket: str, access_key: str, 
                   secret_key: str) -> bool:
        """Test MinIO connection."""
        try:
            s3_client = boto3.client(
                's3',
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                use_ssl=endpoint.startswith('https')
            )
            
            s3_client.head_bucket(Bucket=bucket)
            return True
            
        except Exception as e:
            console.print(f"[red]MinIO connection failed: {e}[/red]")
            return False
    
    def test_azure(self, account_name: str, container: str, account_key: str) -> bool:
        """Test Azure Blob Storage connection."""
        try:
            from azure.storage.blob import BlobServiceClient
            
            blob_service = BlobServiceClient(
                account_url=f"https://{account_name}.blob.core.windows.net",
                credential=account_key
            )
            
            container_client = blob_service.get_container_client(container)
            container_client.get_container_properties()
            return True
            
        except Exception as e:
            console.print(f"[red]Azure connection failed: {e}[/red]")
            return False
    
    def test_gcs(self, project_id: str, bucket: str, credentials_file: str) -> bool:
        """Test Google Cloud Storage connection."""
        try:
            from google.cloud import storage
            
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_file
            client = storage.Client(project=project_id)
            bucket_obj = client.bucket(bucket)
            bucket_obj.reload()
            return True
            
        except Exception as e:
            console.print(f"[red]GCS connection failed: {e}[/red]")
            return False
    
    def test_nfs(self, server: str, export_path: str) -> bool:
        """Test NFS connection."""
        try:
            # Create temporary mount point
            test_mount = tempfile.mkdtemp(prefix="rendiff_nfs_test_")
            
            try:
                # Try to mount
                result = subprocess.run([
                    "mount", "-t", "nfs", "-o", "ro,timeo=10",
                    f"{server}:{export_path}", test_mount
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    # Successfully mounted, now unmount
                    subprocess.run(["umount", test_mount], capture_output=True)
                    return True
                else:
                    console.print(f"[red]NFS mount failed: {result.stderr}[/red]")
                    return False
                    
            finally:
                # Clean up
                try:
                    os.rmdir(test_mount)
                except:
                    pass
                    
        except Exception as e:
            console.print(f"[red]NFS test failed: {e}[/red]")
            return False
    
    def test_local_path(self, path: str) -> Dict[str, Any]:
        """Test local filesystem path."""
        result = {
            "exists": False,
            "writable": False,
            "readable": False,
            "space_available": 0,
            "error": None
        }
        
        try:
            path_obj = Path(path)
            
            # Check if exists
            result["exists"] = path_obj.exists()
            
            if not result["exists"]:
                # Try to create
                path_obj.mkdir(parents=True, exist_ok=True)
                result["exists"] = True
            
            # Check permissions
            result["readable"] = os.access(path, os.R_OK)
            result["writable"] = os.access(path, os.W_OK)
            
            # Check available space
            if result["exists"]:
                stat_result = os.statvfs(path)
                result["space_available"] = stat_result.f_bavail * stat_result.f_frsize
            
        except Exception as e:
            result["error"] = str(e)
        
        return result