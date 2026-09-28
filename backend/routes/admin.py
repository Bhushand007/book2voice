import os
import secrets
from functools import wraps

from flask import Blueprint, render_template, request, Response

from backend.models import Book, AudioFile, ConversionHistory, SystemStats


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def check_auth(username, password):
    expected_username = os.environ.get("ADMIN_USERNAME", "admin")
    expected_password = os.environ.get("ADMIN_DB_PASSWORD")

    if not expected_password:
        return False

    return (
        secrets.compare_digest(username or "", expected_username)
        and secrets.compare_digest(password or "", expected_password)
    )


def authenticate():
    return Response(
        "Login required",
        401,
        {
            "WWW-Authenticate": 'Basic realm="Book2Voice Admin"'
        },
    )


def requires_auth(function):
    @wraps(function)
    def decorated(*args, **kwargs):
        auth = request.authorization

        if not auth or not check_auth(
            auth.username,
            auth.password
        ):
            return authenticate()

        return function(*args, **kwargs)

    return decorated


@admin_bp.route("/database")
@requires_auth
def database_dashboard():

    books = (
        Book.query
        .order_by(Book.created_at.desc())
        .limit(100)
        .all()
    )

    audio_files = (
        AudioFile.query
        .order_by(AudioFile.created_at.desc())
        .limit(100)
        .all()
    )

    histories = (
        ConversionHistory.query
        .order_by(ConversionHistory.created_at.desc())
        .limit(100)
        .all()
    )

    stats = SystemStats.query.first()

    return render_template(
        "admin_database.html",
        books=books,
        audio_files=audio_files,
        histories=histories,
        stats=stats,
    )
