#!/usr/bin/env python3
"""
Rendiff Update & Maintenance System
Safe updates with backup and rollback capabilities
"""
import os
import sys
import json
import shutil
import subprocess
import tempfile
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import click
import requests
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Confirm

console = Console()

class RendiffUpdater:
    """Comprehensive update and maintenance system."""
    
    def __init__(self, base_path: str = None):
        if base_path:
            self.base_path = Path(base_path)
        else:
            self.base_path = Path.cwd()
        
        self.backup_path = self.base_path / "backups"
        self.config_path = self.base_path / "config"
        self.data_path = self.base_path / "data"
        
        # Ensure directories exist
        self.backup_path.mkdir(parents=True, exist_ok=True)
        
        self.current_version = self._get_current_version()
        
    def _get_current_version(self) -> str:
        """Get current version."""
        version_file = self.base_path / "VERSION"
        if version_file.exists():
            return version_file.read_text().strip()
        return "unknown"
    
    def check_updates(self, channel: str = "stable") -> Dict[str, Any]:
        """Check for available updates."""
        console.print(f"[cyan]Checking for updates...[/cyan]")
        
        try:
            if channel == "stable":
                url = "https://api.github.com/repos/rendiff/rendiff/releases/latest"
            else:
                url = "https://api.github.com/repos/rendiff/rendiff/releases"
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            if channel == "stable":
                release = response.json()
                latest_version = release["tag_name"].lstrip("v")
                
                return {
                    "available": self._compare_versions(latest_version, self.current_version),
                    "current": self.current_version,
                    "latest": latest_version,
                    "release_notes": release.get("body", ""),
                    "published_at": release.get("published_at"),
                    "download_url": release.get("tarball_url")
                }
            else:
                releases = response.json()
                if releases:
                    latest = releases[0]
                    latest_version = latest["tag_name"].lstrip("v")
                    
                    return {
                        "available": self._compare_versions(latest_version, self.current_version),
                        "current": self.current_version,
                        "latest": latest_version,
                        "release_notes": latest.get("body", ""),
                        "published_at": latest.get("published_at"),
                        "download_url": latest.get("tarball_url"),
                        "is_beta": True
                    }
        except Exception as e:
            console.print(f"[red]Error checking updates: {e}[/red]")
            return {"available": False, "error": str(e)}
        
        return {"available": False}
    
    def _compare_versions(self, v1: str, v2: str) -> bool:
        """Simple version comparison."""
        try:
            v1_parts = [int(x) for x in v1.split('.')]
            v2_parts = [int(x) for x in v2.split('.')]
            
            # Pad to same length
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts += [0] * (max_len - len(v1_parts))
            v2_parts += [0] * (max_len - len(v2_parts))
            
            return v1_parts > v2_parts
        except:
            return v1 > v2
    
    def create_backup(self, description: str = "") -> Optional[str]:
        """Create system backup."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_id = f"backup_{timestamp}"
        backup_dir = self.backup_path / backup_id
        
        console.print(f"[cyan]Creating backup: {backup_id}[/cyan]")
        
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                
                # Backup configuration
                task = progress.add_task("Backing up configuration...", total=None)
                if self.config_path.exists():
                    shutil.copytree(self.config_path, backup_dir / "config")
                progress.update(task, completed=1)
                
                # Backup data
                task = progress.add_task("Backing up data...", total=None)
                if self.data_path.exists():
                    shutil.copytree(self.data_path, backup_dir / "data")
                progress.update(task, completed=1)
                
                # Backup important files
                task = progress.add_task("Backing up files...", total=None)
                important_files = [
                    "docker-compose.yml", 
                    "docker-compose.override.yml", 
                    ".env", 
                    "VERSION"
                ]
                
                for file in important_files:
                    file_path = self.base_path / file
                    if file_path.exists():
                        shutil.copy2(file_path, backup_dir / file)
                progress.update(task, completed=1)
                
                # Create manifest
                manifest = {
                    "backup_id": backup_id,
                    "timestamp": timestamp,
                    "version": self.current_version,
                    "description": description,
                    "files": []
                }
                
                # Calculate checksums
                task = progress.add_task("Calculating checksums...", total=None)
                for file_path in backup_dir.rglob("*"):
                    if file_path.is_file() and file_path.name != "manifest.json":
                        rel_path = file_path.relative_to(backup_dir)
                        checksum = self._calculate_checksum(file_path)
                        manifest["files"].append({
                            "path": str(rel_path),
                            "checksum": checksum,
                            "size": file_path.stat().st_size
                        })
                
                # Save manifest
                with open(backup_dir / "manifest.json", 'w') as f:
                    json.dump(manifest, f, indent=2)
                
                progress.update(task, completed=1)
            
            console.print(f"[green]✓ Backup created: {backup_id}[/green]")
            return backup_id
            
        except Exception as e:
            console.print(f"[red]Backup failed: {e}[/red]")
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            return None
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backups."""
        backups = []
        
        for backup_dir in self.backup_path.iterdir():
            if backup_dir.is_dir():
                manifest_file = backup_dir / "manifest.json"
                
                if manifest_file.exists():
                    try:
                        with open(manifest_file) as f:
                            manifest = json.load(f)
                        
                        # Calculate total size
                        total_size = sum(
                            file_info["size"] 
                            for file_info in manifest.get("files", [])
                        )
                        
                        backups.append({
                            "id": manifest["backup_id"],
                            "timestamp": manifest["timestamp"],
                            "version": manifest.get("version", "unknown"),
                            "description": manifest.get("description", ""),
                            "size": total_size,
                            "valid": self._verify_backup(backup_dir, manifest)
                        })
                        
                    except Exception as e:
                        console.print(f"[yellow]Warning: Invalid backup {backup_dir.name}: {e}[/yellow]")
        
        return sorted(backups, key=lambda x: x["timestamp"], reverse=True)
    
    def restore_backup(self, backup_id: str) -> bool:
        """Restore from backup."""
        backup_dir = self.backup_path / backup_id
        
        if not backup_dir.exists():
            console.print(f"[red]Backup {backup_id} not found![/red]")
            return False
        
        manifest_file = backup_dir / "manifest.json"
        if not manifest_file.exists():
            console.print(f"[red]Backup {backup_id} is invalid![/red]")
            return False
        
        try:
            with open(manifest_file) as f:
                manifest = json.load(f)
            
            console.print(f"[cyan]Restoring backup: {backup_id}[/cyan]")
            console.print(f"[cyan]Original version: {manifest.get('version', 'unknown')}[/cyan]")
            
            if not Confirm.ask("Continue with restore?", default=True):
                return False
            
            # Stop services if running
            self._stop_services()
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                
                # Restore configuration
                task = progress.add_task("Restoring configuration...", total=None)
                if (backup_dir / "config").exists():
                    if self.config_path.exists():
                        shutil.rmtree(self.config_path)
                    shutil.copytree(backup_dir / "config", self.config_path)
                progress.update(task, completed=1)
                
                # Restore data
                task = progress.add_task("Restoring data...", total=None)
                if (backup_dir / "data").exists():
                    if self.data_path.exists():
                        shutil.rmtree(self.data_path)
                    shutil.copytree(backup_dir / "data", self.data_path)
                progress.update(task, completed=1)
                
                # Restore files
                task = progress.add_task("Restoring files...", total=None)
                important_files = [
                    "docker-compose.yml", 
                    "docker-compose.override.yml", 
                    ".env", 
                    "VERSION"
                ]
                
                for file in important_files:
                    backup_file = backup_dir / file
                    if backup_file.exists():
                        shutil.copy2(backup_file, self.base_path / file)
                progress.update(task, completed=1)
            
            # Start services
            self._start_services()
            
            console.print(f"[green]✓ Backup {backup_id} restored successfully![/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]Restore failed: {e}[/red]")
            return False
    
    def cleanup_backups(self, keep: int = 5) -> int:
        """Clean up old backups."""
        backups = self.list_backups()
        
        if len(backups) <= keep:
            console.print(f"[green]No cleanup needed. {len(backups)} backups found.[/green]")
            return 0
        
        to_delete = backups[keep:]
        deleted_count = 0
        
        console.print(f"[yellow]Cleaning up {len(to_delete)} old backups...[/yellow]")
        
        for backup in to_delete:
            backup_dir = self.backup_path / backup["id"]
            try:
                shutil.rmtree(backup_dir)
                deleted_count += 1
                console.print(f"[dim]Deleted: {backup['id']}[/dim]")
            except Exception as e:
                console.print(f"[red]Failed to delete {backup['id']}: {e}[/red]")
        
        console.print(f"[green]Cleanup completed. Deleted {deleted_count} backups.[/green]")
        return deleted_count
    
    def verify_system(self) -> Dict[str, Any]:
        """Verify system integrity."""
        console.print("[cyan]Verifying system integrity...[/cyan]")
        
        results = {"overall": True, "checks": {}}
        
        # Check critical files
        critical_files = [
            "docker-compose.yml",
            "config/storage.yml", 
            ".env"
        ]
        
        for file_path in critical_files:
            file_obj = self.base_path / file_path
            exists = file_obj.exists()
            results["checks"][f"file_{file_path}"] = {
                "status": "pass" if exists else "fail",
                "message": f"File {file_path} {'exists' if exists else 'missing'}"
            }
            
            if not exists:
                results["overall"] = False
        
        # Check database
        db_file = self.data_path / "rendiff.db"
        if db_file.exists():
            results["checks"]["database"] = {
                "status": "pass",
                "message": "SQLite database exists"
            }
        else:
            results["checks"]["database"] = {
                "status": "fail",
                "message": "SQLite database missing"
            }
            results["overall"] = False
        
        return results
    
    def repair_system(self) -> bool:
        """Attempt system repair."""
        console.print("[yellow]Attempting system repair...[/yellow]")
        
        repaired = False
        
        # Create missing directories
        directories = [self.config_path, self.data_path, self.backup_path]
        for directory in directories:
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                console.print(f"[green]Created directory: {directory}[/green]")
                repaired = True
        
        # Restore .env from example
        env_file = self.base_path / ".env"
        env_example = self.base_path / ".env.example"
        
        if not env_file.exists() and env_example.exists():
            shutil.copy2(env_example, env_file)
            console.print("[green]Restored .env from example[/green]")
            repaired = True
        
        # Initialize database if missing
        db_file = self.data_path / "rendiff.db"
        if not db_file.exists():
            try:
                subprocess.run([
                    "python", "scripts/init-sqlite.py"
                ], cwd=self.base_path, check=True)
                console.print("[green]Recreated SQLite database[/green]")
                repaired = True
            except Exception as e:
                console.print(f"[red]Failed to recreate database: {e}[/red]")
        
        return repaired
    
    def _stop_services(self):
        """Stop services."""
        try:
            subprocess.run([
                "docker-compose", "down"
            ], cwd=self.base_path, capture_output=True)
        except:
            pass
    
    def _start_services(self):
        """Start services."""
        try:
            subprocess.run([
                "docker-compose", "up", "-d"
            ], cwd=self.base_path, capture_output=True)
        except:
            pass
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def _verify_backup(self, backup_dir: Path, manifest: Dict) -> bool:
        """Verify backup integrity."""
        try:
            for file_info in manifest.get("files", []):
                file_path = backup_dir / file_info["path"]
                if not file_path.exists():
                    return False
                
                if file_path.stat().st_size != file_info["size"]:
                    return False
                
                checksum = self._calculate_checksum(file_path)
                if checksum != file_info["checksum"]:
                    return False
            
            return True
        except:
            return False


