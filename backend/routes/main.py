import os
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request, send_file, send_from_directory, url_for

from backend.extensions import db
from backend.models import AudioFile, Book, ConversionHistory
from backend.services.file_service import FileService
from backend.services.stats_service import StatsService
from backend.services.text_processing import TextProcessingService
from backend.services.tts_service import TTSService, TTSServiceUnavailable


main_bp = Blueprint("main", __name__)


def json_error(message: str, status_code: int = 400, details: str | None = None):
    payload = {"success": False, "error": message}
    if details:
        payload["details"] = details
    return jsonify(payload), status_code


def sanitize_title(value: str) -> str:
    title = (value or "").strip()
    return (title or "Untitled Book")[:255]


@main_bp.get("/")
def index():
    return render_template("index.html")


@main_bp.get("/health")
def health():
    return jsonify({"success": True, "status": "ok"})


@main_bp.get("/voice-status")
def voice_status():
    available = TTSService.voice_service_available()
    return jsonify(
        {
            "success": available,
            "available": available,
            "message": "Neural voices are ready." if available else "Neural voice service is temporarily unreachable.",
        }
    ), 200 if available else 503


@main_bp.post("/upload")
def upload_file():
    incoming_file = request.files.get("file")
    if not incoming_file:
        return json_error("No file received. Please upload a PDF file.", 400)

    try:
        saved = FileService.save_uploaded_file(
            incoming_file=incoming_file,
            upload_dir=Path(current_app.config["UPLOAD_FOLDER"]),
            max_size_bytes=current_app.config["MAX_CONTENT_LENGTH"],
            allowed_extensions=current_app.config["ALLOWED_EXTENSIONS"],
        )
        cleaned_text = TextProcessingService.clean_text(saved["raw_text"])
        if not cleaned_text:
            return json_error("Uploaded file does not contain readable text.", 400)

        analysis = TextProcessingService.analyze_text(cleaned_text)
        book = Book(
            title=sanitize_title(Path(saved["original_name"]).stem),
            source_type="upload",
            original_filename=saved["original_name"],
            text_content=cleaned_text,
            word_count=analysis["word_count"],
            char_count=analysis["char_count"],
            paragraph_count=analysis["paragraph_count"],
            estimated_listening_minutes=analysis["estimated_listening_minutes"],
        )
        db.session.add(book)
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": "File uploaded and text extracted successfully.",
                "book": {
                    "id": book.id,
                    "title": book.title,
                    "source_type": book.source_type,
                    "word_count": book.word_count,
                    "char_count": book.char_count,
                    "paragraph_count": book.paragraph_count,
                    "estimated_listening_minutes": book.estimated_listening_minutes,
                    "created_at": book.created_at.isoformat(),
                },
                "text": cleaned_text,
            }
        )
    except ValueError as exc:
        return json_error(str(exc), 400)
    except Exception as exc:
        current_app.logger.exception("Upload failed")
        return json_error("File upload failed.", 500, str(exc))


