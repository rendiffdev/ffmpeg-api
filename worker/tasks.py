"""
Celery tasks for processing jobs - Refactored with base classes
"""
import asyncio
from pathlib import Path
from typing import Dict, Any
import structlog

from api.models.job import Job
from worker.base import BaseWorkerTask, TaskExecutionMixin
from worker.processors.video import VideoProcessor
from worker.processors.analysis import AnalysisProcessor

logger = structlog.get_logger()


class VideoProcessingTask(BaseWorkerTask, TaskExecutionMixin):
    """Task for video processing with base functionality."""
    
    async def process_video_async(self, job: Job) -> Dict[str, Any]:
        """Process video with the refactored async logic."""
        # Create storage backends
        input_backend, output_backend = await self.create_storage_backends(
            job.input_path, job.output_path
        )
        
        # Parse paths
        _, input_path = self.parse_storage_path(job.input_path)
        _, output_path = self.parse_storage_path(job.output_path)
        
        # Create temporary directory for processing
        with await self.with_temp_directory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Download input file
            await self.progress_tracker.update(0, "downloading", "Downloading input file")
            local_input = temp_path / "input" / Path(input_path).name
            await self.download_file(input_backend, input_path, local_input)
            
            # Probe and process file
            await self.progress_tracker.update(10, "analyzing", "Analyzing input file")
            processor = VideoProcessor()
            await processor.initialize()
            video_info = await processor.get_video_info(str(local_input))
            
            # Prepare output path
            local_output = temp_path / "output" / Path(output_path).name
            local_output.parent.mkdir(parents=True, exist_ok=True)
            
            # Process file
            await self.progress_tracker.update(20, "processing", "Processing video")
            result = await processor.safe_process(
                input_path=str(local_input),
                output_path=str(local_output),
                options=job.options,
                operations=job.operations,
                progress_callback=self.progress_tracker.ffmpeg_callback,
            )
            
            # Upload output file
            await self.progress_tracker.update(90, "uploading", "Uploading output file")
            await self.upload_file(output_backend, local_output, output_path)
            
            # Complete
            await self.progress_tracker.update(100, "complete", "Processing complete")
            
            return {
                "output_path": job.output_path,
                "metrics": result.get('metrics', {}),
                "vmaf_score": result.get("metrics", {}).get("vmaf"),
                "psnr_score": result.get("metrics", {}).get("psnr"),
            }


class AnalysisTask(BaseWorkerTask, TaskExecutionMixin):
    """Task for media analysis."""
    
    async def analyze_media_async(self, job: Job) -> Dict[str, Any]:
        """Analyze media quality metrics."""
        processor = AnalysisProcessor()
        await processor.initialize()
        
        result = await processor.analyze(job)
        
        # Update job with analysis results
        await self.update_job_status(
            str(job.id),
            job.status,
            vmaf_score=result.get("vmaf"),
            psnr_score=result.get("psnr"),
            ssim_score=result.get("ssim")
        )
        
        return result


class StreamingTask(BaseWorkerTask, TaskExecutionMixin):
    """Task for creating streaming formats."""
    
    async def process_streaming_async(self, job: Job) -> Dict[str, Any]:
        """Process streaming formats (HLS/DASH)."""
        from worker.processors.streaming import StreamingProcessor
        
        # Create storage backends
        input_backend, output_backend = await self.create_storage_backends(
            job.input_path, job.output_path
        )
        
        # Parse paths
        _, input_path = self.parse_storage_path(job.input_path)
        _, output_path = self.parse_storage_path(job.output_path)
        
        # Create temporary directory for processing
        with await self.with_temp_directory("rendiff_streaming_") as temp_dir:
            temp_path = Path(temp_dir)
            
            # Download input file
            await self.progress_tracker.update(0, "downloading", "Downloading input file")
            local_input = temp_path / "input" / Path(input_path).name
            await self.download_file(input_backend, input_path, local_input)
            
            # Process streaming formats
            await self.progress_tracker.update(20, "processing", "Creating streaming formats")
            processor = StreamingProcessor()
            await processor.initialize()
            
            local_output_dir = temp_path / "output"
            result = await processor.safe_process(
                input_path=str(local_input),
                output_path=str(local_output_dir),
                options=job.options,
                operations=job.operations,
                progress_callback=self.progress_tracker.ffmpeg_callback,
            )
            
            # Upload streaming files
            await self.progress_tracker.update(80, "uploading", "Uploading streaming files")
            # Upload the entire streaming directory structure
            await self.upload_streaming_directory(output_backend, local_output_dir, output_path)
            
            await self.progress_tracker.update(100, "complete", "Streaming creation complete")
            
            return {
                "output_path": job.output_path,
                "streaming_info": result.get("streaming_info", {}),
            }
    
    async def upload_streaming_directory(self, backend, local_dir: Path, remote_base_path: str):
        """Upload streaming directory structure."""
        for file_path in local_dir.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(local_dir)
                remote_path = f"{remote_base_path}/{relative_path}"
                await self.upload_file(backend, file_path, remote_path)


# Task instances
video_task = VideoProcessingTask()
analysis_task = AnalysisTask()
streaming_task = StreamingTask()


def process_job(job_id: str) -> Dict[str, Any]:
    """
    Main task for processing conversion jobs - Refactored.
    """
    logger.info(f"Starting job processing: {job_id}")
    return asyncio.run(video_task.execute_with_error_handling(
        job_id, video_task.process_video_async
    ))


def analyze_media(job_id: str) -> Dict[str, Any]:
    """
    Task for analyzing media quality metrics - Refactored.
    """
    logger.info(f"Starting media analysis: {job_id}")
    return asyncio.run(analysis_task.execute_with_error_handling(
        job_id, analysis_task.analyze_media_async
    ))


def create_streaming(job_id: str) -> Dict[str, Any]:
    """
    Task for creating streaming formats (HLS/DASH) - Refactored.
    """
    logger.info(f"Starting streaming creation: {job_id}")
    return asyncio.run(streaming_task.execute_with_error_handling(
        job_id, streaming_task.process_streaming_async
    ))