import logging
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
from server.api.chat import router as chat_router
from server.config import LOG_LEVEL, LOG_FORMAT, LOG_FILE, APP_NAME, APP_VERSION

# Configuration du logging
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

app = FastAPI(title=APP_NAME, version=APP_VERSION)

logger.info(f"Démarrage de {APP_NAME} v{APP_VERSION}")

app.mount("/ui", StaticFiles(directory="server/ui", html=True), name="ui")

@app.get("/")
def health():
    return {"status": "ok"}

app.include_router(chat_router)
