from fastapi import FastAPI

from app.core.config import get_settings
from app.routes import auth
from app.routes import marketplaces

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.APP_DEBUG,
)
app.include_router(auth.router)
app.include_router(marketplaces.router)

@app.get("/")
def health_check():
    return {"status": "ok"}
