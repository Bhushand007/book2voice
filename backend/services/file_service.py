import os
import uuid
from pathlib import Path

from PyPDF2 import PdfReader
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


class FileService:
    @staticmethod
    def extension(filename: str) -> str:
        return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    @staticmethod
    def validate_content(file_path: Path, extension: str) -> None:
        if extension == "pdf":
            with file_path.open("rb") as source:
                if source.read(5) != b"%PDF-":
                    raise ValueError("Invalid PDF content.")

    @staticmethod
    def extract_text(file_path: Path, extension: str) -> str:
        if extension == "pdf":
            reader = PdfReader(str(file_path))
            return "\n".join(page.extract_text() or "" for page in reader.pages).strip()

        raise ValueError("Unsupported file extension.")

    @staticmethod
    def save_uploaded_file(
        incoming_file: FileStorage,
        upload_dir: Path,
        max_size_bytes: int,
        allowed_extensions: set[str],
    ) -> dict:
        if not incoming_file or not incoming_file.filename:
            raise ValueError("No file selected.")

        original_name = secure_filename(incoming_file.filename)
        extension = FileService.extension(original_name)
        if extension not in allowed_extensions:
            raise ValueError("Only PDF files are allowed.")

        upload_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}_{original_name}"
        stored_path = upload_dir / stored_name
        incoming_file.save(stored_path)

        if stored_path.stat().st_size > max_size_bytes:
            stored_path.unlink(missing_ok=True)
            raise ValueError("File exceeds maximum size limit.")

        try:
            FileService.validate_content(stored_path, extension)
            raw_text = FileService.extract_text(stored_path, extension)
        except Exception:
            stored_path.unlink(missing_ok=True)
            raise

        if not raw_text.strip():
            stored_path.unlink(missing_ok=True)
            raise ValueError("No extractable text found in file.")

        return {
            "original_name": original_name,
            "stored_name": stored_name,
            "stored_path": str(stored_path),
            "extension": extension,
            "raw_text": raw_text,
            "file_size": os.path.getsize(stored_path),
        }
