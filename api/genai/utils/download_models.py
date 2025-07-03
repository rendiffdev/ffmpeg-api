"""
Model Download Utility

Downloads required AI models for GenAI functionality.
"""

import asyncio
import os
from pathlib import Path
from typing import List, Dict, Any
import structlog

from ..config import genai_settings

logger = structlog.get_logger()


async def download_required_models() -> Dict[str, bool]:
    """
    Download all required AI models for GenAI functionality.
    
    Returns:
        Dictionary with model names and download status
    """
    results = {}
    
    # Create model directory
    model_path = Path(genai_settings.MODEL_PATH)
    model_path.mkdir(parents=True, exist_ok=True)
    
    # Download Real-ESRGAN models
    esrgan_results = await download_esrgan_models()
    results.update(esrgan_results)
    
    # Download VideoMAE models
    videomae_results = await download_videomae_models()
    results.update(videomae_results)
    
    return results


async def download_esrgan_models() -> Dict[str, bool]:
    """Download Real-ESRGAN models."""
    results = {}
    
    # Real-ESRGAN model URLs
    model_urls = {
        "RealESRGAN_x4plus": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        "RealESRGAN_x2plus": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.1/RealESRGAN_x2plus.pth",
        "RealESRGAN_x8plus": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x8plus.pth",
    }
    
    for model_name, url in model_urls.items():
        try:
            model_file = Path(genai_settings.MODEL_PATH) / f"{model_name}.pth"
            
            if model_file.exists():
                logger.info(f"Model already exists: {model_name}")
                results[model_name] = True
                continue
            
            logger.info(f"Downloading {model_name} from {url}")
            success = await download_file(url, str(model_file))
            results[model_name] = success
            
            if success:
                logger.info(f"Successfully downloaded {model_name}")
            else:
                logger.error(f"Failed to download {model_name}")
                
        except Exception as e:
            logger.error(f"Error downloading {model_name}: {e}")
            results[model_name] = False
    
    return results


async def download_videomae_models() -> Dict[str, bool]:
    """Download VideoMAE models via Hugging Face."""
    results = {}
    
    try:
        from transformers import VideoMAEImageProcessor, VideoMAEForVideoClassification
        
        model_name = genai_settings.VIDEOMAE_MODEL
        logger.info(f"Downloading VideoMAE model: {model_name}")
        
        # Download processor
        processor = VideoMAEImageProcessor.from_pretrained(model_name)
        processor.save_pretrained(Path(genai_settings.MODEL_PATH) / "videomae" / "processor")
        
        # Download model
        model = VideoMAEForVideoClassification.from_pretrained(model_name)
        model.save_pretrained(Path(genai_settings.MODEL_PATH) / "videomae" / "model")
        
        results["videomae"] = True
        logger.info("Successfully downloaded VideoMAE model")
        
    except ImportError:
        logger.error("Transformers library not installed, cannot download VideoMAE")
        results["videomae"] = False
    except Exception as e:
        logger.error(f"Error downloading VideoMAE model: {e}")
        results["videomae"] = False
    
    return results


async def download_file(url: str, file_path: str) -> bool:
    """
    Download a file from URL.
    
    Args:
        url: URL to download from
        file_path: Local path to save file
    
    Returns:
        True if successful, False otherwise
    """
    try:
        import aiohttp
        import aiofiles
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    async with aiofiles.open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                    return True
                else:
                    logger.error(f"HTTP {response.status} for {url}")
                    return False
                    
    except ImportError:
        # Fallback to synchronous download
        logger.warning("aiohttp not available, using synchronous download")
        return download_file_sync(url, file_path)
    except Exception as e:
        logger.error(f"Download failed for {url}: {e}")
        return False


def download_file_sync(url: str, file_path: str) -> bool:
    """Synchronous file download fallback."""
    try:
        import urllib.request
        
        urllib.request.urlretrieve(url, file_path)
        return True
        
    except Exception as e:
        logger.error(f"Sync download failed for {url}: {e}")
        return False


if __name__ == "__main__":
    """Run model downloader as standalone script."""
    async def main():
        logger.info("Starting model download process")
        results = await download_required_models()
        
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        logger.info(
            "Model download completed",
            success=success_count,
            total=total_count,
            results=results,
        )
        
        if success_count == total_count:
            logger.info("All models downloaded successfully")
        else:
            logger.warning(f"Only {success_count}/{total_count} models downloaded")
    
    asyncio.run(main())