@click.group()
@click.option('--base-path', default='.', help='Base path for Rendiff installation')
@click.pass_context
def cli(ctx, base_path):
    """Rendiff Update & Maintenance System"""
    ctx.ensure_object(dict)
    ctx.obj['updater'] = RendiffUpdater(base_path)


@cli.command()
@click.option('--channel', default='stable', type=click.Choice(['stable', 'beta']))
def check(channel):
    """Check for available updates."""
    updater = click.get_current_context().obj['updater']
    
    update_info = updater.check_updates(channel)
    
    if update_info.get('error'):
        console.print(f"[red]Error: {update_info['error']}[/red]")
        return
    
    table = Table(title="Update Information")
    table.add_column("Component", style="cyan")
    table.add_column("Current")
    table.add_column("Latest")
    table.add_column("Status")
    
    status = ("[green]Up to date[/green]" if not update_info.get('available') 
             else "[yellow]Update available[/yellow]")
    
    table.add_row(
        "Rendiff", 
        update_info.get('current', 'unknown'), 
        update_info.get('latest', 'unknown'), 
        status
    )
    
    console.print(table)
    
    if update_info.get('available') and update_info.get('release_notes'):
        console.print(f"\n[bold]Release Notes:[/bold]")
        notes = update_info['release_notes']
        if len(notes) > 500:
            notes = notes[:500] + "..."
        console.print(notes)


