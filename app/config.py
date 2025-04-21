from pydantic import BaseSettings, Field
from pathlib import Path
from typing import Optional

class Settings(BaseSettings):
    HOST: str
    PORT: int
    WORKERS: int

    FFMPEG_PATH: Path
    FFPROBE_PATH: Path
    VMAF_PATH: Path
    MODE: str
    SSH_HOST: Optional[str]
    SSH_USER: Optional[str]
    SSH_KEY_PATH: Optional[Path]

    AWS_ACCESS_KEY_ID: Optional[str]
    AWS_SECRET_ACCESS_KEY: Optional[str]
    AWS_REGION: str

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    class Config:
        env_file = ".env"

settings = Settings()






