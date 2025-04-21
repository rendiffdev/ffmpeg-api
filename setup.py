#!/usr/bin/env python3
from pathlib import Path

def prompt(text, default=None):
    val = input(f"{text}{f' [{default}]' if default else ''}: ")
    return val.strip() or default

cfg = {}
cfg['FFMPEG_PATH'] = prompt('Path to ffmpeg', '/usr/bin/ffmpeg')
cfg['FFPROBE_PATH'] = prompt('Path to ffprobe', '/usr/bin/ffprobe')
cfg['VMAF_PATH'] = prompt('Path to ffmpeg-quality-metrics', '/usr/local/bin/ffmpeg-quality-metrics')
cfg['MODE'] = prompt('Mode (local/ssh)', 'local')
if cfg['MODE']=='ssh':
    cfg['SSH_HOST'] = prompt('SSH host')
    cfg['SSH_USER'] = prompt('SSH user')
    cfg['SSH_KEY_PATH'] = prompt('SSH key path')
use_s3 = prompt('Use AWS S3? (yes/no)', 'no')
if use_s3.lower()=='yes':
    cfg['AWS_ACCESS_KEY_ID'] = prompt('AWS Access Key ID')
    cfg['AWS_SECRET_ACCESS_KEY'] = prompt('AWS Secret Access Key')
    cfg['AWS_REGION'] = prompt('AWS Region', 'us-east-1')
else:
    cfg['AWS_ACCESS_KEY_ID']=''
    cfg['AWS_SECRET_ACCESS_KEY']=''
    cfg['AWS_REGION']='us-east-1'
cfg['SECRET_KEY'] = prompt('JWT Secret Key')
cfg['ALGORITHM'] = 'HS256'
cfg['ACCESS_TOKEN_EXPIRE_MINUTES'] = prompt('Token expiry minutes', '60')
cfg['HOST'] = prompt('API Host', '0.0.0.0')
cfg['PORT'] = prompt('API Port', '8000')
cfg['WORKERS'] = prompt('Workers', '4')
path=Path('.env')
if path.exists() and prompt('.env exists overwrite? (yes/no)', 'no')!='yes': exit(0)
with open(path,'w') as f:
    for k,v in cfg.items(): f.write(f"{k}={v}\n")
print('Generated .env')
