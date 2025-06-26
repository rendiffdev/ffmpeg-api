#!/usr/bin/env python3
"""
Rendiff Setup Wizard - Interactive configuration tool
"""
import os
import sys
import yaml
import secrets
import subprocess
from pathlib import Path
from typing import Dict, Any
from rich.console import Console
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

class SetupWizard:
    """Interactive setup wizard for Rendiff configuration."""
    
    def __init__(self):
        self.config = {
            "version": "1.0.0",
            "storage": {
                "default_backend": "local",
                "backends": {},
                "policies": {
                    "input_backends": [],
                    "output_backends": [],
                    "retention": {"default": "7d"}
                }
            },
            "api": {
                "host": "0.0.0.0",
                "port": 8080,
                "workers": 4
            },
            "security": {
                "enable_api_keys": True,
                "api_keys": []
            },
            "resources": {
                "max_file_size": "10GB",
                "max_concurrent_jobs": 10,
                "enable_gpu": False
            }
        }
        self.env_vars = {}
        
    def run(self):
        """Run the setup wizard."""
        self.show_welcome()
        
        # Basic setup
        self.setup_deployment_type()
        self.setup_api_configuration()
        
        # Storage setup
        self.setup_storage()
        
        # Security setup
        self.setup_security()
        
        # Resource configuration
        self.setup_resources()
        
        # Advanced options
        if Confirm.ask("\n[cyan]Configure advanced options?[/cyan]", default=False):
            self.setup_advanced()
        
        # Review and save
        self.review_configuration()
        if Confirm.ask("\n[green]Save configuration?[/green]", default=True):
            self.save_configuration()
            self.initialize_system()
        
    def show_welcome(self):
        """Display welcome message."""
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]Rendiff FFmpeg API Setup Wizard[/bold cyan]\n\n"
            "This wizard will help you configure your Rendiff installation.\n"
            "Press Ctrl+C at any time to exit.",
            border_style="cyan"
        ))
        console.print()
        
    def setup_deployment_type(self):
        """Choose deployment type."""
        console.print("[bold]Deployment Configuration[/bold]\n")
        
        deployment_type = Prompt.ask(
            "Choose deployment type",
            choices=["docker", "kubernetes", "manual"],
            default="docker"
        )
        self.config["deployment_type"] = deployment_type
        
        if deployment_type == "docker":
            self.config["docker"] = {
                "compose_file": "docker-compose.yml",
                "profile": Prompt.ask(
                    "Docker profile",
                    choices=["minimal", "standard", "full"],
                    default="standard"
                )
            }
            
    def setup_api_configuration(self):
        """Configure API settings."""
        console.print("\n[bold]API Configuration[/bold]\n")
        
        self.config["api"]["host"] = Prompt.ask(
            "API bind address",
            default="0.0.0.0"
        )
        
        self.config["api"]["port"] = IntPrompt.ask(
            "API port",
            default=8080,
            show_default=True
        )
        
        self.config["api"]["workers"] = IntPrompt.ask(
            "Number of API workers",
            default=4,
            show_default=True
        )
        
        # External URL
        external_url = Prompt.ask(
            "External URL (for webhooks)",
            default=f"http://localhost:{self.config['api']['port']}"
        )
        self.config["api"]["external_url"] = external_url
        
    def setup_storage(self):
        """Configure storage backends."""
        console.print("\n[bold]Storage Configuration[/bold]\n")
        console.print("Configure one or more storage backends for input/output files.\n")
        
        backends = []
        
        # Always add local storage
        if Confirm.ask("Configure local storage?", default=True):
            backend = self.setup_local_storage()
            backends.append(backend)
            self.config["storage"]["backends"][backend["name"]] = backend
        
        # Additional backends
        while Confirm.ask("\nAdd another storage backend?", default=False):
            storage_type = Prompt.ask(
                "Storage type",
                choices=["nfs", "s3", "azure", "gcs", "minio"],
            )
            
            if storage_type == "nfs":
                backend = self.setup_nfs_storage()
            elif storage_type == "s3":
                backend = self.setup_s3_storage()
            elif storage_type == "azure":
                backend = self.setup_azure_storage()
            elif storage_type == "gcs":
                backend = self.setup_gcs_storage()
            elif storage_type == "minio":
                backend = self.setup_minio_storage()
            
            if backend:
                backends.append(backend)
                self.config["storage"]["backends"][backend["name"]] = backend
        
        # Select default backend
        if backends:
            backend_names = [b["name"] for b in backends]
            default_backend = Prompt.ask(
                "\nSelect default storage backend",
                choices=backend_names,
                default=backend_names[0]
            )
            self.config["storage"]["default_backend"] = default_backend
            
            # Configure input/output policies
            console.print("\nSelect which backends can be used for input files:")
            for name in backend_names:
                if Confirm.ask(f"  Allow '{name}' for input?", default=True):
                    self.config["storage"]["policies"]["input_backends"].append(name)
            
            console.print("\nSelect which backends can be used for output files:")
            for name in backend_names:
                if Confirm.ask(f"  Allow '{name}' for output?", default=True):
                    self.config["storage"]["policies"]["output_backends"].append(name)
    
    def setup_local_storage(self) -> Dict[str, Any]:
        """Configure local filesystem storage."""
        console.print("\n[cyan]Local Storage Configuration[/cyan]")
        
        name = Prompt.ask("Backend name", default="local")
        
        # Get storage path
        while True:
            path = Prompt.ask(
                "Storage directory path",
                default="/var/lib/rendiff/storage"
            )
            
            path_obj = Path(path)
            
            # Check if path exists or can be created
            if path_obj.exists():
                if not path_obj.is_dir():
                    console.print(f"[red]Error: {path} exists but is not a directory[/red]")
                    continue
                    
                # Check permissions
                if not os.access(path, os.W_OK):
                    console.print(f"[yellow]Warning: No write permission for {path}[/yellow]")
                    if not Confirm.ask("Continue anyway?", default=False):
                        continue
                break
            else:
                if Confirm.ask(f"Directory {path} doesn't exist. Create it?", default=True):
                    try:
                        path_obj.mkdir(parents=True, exist_ok=True)
                        console.print(f"[green]Created directory: {path}[/green]")
                        break
                    except Exception as e:
                        console.print(f"[red]Error creating directory: {e}[/red]")
                        continue
        
        return {
            "name": name,
            "type": "filesystem",
            "base_path": str(path_obj),
            "permissions": "0755"
        }
    
    def setup_nfs_storage(self) -> Dict[str, Any]:
        """Configure NFS storage."""
        console.print("\n[cyan]NFS Storage Configuration[/cyan]")
        
        name = Prompt.ask("Backend name", default="nfs")
        server = Prompt.ask("NFS server address")
        export_path = Prompt.ask("Export path", default="/")
        
        # Test NFS connection
        if Confirm.ask("Test NFS connection?", default=True):
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Testing NFS connection...", total=None)
                
                # Try to mount temporarily
                test_mount = f"/tmp/rendiff_nfs_test_{secrets.token_hex(4)}"
                try:
                    os.makedirs(test_mount, exist_ok=True)
                    result = subprocess.run(
                        ["mount", "-t", "nfs", f"{server}:{export_path}", test_mount],
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode == 0:
                        subprocess.run(["umount", test_mount], capture_output=True)
                        console.print("[green]✓ NFS connection successful[/green]")
                    else:
                        console.print(f"[yellow]Warning: Could not mount NFS: {result.stderr}[/yellow]")
                finally:
                    try:
                        os.rmdir(test_mount)
                    except:
                        pass
        
        return {
            "name": name,
            "type": "network",
            "protocol": "nfs",
            "server": server,
            "export": export_path,
            "mount_options": "rw,sync,hard,intr"
        }
    
    def setup_s3_storage(self) -> Dict[str, Any]:
        """Configure S3 storage."""
        console.print("\n[cyan]S3 Storage Configuration[/cyan]")
        
        name = Prompt.ask("Backend name", default="s3")
        
        # AWS or S3-compatible
        is_aws = Confirm.ask("Is this AWS S3?", default=True)
        
        if is_aws:
            endpoint = "https://s3.amazonaws.com"
            region = Prompt.ask("AWS region", default="us-east-1")
        else:
            endpoint = Prompt.ask("S3 endpoint URL")
            region = Prompt.ask("Region", default="us-east-1")
        
        bucket = Prompt.ask("Bucket name")
        
        # Authentication
        console.print("\n[yellow]S3 Authentication[/yellow]")
        auth_method = Prompt.ask(
            "Authentication method",
            choices=["access_key", "iam_role", "env_vars"],
            default="access_key"
        )
        
        access_key = None
        secret_key = None
        
        if auth_method == "access_key":
            access_key = Prompt.ask("Access key ID")
            secret_key = Prompt.ask("Secret access key", password=True)
            
            # Store in environment variables
            self.env_vars[f"S3_{name.upper()}_ACCESS_KEY"] = access_key
            self.env_vars[f"S3_{name.upper()}_SECRET_KEY"] = secret_key
            
            # Test connection
            if Confirm.ask("Test S3 connection?", default=True):
                if self.test_s3_connection(endpoint, region, bucket, access_key, secret_key):
                    console.print("[green]✓ S3 connection successful[/green]")
                else:
                    console.print("[yellow]Warning: Could not connect to S3[/yellow]")
        
        config = {
            "name": name,
            "type": "s3",
            "endpoint": endpoint,
            "region": region,
            "bucket": bucket,
            "path_style": not is_aws
        }
        
        if auth_method == "access_key":
            config["access_key"] = f"${{{f'S3_{name.upper()}_ACCESS_KEY'}}}"
            config["secret_key"] = f"${{{f'S3_{name.upper()}_SECRET_KEY'}}}"
        elif auth_method == "iam_role":
            config["use_iam_role"] = True
            
        return config
    
    def setup_azure_storage(self) -> Dict[str, Any]:
        """Configure Azure Blob Storage."""
        console.print("\n[cyan]Azure Storage Configuration[/cyan]")
        
        name = Prompt.ask("Backend name", default="azure")
        account_name = Prompt.ask("Storage account name")
        container = Prompt.ask("Container name")
        
        # Authentication
        console.print("\n[yellow]Azure Authentication[/yellow]")
        auth_method = Prompt.ask(
            "Authentication method",
            choices=["account_key", "sas_token", "managed_identity"],
            default="account_key"
        )
        
        if auth_method == "account_key":
            account_key = Prompt.ask("Account key", password=True)
            self.env_vars[f"AZURE_{name.upper()}_KEY"] = account_key
            
            # Test connection
            if Confirm.ask("Test Azure connection?", default=True):
                if self.test_azure_connection(account_name, account_key, container):
                    console.print("[green]✓ Azure connection successful[/green]")
                else:
                    console.print("[yellow]Warning: Could not connect to Azure[/yellow]")
        
        config = {
            "name": name,
            "type": "azure",
            "account_name": account_name,
            "container": container
        }
        
        if auth_method == "account_key":
            config["account_key"] = f"${{{f'AZURE_{name.upper()}_KEY'}}}"
        elif auth_method == "sas_token":
            sas_token = Prompt.ask("SAS token", password=True)
            self.env_vars[f"AZURE_{name.upper()}_SAS"] = sas_token
            config["sas_token"] = f"${{{f'AZURE_{name.upper()}_SAS'}}}"
        elif auth_method == "managed_identity":
            config["use_managed_identity"] = True
            
        return config
    
    def setup_gcs_storage(self) -> Dict[str, Any]:
        """Configure Google Cloud Storage."""
        console.print("\n[cyan]Google Cloud Storage Configuration[/cyan]")
        
        name = Prompt.ask("Backend name", default="gcs")
        project_id = Prompt.ask("GCP project ID")
        bucket = Prompt.ask("Bucket name")
        
        # Authentication
        console.print("\n[yellow]GCS Authentication[/yellow]")
        auth_method = Prompt.ask(
            "Authentication method",
            choices=["service_account", "application_default"],
            default="service_account"
        )
        
        config = {
            "name": name,
            "type": "gcs",
            "project_id": project_id,
            "bucket": bucket
        }
        
        if auth_method == "service_account":
            key_file = Prompt.ask("Service account key file path")
            
            # Copy key file to config directory
            if os.path.exists(key_file):
                dest_path = f"/etc/rendiff/gcs_{name}_key.json"
                self.config.setdefault("files_to_copy", []).append({
                    "src": key_file,
                    "dst": dest_path
                })
                config["credentials_file"] = dest_path
            else:
                console.print("[yellow]Warning: Key file not found[/yellow]")
        else:
            config["use_default_credentials"] = True
            
        return config
    
    def setup_minio_storage(self) -> Dict[str, Any]:
        """Configure MinIO storage."""
        console.print("\n[cyan]MinIO Storage Configuration[/cyan]")
        
        name = Prompt.ask("Backend name", default="minio")
        endpoint = Prompt.ask("MinIO endpoint", default="http://localhost:9000")
        bucket = Prompt.ask("Bucket name", default="rendiff")
        
        access_key = Prompt.ask("Access key", default="minioadmin")
        secret_key = Prompt.ask("Secret key", password=True, default="minioadmin")
        
        self.env_vars[f"MINIO_{name.upper()}_ACCESS_KEY"] = access_key
        self.env_vars[f"MINIO_{name.upper()}_SECRET_KEY"] = secret_key
        
        return {
            "name": name,
            "type": "s3",
            "endpoint": endpoint,
            "bucket": bucket,
            "access_key": f"${{{f'MINIO_{name.upper()}_ACCESS_KEY'}}}", 
            "secret_key": f"${{{f'MINIO_{name.upper()}_SECRET_KEY'}}}",
            "path_style": True,
            "verify_ssl": endpoint.startswith("https")
        }
    
    def setup_security(self):
        """Configure security settings."""
        console.print("\n[bold]Security Configuration[/bold]\n")
        
        # API Keys
        self.config["security"]["enable_api_keys"] = Confirm.ask(
            "Enable API key authentication?",
            default=True
        )
        
        if self.config["security"]["enable_api_keys"]:
            # Generate default API key
            default_key = secrets.token_urlsafe(32)
            self.config["security"]["api_keys"].append({
                "name": "default",
                "key": default_key,
                "role": "admin",
                "created_at": "setup"
            })
            
            console.print(f"\n[green]Generated default API key:[/green] {default_key}")
            console.print("[yellow]Save this key securely - it won't be shown again![/yellow]")
            
            if Confirm.ask("\nAdd additional API keys?", default=False):
                while True:
                    name = Prompt.ask("Key name")
                    role = Prompt.ask("Role", choices=["admin", "user"], default="user")
                    key = secrets.token_urlsafe(32)
                    
                    self.config["security"]["api_keys"].append({
                        "name": name,
                        "key": key,
                        "role": role,
                        "created_at": "setup"
                    })
                    
                    console.print(f"[green]Generated key '{name}':[/green] {key}")
                    
                    if not Confirm.ask("Add another key?", default=False):
                        break
        
        # IP Whitelisting
        if Confirm.ask("\nEnable IP whitelisting?", default=False):
            self.config["security"]["enable_ip_whitelist"] = True
            self.config["security"]["ip_whitelist"] = []
            
            console.print("Enter IP addresses or CIDR ranges (one per line, empty to finish):")
            while True:
                ip = Prompt.ask("IP/CIDR", default="")
                if not ip:
                    break
                self.config["security"]["ip_whitelist"].append(ip)
    
    def setup_resources(self):
        """Configure resource limits."""
        console.print("\n[bold]Resource Configuration[/bold]\n")
        
        # File size limits
        max_size = Prompt.ask(
            "Maximum file size",
            default="10GB",
            choices=["1GB", "5GB", "10GB", "50GB", "100GB", "unlimited"]
        )
        self.config["resources"]["max_file_size"] = max_size
        
        # Concurrent jobs
        self.config["resources"]["max_concurrent_jobs"] = IntPrompt.ask(
            "Maximum concurrent jobs per API key",
            default=10,
            show_default=True
        )
        
        # Worker configuration
        cpu_workers = IntPrompt.ask(
            "Number of CPU workers",
            default=4,
            show_default=True
        )
        self.config["resources"]["cpu_workers"] = cpu_workers
        
        # GPU support
        if Confirm.ask("\nEnable GPU acceleration?", default=False):
            self.config["resources"]["enable_gpu"] = True
            self.config["resources"]["gpu_workers"] = IntPrompt.ask(
                "Number of GPU workers",
                default=1,
                show_default=True
            )
            
            # Check for NVIDIA GPU
            if self.check_nvidia_gpu():
                console.print("[green]✓ NVIDIA GPU detected[/green]")
            else:
                console.print("[yellow]Warning: No NVIDIA GPU detected[/yellow]")
    
    def setup_advanced(self):
        """Configure advanced options."""
        console.print("\n[bold]Advanced Configuration[/bold]\n")
        
        # Database
        if Confirm.ask("Configure external database?", default=False):
            db_type = Prompt.ask(
                "Database type",
                choices=["postgresql", "mysql"],
                default="postgresql"
            )
            
            if db_type == "postgresql":
                host = Prompt.ask("Database host", default="localhost")
                port = IntPrompt.ask("Database port", default=5432)
                database = Prompt.ask("Database name", default="rendiff")
                username = Prompt.ask("Database user", default="rendiff")
                password = Prompt.ask("Database password", password=True)
                
                db_url = f"postgresql://{username}:{password}@{host}:{port}/{database}"
                self.env_vars["DATABASE_URL"] = db_url
        
        # Monitoring
        if Confirm.ask("\nEnable monitoring?", default=True):
            self.config["monitoring"] = {
                "prometheus": True,
                "grafana": Confirm.ask("Enable Grafana dashboards?", default=True)
            }
        
        # Webhooks
        if Confirm.ask("\nConfigure webhook settings?", default=False):
            self.config["webhooks"] = {
                "timeout": IntPrompt.ask("Webhook timeout (seconds)", default=30),
                "max_retries": IntPrompt.ask("Maximum retries", default=3),
                "retry_delay": IntPrompt.ask("Retry delay (seconds)", default=60)
            }
    
    def test_s3_connection(self, endpoint: str, region: str, bucket: str, 
                          access_key: str, secret_key: str) -> bool:
        """Test S3 connection."""
        try:
            if endpoint == "https://s3.amazonaws.com":
                s3 = boto3.client(
                    's3',
                    region_name=region,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key
                )
            else:
                s3 = boto3.client(
                    's3',
                    endpoint_url=endpoint,
                    region_name=region,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key
                )
            
            s3.head_bucket(Bucket=bucket)
            return True
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            return False
    
    def test_azure_connection(self, account_name: str, account_key: str, 
                            container: str) -> bool:
        """Test Azure connection."""
        try:
            blob_service = BlobServiceClient(
                account_url=f"https://{account_name}.blob.core.windows.net",
                credential=account_key
            )
            
            container_client = blob_service.get_container_client(container)
            container_client.get_container_properties()
            return True
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            return False
    
    def check_nvidia_gpu(self) -> bool:
        """Check if NVIDIA GPU is available."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def review_configuration(self):
        """Review configuration before saving."""
        console.print("\n[bold]Configuration Review[/bold]\n")
        
        # API Configuration
        table = Table(title="API Configuration", show_header=False)
        table.add_column("Setting", style="cyan")
        table.add_column("Value")
        
        table.add_row("Host", self.config["api"]["host"])
        table.add_row("Port", str(self.config["api"]["port"]))
        table.add_row("Workers", str(self.config["api"]["workers"]))
        table.add_row("External URL", self.config["api"]["external_url"])
        
        console.print(table)
        
        # Storage Configuration
        table = Table(title="\nStorage Configuration")
        table.add_column("Backend", style="cyan")
        table.add_column("Type")
        table.add_column("Location")
        table.add_column("Input", justify="center")
        table.add_column("Output", justify="center")
        
        for name, backend in self.config["storage"]["backends"].items():
            location = backend.get("base_path", backend.get("bucket", backend.get("server", "N/A")))
            input_allowed = "✓" if name in self.config["storage"]["policies"]["input_backends"] else "✗"
            output_allowed = "✓" if name in self.config["storage"]["policies"]["output_backends"] else "✗"
            
            table.add_row(
                name,
                backend["type"],
                location,
                input_allowed,
                output_allowed
            )
        
        console.print(table)
        
        # Security Configuration
        if self.config["security"]["enable_api_keys"]:
            console.print(f"\n[cyan]API Keys:[/cyan] {len(self.config['security']['api_keys'])} configured")
        
        # Resource Configuration
        console.print(f"\n[cyan]Resource Limits:[/cyan]")
        console.print(f"  Max file size: {self.config['resources']['max_file_size']}")
        console.print(f"  Max concurrent jobs: {self.config['resources']['max_concurrent_jobs']}")
        console.print(f"  CPU workers: {self.config['resources'].get('cpu_workers', 4)}")
        if self.config["resources"]["enable_gpu"]:
            console.print(f"  GPU workers: {self.config['resources'].get('gpu_workers', 1)}")
    
    def save_configuration(self):
        """Save configuration files."""
        console.print("\n[bold]Saving Configuration[/bold]\n")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Create config directory
            task = progress.add_task("Creating directories...", total=4)
            
            os.makedirs("/etc/rendiff", exist_ok=True)
            progress.update(task, advance=1)
            
            # Save storage configuration
            progress.update(task, description="Saving storage configuration...")
            storage_config = {
                "storage": self.config["storage"]
            }
            
            with open("/etc/rendiff/storage.yml", "w") as f:
                yaml.dump(storage_config, f, default_flow_style=False)
            progress.update(task, advance=1)
            
            # Save environment variables
            progress.update(task, description="Saving environment variables...")
            with open("/etc/rendiff/.env", "w") as f:
                f.write("# Rendiff Configuration\n")
                f.write("# Generated by setup wizard\n\n")
                
                # API configuration
                f.write(f"API_HOST={self.config['api']['host']}\n")
                f.write(f"API_PORT={self.config['api']['port']}\n")
                f.write(f"API_WORKERS={self.config['api']['workers']}\n")
                f.write(f"EXTERNAL_URL={self.config['api']['external_url']}\n\n")
                
                # Storage
                f.write("STORAGE_CONFIG=/etc/rendiff/storage.yml\n\n")
                
                # Security
                f.write(f"ENABLE_API_KEYS={str(self.config['security']['enable_api_keys']).lower()}\n")
                if self.config['security'].get('enable_ip_whitelist'):
                    f.write("ENABLE_IP_WHITELIST=true\n")
                    f.write(f"IP_WHITELIST={','.join(self.config['security']['ip_whitelist'])}\n")
                f.write("\n")
                
                # Resources
                f.write(f"MAX_UPLOAD_SIZE={self.parse_size(self.config['resources']['max_file_size'])}\n")
                f.write(f"MAX_CONCURRENT_JOBS_PER_KEY={self.config['resources']['max_concurrent_jobs']}\n\n")
                
                # Custom environment variables
                for key, value in self.env_vars.items():
                    f.write(f"{key}={value}\n")
            
            progress.update(task, advance=1)
            
            # Save API keys
            if self.config["security"]["enable_api_keys"]:
                progress.update(task, description="Saving API keys...")
                
                keys_data = {
                    "api_keys": self.config["security"]["api_keys"]
                }
                
                with open("/etc/rendiff/api_keys.json", "w") as f:
                    json.dump(keys_data, f, indent=2)
                
                # Secure the file
                os.chmod("/etc/rendiff/api_keys.json", 0o600)
            
            progress.update(task, advance=1)
            
            # Copy additional files
            if "files_to_copy" in self.config:
                for file_info in self.config["files_to_copy"]:
                    shutil.copy2(file_info["src"], file_info["dst"])
                    os.chmod(file_info["dst"], 0o600)
            
            progress.update(task, description="Configuration saved!")
        
        console.print("\n[green]✓ Configuration saved successfully![/green]")
    
    def initialize_system(self):
        """Initialize the system with the new configuration."""
        console.print("\n[bold]Initializing System[/bold]\n")
        
        if Confirm.ask("Start Rendiff services now?", default=True):
            deployment_type = self.config.get("deployment_type", "docker")
            
            if deployment_type == "docker":
                # Generate docker-compose override
                self.generate_docker_override()
                
                # Start services
                console.print("\nStarting services...")
                try:
                    subprocess.run(
                        ["docker-compose", "up", "-d"],
                        check=True,
                        cwd="/opt/rendiff"
                    )
                    console.print("[green]✓ Services started successfully![/green]")
                    
                    # Show access information
                    self.show_access_info()
                except subprocess.CalledProcessError as e:
                    console.print(f"[red]Error starting services: {e}[/red]")
                    console.print("You can start services manually with: docker-compose up -d")
    
    def generate_docker_override(self):
        """Generate docker-compose.override.yml based on configuration."""
        override = {
            "version": "3.8",
            "services": {}
        }
        
        # Add GPU service if enabled
        if self.config["resources"]["enable_gpu"]:
            override["services"]["worker-gpu"] = {
                "profiles": [],  # Remove profile to always start
                "deploy": {
                    "replicas": self.config["resources"].get("gpu_workers", 1)
                }
            }
        
        # Adjust CPU workers
        override["services"]["worker-cpu"] = {
            "deploy": {
                "replicas": self.config["resources"].get("cpu_workers", 4)
            }
        }
        
        # Add monitoring if enabled
        if self.config.get("monitoring", {}).get("prometheus"):
            override["services"]["prometheus"] = {"profiles": []}
            
        if self.config.get("monitoring", {}).get("grafana"):
            override["services"]["grafana"] = {"profiles": []}
        
        # Save override file
        with open("/opt/rendiff/docker-compose.override.yml", "w") as f:
            yaml.dump(override, f, default_flow_style=False)
    
    def show_access_info(self):
        """Show access information after setup."""
        console.print("\n" + "="*50)
        console.print("[bold green]Rendiff is ready![/bold green]\n")
        
        console.print("[cyan]Access Information:[/cyan]")
        console.print(f"  API URL: {self.config['api']['external_url']}")
        console.print(f"  API Docs: {self.config['api']['external_url']}/docs")
        console.print(f"  Health Check: {self.config['api']['external_url']}/api/v1/health")
        
        if self.config.get("monitoring", {}).get("grafana"):
            console.print(f"  Grafana: http://localhost:3000 (admin/admin)")
        
        if self.config["security"]["enable_api_keys"]:
            console.print("\n[cyan]API Keys:[/cyan]")
            for key_info in self.config["security"]["api_keys"]:
                console.print(f"  {key_info['name']}: {key_info['key']}")
        
        console.print("\n[yellow]Next steps:[/yellow]")
        console.print("  1. Test the API: curl http://localhost:8080/api/v1/health")
        console.print("  2. Create your first job using the API")
        console.print("  3. Monitor logs: docker-compose logs -f")
        console.print("\n" + "="*50)
    
    def parse_size(self, size_str: str) -> int:
        """Parse size string to bytes."""
        if size_str == "unlimited":
            return 0
        
        units = {"GB": 1024**3, "MB": 1024**2, "KB": 1024}
        for unit, multiplier in units.items():
            if size_str.endswith(unit):
                return int(size_str[:-2]) * multiplier
        
        return int(size_str)


def main():
    """Main entry point."""
    try:
        wizard = SetupWizard()
        wizard.run()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Setup cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()