from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path
from typing import Optional

class Settings(BaseSettings):
    HOST: str = Field("0.0.0.0")
    PORT: int = Field(8000)
    WORKERS: int = Field(4)

    FFMPEG_PATH: Path = Field(Path("/usr/bin/ffmpeg"))
    FFPROBE_PATH: Path = Field(Path("/usr/bin/ffprobe"))
    VMAF_PATH: Path = Field(Path("/usr/local/bin/ffmpeg-quality-metrics"))
    MODE: str = Field("local")
    SSH_HOST: Optional[str]
    SSH_USER: Optional[str]
    SSH_KEY_PATH: Optional[Path]

    AWS_ACCESS_KEY_ID: Optional[str]
    AWS_SECRET_ACCESS_KEY: Optional[str]
    AWS_REGION: str = Field("us-east-1")

    SECRET_KEY: str = Field(...)
    ALGORITHM: str = Field("HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(60)

    class Config:
        env_file = ".env"

settings = Settings()
