from fastapi import FastAPI
from app.config import settings
from app.routers import auth, video, image, audio
import uvicorn

app = FastAPI(title="FFmpeg API Service")
app.include_router(auth.router)
app.include_router(video.router)
app.include_router(image.router)
app.include_router(audio.router)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, workers=settings.WORKERS)