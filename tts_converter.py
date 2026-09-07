from backend.config import Config
from backend.services.tts_service import TTSService


class TTSConverter(TTSService):
    def __init__(self):
        super().__init__(Config.AUDIO_FOLDER, Config.AI_VOICES, Config.DEFAULT_VOICE)

