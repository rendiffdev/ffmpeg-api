#!/usr/bin/env python3
"""
FFmpeg Auto-Update Script
Downloads and installs the latest FFmpeg build from BtbN/FFmpeg-Builds
"""
import os
import sys
import json
import platform
import tarfile
import zipfile
import shutil
import hashlib
from pathlib import Path
from typing import Dict, Optional, Tuple
import urllib.request
import urllib.error
import tempfile
import subprocess
from datetime import datetime


class FFmpegUpdater:
    """Manages FFmpeg installation and updates from BtbN/FFmpeg-Builds."""
    
    GITHUB_API_URL = "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest"
    FFMPEG_INSTALL_DIR = "/usr/local/ffmpeg"
    FFMPEG_BIN_DIR = "/usr/local/bin"
    VERSION_FILE = "/usr/local/ffmpeg/version.json"
    
    def __init__(self):
        self.platform = self._detect_platform()
        self.architecture = self._detect_architecture()
        
    def _detect_platform(self) -> str:
        """Detect the current operating system."""
        system = platform.system().lower()
        if system == "linux":
            return "linux"
        elif system == "darwin":
            return "macos"
        elif system == "windows":
            return "windows"
        else:
            raise ValueError(f"Unsupported platform: {system}")
    
    def _detect_architecture(self) -> str:
        """Detect the current CPU architecture."""
        machine = platform.machine().lower()
        if machine in ["x86_64", "amd64"]:
            return "amd64"
        elif machine in ["arm64", "aarch64"]:
            return "arm64"
        else:
            raise ValueError(f"Unsupported architecture: {machine}")
    
    def _get_asset_name(self) -> str:
        """Get the appropriate asset name based on platform and architecture."""
        # BtbN naming convention
        if self.platform == "linux":
            if self.architecture == "amd64":
                return "ffmpeg-master-latest-linux64-gpl.tar.xz"
            elif self.architecture == "arm64":
                return "ffmpeg-master-latest-linuxarm64-gpl.tar.xz"
        elif self.platform == "macos":
            # BtbN doesn't provide macOS builds, we'll use a different approach
            raise ValueError("macOS builds not available from BtbN, use homebrew instead")
        elif self.platform == "windows":
            return "ffmpeg-master-latest-win64-gpl.zip"
        
        raise ValueError(f"No asset available for {self.platform}-{self.architecture}")
    
    def get_current_version(self) -> Optional[Dict[str, str]]:
        """Get the currently installed FFmpeg version info."""
        try:
            if os.path.exists(self.VERSION_FILE):
                with open(self.VERSION_FILE, 'r') as f:
                    return json.load(f)
            
            # Try to get version from ffmpeg command
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                return {
                    'version': version_line,
                    'installed_date': 'unknown',
                    'source': 'system'
                }
        except Exception:
            pass
        
        return None
    
    def fetch_latest_release(self) -> Dict[str, any]:
        """Fetch the latest release information from GitHub."""
        try:
            print("Fetching latest release information...")
            
            req = urllib.request.Request(
                self.GITHUB_API_URL,
                headers={'Accept': 'application/vnd.github.v3+json'}
            )
            
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode())
                
        except urllib.error.HTTPError as e:
            raise Exception(f"Failed to fetch release info: {e}")
    
    def download_ffmpeg(self, download_url: str, output_path: str) -> None:
        """Download FFmpeg binary from the given URL."""
        print(f"Downloading FFmpeg from {download_url}")
        print(f"This may take a while...")
        
        try:
            # Download with progress
            def download_progress(block_num, block_size, total_size):
                downloaded = block_num * block_size
                percent = min(downloaded * 100 / total_size, 100)
                progress = int(50 * percent / 100)
                sys.stdout.write(f'\r[{"=" * progress}{" " * (50 - progress)}] {percent:.1f}%')
                sys.stdout.flush()
            
            urllib.request.urlretrieve(download_url, output_path, reporthook=download_progress)
            print()  # New line after progress
            
        except Exception as e:
            raise Exception(f"Download failed: {e}")
    
    def extract_archive(self, archive_path: str, extract_to: str) -> str:
        """Extract the downloaded archive."""
        print(f"Extracting {archive_path}...")
        
        os.makedirs(extract_to, exist_ok=True)
        
        if archive_path.endswith('.tar.xz'):
            # Handle tar.xz files
            subprocess.run(['tar', '-xf', archive_path, '-C', extract_to], check=True)
        elif archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
        else:
            raise ValueError(f"Unsupported archive format: {archive_path}")
        
        # Find the extracted directory
        extracted_dirs = [d for d in os.listdir(extract_to) 
                         if os.path.isdir(os.path.join(extract_to, d)) and 'ffmpeg' in d]
        
        if not extracted_dirs:
            raise Exception("No FFmpeg directory found in archive")
        
        return os.path.join(extract_to, extracted_dirs[0])
    
    def install_ffmpeg(self, source_dir: str) -> None:
        """Install FFmpeg binaries to the system."""
        print("Installing FFmpeg...")
        
        # Create installation directory
        os.makedirs(self.FFMPEG_INSTALL_DIR, exist_ok=True)
        os.makedirs(self.FFMPEG_BIN_DIR, exist_ok=True)
        
        # Find binaries
        bin_dir = os.path.join(source_dir, 'bin')
        if not os.path.exists(bin_dir):
            # Sometimes binaries are in the root
            bin_dir = source_dir
        
        binaries = ['ffmpeg', 'ffprobe', 'ffplay']
        if self.platform == 'windows':
            binaries = [b + '.exe' for b in binaries]
        
        # Copy binaries
        for binary in binaries:
            src = os.path.join(bin_dir, binary)
            if os.path.exists(src):
                dst = os.path.join(self.FFMPEG_BIN_DIR, binary)
                print(f"Installing {binary}...")
                shutil.copy2(src, dst)
                if self.platform != 'windows':
                    os.chmod(dst, 0o755)
        
        # Copy other files (licenses, etc.)
        for item in ['LICENSE', 'README.txt', 'doc']:
            src = os.path.join(source_dir, item)
            if os.path.exists(src):
                dst = os.path.join(self.FFMPEG_INSTALL_DIR, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
    
    def save_version_info(self, release_info: Dict[str, any]) -> None:
        """Save version information for future reference."""
        version_info = {
            'version': release_info.get('tag_name', 'unknown'),
            'release_date': release_info.get('published_at', ''),
            'installed_date': datetime.now().isoformat(),
            'source': 'BtbN/FFmpeg-Builds',
            'platform': self.platform,
            'architecture': self.architecture
        }
        
        with open(self.VERSION_FILE, 'w') as f:
            json.dump(version_info, f, indent=2)
    
    def verify_installation(self) -> bool:
        """Verify that FFmpeg was installed correctly."""
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("\nFFmpeg installation verified:")
                print(result.stdout.split('\n')[0])
                return True
        except Exception as e:
            print(f"Verification failed: {e}")
        
        return False
    
    def update(self, force: bool = False) -> bool:
        """Update FFmpeg to the latest version."""
        try:
            # Check current version
            current_version = self.get_current_version()
            if current_version and not force:
                print(f"Current FFmpeg version: {current_version.get('version', 'unknown')}")
            
            # Fetch latest release
            release_info = self.fetch_latest_release()
            latest_version = release_info.get('tag_name', 'unknown')
            
            if current_version and not force:
                if current_version.get('version', '').find(latest_version) != -1:
                    print(f"FFmpeg is already up to date ({latest_version})")
                    return True
            
            print(f"Latest version available: {latest_version}")
            
            # Find the appropriate asset
            asset_name = self._get_asset_name()
            asset = None
            
            for a in release_info.get('assets', []):
                if a['name'] == asset_name:
                    asset = a
                    break
            
            if not asset:
                raise Exception(f"Asset not found: {asset_name}")
            
            download_url = asset['browser_download_url']
            
            # Download and install
            with tempfile.TemporaryDirectory() as temp_dir:
                download_path = os.path.join(temp_dir, asset_name)
                extract_path = os.path.join(temp_dir, 'extract')
                
                self.download_ffmpeg(download_url, download_path)
                source_dir = self.extract_archive(download_path, extract_path)
                self.install_ffmpeg(source_dir)
                self.save_version_info(release_info)
            
            # Verify installation
            if self.verify_installation():
                print("\nFFmpeg updated successfully!")
                return True
            else:
                print("\nFFmpeg update completed but verification failed")
                return False
                
        except Exception as e:
            print(f"\nError updating FFmpeg: {e}")
            return False
    
    def check_for_updates(self) -> bool:
        """Check if updates are available without installing."""
        try:
            current_version = self.get_current_version()
            release_info = self.fetch_latest_release()
            latest_version = release_info.get('tag_name', 'unknown')
            
            if current_version:
                current = current_version.get('version', '')
                if current.find(latest_version) == -1:
                    print(f"Update available: {latest_version}")
                    return True
                else:
                    print(f"FFmpeg is up to date ({latest_version})")
                    return False
            else:
                print(f"FFmpeg not installed. Latest version: {latest_version}")
                return True
                
        except Exception as e:
            print(f"Error checking for updates: {e}")
            return False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='FFmpeg Auto-Update Tool')
    parser.add_argument('command', choices=['update', 'check', 'version'],
                       help='Command to execute')
    parser.add_argument('--force', action='store_true',
                       help='Force update even if already up to date')
    
    args = parser.parse_args()
    
    updater = FFmpegUpdater()
    
    if args.command == 'update':
        success = updater.update(force=args.force)
        sys.exit(0 if success else 1)
    
    elif args.command == 'check':
        has_updates = updater.check_for_updates()
        sys.exit(0 if not has_updates else 1)
    
    elif args.command == 'version':
        version = updater.get_current_version()
        if version:
            print(json.dumps(version, indent=2))
        else:
            print("FFmpeg not installed")
            sys.exit(1)


if __name__ == '__main__':
    main()