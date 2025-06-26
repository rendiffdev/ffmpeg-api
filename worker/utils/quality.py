"""
Quality metrics calculation utilities for video analysis.
Implements VMAF, PSNR, SSIM, and other video quality metrics.
"""
import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import structlog

from worker.utils.ffmpeg import FFmpegWrapper, FFmpegError

logger = structlog.get_logger()


class QualityMetricsError(Exception):
    """Base exception for quality metrics calculation errors."""
    pass


class QualityCalculator:
    """Calculate video quality metrics using FFmpeg filters."""
    
    def __init__(self):
        self.ffmpeg = FFmpegWrapper()
        self.initialized = False
        
        # VMAF model paths (these would need to be provided)
        self.vmaf_models = {
            '4k': '/usr/local/share/vmaf/model/vmaf_4k_v0.6.1.pkl',
            'hd': '/usr/local/share/vmaf/model/vmaf_v0.6.1.pkl', 
            'mobile': '/usr/local/share/vmaf/model/vmaf_v0.6.1neg.pkl'
        }
    
    async def initialize(self):
        """Initialize the quality calculator."""
        if not self.initialized:
            await self.ffmpeg.initialize()
            self.initialized = True
            logger.info("QualityCalculator initialized")
    
    async def calculate_all_metrics(self, reference_path: str, test_path: str,
                                  model: str = 'hd') -> Dict[str, Any]:
        """
        Calculate all quality metrics (VMAF, PSNR, SSIM) between reference and test videos.
        
        Args:
            reference_path: Path to reference (original) video
            test_path: Path to test (processed) video
            model: VMAF model to use ('4k', 'hd', 'mobile')
            
        Returns:
            Dict containing all calculated metrics
        """
        await self.initialize()
        
        try:
            logger.info(
                "Starting quality metrics calculation",
                reference=reference_path,
                test=test_path,
                model=model
            )
            
            # Validate input files
            await self._validate_inputs(reference_path, test_path)
            
            # Calculate metrics in parallel for efficiency
            vmaf_task = asyncio.create_task(self.calculate_vmaf(reference_path, test_path, model))
            psnr_ssim_task = asyncio.create_task(self.calculate_psnr_ssim(reference_path, test_path))
            
            # Wait for all calculations
            vmaf_result = await vmaf_task
            psnr_ssim_result = await psnr_ssim_task
            
            # Combine results
            metrics = {
                'vmaf': vmaf_result,
                'psnr': psnr_ssim_result.get('psnr'),
                'ssim': psnr_ssim_result.get('ssim'),
                'model_used': model,
                'reference_file': reference_path,
                'test_file': test_path
            }
            
            logger.info("Quality metrics calculation completed", metrics=metrics)
            return metrics
            
        except Exception as e:
            logger.error("Quality metrics calculation failed", error=str(e))
            raise QualityMetricsError(f"Quality metrics calculation failed: {e}")
    
    async def calculate_vmaf(self, reference_path: str, test_path: str, 
                           model: str = 'hd') -> Dict[str, Any]:
        """
        Calculate VMAF (Video Multi-Method Assessment Fusion) score.
        
        Args:
            reference_path: Path to reference video
            test_path: Path to test video
            model: VMAF model to use
            
        Returns:
            Dict containing VMAF scores and statistics
        """
        await self.initialize()
        
        try:
            # Check if VMAF model exists
            model_path = self.vmaf_models.get(model)
            if not model_path or not os.path.exists(model_path):
                logger.warning(f"VMAF model not found: {model_path}, using built-in model")
                model_path = None
            
            # Create temporary file for VMAF output
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as vmaf_log:
                vmaf_log_path = vmaf_log.name
            
            try:
                # Build VMAF filter
                if model_path:
                    vmaf_filter = f"vmaf=model_path={model_path}:log_path={vmaf_log_path}:log_fmt=json"
                else:
                    vmaf_filter = f"vmaf=log_path={vmaf_log_path}:log_fmt=json"
                
                # Build FFmpeg command for VMAF calculation
                cmd = [
                    'ffmpeg', '-y',
                    '-i', test_path,      # Test video (distorted)
                    '-i', reference_path,  # Reference video (original)
                    '-lavfi', f"[0:v][1:v]{vmaf_filter}",
                    '-f', 'null', '-'
                ]
                
                # Execute FFmpeg command
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    error_msg = stderr.decode() if stderr else "Unknown FFmpeg error"
                    raise QualityMetricsError(f"VMAF calculation failed: {error_msg}")
                
                # Parse VMAF results
                vmaf_results = self._parse_vmaf_log(vmaf_log_path)
                
                logger.info("VMAF calculation completed", results=vmaf_results)
                return vmaf_results
                
            finally:
                # Clean up temporary file
                if os.path.exists(vmaf_log_path):
                    os.unlink(vmaf_log_path)
                    
        except Exception as e:
            logger.error("VMAF calculation failed", error=str(e))
            raise QualityMetricsError(f"VMAF calculation failed: {e}")
    
    async def calculate_psnr_ssim(self, reference_path: str, test_path: str) -> Dict[str, Any]:
        """
        Calculate PSNR (Peak Signal-to-Noise Ratio) and SSIM (Structural Similarity Index).
        
        Args:
            reference_path: Path to reference video
            test_path: Path to test video
            
        Returns:
            Dict containing PSNR and SSIM values
        """
        await self.initialize()
        
        try:
            # Build filter for PSNR and SSIM calculation
            psnr_ssim_filter = "[0:v][1:v]psnr=stats_file=-:ssim=stats_file=-"
            
            # Build FFmpeg command
            cmd = [
                'ffmpeg', '-y',
                '-i', test_path,       # Test video (distorted)
                '-i', reference_path,   # Reference video (original)
                '-lavfi', psnr_ssim_filter,
                '-f', 'null', '-'
            ]
            
            # Execute FFmpeg command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown FFmpeg error"
                raise QualityMetricsError(f"PSNR/SSIM calculation failed: {error_msg}")
            
            # Parse PSNR and SSIM from stderr output
            stderr_text = stderr.decode()
            psnr_ssim_results = self._parse_psnr_ssim_output(stderr_text)
            
            logger.info("PSNR/SSIM calculation completed", results=psnr_ssim_results)
            return psnr_ssim_results
            
        except Exception as e:
            logger.error("PSNR/SSIM calculation failed", error=str(e))
            raise QualityMetricsError(f"PSNR/SSIM calculation failed: {e}")
    
    async def calculate_bitrate_comparison(self, reference_path: str, test_path: str) -> Dict[str, Any]:
        """Calculate bitrate comparison metrics."""
        await self.initialize()
        
        try:
            # Get file information for both videos
            ref_info = await self.ffmpeg.probe_file(reference_path)
            test_info = await self.ffmpeg.probe_file(test_path)
            
            # Extract bitrates
            ref_bitrate = int(ref_info.get('format', {}).get('bit_rate', 0))
            test_bitrate = int(test_info.get('format', {}).get('bit_rate', 0))
            
            # Extract file sizes
            ref_size = int(ref_info.get('format', {}).get('size', 0))
            test_size = int(test_info.get('format', {}).get('size', 0))
            
            # Calculate metrics
            bitrate_reduction = ((ref_bitrate - test_bitrate) / ref_bitrate * 100) if ref_bitrate > 0 else 0
            size_reduction = ((ref_size - test_size) / ref_size * 100) if ref_size > 0 else 0
            compression_ratio = ref_size / test_size if test_size > 0 else 0
            
            return {
                'reference_bitrate': ref_bitrate,
                'test_bitrate': test_bitrate,
                'bitrate_reduction_percent': bitrate_reduction,
                'reference_size': ref_size,
                'test_size': test_size,
                'size_reduction_percent': size_reduction,
                'compression_ratio': compression_ratio
            }
            
        except Exception as e:
            logger.error("Bitrate comparison failed", error=str(e))
            raise QualityMetricsError(f"Bitrate comparison failed: {e}")
    
    async def _validate_inputs(self, reference_path: str, test_path: str):
        """Validate input files for quality metrics calculation."""
        # Check if files exist
        if not os.path.exists(reference_path):
            raise QualityMetricsError(f"Reference file not found: {reference_path}")
        if not os.path.exists(test_path):
            raise QualityMetricsError(f"Test file not found: {test_path}")
        
        # Probe both files
        try:
            ref_info = await self.ffmpeg.probe_file(reference_path)
            test_info = await self.ffmpeg.probe_file(test_path)
        except FFmpegError as e:
            raise QualityMetricsError(f"Failed to probe input files: {e}")
        
        # Extract video stream info
        ref_video = next((s for s in ref_info.get('streams', []) 
                         if s.get('codec_type') == 'video'), None)
        test_video = next((s for s in test_info.get('streams', []) 
                          if s.get('codec_type') == 'video'), None)
        
        if not ref_video:
            raise QualityMetricsError(f"No video stream in reference file: {reference_path}")
        if not test_video:
            raise QualityMetricsError(f"No video stream in test file: {test_path}")
        
        # Check if resolutions match (warn if different)
        ref_res = (ref_video.get('width', 0), ref_video.get('height', 0))
        test_res = (test_video.get('width', 0), test_video.get('height', 0))
        
        if ref_res != test_res:
            logger.warning(
                "Video resolutions differ - results may be inaccurate",
                reference_resolution=f"{ref_res[0]}x{ref_res[1]}",
                test_resolution=f"{test_res[0]}x{test_res[1]}"
            )
    
    def _parse_vmaf_log(self, log_path: str) -> Dict[str, Any]:
        """Parse VMAF JSON log file."""
        try:
            with open(log_path, 'r') as f:
                vmaf_data = json.load(f)
            
            # Extract VMAF scores
            frames = vmaf_data.get('frames', [])
            if not frames:
                raise QualityMetricsError("No VMAF data found in log file")
            
            # Calculate statistics
            vmaf_scores = [frame['metrics']['vmaf'] for frame in frames if 'vmaf' in frame.get('metrics', {})]
            
            if not vmaf_scores:
                raise QualityMetricsError("No VMAF scores found in log file")
            
            return {
                'mean': sum(vmaf_scores) / len(vmaf_scores),
                'min': min(vmaf_scores),
                'max': max(vmaf_scores),
                'percentile_1': self._percentile(vmaf_scores, 1),
                'percentile_5': self._percentile(vmaf_scores, 5),
                'percentile_95': self._percentile(vmaf_scores, 95),
                'percentile_99': self._percentile(vmaf_scores, 99),
                'frame_count': len(vmaf_scores),
                'scores': vmaf_scores[:100]  # First 100 scores for analysis
            }
            
        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            raise QualityMetricsError(f"Failed to parse VMAF log: {e}")
    
    def _parse_psnr_ssim_output(self, output: str) -> Dict[str, Any]:
        """Parse PSNR and SSIM values from FFmpeg output."""
        import re
        
        psnr_pattern = r'PSNR.*?average:(\d+\.?\d*)'
        ssim_pattern = r'SSIM.*?All:(\d+\.?\d*)'
        
        psnr_match = re.search(psnr_pattern, output)
        ssim_match = re.search(ssim_pattern, output)
        
        psnr_value = float(psnr_match.group(1)) if psnr_match else None
        ssim_value = float(ssim_match.group(1)) if ssim_match else None
        
        # Also try to extract Y, U, V components for PSNR
        psnr_y_pattern = r'PSNR y:(\d+\.?\d*)'
        psnr_u_pattern = r'u:(\d+\.?\d*)'
        psnr_v_pattern = r'v:(\d+\.?\d*)'
        
        psnr_y = float(re.search(psnr_y_pattern, output).group(1)) if re.search(psnr_y_pattern, output) else None
        psnr_u = float(re.search(psnr_u_pattern, output).group(1)) if re.search(psnr_u_pattern, output) else None
        psnr_v = float(re.search(psnr_v_pattern, output).group(1)) if re.search(psnr_v_pattern, output) else None
        
        return {
            'psnr': {
                'average': psnr_value,
                'y': psnr_y,
                'u': psnr_u,
                'v': psnr_v
            },
            'ssim': {
                'average': ssim_value
            }
        }
    
    def _percentile(self, data: list, percentile: float) -> float:
        """Calculate percentile of a list of values."""
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        index = percentile / 100 * (len(sorted_data) - 1)
        
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))
    
    async def generate_quality_report(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a comprehensive quality assessment report."""
        try:
            report = {
                'overall_score': 'unknown',
                'quality_grade': 'unknown',
                'assessment': 'Unable to generate assessment',
                'metrics': metrics,
                'recommendations': []
            }
            
            # VMAF-based assessment
            vmaf_data = metrics.get('vmaf', {})
            if isinstance(vmaf_data, dict) and 'mean' in vmaf_data:
                vmaf_score = vmaf_data['mean']
                
                # Quality grades based on VMAF score
                if vmaf_score >= 95:
                    grade = 'Excellent'
                    assessment = 'Visually lossless quality'
                elif vmaf_score >= 80:
                    grade = 'Very Good'
                    assessment = 'High quality with minimal artifacts'
                elif vmaf_score >= 60:
                    grade = 'Good'
                    assessment = 'Acceptable quality for most use cases'
                elif vmaf_score >= 40:
                    grade = 'Fair'
                    assessment = 'Noticeable quality degradation'
                else:
                    grade = 'Poor'
                    assessment = 'Significant quality loss'
                
                report.update({
                    'overall_score': vmaf_score,
                    'quality_grade': grade,
                    'assessment': assessment
                })
                
                # Add recommendations
                if vmaf_score < 60:
                    report['recommendations'].append('Consider increasing bitrate or using higher quality settings')
                if vmaf_data.get('min', 0) < 30:
                    report['recommendations'].append('Some frames have very low quality - check for scene complexity')
            
            # PSNR assessment
            psnr_data = metrics.get('psnr', {})
            if isinstance(psnr_data, dict) and psnr_data.get('average'):
                psnr_avg = psnr_data['average']
                if psnr_avg < 30:
                    report['recommendations'].append(f'Low PSNR ({psnr_avg:.1f}dB) indicates significant noise')
            
            # Bitrate efficiency
            if 'compression_ratio' in metrics:
                ratio = metrics['compression_ratio']
                if ratio > 10:
                    report['recommendations'].append('Excellent compression efficiency achieved')
                elif ratio < 2:
                    report['recommendations'].append('Consider more aggressive compression settings')
            
            return report
            
        except Exception as e:
            logger.error("Failed to generate quality report", error=str(e))
            return {
                'error': f"Failed to generate quality report: {e}",
                'metrics': metrics
            }