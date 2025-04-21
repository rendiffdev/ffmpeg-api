from fastapi import HTTPException
from app.utils.ffmpeg_client import run_ffmpeg_command
from app.config import settings


def transcode(input_path, output_path, codec, crf, preset):
    cmd = ['-y', '-i', input_path, '-c:v', codec, '-preset', preset, '-crf', str(crf), output_path]
    res = run_ffmpeg_command(cmd)
    if res.returncode != 0:
        raise HTTPException(status_code=500, detail=res.stderr.decode())
    return output_path


def measure_quality(reference_path, distorted_path, metrics: list):
    result = {}
    if 'vmaf' in metrics:
        cmd = ['-i', distorted_path, '-i', reference_path, '-lavfi', f"libvmaf=model_path={settings.VMAF_PATH}", '-f', 'null', '-']
        r = run_ffmpeg_command(cmd)
        if r.returncode != 0:
            raise HTTPException(status_code=500, detail=r.stderr.decode())
        result['vmaf'] = r.stderr.decode()
    if 'psnr' in metrics:
        cmd = ['-i', distorted_path, '-i', reference_path, '-lavfi', 'psnr', '-f', 'null', '-']
        r = run_ffmpeg_command(cmd)
        result['psnr'] = r.stderr.decode()
    if 'ssim' in metrics:
        cmd = ['-i', distorted_path, '-i', reference_path, '-lavfi', 'ssim', '-f', 'null', '-']
        r = run_ffmpeg_command(cmd)
        result['ssim'] = r.stderr.decode()
    return result


def process_image(req, input_path, output_path):
    filters = []
    for op in req.operations:
        if op.type == 'resize':
            filters.append(f"scale={op.params['width']}:{op.params['height']}")
        if op.type == 'crop':
            filters.append(f"crop={op.params['width']}:{op.params['height']}:{op.params.get('x',0)}:{op.params.get('y',0)}")
        if op.type == 'filter':
            filters.append(f"{op.params['name']}={op.params.get('args','')}")
        if op.type == 'watermark':
            filters.append(f"movie={op.params['file']}[wm];[in][wm]overlay={op.params.get('x',10)}:{op.params.get('y',10)}")
    cmd = ['-y', '-i', input_path, '-vf', ','.join(filters), output_path]
    res = run_ffmpeg_command(cmd)
    if res.returncode != 0:
        raise HTTPException(status_code=500, detail=res.stderr.decode())
    return output_path


def convert_audio(req, input_path, output_path):
    cmd = ['-y', '-i', input_path, '-c:a', req.target_codec, '-b:a', req.bitrate, '-ar', str(req.sample_rate), '-ac', str(req.channels), output_path]
    res = run_ffmpeg_command(cmd)
    if res.returncode != 0:
        raise HTTPException(status_code=500, detail=res.stderr.decode())
    return output_path