FROM python:3.10-slim

RUN useradd -m ffapi
WORKDIR /home/ffapi/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ssh gcc libsm6 libxext6 libxrender1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
USER ffapi
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
