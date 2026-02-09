from fastapi import FastAPI

from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.APP_DEBUG,
)


@app.get("/")
def health_check():
    return {"status": "ok"}
