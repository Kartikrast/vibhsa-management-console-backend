from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# allow CORS origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    return {"status": "ok"}
