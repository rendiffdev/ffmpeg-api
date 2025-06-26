#!/usr/bin/env python3
"""
Rendiff System Updater - Internal Update/Upgrade System
Safe component updates with rollback capabilities
"""
import os
import sys
import json
import shutil
import subprocess
import tempfile
import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Handle optional imports gracefully
try:
    import yaml
except ImportError:
    yaml = None

try:
    import requests
except ImportError:
    requests = None

try:
    import click
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.prompt import Confirm
    from rich.panel import Panel
except ImportError:
    print("Warning: Rich and Click not available. Some features may be limited.")
    # Provide basic fallbacks
    class Console:
        def print(self, *args, **kwargs):
            print(*args)
    
    class Table:
        def __init__(self, *args, **kwargs):
            pass
        def add_column(self, *args, **kwargs):
            pass
        def add_row(self, *args, **kwargs):
            pass

console = Console()

class ComponentError(Exception):
    """Exception for component update errors"""
    pass

class SystemUpdater:
    """Advanced system updater with rollback capabilities"""
    
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.backup_path = self.base_path / "backups" / "updates"
        self.temp_path = self.base_path / "tmp" / "updates"
        self.config_path = self.base_path / "config"
        
        # Component definitions
        self.components = {
            "api": {
                "type": "container",
                "image": "rendiff/api",
                "service": "api",
                "health_check": "/api/v1/health",
                "dependencies": ["database", "redis"]
            },
            "worker-cpu": {
                "type": "container", 
                "image": "rendiff/worker",
                "service": "worker-cpu",
                "dependencies": ["api", "redis"]
            },
            "worker-gpu": {
                "type": "container",
                "image": "rendiff/worker-gpu", 
                "service": "worker-gpu",
                "dependencies": ["api", "redis"],
                "optional": True
            },
            "database": {
                "type": "data",
                "path": "/data",
                "schema_file": "api/models/database.py",
                "migrations": "migrations/"
            },
            "config": {
                "type": "config",
                "path": "/config",
                "files": ["storage.yml", ".env", "api_keys.json"]
            },
            "ffmpeg": {
                "type": "binary",
                "container": "worker-cpu",
                "version_command": ["ffmpeg", "-version"],
                "dependencies": []
            }
        }
        
        # Ensure directories exist
        self.backup_path.mkdir(parents=True, exist_ok=True)
        self.temp_path.mkdir(parents=True, exist_ok=True)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        console.print("[cyan]Checking system status...[/cyan]")
        
        status = {
            "timestamp": datetime.utcnow().isoformat(),
            "components": {},
            "services": {},
            "health": "unknown"
        }
        
        # Check Docker services
        try:
            result = subprocess.run([
                "docker-compose", "ps", "--format", "json"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                services = json.loads(f"[{result.stdout.replace('}{', '},{')}]")
                for service in services:
                    status["services"][service["Service"]] = {
                        "state": service["State"],
                        "status": service["Status"],
                        "health": service.get("Health", "unknown")
                    }
        except Exception as e:
            console.print(f"[yellow]Could not check services: {e}[/yellow]")
        
        # Check component versions
        for name, component in self.components.items():
            try:
                version = self._get_component_version(name, component)
                status["components"][name] = {
                    "version": version,
                    "type": component["type"],
                    "status": "available"
                }
            except Exception as e:
                status["components"][name] = {
                    "version": "unknown",
                    "type": component["type"],
                    "status": "error",
                    "error": str(e)
                }
        
        # Overall health assessment
        healthy_services = sum(1 for s in status["services"].values() 
                             if s["state"] == "running")
        total_services = len(status["services"])
        
        if total_services == 0:
            status["health"] = "stopped"
        elif healthy_services == total_services:
            status["health"] = "healthy"
        elif healthy_services > 0:
            status["health"] = "degraded"
        else:
            status["health"] = "unhealthy"
        
        return status
    
    def check_updates(self) -> Dict[str, Any]:
        """Check for available updates"""
        console.print("[cyan]Checking for available updates...[/cyan]")
        
        updates = {
            "available": False,
            "components": {},
            "total_updates": 0,
            "security_updates": 0
        }
        
        for name, component in self.components.items():
            try:
                current_version = self._get_component_version(name, component)
                latest_version = self._get_latest_version(name, component)
                
                if self._version_compare(latest_version, current_version) > 0:
                    updates["components"][name] = {
                        "current": current_version,
                        "latest": latest_version,
                        "type": component["type"],
                        "security": self._is_security_update(name, current_version, latest_version),
                        "changelog": self._get_changelog(name, current_version, latest_version)
                    }
                    updates["total_updates"] += 1
                    
                    if updates["components"][name]["security"]:
                        updates["security_updates"] += 1
                        
            except Exception as e:
                console.print(f"[yellow]Could not check updates for {name}: {e}[/yellow]")
        
        updates["available"] = updates["total_updates"] > 0
        return updates
    
    def create_update_backup(self, description: str = "") -> str:
        """Create backup before update"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_id = f"update_{timestamp}"
        backup_dir = self.backup_path / backup_id
        
        console.print(f"[cyan]Creating update backup: {backup_id}[/cyan]")
        
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Backup system state
            system_status = self.get_system_status()
            with open(backup_dir / "system_status.json", "w") as f:
                json.dump(system_status, f, indent=2)
            
            # Backup Docker images
            self._backup_docker_images(backup_dir)
            
            # Backup configuration
            if self.config_path.exists():
                shutil.copytree(self.config_path, backup_dir / "config")
            
            # Backup data (excluding large files)
            data_path = self.base_path / "data"
            if data_path.exists():
                self._backup_data(data_path, backup_dir / "data")
            
            # Create backup manifest
            manifest = {
                "backup_id": backup_id,
                "timestamp": timestamp,
                "description": description,
                "type": "update_backup",
                "system_status": system_status,
                "files": []
            }
            
            # Calculate checksums
            for file_path in backup_dir.rglob("*"):
                if file_path.is_file() and file_path.name != "manifest.json":
                    rel_path = file_path.relative_to(backup_dir)
                    checksum = self._calculate_checksum(file_path)
                    manifest["files"].append({
                        "path": str(rel_path),
                        "checksum": checksum,
                        "size": file_path.stat().st_size
                    })
            
            with open(backup_dir / "manifest.json", "w") as f:
                json.dump(manifest, f, indent=2)
            
            console.print(f"[green]✓ Update backup created: {backup_id}[/green]")
            return backup_id
            
        except Exception as e:
            console.print(f"[red]Backup failed: {e}[/red]")
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            raise
    
    def update_component(self, component_name: str, target_version: str = "latest", 
                        dry_run: bool = False) -> Dict[str, Any]:
        """Update a specific component"""
        if component_name not in self.components:
            raise ComponentError(f"Unknown component: {component_name}")
        
        component = self.components[component_name]
        
        console.print(f"[cyan]Updating component: {component_name}[/cyan]")
        
        if dry_run:
            console.print("[yellow]DRY RUN - No changes will be made[/yellow]")
        
        update_result = {
            "component": component_name,
            "success": False,
            "old_version": None,
            "new_version": None,
            "actions": [],
            "rollback_info": None
        }
        
        try:
            # Get current version
            current_version = self._get_component_version(component_name, component)
            update_result["old_version"] = current_version
            
            # Determine target version
            if target_version == "latest":
                target_version = self._get_latest_version(component_name, component)
            
            update_result["new_version"] = target_version
            
            # Check if update is needed
            if current_version == target_version:
                console.print(f"[green]Component {component_name} is already up to date[/green]")
                update_result["success"] = True
                return update_result
            
            # Pre-update checks
            self._pre_update_checks(component_name, component, current_version, target_version)
            
            # Create component backup
            if not dry_run:
                backup_id = self.create_update_backup(f"Before updating {component_name}")
                update_result["rollback_info"] = {"backup_id": backup_id}
            
            # Perform update based on component type
            if component["type"] == "container":
                actions = self._update_container(component_name, component, target_version, dry_run)
            elif component["type"] == "data":
                actions = self._update_data(component_name, component, target_version, dry_run)
            elif component["type"] == "config":
                actions = self._update_config(component_name, component, target_version, dry_run)
            elif component["type"] == "binary":
                actions = self._update_binary(component_name, component, target_version, dry_run)
            else:
                raise ComponentError(f"Unsupported component type: {component['type']}")
            
            update_result["actions"] = actions
            
            # Post-update verification
            if not dry_run:
                self._post_update_verification(component_name, component, target_version)
            
            update_result["success"] = True
            console.print(f"[green]✓ Component {component_name} updated successfully[/green]")
            
        except Exception as e:
            console.print(f"[red]Update failed for {component_name}: {e}[/red]")
            update_result["error"] = str(e)
            
            # Attempt rollback if backup was created
            if update_result.get("rollback_info") and not dry_run:
                console.print("[yellow]Attempting automatic rollback...[/yellow]")
                try:
                    self.rollback_update(update_result["rollback_info"]["backup_id"])
                    console.print("[green]✓ Rollback completed[/green]")
                except Exception as rollback_error:
                    console.print(f"[red]Rollback failed: {rollback_error}[/red]")
            
            raise
        
        return update_result
    
    def update_system(self, components: List[str] = None, dry_run: bool = False) -> Dict[str, Any]:
        """Update multiple components or entire system"""
        if components is None:
            components = list(self.components.keys())
        
        console.print(f"[cyan]Starting system update for components: {', '.join(components)}[/cyan]")
        
        if dry_run:
            console.print("[yellow]DRY RUN - No changes will be made[/yellow]")
        
        # Check for updates
        available_updates = self.check_updates()
        if not available_updates["available"]:
            console.print("[green]System is up to date[/green]")
            return {"success": True, "message": "No updates available"}
        
        # Filter components that have updates
        components_to_update = [
            comp for comp in components 
            if comp in available_updates["components"]
        ]
        
        if not components_to_update:
            console.print("[green]No updates available for specified components[/green]")
            return {"success": True, "message": "No updates for specified components"}
        
        # Show update plan
        self._show_update_plan(components_to_update, available_updates)
        
        if not dry_run and not Confirm.ask("\nProceed with system update?", default=True):
            return {"success": False, "message": "Update cancelled by user"}
        
        # Create system backup
        if not dry_run:
            system_backup_id = self.create_update_backup("System update")
        
        update_results = []
        failed_components = []
        
        # Update components in dependency order
        ordered_components = self._order_components_by_dependencies(components_to_update)
        
        for component_name in ordered_components:
            try:
                result = self.update_component(component_name, dry_run=dry_run)
                update_results.append(result)
                
                if not result["success"]:
                    failed_components.append(component_name)
                    break  # Stop on first failure
                    
            except Exception as e:
                failed_components.append(component_name)
                console.print(f"[red]Failed to update {component_name}: {e}[/red]")
                break
        
        # Summary
        if failed_components:
            console.print(f"[red]System update failed. Failed components: {', '.join(failed_components)}[/red]")
            return {
                "success": False,
                "failed_components": failed_components,
                "update_results": update_results,
                "system_backup": system_backup_id if not dry_run else None
            }
        else:
            console.print("[green]✓ System update completed successfully[/green]")
            return {
                "success": True,
                "updated_components": components_to_update,
                "update_results": update_results,
                "system_backup": system_backup_id if not dry_run else None
            }
    
    def rollback_update(self, backup_id: str) -> bool:
        """Rollback to a previous backup"""
        console.print(f"[cyan]Rolling back to backup: {backup_id}[/cyan]")
        
        backup_dir = self.backup_path / backup_id
        if not backup_dir.exists():
            raise ValueError(f"Backup {backup_id} not found")
        
        manifest_file = backup_dir / "manifest.json"
        if not manifest_file.exists():
            raise ValueError(f"Backup {backup_id} is invalid (no manifest)")
        
        with open(manifest_file) as f:
            manifest = json.load(f)
        
        try:
            # Stop services
            console.print("Stopping services...")
            subprocess.run(["docker-compose", "down"], capture_output=True)
            
            # Restore Docker images
            self._restore_docker_images(backup_dir)
            
            # Restore configuration
            if (backup_dir / "config").exists():
                if self.config_path.exists():
                    shutil.rmtree(self.config_path)
                shutil.copytree(backup_dir / "config", self.config_path)
            
            # Restore data
            if (backup_dir / "data").exists():
                data_path = self.base_path / "data"
                if data_path.exists():
                    shutil.rmtree(data_path)
                shutil.copytree(backup_dir / "data", data_path)
            
            # Start services
            console.print("Starting services...")
            subprocess.run(["docker-compose", "up", "-d"], capture_output=True)
            
            console.print(f"[green]✓ Rollback to {backup_id} completed[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]Rollback failed: {e}[/red]")
            raise
    
    def _get_component_version(self, name: str, component: Dict[str, Any]) -> str:
        """Get current version of a component"""
        if component["type"] == "container":
            try:
                result = subprocess.run([
                    "docker", "inspect", f"rendiff-{component['service']}",
                    "--format", "{{.Config.Labels.version}}"
                ], capture_output=True, text=True)
                return result.stdout.strip() or "unknown"
            except:
                return "unknown"
        
        elif component["type"] == "binary":
            try:
                result = subprocess.run([
                    "docker-compose", "exec", "-T", component["container"]
                ] + component["version_command"], capture_output=True, text=True)
                
                if "ffmpeg" in component["version_command"][0]:
                    # Parse FFmpeg version
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if line.startswith('ffmpeg version'):
                            return line.split()[2]
                
                return result.stdout.split('\n')[0].strip()
            except:
                return "unknown"
        
        return "1.0.0"  # Default for other types
    
    def _get_latest_version(self, name: str, component: Dict[str, Any]) -> str:
        """Get latest available version"""
        # In a real implementation, this would check:
        # - Docker registry for container images
        # - Package repositories for binaries
        # - GitHub releases for source code
        # For now, return a mock version
        return "1.1.0"
    
    def _version_compare(self, v1: str, v2: str) -> int:
        """Compare two version strings"""
        try:
            v1_parts = [int(x) for x in v1.split('.')]
            v2_parts = [int(x) for x in v2.split('.')]
            
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts += [0] * (max_len - len(v1_parts))
            v2_parts += [0] * (max_len - len(v2_parts))
            
            for i in range(max_len):
                if v1_parts[i] > v2_parts[i]:
                    return 1
                elif v1_parts[i] < v2_parts[i]:
                    return -1
            return 0
        except:
            return 1 if v1 > v2 else (-1 if v1 < v2 else 0)
    
    def _is_security_update(self, name: str, current: str, latest: str) -> bool:
        """Check if update contains security fixes"""
        # Mock implementation - in reality would check CVE databases
        return False
    
    def _get_changelog(self, name: str, current: str, latest: str) -> str:
        """Get changelog between versions"""
        return f"Changes from {current} to {latest}"
    
    def _pre_update_checks(self, name: str, component: Dict, current: str, target: str):
        """Perform pre-update validation checks"""
        # Check dependencies
        for dep in component.get("dependencies", []):
            if dep in self.components:
                # Ensure dependency is healthy
                pass
        
        # Check disk space
        # Check memory
        # Check compatibility
        pass
    
    def _post_update_verification(self, name: str, component: Dict, version: str):
        """Verify component is working after update"""
        if component["type"] == "container":
            # Check if service is running
            result = subprocess.run([
                "docker-compose", "ps", component["service"]
            ], capture_output=True, text=True)
            
            if component["service"] not in result.stdout:
                raise ComponentError(f"Service {component['service']} not running after update")
            
            # Check health endpoint if available
            if "health_check" in component:
                time.sleep(10)  # Wait for service to start
                try:
                    import requests
                    response = requests.get(f"http://localhost:8080{component['health_check']}", timeout=30)
                    if response.status_code != 200:
                        raise ComponentError(f"Health check failed for {name}")
                except Exception as e:
                    raise ComponentError(f"Health check failed for {name}: {e}")
    
    def _update_container(self, name: str, component: Dict, version: str, dry_run: bool) -> List[str]:
        """Update a container component"""
        actions = []
        service = component["service"]
        
        if dry_run:
            actions.append(f"Would pull new image for {service}")
            actions.append(f"Would recreate container {service}")
            return actions
        
        # Pull new image
        console.print(f"Pulling new image for {service}...")
        result = subprocess.run([
            "docker-compose", "pull", service
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise ComponentError(f"Failed to pull image: {result.stderr}")
        
        actions.append(f"Pulled new image for {service}")
        
        # Recreate service
        console.print(f"Recreating service {service}...")
        result = subprocess.run([
            "docker-compose", "up", "-d", "--force-recreate", service
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise ComponentError(f"Failed to recreate service: {result.stderr}")
        
        actions.append(f"Recreated service {service}")
        return actions
    
    def _update_data(self, name: str, component: Dict, version: str, dry_run: bool) -> List[str]:
        """Update data component (run migrations, etc.)"""
        actions = []
        
        if dry_run:
            actions.append(f"Would run data migrations for {name}")
            return actions
        
        # Run database migrations
        console.print(f"Running migrations for {name}...")
        result = subprocess.run([
            "python3", "scripts/init-db.py"
        ], cwd=self.base_path, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise ComponentError(f"Migration failed: {result.stderr}")
        
        actions.append(f"Ran migrations for {name}")
        return actions
    
    def _update_config(self, name: str, component: Dict, version: str, dry_run: bool) -> List[str]:
        """Update configuration component"""
        # Configuration updates would be handled by setup wizard
        return [f"Configuration {name} is managed by setup wizard"]
    
    def _update_binary(self, name: str, component: Dict, version: str, dry_run: bool) -> List[str]:
        """Update binary component (like FFmpeg in container)"""
        # Binary updates happen through container updates
        return [f"Binary {name} updated through container rebuild"]
    
    def _backup_docker_images(self, backup_dir: Path):
        """Backup current Docker images"""
        images_dir = backup_dir / "docker_images"
        images_dir.mkdir(exist_ok=True)
        
        # Get list of Rendiff images
        result = subprocess.run([
            "docker", "images", "--format", "{{.Repository}}:{{.Tag}}", "--filter", "reference=rendiff*"
        ], capture_output=True, text=True)
        
        for image in result.stdout.strip().split('\n'):
            if image.strip():
                safe_name = image.replace(':', '_').replace('/', '_')
                subprocess.run([
                    "docker", "save", "-o", str(images_dir / f"{safe_name}.tar"), image
                ], capture_output=True)
    
    def _restore_docker_images(self, backup_dir: Path):
        """Restore Docker images from backup"""
        images_dir = backup_dir / "docker_images"
        if not images_dir.exists():
            return
        
        for image_file in images_dir.glob("*.tar"):
            subprocess.run([
                "docker", "load", "-i", str(image_file)
            ], capture_output=True)
    
    def _backup_data(self, data_path: Path, backup_data_path: Path):
        """Backup data excluding large files"""
        backup_data_path.mkdir(parents=True, exist_ok=True)
        
        for item in data_path.iterdir():
            if item.is_file() and item.stat().st_size < 100 * 1024 * 1024:  # < 100MB
                shutil.copy2(item, backup_data_path)
            elif item.is_dir() and item.name != "temp":
                shutil.copytree(item, backup_data_path / item.name)
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def _show_update_plan(self, components: List[str], updates: Dict[str, Any]):
        """Show update plan to user"""
        table = Table(title="Update Plan")
        table.add_column("Component", style="cyan")
        table.add_column("Current")
        table.add_column("Latest")
        table.add_column("Type")
        table.add_column("Security", justify="center")
        
        for comp in components:
            update_info = updates["components"][comp]
            security = "🔒" if update_info["security"] else "○"
            
            table.add_row(
                comp,
                update_info["current"],
                update_info["latest"],
                update_info["type"],
                security
            )
        
        console.print(table)
        
        if updates["security_updates"] > 0:
            console.print(f"\n[red]⚠️  {updates['security_updates']} security updates available[/red]")
    
    def _order_components_by_dependencies(self, components: List[str]) -> List[str]:
        """Order components by their dependencies"""
        ordered = []
        remaining = components.copy()
        
        while remaining:
            made_progress = False
            
            for comp in remaining[:]:
                deps = self.components[comp].get("dependencies", [])
                
                # Check if all dependencies are either already processed or not in update list
                deps_satisfied = all(
                    dep in ordered or dep not in components 
                    for dep in deps
                )
                
                if deps_satisfied:
                    ordered.append(comp)
                    remaining.remove(comp)
                    made_progress = True
            
            if not made_progress:
                # Circular dependency or missing dependency - add remaining in original order
                ordered.extend(remaining)
                break
        
        return ordered


# CLI Interface
@click.group()
@click.option('--base-path', default='.', help='Base path for Rendiff installation')
@click.pass_context
def cli(ctx, base_path):
    """Rendiff System Updater - Internal Update/Upgrade System"""
    ctx.ensure_object(dict)
    ctx.obj['updater'] = SystemUpdater(base_path)


@cli.command()
def status():
    """Show current system status"""
    updater = click.get_current_context().obj['updater']
    
    status = updater.get_system_status()
    
    # Services table
    if status["services"]:
        table = Table(title="Service Status")
        table.add_column("Service", style="cyan")
        table.add_column("State")
        table.add_column("Status")
        table.add_column("Health")
        
        for name, info in status["services"].items():
            state_color = "green" if info["state"] == "running" else "red"
            table.add_row(
                name,
                f"[{state_color}]{info['state']}[/{state_color}]",
                info["status"],
                info["health"]
            )
        
        console.print(table)
    
    # Components table
    table = Table(title="Component Versions")
    table.add_column("Component", style="cyan")
    table.add_column("Version")
    table.add_column("Type")
    table.add_column("Status")
    
    for name, info in status["components"].items():
        status_color = "green" if info["status"] == "available" else "red"
        table.add_row(
            name,
            info["version"],
            info["type"],
            f"[{status_color}]{info['status']}[/{status_color}]"
        )
    
    console.print(table)
    
    # Overall health
    health_color = {
        "healthy": "green",
        "degraded": "yellow",
        "unhealthy": "red",
        "stopped": "red"
    }.get(status["health"], "white")
    
    console.print(f"\n[bold]Overall Health: [{health_color}]{status['health'].upper()}[/{health_color}][/bold]")


@cli.command()
def check():
    """Check for available updates"""
    updater = click.get_current_context().obj['updater']
    
    updates = updater.check_updates()
    
    if not updates["available"]:
        console.print("[green]✓ System is up to date[/green]")
        return
    
    table = Table(title="Available Updates")
    table.add_column("Component", style="cyan")
    table.add_column("Current")
    table.add_column("Latest")
    table.add_column("Type")
    table.add_column("Security", justify="center")
    
    for name, info in updates["components"].items():
        security = "🔒" if info["security"] else "○"
        
        table.add_row(
            name,
            info["current"],
            info["latest"],
            info["type"],
            security
        )
    
    console.print(table)
    
    console.print(f"\n[cyan]Total updates available: {updates['total_updates']}[/cyan]")
    if updates["security_updates"] > 0:
        console.print(f"[red]Security updates: {updates['security_updates']}[/red]")


@cli.command()
@click.option('--component', help='Specific component to update')
@click.option('--version', default='latest', help='Target version')
@click.option('--dry-run', is_flag=True, help='Show what would be updated without making changes')
def update(component, version, dry_run):
    """Update system or specific component"""
    updater = click.get_current_context().obj['updater']
    
    try:
        if component:
            result = updater.update_component(component, version, dry_run)
            if result["success"]:
                console.print(f"[green]✓ Component {component} updated successfully[/green]")
            else:
                console.print(f"[red]✗ Component {component} update failed[/red]")
        else:
            result = updater.update_system(dry_run=dry_run)
            if result["success"]:
                console.print("[green]✓ System update completed successfully[/green]")
            else:
                console.print("[red]✗ System update failed[/red]")
                
    except Exception as e:
        console.print(f"[red]Update failed: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument('backup_id')
def rollback(backup_id):
    """Rollback to a previous backup"""
    updater = click.get_current_context().obj['updater']
    
    try:
        success = updater.rollback_update(backup_id)
        if success:
            console.print(f"[green]✓ Rollback to {backup_id} completed[/green]")
        else:
            console.print(f"[red]✗ Rollback to {backup_id} failed[/red]")
    except Exception as e:
        console.print(f"[red]Rollback failed: {e}[/red]")
        sys.exit(1)


if __name__ == '__main__':
    cli()