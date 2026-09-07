import asyncio
import re
import socket
from datetime import datetime
from pathlib import Path

import aiohttp
import edge_tts


class TTSServiceUnavailable(RuntimeError):
    """Raised when the remote neural voice provider cannot be reached."""


class TTSService:
    MAX_ATTEMPTS = 3
    RETRY_DELAYS_SECONDS = (1, 3)
    VOICE_HOST = "speech.platform.bing.com"

    def __init__(self, audio_folder: Path, voices: dict[str, str], default_voice: str):
        self.audio_folder = audio_folder
        self.voices = voices
        self.default_voice = default_voice
        self.audio_folder.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def estimate_duration_seconds(text: str, speed: float) -> float:
        words = max(len(text.split()), 1)
        words_per_minute = 165 * max(speed, 0.75)
        return round((words / words_per_minute) * 60, 2)

    @staticmethod
    def rate_from_speed(speed: float) -> str:
        percent = int(round((speed - 1.0) * 100))
        return f"{percent:+d}%"

    @staticmethod
    def split_text(text: str, max_chars: int = 3500) -> list[str]:
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        chunks: list[str] = []
        current = ""

        for paragraph in paragraphs:
            sentences = re.split(r"(?<=[.!?])\s+", paragraph) if len(paragraph) > max_chars else [paragraph]
            for sentence in sentences:
                # Very long sentences are divided without dropping any text.
                while len(sentence) > max_chars:
                    split_at = sentence.rfind(" ", 0, max_chars)
                    split_at = split_at if split_at > 0 else max_chars
                    if current:
                        chunks.append(current)
                        current = ""
                    chunks.append(sentence[:split_at].strip())
                    sentence = sentence[split_at:].strip()

                candidate = f"{current}\n\n{sentence}".strip() if current else sentence
                if len(candidate) <= max_chars:
                    current = candidate
                    continue

                if current:
                    chunks.append(current)
                current = sentence[:max_chars]

        if current:
            chunks.append(current)

        return chunks or [text[:max_chars]]

    @classmethod
    def voice_service_available(cls) -> bool:
        """Check DNS before starting a conversion, without making a full TTS request."""
        try:
            socket.getaddrinfo(cls.VOICE_HOST, 443, type=socket.SOCK_STREAM)
            return True
        except socket.gaierror:
            return False

    async def _stream_to_mp3(self, chunks: list[str], voice: str, rate: str, audio_path: Path) -> None:
        with audio_path.open("wb") as output:
            for chunk_number, chunk in enumerate(chunks, start=1):
                last_error: Exception | None = None
                for attempt in range(self.MAX_ATTEMPTS):
                    try:
                        # Buffer each chunk so a failed retry never corrupts the MP3.
                        audio_data = bytearray()
                        communicator = edge_tts.Communicate(chunk, voice=voice, rate=rate)
                        async for message in communicator.stream():
                            if message["type"] == "audio":
                                audio_data.extend(message["data"])

                        if not audio_data:
                            raise RuntimeError("The voice provider returned no audio data.")
                        output.write(audio_data)
                        break
                    except (aiohttp.ClientError, asyncio.TimeoutError, OSError, RuntimeError) as exc:
                        last_error = exc
                        if attempt < self.MAX_ATTEMPTS - 1:
                            await asyncio.sleep(self.RETRY_DELAYS_SECONDS[attempt])
                else:
                    raise TTSServiceUnavailable(
                        "The neural voice service could not be reached after 3 attempts. "
                        "Check the server internet connection and DNS, then try again."
                    ) from last_error

    def convert(self, text: str, language: str, speed: float, title_hint: str, voice_key: str | None = None) -> dict:
        if language != "en":
            raise ValueError("Only English voice conversion is supported.")
        if not text.strip():
            raise ValueError("Text is empty.")

        selected_voice_key = voice_key if voice_key in self.voices else self.default_voice
        voice = self.voices[selected_voice_key]
        safe_title = "".join(ch if ch.isalnum() else "_" for ch in title_hint).strip("_") or "book_audio"
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        filename = f"{safe_title[:40]}_{selected_voice_key}_{timestamp}.mp3"
        audio_path = self.audio_folder / filename

        if not self.voice_service_available():
            raise TTSServiceUnavailable(
                "The neural voice service is temporarily unreachable. "
                "Check the server internet connection and DNS, then try again."
            )

        chunks = self.split_text(text)
        try:
            asyncio.run(self._stream_to_mp3(chunks, voice=voice, rate=self.rate_from_speed(speed), audio_path=audio_path))
        except Exception:
            # Never leave partial files in the audio library after a failed conversion.
            audio_path.unlink(missing_ok=True)
            raise

        if not audio_path.exists() or audio_path.stat().st_size == 0:
            raise RuntimeError("Voice engine did not produce audio.")

        return {
            "filename": filename,
            "file_path": str(audio_path),
            "duration_seconds": self.estimate_duration_seconds(text, speed),
            "file_size": audio_path.stat().st_size,
            "voice": selected_voice_key,
        }