@cli.command()
@click.option('--description', help='Backup description')
def backup(description):
    """Create system backup."""
    updater = click.get_current_context().obj['updater']
    
    backup_id = updater.create_backup(description or "Manual backup")
    if backup_id:
        console.print(f"[green]Backup created: {backup_id}[/green]")
    else:
        console.print("[red]Backup failed![/red]")
        sys.exit(1)


@cli.command("list-backups")
def list_backups():
    """List available backups."""
    updater = click.get_current_context().obj['updater']
    
    backups = updater.list_backups()
    
    if not backups:
        console.print("[yellow]No backups found.[/yellow]")
        return
    
    table = Table(title="Available Backups")
    table.add_column("Backup ID", style="cyan")
    table.add_column("Date")
    table.add_column("Version")
    table.add_column("Size")
    table.add_column("Status")
    table.add_column("Description")
    
    for backup in backups:
        size_mb = backup['size'] / (1024 * 1024)
        size_str = f"{size_mb:.1f} MB" if size_mb < 1024 else f"{size_mb/1024:.1f} GB"
        status = "[green]Valid[/green]" if backup['valid'] else "[red]Invalid[/red]"
        
        table.add_row(
            backup['id'],
            backup['timestamp'].replace('_', ' '),
            backup['version'],
            size_str,
            status,
            backup.get('description', '')
        )
    
    console.print(table)


