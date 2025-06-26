"""
GPU detection and configuration utilities
"""
import subprocess
import json
from typing import Dict, List, Any, Optional
from rich.console import Console

console = Console()


class GPUDetector:
    """Detect and configure GPU acceleration."""
    
    def detect_gpus(self) -> Dict[str, Any]:
        """Detect available GPUs."""
        result = {
            "has_gpu": False,
            "nvidia_available": False,
            "amd_available": False,
            "intel_available": False,
            "gpus": [],
            "driver_version": None,
            "cuda_version": None
        }
        
        # Check NVIDIA GPUs
        nvidia_info = self._detect_nvidia()
        if nvidia_info["available"]:
            result["has_gpu"] = True
            result["nvidia_available"] = True
            result["gpus"].extend(nvidia_info["gpus"])
            result["driver_version"] = nvidia_info["driver_version"]
            result["cuda_version"] = nvidia_info["cuda_version"]
        
        # Check AMD GPUs
        amd_info = self._detect_amd()
        if amd_info["available"]:
            result["has_gpu"] = True
            result["amd_available"] = True
            result["gpus"].extend(amd_info["gpus"])
        
        # Check Intel GPUs
        intel_info = self._detect_intel()
        if intel_info["available"]:
            result["has_gpu"] = True
            result["intel_available"] = True
            result["gpus"].extend(intel_info["gpus"])
        
        return result
    
    def _detect_nvidia(self) -> Dict[str, Any]:
        """Detect NVIDIA GPUs."""
        result = {
            "available": False,
            "gpus": [],
            "driver_version": None,
            "cuda_version": None
        }
        
        try:
            # Check nvidia-smi
            nvidia_smi_result = subprocess.run([
                "nvidia-smi", 
                "--query-gpu=index,name,memory.total,driver_version",
                "--format=csv,noheader,nounits"
            ], capture_output=True, text=True, timeout=10)
            
            if nvidia_smi_result.returncode == 0:
                result["available"] = True
                
                lines = nvidia_smi_result.stdout.strip().split('\n')
                for line in lines:
                    if line.strip():
                        parts = [p.strip() for p in line.split(',')]
                        if len(parts) >= 4:
                            result["gpus"].append({
                                "index": int(parts[0]),
                                "name": parts[1],
                                "memory": int(parts[2]),
                                "type": "nvidia"
                            })
                            result["driver_version"] = parts[3]
            
            # Check CUDA version
            try:
                cuda_result = subprocess.run([
                    "nvcc", "--version"
                ], capture_output=True, text=True, timeout=5)
                
                if cuda_result.returncode == 0:
                    # Parse CUDA version from output
                    for line in cuda_result.stdout.split('\n'):
                        if 'release' in line.lower():
                            # Extract version number
                            import re
                            match = re.search(r'release (\d+\.\d+)', line)
                            if match:
                                result["cuda_version"] = match.group(1)
                                break
                            
            except:
                pass
                
        except Exception as e:
            console.print(f"[yellow]NVIDIA detection failed: {e}[/yellow]")
        
        return result
    
    def _detect_amd(self) -> Dict[str, Any]:
        """Detect AMD GPUs."""
        result = {
            "available": False,
            "gpus": []
        }
        
        try:
            # Check rocm-smi
            rocm_result = subprocess.run([
                "rocm-smi", "--showproductname", "--csv"
            ], capture_output=True, text=True, timeout=10)
            
            if rocm_result.returncode == 0:
                result["available"] = True
                
                lines = rocm_result.stdout.strip().split('\n')
                for i, line in enumerate(lines[1:]):  # Skip header
                    if line.strip():
                        parts = [p.strip() for p in line.split(',')]
                        if len(parts) >= 2:
                            result["gpus"].append({
                                "index": i,
                                "name": parts[1],
                                "type": "amd"
                            })
                            
        except Exception:
            # Try alternative detection
            try:
                lspci_result = subprocess.run([
                    "lspci", "-nn"
                ], capture_output=True, text=True, timeout=5)
                
                if lspci_result.returncode == 0:
                    amd_gpus = []
                    for line in lspci_result.stdout.split('\n'):
                        if 'VGA' in line and ('AMD' in line or 'ATI' in line):
                            amd_gpus.append({
                                "index": len(amd_gpus),
                                "name": line.split(':')[-1].strip(),
                                "type": "amd"
                            })
                    
                    if amd_gpus:
                        result["available"] = True
                        result["gpus"] = amd_gpus
                        
            except Exception:
                pass
        
        return result
    
    def _detect_intel(self) -> Dict[str, Any]:
        """Detect Intel GPUs."""
        result = {
            "available": False,
            "gpus": []
        }
        
        try:
            # Check for Intel GPU via lspci
            lspci_result = subprocess.run([
                "lspci", "-nn"
            ], capture_output=True, text=True, timeout=5)
            
            if lspci_result.returncode == 0:
                intel_gpus = []
                for line in lspci_result.stdout.split('\n'):
                    if 'VGA' in line and 'Intel' in line:
                        intel_gpus.append({
                            "index": len(intel_gpus),
                            "name": line.split(':')[-1].strip(),
                            "type": "intel"
                        })
                
                if intel_gpus:
                    result["available"] = True
                    result["gpus"] = intel_gpus
                    
        except Exception:
            pass
        
        return result
    
    def check_docker_gpu_support(self) -> Dict[str, bool]:
        """Check Docker GPU support."""
        result = {
            "nvidia_runtime": False,
            "nvidia_container_toolkit": False
        }
        
        try:
            # Check Docker daemon configuration
            docker_info = subprocess.run([
                "docker", "info", "--format", "json"
            ], capture_output=True, text=True, timeout=10)
            
            if docker_info.returncode == 0:
                info_data = json.loads(docker_info.stdout)
                
                # Check for NVIDIA runtime
                runtimes = info_data.get("Runtimes", {})
                result["nvidia_runtime"] = "nvidia" in runtimes
                
            # Check nvidia-container-toolkit
            toolkit_check = subprocess.run([
                "which", "nvidia-container-runtime"
            ], capture_output=True, timeout=5)
            
            result["nvidia_container_toolkit"] = toolkit_check.returncode == 0
            
        except Exception:
            pass
        
        return result
    
    def get_gpu_recommendations(self, gpu_info: Dict[str, Any]) -> List[str]:
        """Get GPU configuration recommendations."""
        recommendations = []
        
        if not gpu_info["has_gpu"]:
            recommendations.append("No GPU detected. CPU-only processing will be used.")
            return recommendations
        
        if gpu_info["nvidia_available"]:
            gpu_count = len([g for g in gpu_info["gpus"] if g["type"] == "nvidia"])
            
            if gpu_count == 1:
                recommendations.append("Single NVIDIA GPU detected. Recommended: 1-2 GPU workers.")
            else:
                recommendations.append(f"{gpu_count} NVIDIA GPUs detected. Recommended: {min(gpu_count, 4)} GPU workers.")
            
            if gpu_info["cuda_version"]:
                recommendations.append(f"CUDA {gpu_info['cuda_version']} available for acceleration.")
            else:
                recommendations.append("Consider installing CUDA for better GPU performance.")
            
            # Check memory
            total_memory = sum(g.get("memory", 0) for g in gpu_info["gpus"] if g["type"] == "nvidia")
            if total_memory > 0:
                if total_memory < 4000:  # Less than 4GB
                    recommendations.append("Limited GPU memory. Consider smaller batch sizes.")
                elif total_memory > 8000:  # More than 8GB
                    recommendations.append("High GPU memory available. Can handle large files efficiently.")
        
        if gpu_info["amd_available"]:
            recommendations.append("AMD GPU detected. ROCm acceleration may be available.")
        
        if gpu_info["intel_available"]:
            recommendations.append("Intel GPU detected. Quick Sync acceleration may be available.")
        
        return recommendations