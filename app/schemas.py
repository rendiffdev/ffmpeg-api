from pydantic import BaseModel
from typing import Literal, List
class Location(BaseModel):
    local_path: str | None
    s3_path: str | None
class TranscodeReq(BaseModel):
    input: Location
    output: Location
    codec: Literal['h264','hevc','vp9','av1']
    crf: int
    preset: str
class QualityReq(BaseModel):
    reference: Location
    distorted: Location
    metrics: List[Literal['vmaf','psnr','ssim']]
class ImageOp(BaseModel):
    type: Literal['resize','crop','filter','watermark']
    params: dict
class ImageReq(BaseModel):
    input: Location
    output: Location
    operations: List[ImageOp]
class AudioReq(BaseModel):
    input: Location
    output: Location
    target_codec: Literal['aac','opus','mp3','wav']
    bitrate: str
    sample_rate: int
    channels: int
class JobResp(BaseModel):
    job_id: str
class JobStatusResp(BaseModel):
    id: str
    status: str
    log: str
    error: str
    time_taken: float | None