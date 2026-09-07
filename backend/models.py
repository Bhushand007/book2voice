from datetime import datetime

from backend.extensions import db


class Book(db.Model):
    __tablename__ = "books"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    source_type = db.Column(db.String(32), nullable=False, default="manual", index=True)
    original_filename = db.Column(db.String(255), nullable=True)
    text_content = db.Column(db.Text, nullable=False)
    word_count = db.Column(db.Integer, nullable=False, default=0)
    char_count = db.Column(db.Integer, nullable=False, default=0)
    paragraph_count = db.Column(db.Integer, nullable=False, default=0)
    estimated_listening_minutes = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    audio_files = db.relationship("AudioFile", back_populates="book", lazy="dynamic")
    conversion_history = db.relationship("ConversionHistory", back_populates="book", lazy="dynamic")


class AudioFile(db.Model):
    __tablename__ = "audio_files"

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False, unique=True)
    original_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    public_url = db.Column(db.String(500), nullable=False)
    duration_seconds = db.Column(db.Float, nullable=False, default=0.0)
    language = db.Column(db.String(12), nullable=False, default="en", index=True)
    speed = db.Column(db.Float, nullable=False, default=1.0)
    file_size = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    book = db.relationship("Book", back_populates="audio_files")
    histories = db.relationship("ConversionHistory", back_populates="audio_file", lazy="dynamic")

    __table_args__ = (db.Index("ix_audio_book_created", "book_id", "created_at"),)


class ConversionHistory(db.Model):
    __tablename__ = "conversion_history"

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False, index=True)
    audio_file_id = db.Column(db.Integer, db.ForeignKey("audio_files.id"), nullable=True, index=True)
    status = db.Column(db.String(24), nullable=False, default="completed", index=True)
    language = db.Column(db.String(12), nullable=False, default="en")
    speed = db.Column(db.Float, nullable=False, default=1.0)
    chars_processed = db.Column(db.Integer, nullable=False, default=0)
    word_count = db.Column(db.Integer, nullable=False, default=0)
    duration_seconds = db.Column(db.Float, nullable=False, default=0.0)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    book = db.relationship("Book", back_populates="conversion_history")
    audio_file = db.relationship("AudioFile", back_populates="histories")

    __table_args__ = (db.Index("ix_history_created_status", "created_at", "status"),)


class SystemStats(db.Model):
    __tablename__ = "system_stats"

    id = db.Column(db.Integer, primary_key=True)
    total_conversions = db.Column(db.Integer, nullable=False, default=0)
    total_listening_minutes = db.Column(db.Float, nullable=False, default=0.0)
    total_words_processed = db.Column(db.Integer, nullable=False, default=0)
    total_characters_processed = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

