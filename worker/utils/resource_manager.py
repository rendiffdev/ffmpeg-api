"""
Resource management and cleanup utilities for video processing.
"""
import asyncio
import os
import shutil
import tempfile
import psutil
from pathlib import Path
from typing import Dict, Any, Optional, List
import structlog

logger = structlog.get_logger()


class ResourceManager:
    """Manages system resources and cleanup for video processing tasks."""
    
    def __init__(self):
        self.temp_dirs = []
        self.temp_files = []
        self.process_monitors = {}
        
        # Resource limits
        self.max_memory_usage_percent = 80  # Max 80% memory usage
        self.max_disk_usage_percent = 90    # Max 90% disk usage
        self.min_free_disk_gb = 5           # Minimum 5GB free disk space
        
    async def check_system_resources(self) -> Dict[str, Any]:
        """Check current system resource usage."""
        try:
            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage = {
                'total_gb': round(memory.total / (1024**3), 2),
                'available_gb': round(memory.available / (1024**3), 2),
                'used_percent': memory.percent,
                'free_percent': 100 - memory.percent
            }
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage = {
                'total_gb': round(disk.total / (1024**3), 2),
                'free_gb': round(disk.free / (1024**3), 2),
                'used_percent': round((disk.used / disk.total) * 100, 2),
                'free_percent': round((disk.free / disk.total) * 100, 2)
            }
            
            # CPU usage
            cpu_usage = {
                'percent': psutil.cpu_percent(interval=1),
                'count': psutil.cpu_count(),
                'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
            }
            
            # Temperature (if available)
            temperature = None
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        if entries:
                            temperature = entries[0].current
                            break
            except (AttributeError, OSError):
                pass
            
            return {
                'memory': memory_usage,
                'disk': disk_usage,
                'cpu': cpu_usage,
                'temperature': temperature,
                'timestamp': asyncio.get_event_loop().time()
            }
            
        except Exception as e:
            logger.error("Failed to check system resources", error=str(e))
            return {'error': str(e)}
    
    async def check_resource_availability(self, required_memory_gb: Optional[float] = None,
                                        required_disk_gb: Optional[float] = None) -> Dict[str, Any]:
        """Check if sufficient resources are available for processing."""
        try:
            resources = await self.check_system_resources()
            
            if 'error' in resources:
                return {'available': False, 'reason': resources['error']}
            
            checks = []
            
            # Memory check
            memory_available = resources['memory']['available_gb']
            if required_memory_gb:
                if memory_available < required_memory_gb:
                    checks.append(f"Insufficient memory: {memory_available:.1f}GB available, {required_memory_gb:.1f}GB required")
            
            if resources['memory']['used_percent'] > self.max_memory_usage_percent:
                checks.append(f"High memory usage: {resources['memory']['used_percent']:.1f}%")
            
            # Disk check
            disk_free = resources['disk']['free_gb']
            if required_disk_gb:
                if disk_free < required_disk_gb:
                    checks.append(f"Insufficient disk space: {disk_free:.1f}GB free, {required_disk_gb:.1f}GB required")
            
            if disk_free < self.min_free_disk_gb:
                checks.append(f"Low disk space: {disk_free:.1f}GB free (minimum {self.min_free_disk_gb}GB)")
            
            if resources['disk']['used_percent'] > self.max_disk_usage_percent:
                checks.append(f"High disk usage: {resources['disk']['used_percent']:.1f}%")
            
            # CPU check (warning only)
            if resources['cpu']['percent'] > 95:
                checks.append(f"High CPU usage: {resources['cpu']['percent']:.1f}%")
            
            return {
                'available': len(checks) == 0,
                'reason': '; '.join(checks) if checks else 'Resources available',
                'resources': resources
            }
            
        except Exception as e:
            logger.error("Resource availability check failed", error=str(e))
            return {'available': False, 'reason': f'Check failed: {e}'}
    
    async def estimate_processing_requirements(self, input_file_path: str,
                                            operations: List[Dict[str, Any]]) -> Dict[str, float]:
        """Estimate resource requirements for processing."""
        try:
            if not os.path.exists(input_file_path):
                return {'memory_gb': 2.0, 'disk_gb': 5.0}  # Default estimates
            
            # Get input file size
            file_size_gb = os.path.getsize(input_file_path) / (1024**3)
            
            # Base requirements
            memory_gb = max(1.0, file_size_gb * 0.5)  # 50% of file size for memory
            disk_gb = file_size_gb * 3  # 3x file size for temporary files
            
            # Adjust based on operations
            for operation in operations:
                op_type = operation.get('type', '')
                
                if op_type == 'transcode':
                    # Transcoding needs more memory for encoding
                    memory_gb *= 1.5
                    disk_gb *= 1.2
                elif op_type == 'watermark':
                    # Watermarking needs memory for overlay
                    memory_gb *= 1.2
                elif op_type == 'filter':
                    # Filters can be memory intensive
                    memory_gb *= 1.3
                elif op_type == 'trim':
                    # Trimming reduces disk needs
                    disk_gb *= 0.8
            
            # Set reasonable bounds
            memory_gb = max(1.0, min(memory_gb, 16.0))  # 1GB to 16GB
            disk_gb = max(2.0, min(disk_gb, 100.0))     # 2GB to 100GB
            
            return {
                'memory_gb': round(memory_gb, 1),
                'disk_gb': round(disk_gb, 1),
                'input_size_gb': round(file_size_gb, 2)
            }
            
        except Exception as e:
            logger.error("Failed to estimate requirements", error=str(e))
            return {'memory_gb': 2.0, 'disk_gb': 5.0}
    
    def create_temp_directory(self, prefix: str = "rendiff_") -> str:
        """Create a temporary directory and track it for cleanup."""
        try:
            temp_dir = tempfile.mkdtemp(prefix=prefix)
            self.temp_dirs.append(temp_dir)
            logger.debug("Created temporary directory", path=temp_dir)
            return temp_dir
        except Exception as e:
            logger.error("Failed to create temporary directory", error=str(e))
            raise
    
    def create_temp_file(self, suffix: str = "", prefix: str = "rendiff_") -> str:
        """Create a temporary file and track it for cleanup."""
        try:
            fd, temp_file = tempfile.mkstemp(suffix=suffix, prefix=prefix)
            os.close(fd)  # Close the file descriptor
            self.temp_files.append(temp_file)
            logger.debug("Created temporary file", path=temp_file)
            return temp_file
        except Exception as e:
            logger.error("Failed to create temporary file", error=str(e))
            raise
    
    async def cleanup_temp_resources(self):
        """Clean up all temporary resources."""
        cleanup_results = {
            'directories_cleaned': 0,
            'files_cleaned': 0,
            'errors': []
        }
        
        # Clean up temporary directories
        for temp_dir in self.temp_dirs:
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    cleanup_results['directories_cleaned'] += 1
                    logger.debug("Cleaned up temporary directory", path=temp_dir)
            except Exception as e:
                error_msg = f"Failed to cleanup directory {temp_dir}: {e}"
                cleanup_results['errors'].append(error_msg)
                logger.error(error_msg)
        
        # Clean up temporary files
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    cleanup_results['files_cleaned'] += 1
                    logger.debug("Cleaned up temporary file", path=temp_file)
            except Exception as e:
                error_msg = f"Failed to cleanup file {temp_file}: {e}"
                cleanup_results['errors'].append(error_msg)
                logger.error(error_msg)
        
        # Clear the tracking lists
        self.temp_dirs.clear()
        self.temp_files.clear()
        
        logger.info("Temporary resource cleanup completed", results=cleanup_results)
        return cleanup_results
    
    async def monitor_process_resources(self, process_id: int, interval: float = 5.0) -> Dict[str, Any]:
        """Monitor resource usage of a specific process."""
        try:
            process = psutil.Process(process_id)
            monitoring_data = []
            
            while process.is_running():
                try:
                    # Get process info
                    proc_info = {
                        'timestamp': asyncio.get_event_loop().time(),
                        'cpu_percent': process.cpu_percent(),
                        'memory_mb': round(process.memory_info().rss / (1024**2), 1),
                        'memory_percent': process.memory_percent(),
                        'status': process.status()
                    }
                    
                    monitoring_data.append(proc_info)
                    
                    # Log warning if resource usage is high
                    if proc_info['memory_percent'] > 50:
                        logger.warning(
                            "High memory usage detected",
                            process_id=process_id,
                            memory_percent=proc_info['memory_percent']
                        )
                    
                    await asyncio.sleep(interval)
                    
                except psutil.NoSuchProcess:
                    break
                except Exception as e:
                    logger.error("Process monitoring error", error=str(e))
                    break
            
            return {
                'process_id': process_id,
                'monitoring_data': monitoring_data,
                'total_samples': len(monitoring_data)
            }
            
        except psutil.NoSuchProcess:
            return {'error': f'Process {process_id} not found'}
        except Exception as e:
            logger.error("Process monitoring failed", error=str(e))
            return {'error': str(e)}
    
    async def cleanup_old_files(self, directory: str, max_age_hours: int = 24) -> Dict[str, Any]:
        """Clean up old files in a directory."""
        import time
        
        cleanup_results = {
            'files_removed': 0,
            'space_freed_mb': 0,
            'errors': []
        }
        
        try:
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        # Check file age
                        file_age = current_time - os.path.getmtime(file_path)
                        
                        if file_age > max_age_seconds:
                            file_size = os.path.getsize(file_path)
                            os.unlink(file_path)
                            
                            cleanup_results['files_removed'] += 1
                            cleanup_results['space_freed_mb'] += file_size / (1024**2)
                            
                            logger.debug("Removed old file", path=file_path, age_hours=file_age/3600)
                    
                    except Exception as e:
                        error_msg = f"Failed to remove {file_path}: {e}"
                        cleanup_results['errors'].append(error_msg)
                        logger.error(error_msg)
            
            cleanup_results['space_freed_mb'] = round(cleanup_results['space_freed_mb'], 1)
            
            logger.info("Old file cleanup completed", results=cleanup_results)
            return cleanup_results
            
        except Exception as e:
            logger.error("Old file cleanup failed", error=str(e))
            return {'error': str(e)}
    
    async def optimize_system_for_processing(self) -> Dict[str, Any]:
        """Optimize system settings for video processing."""
        optimizations = {
            'applied': [],
            'failed': [],
            'recommendations': []
        }
        
        try:
            # Check if we can apply optimizations (requires privileges)
            
            # 1. Increase file descriptor limits (if possible)
            try:
                import resource
                soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
                if soft < 4096:
                    resource.setrlimit(resource.RLIMIT_NOFILE, (min(4096, hard), hard))
                    optimizations['applied'].append("Increased file descriptor limit")
            except Exception as e:
                optimizations['failed'].append(f"File descriptor limit: {e}")
            
            # 2. Set process priority (if possible)
            try:
                current_process = psutil.Process()
                if current_process.nice() > -5:  # Only if not already high priority
                    current_process.nice(-1)  # Increase priority slightly
                    optimizations['applied'].append("Increased process priority")
            except Exception as e:
                optimizations['failed'].append(f"Process priority: {e}")
            
            # 3. Memory recommendations
            memory = psutil.virtual_memory()
            if memory.available < 2 * (1024**3):  # Less than 2GB available
                optimizations['recommendations'].append("Consider freeing memory before processing large files")
            
            # 4. Disk space recommendations
            disk = psutil.disk_usage('/')
            if disk.free < 10 * (1024**3):  # Less than 10GB free
                optimizations['recommendations'].append("Consider freeing disk space for temporary files")
            
            logger.info("System optimization completed", results=optimizations)
            return optimizations
            
        except Exception as e:
            logger.error("System optimization failed", error=str(e))
            return {'error': str(e)}
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        asyncio.create_task(self.cleanup_temp_resources())