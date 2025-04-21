import subprocess
from app.config import settings

def run_ffmpeg_command(cmd: list):
    if settings.MODE == 'local':
        full = [str(settings.FFMPEG_PATH)] + cmd
    else:
        full = ['ssh', '-i', str(settings.SSH_KEY_PATH), f"{settings.SSH_USER}@{settings.SSH_HOST}", str(settings.FFMPEG_PATH)] + cmd
    return subprocess.run(full, capture_output=True)
