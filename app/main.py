from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path


from app.core.config import get_settings
from app.routes import auth
from app.routes import marketplaces
from app.routes import products
from app.routes import taxonomy

MEDIA_DIR = Path("media")
MEDIA_DIR.mkdir(exist_ok=True)


settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.APP_DEBUG,
)

app.include_router(auth.router)
app.include_router(marketplaces.router)
app.include_router(products.router)
app.include_router(taxonomy.router)

# allow CORS origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

@app.get("/")
def health_check():
    return {"status": "ok"}
