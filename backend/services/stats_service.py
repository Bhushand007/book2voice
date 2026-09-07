from sqlalchemy import func

from backend.extensions import db
from backend.models import AudioFile, Book, ConversionHistory, SystemStats


class StatsService:
    @staticmethod
    def ensure_stats() -> SystemStats:
        stats = SystemStats.query.first()
        if not stats:
            stats = SystemStats()
            db.session.add(stats)
            db.session.commit()
        return stats

    @staticmethod
    def update_after_conversion(word_count: int, char_count: int, duration_seconds: float) -> None:
        stats = StatsService.ensure_stats()
        stats.total_conversions += 1
        stats.total_words_processed += max(word_count, 0)
        stats.total_characters_processed += max(char_count, 0)
        stats.total_listening_minutes += max(duration_seconds, 0) / 60

    @staticmethod
    def dashboard_payload() -> dict:
        stats = StatsService.ensure_stats()
        recent = (
            db.session.query(ConversionHistory, Book.title, AudioFile.original_name)
            .join(Book, Book.id == ConversionHistory.book_id)
            .outerjoin(AudioFile, AudioFile.id == ConversionHistory.audio_file_id)
            .order_by(ConversionHistory.created_at.desc())
            .limit(8)
            .all()
        )
        timeline_rows = (
            db.session.query(
                func.date(ConversionHistory.created_at).label("day"),
                func.count(ConversionHistory.id).label("count"),
            )
            .filter(ConversionHistory.status == "completed")
            .group_by(func.date(ConversionHistory.created_at))
            .order_by(func.date(ConversionHistory.created_at).desc())
            .limit(14)
            .all()
        )

        return {
            "totals": {
                "conversions": stats.total_conversions,
                "listening_minutes": round(stats.total_listening_minutes, 2),
                "words_processed": stats.total_words_processed,
                "audio_files": AudioFile.query.count(),
            },
            "recent_conversions": [
                {
                    "history_id": history.id,
                    "book_title": title,
                    "audio_name": audio_name or "Deleted audio",
                    "status": history.status,
                    "language": history.language,
                    "speed": history.speed,
                    "duration_seconds": history.duration_seconds,
                    "created_at": history.created_at.isoformat(),
                }
                for history, title, audio_name in recent
            ],
            "timeline": [
                {"date": day, "count": count}
                for day, count in sorted(timeline_rows, key=lambda row: row[0])
            ],
        }

