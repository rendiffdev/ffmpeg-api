"""
Media file validation utility for security and integrity checks.
Prevents malicious uploads and ensures file safety.
"""
import hashlib
import magic
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import structlog

from worker.utils.ffmpeg import FFmpegWrapper, FFmpegError

logger = structlog.get_logger()


class MediaValidationError(Exception):
    """Exception raised for media validation failures."""
    pass


class MaliciousFileError(MediaValidationError):
    """Exception raised for potentially malicious files."""
    pass


class MediaValidator:
    """Advanced media file validator for security and integrity."""
    
    def __init__(self):
        self.ffmpeg = FFmpegWrapper()
        
        # Allowed MIME types for media files
        self.allowed_mime_types = {
            # Video formats
            'video/mp4',
            'video/quicktime',
            'video/x-msvideo',  # AVI
            'video/x-matroska',  # MKV
            'video/webm',
            'video/x-flv',
            'video/3gpp',
            'video/mp2t',  # MPEG-TS
            'video/mpeg',
            'video/ogg',
            
            # Audio formats  
            'audio/mpeg',  # MP3
            'audio/mp4',  # M4A/AAC
            'audio/wav',
            'audio/x-wav',
            'audio/ogg',
            'audio/flac',
            'audio/x-flac',
            'audio/aac',
            'audio/webm',
        }
        
        # Dangerous file extensions that should never be processed
        self.dangerous_extensions = {
            '.exe', '.bat', '.cmd', '.com', '.scr', '.pif', '.vbs', '.js',
            '.jar', '.app', '.deb', '.rpm', '.dmg', '.pkg', '.msi',
            '.sh', '.bash', '.zsh', '.fish', '.ps1', '.php', '.asp', '.jsp'
        }
        
        # Maximum file sizes (in bytes)
        self.max_file_sizes = {
            'free': 100 * 1024 * 1024,      # 100MB
            'basic': 500 * 1024 * 1024,     # 500MB  
            'premium': 2 * 1024 * 1024 * 1024,  # 2GB
            'enterprise': 10 * 1024 * 1024 * 1024  # 10GB
        }
        
        # Known malicious file signatures (hex patterns)
        self.malicious_signatures = [
            b'MZ',  # PE executable header
            b'\x7fELF',  # ELF executable header
            b'\xca\xfe\xba\xbe',  # Java class file
            b'PK\x03\x04',  # ZIP header (could contain malicious content)
        ]
    
    async def validate_media_file(self, file_path: str, api_key_tier: str = 'free',
                                 check_content: bool = True) -> Dict[str, any]:
        """
        Comprehensive media file validation.
        
        Args:
            file_path: Path to the media file
            api_key_tier: API key tier for size limits
            check_content: Whether to perform deep content analysis
            
        Returns:
            Dict with validation results
            
        Raises:
            MediaValidationError: If validation fails
            MaliciousFileError: If file appears malicious
        """
        try:
            await self.ffmpeg.initialize()
            
            validation_results = {
                'file_path': file_path,
                'is_valid': False,
                'file_size': 0,
                'mime_type': None,
                'format_info': None,
                'security_checks': {},
                'warnings': [],
                'errors': []
            }
            
            # Basic file existence and accessibility
            if not os.path.exists(file_path):
                raise MediaValidationError(f"File not found: {file_path}")
            
            if not os.access(file_path, os.R_OK):
                raise MediaValidationError(f"File not readable: {file_path}")
            
            # File size validation
            file_size = os.path.getsize(file_path)
            validation_results['file_size'] = file_size
            
            max_size = self.max_file_sizes.get(api_key_tier, self.max_file_sizes['free'])
            if file_size > max_size:
                raise MediaValidationError(
                    f"File size {file_size} exceeds limit {max_size} for tier {api_key_tier}"
                )
            
            if file_size == 0:
                raise MediaValidationError("File is empty")
            
            # Extension validation
            file_ext = Path(file_path).suffix.lower()
            if file_ext in self.dangerous_extensions:
                raise MaliciousFileError(f"Dangerous file extension: {file_ext}")
            
            # MIME type validation
            mime_type = self._get_mime_type(file_path)
            validation_results['mime_type'] = mime_type
            
            if mime_type not in self.allowed_mime_types:
                raise MediaValidationError(f"Unsupported MIME type: {mime_type}")
            
            # Security checks
            security_results = await self._perform_security_checks(file_path)
            validation_results['security_checks'] = security_results
            
            if security_results.get('malicious_signatures'):
                raise MaliciousFileError("File contains malicious signatures")
            
            # Content validation with FFmpeg/FFprobe
            if check_content:
                try:
                    format_info = await self._validate_media_content(file_path)
                    validation_results['format_info'] = format_info
                    
                    # Additional content-based security checks
                    content_security = await self._check_content_security(file_path, format_info)
                    if content_security.get('suspicious'):
                        validation_results['warnings'].extend(content_security.get('warnings', []))
                        
                except FFmpegError as e:
                    raise MediaValidationError(f"Media content validation failed: {e}")
            
            validation_results['is_valid'] = True
            
            logger.info(
                "Media file validation successful",
                file_path=file_path,
                file_size=file_size,
                mime_type=mime_type,
                tier=api_key_tier
            )
            
            return validation_results
            
        except Exception as e:
            logger.error("Media validation failed", file_path=file_path, error=str(e))
            raise
    
    def _get_mime_type(self, file_path: str) -> str:
        """Get MIME type using python-magic."""
        try:
            mime = magic.Magic(mime=True)
            return mime.from_file(file_path)
        except Exception:
            # Fallback to basic extension-based detection
            ext = Path(file_path).suffix.lower()
            mime_map = {
                '.mp4': 'video/mp4',
                '.avi': 'video/x-msvideo',
                '.mov': 'video/quicktime',
                '.mkv': 'video/x-matroska',
                '.webm': 'video/webm',
                '.mp3': 'audio/mpeg',
                '.wav': 'audio/wav',
                '.flac': 'audio/flac'
            }
            return mime_map.get(ext, 'application/octet-stream')
    
    async def _perform_security_checks(self, file_path: str) -> Dict[str, any]:
        """Perform security-focused file analysis."""
        security_results = {
            'malicious_signatures': False,
            'file_hash': None,
            'entropy_analysis': None,
            'embedded_executables': False
        }
        
        try:
            # Calculate file hash for integrity
            with open(file_path, 'rb') as f:
                file_content = f.read(8192)  # Read first 8KB for analysis
                security_results['file_hash'] = hashlib.sha256(f.read()).hexdigest()
                
                # Check for malicious signatures in file header
                for signature in self.malicious_signatures:
                    if signature in file_content:
                        security_results['malicious_signatures'] = True
                        break
                
                # Basic entropy analysis (high entropy might indicate packed/encrypted content)
                if len(file_content) > 0:
                    entropy = self._calculate_entropy(file_content)
                    security_results['entropy_analysis'] = {
                        'entropy': entropy,
                        'suspicious': entropy > 7.5  # High entropy threshold
                    }
            
            return security_results
            
        except Exception as e:
            logger.warning("Security check failed", file_path=file_path, error=str(e))
            return security_results
    
    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of data."""
        if not data:
            return 0
        
        # Count byte frequencies
        freq = [0] * 256
        for byte in data:
            freq[byte] += 1
        
        # Calculate entropy
        entropy = 0
        data_len = len(data)
        for count in freq:
            if count > 0:
                p = count / data_len
                entropy -= p * (p.bit_length() - 1)
        
        return entropy
    
    async def _validate_media_content(self, file_path: str) -> Dict[str, any]:
        """Validate media content using FFprobe."""
        try:
            probe_info = await self.ffmpeg.probe_file(file_path)
            
            # Basic format validation
            format_info = probe_info.get('format', {})
            streams = probe_info.get('streams', [])
            
            if not streams:
                raise MediaValidationError("No streams found in media file")
            
            # Validate stream types
            valid_stream_types = {'video', 'audio', 'subtitle', 'attachment'}
            for stream in streams:
                codec_type = stream.get('codec_type', '')
                if codec_type not in valid_stream_types:
                    raise MediaValidationError(f"Invalid stream type: {codec_type}")
            
            return {
                'format_name': format_info.get('format_name', ''),
                'duration': float(format_info.get('duration', 0)),
                'bit_rate': int(format_info.get('bit_rate', 0)),
                'size': int(format_info.get('size', 0)),
                'nb_streams': format_info.get('nb_streams', 0),
                'streams': [
                    {
                        'index': s.get('index', 0),
                        'codec_type': s.get('codec_type', ''),
                        'codec_name': s.get('codec_name', ''),
                        'duration': float(s.get('duration', 0))
                    }
                    for s in streams
                ]
            }
            
        except Exception as e:
            raise MediaValidationError(f"Content validation failed: {e}")
    
    async def _check_content_security(self, file_path: str, format_info: Dict) -> Dict[str, any]:
        """Perform additional security checks on media content."""
        security_info = {
            'suspicious': False,
            'warnings': []
        }
        
        try:
            # Check for suspicious duration (extremely long files)
            duration = format_info.get('duration', 0)
            if duration > 86400:  # > 24 hours
                security_info['warnings'].append(f"Unusually long duration: {duration}s")
                security_info['suspicious'] = True
            
            # Check for suspicious stream count
            stream_count = format_info.get('nb_streams', 0)
            if stream_count > 50:  # Unusual number of streams
                security_info['warnings'].append(f"Unusual stream count: {stream_count}")
                security_info['suspicious'] = True
            
            # Check for suspicious codec combinations
            streams = format_info.get('streams', [])
            codec_names = [s.get('codec_name', '') for s in streams]
            
            # Flag unusual or potentially dangerous codecs
            suspicious_codecs = {'bintext', 'idf', 'executable'}
            for codec in codec_names:
                if codec in suspicious_codecs:
                    security_info['warnings'].append(f"Suspicious codec: {codec}")
                    security_info['suspicious'] = True
            
            return security_info
            
        except Exception as e:
            logger.warning("Content security check failed", error=str(e))
            return security_info
    
    async def validate_batch_files(self, file_paths: List[str], 
                                 api_key_tier: str = 'free') -> Dict[str, any]:
        """Validate multiple files in batch."""
        results = {
            'total_files': len(file_paths),
            'valid_files': 0,
            'invalid_files': 0,
            'total_size': 0,
            'results': []
        }
        
        for file_path in file_paths:
            try:
                validation = await self.validate_media_file(file_path, api_key_tier)
                results['valid_files'] += 1
                results['total_size'] += validation['file_size']
                results['results'].append({
                    'file_path': file_path,
                    'status': 'valid',
                    'validation': validation
                })
            except Exception as e:
                results['invalid_files'] += 1
                results['results'].append({
                    'file_path': file_path,
                    'status': 'invalid',
                    'error': str(e)
                })
        
        return results


# Global validator instance
media_validator = MediaValidator()