@cli.command()
@click.argument('backup_id')
def restore(backup_id):
    """Restore from backup."""
    updater = click.get_current_context().obj['updater']
    
    success = updater.restore_backup(backup_id)
    if success:
        console.print("[green]Restore completed successfully![/green]")
    else:
        console.print("[red]Restore failed![/red]")
        sys.exit(1)


@cli.command()
@click.option('--keep', default=5, help='Number of backups to keep')
def cleanup(keep):
    """Clean up old backups."""
    updater = click.get_current_context().obj['updater']
    
    deleted = updater.cleanup_backups(keep)
    console.print(f"[green]Cleaned up {deleted} old backups.[/green]")


@cli.command()
def verify():
    """Verify system integrity."""
    updater = click.get_current_context().obj['updater']
    
    results = updater.verify_system()
    
    table = Table(title="System Verification")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Message")
    
    for check_name, check_result in results['checks'].items():
        status_color = {
            'pass': 'green',
            'fail': 'red',
            'error': 'yellow'
        }.get(check_result['status'], 'white')
        
        table.add_row(
            check_name.replace('_', ' ').title(),
            f"[{status_color}]{check_result['status'].upper()}[/{status_color}]",
            check_result['message']
        )
    
    console.print(table)
    
    if results['overall']:
        console.print("\n[green]✓ System verification passed![/green]")
    else:
        console.print("\n[red]✗ System verification failed![/red]")
        console.print("[yellow]Run 'python scripts/updater.py repair' to attempt fixes.[/yellow]")


@cli.command()
def repair():
    """Attempt automatic system repair."""
    updater = click.get_current_context().obj['updater']
    
    success = updater.repair_system()
    if success:
        console.print("[green]System repair completed![/green]")
    else:
        console.print("[yellow]Some issues could not be automatically repaired.[/yellow]")


if __name__ == '__main__':
    cli()