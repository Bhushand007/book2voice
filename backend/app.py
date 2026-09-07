import logging
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import Config
from backend.extensions import db
from backend.routes import main_bp
from backend.services.stats_service import StatsService


def configure_logging(app: Flask) -> None:
    log_dir = Path(app.config["LOG_FOLDER"])
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

    app.logger.setLevel(logging.INFO)
    if not any(
        isinstance(existing, logging.FileHandler) and getattr(existing, "baseFilename", "") == str(log_file)
        for existing in app.logger.handlers
    ):
        app.logger.addHandler(handler)


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Config.TEMPLATE_DIR),
        static_folder=str(Config.STATIC_DIR),
        static_url_path="/static",
    )
    app.config.from_object(Config)
    configure_logging(app)

    db.init_app(app)
    app.register_blueprint(main_bp)

    for folder in (Config.UPLOAD_FOLDER, Config.AUDIO_FOLDER, Config.LOG_FOLDER):
        folder.mkdir(parents=True, exist_ok=True)

    with app.app_context():
        db.create_all()
        StatsService.ensure_stats()

    @app.errorhandler(404)
    def not_found_error(error):
        api_prefixes = ("/upload", "/convert", "/audio-list", "/delete-audio", "/stats", "/audio", "/download", "/health")
        if request.path.startswith(api_prefixes):
            return jsonify({"success": False, "error": "Endpoint not found."}), 404
        return "<h1>404 Not Found</h1>", 404

    @app.errorhandler(413)
    def too_large(error):
        return jsonify({"success": False, "error": "File is too large."}), 413

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"success": False, "error": "Internal server error."}), 500

    return app


if __name__ == "__main__":
    flask_app = create_app()
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    debug_mode = os.environ.get("FLASK_DEBUG", "1") == "1"
    flask_app.run(host=host, port=port, debug=debug_mode)

