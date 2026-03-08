"""
Configuration centralisée pour l'application FLO
"""
import os
from pathlib import Path

# Chemins de base
BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"

# Configuration de l'application
APP_NAME = "FLO LLM Manager"
APP_VERSION = "0.3"
HOST = os.getenv("FLO_HOST", "127.0.0.1")
PORT = int(os.getenv("FLO_PORT", "8000"))
RELOAD = os.getenv("FLO_RELOAD", "true").lower() == "true"
WORKERS = int(os.getenv("FLO_WORKERS", "1"))

# Configuration des sessions
MAX_HISTORY_TOKENS = 1500
SESSION_CLEANUP_INTERVAL = 3600  # secondes
SESSION_MAX_AGE = 86400  # secondes (24h)

# Configuration du logging
LOG_LEVEL = os.getenv("FLO_LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = BASE_DIR / "logs" / "flo.log"

# Configuration des modèles
DEFAULT_MODEL_ID = "mistral_7b"
MODEL_LOAD_TIMEOUT = 120  # secondes

# Configuration de l'API
API_TITLE = f"{APP_NAME} API"
API_DESCRIPTION = "API pour interagir avec des modèles LLM locaux"
API_VERSION = APP_VERSION
CORS_ORIGINS = ["*"]  # À restreindre en production

# Paramètres par défaut pour les LLM
DEFAULT_LLM_PARAMS = {
    "n_ctx": 2048,
    "temperature": 0.7,
    "top_p": 0.9,
    "repeat_penalty": 1.1,
    "max_tokens": 512,
}
