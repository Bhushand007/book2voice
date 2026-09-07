import os
from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent
    FRONTEND_DIR = BASE_DIR / "frontend"
    TEMPLATE_DIR = FRONTEND_DIR / "templates"
    STATIC_DIR = FRONTEND_DIR / "static"

    DATA_DIR = Path(os.environ.get("APP_DATA_DIR", str(BASE_DIR)))
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    SECRET_KEY = os.environ.get("SECRET_KEY", "book2voice-local-secret")

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = database_url or f"sqlite:///{(DATA_DIR / 'book2voice.db').as_posix()}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAX_CONTENT_LENGTH = 25 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"pdf"}
    SUPPORTED_LANGUAGES = {"en"}
    AI_VOICES = {
        "aria": "en-US-AriaNeural",
        "jenny": "en-US-JennyNeural",
        "guy": "en-US-GuyNeural",
        "ryan": "en-GB-RyanNeural",
    }
    DEFAULT_VOICE = "aria"

    UPLOAD_FOLDER = DATA_DIR / "uploads"
    AUDIO_FOLDER = DATA_DIR / "generated_audio"
    LOG_FOLDER = DATA_DIR / "logs"