@main_bp.post("/convert")
def convert_to_speech():
    data = request.get_json(silent=True) or {}
    language = str(data.get("language", "en")).strip().lower()
    if language not in current_app.config["SUPPORTED_LANGUAGES"]:
        return json_error("Unsupported language selected.", 400)

    try:
        speed = min(max(float(data.get("speed", 1.0)), 0.75), 1.75)
    except (TypeError, ValueError):
        return json_error("Invalid speed value.", 400)

    voice_key = str(data.get("voice", current_app.config["DEFAULT_VOICE"])).strip().lower()
    if voice_key not in current_app.config["AI_VOICES"]:
        return json_error("Unsupported English voice selected.", 400)

    book_id = data.get("book_id")
    incoming_text = (data.get("text") or "").strip()
    title_input = sanitize_title(data.get("title") or "Manual Input")

    try:
        book = None
        if book_id is not None:
            try:
                book = Book.query.get(int(book_id))
            except (TypeError, ValueError):
                return json_error("Invalid book_id value.", 400)
            if not book:
                return json_error("Book record not found. Please upload again.", 404)

        if incoming_text:
            cleaned_text = TextProcessingService.clean_text(incoming_text)
            analysis = TextProcessingService.analyze_text(cleaned_text)
            if not cleaned_text:
                return json_error("Input text is empty after cleaning.", 400)

            if book:
                book.text_content = cleaned_text
                book.word_count = analysis["word_count"]
                book.char_count = analysis["char_count"]
                book.paragraph_count = analysis["paragraph_count"]
                book.estimated_listening_minutes = analysis["estimated_listening_minutes"]
            else:
                book = Book(
                    title=title_input,
                    source_type="manual",
                    text_content=cleaned_text,
                    word_count=analysis["word_count"],
                    char_count=analysis["char_count"],
                    paragraph_count=analysis["paragraph_count"],
                    estimated_listening_minutes=analysis["estimated_listening_minutes"],
                )
                db.session.add(book)
                db.session.flush()
        elif book:
            cleaned_text = book.text_content
            analysis = TextProcessingService.analyze_text(cleaned_text)
        else:
            return json_error("No text provided for conversion.", 400)

        audio_result = TTSService(
            Path(current_app.config["AUDIO_FOLDER"]),
            voices=current_app.config["AI_VOICES"],
            default_voice=current_app.config["DEFAULT_VOICE"],
        ).convert(
            text=cleaned_text,
            language=language,
            speed=speed,
            title_hint=book.title,
            voice_key=voice_key,
        )
        audio = AudioFile(
            book_id=book.id,
            filename=audio_result["filename"],
            original_name=f"{book.title}.mp3",
            file_path=audio_result["file_path"],
            public_url=url_for("main.stream_audio", filename=audio_result["filename"]),
            duration_seconds=audio_result["duration_seconds"],
            language=language,
            speed=speed,
            file_size=audio_result["file_size"],
        )
        db.session.add(audio)
        db.session.flush()

        db.session.add(
            ConversionHistory(
                book_id=book.id,
                audio_file_id=audio.id,
                status="completed",
                language=language,
                speed=speed,
                chars_processed=analysis["char_count"],
                word_count=analysis["word_count"],
                duration_seconds=audio.duration_seconds,
            )
        )
        StatsService.update_after_conversion(
            word_count=analysis["word_count"],
            char_count=analysis["char_count"],
            duration_seconds=audio.duration_seconds,
        )
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": "Text converted to audio successfully.",
                "audio": {
                    "id": audio.id,
                    "filename": audio.filename,
                    "audio_url": audio.public_url,
                    "download_url": url_for("main.download_audio", audio_id=audio.id),
                    "duration_seconds": audio.duration_seconds,
                    "language": audio.language,
                    "voice": audio_result["voice"],
                    "speed": audio.speed,
                    "created_at": audio.created_at.isoformat(),
                },
                "book": {
                    "id": book.id,
                    "title": book.title,
                    "word_count": analysis["word_count"],
                    "char_count": analysis["char_count"],
                    "estimated_listening_minutes": analysis["estimated_listening_minutes"],
                },
            }
        )
    except TTSServiceUnavailable as exc:
        db.session.rollback()
        current_app.logger.warning("Neural voice provider unavailable: %s", exc)
        return jsonify(
            {
                "success": False,
                "error": str(exc),
                "code": "VOICE_SERVICE_UNAVAILABLE",
                "retryable": True,
            }
        ), 503
    except ValueError as exc:
        db.session.rollback()
        return json_error(str(exc), 400)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Conversion failed")
        return json_error("TTS conversion failed.", 500, str(exc))


@main_bp.get("/audio-list")
def get_audio_list():
    items = AudioFile.query.order_by(AudioFile.created_at.desc()).all()
    return jsonify(
        {
            "success": True,
            "count": len(items),
            "items": [
                {
                    "id": item.id,
                    "book_id": item.book_id,
                    "book_title": item.book.title if item.book else "Unknown",
                    "filename": item.filename,
                    "original_name": item.original_name,
                    "duration_seconds": item.duration_seconds,
                    "language": item.language,
                    "speed": item.speed,
                    "file_size": item.file_size,
                    "audio_url": item.public_url,
                    "download_url": url_for("main.download_audio", audio_id=item.id),
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ],
        }
    )


@main_bp.delete("/delete-audio/<int:audio_id>")
def delete_audio(audio_id: int):
    audio = AudioFile.query.get(audio_id)
    if not audio:
        return json_error("Audio file not found.", 404)

    try:
        for history in audio.histories.all():
            history.audio_file_id = None
        if os.path.exists(audio.file_path):
            os.remove(audio.file_path)
        db.session.delete(audio)
        db.session.commit()
        return jsonify({"success": True, "message": "Audio deleted successfully."})
    except Exception as exc:
        db.session.rollback()
        return json_error("Failed to delete audio.", 500, str(exc))


@main_bp.get("/stats")
def get_stats():
    return jsonify({"success": True, **StatsService.dashboard_payload()})


@main_bp.get("/audio/<path:filename>")
def stream_audio(filename: str):
    return send_from_directory(
        directory=current_app.config["AUDIO_FOLDER"],
        path=filename,
        mimetype="audio/mpeg",
    )


@main_bp.get("/download/<int:audio_id>")
def download_audio(audio_id: int):
    audio = AudioFile.query.get(audio_id)
    if not audio:
        return json_error("Audio file not found.", 404)

    return send_file(
        audio.file_path,
        mimetype="audio/mpeg",
        as_attachment=True,
        download_name=audio.original_name,
    )
