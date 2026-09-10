import os
import secrets
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Falls back to a key generated fresh per process if not set in the
# environment. This keeps local/dev usage simple, while still avoiding a
# fixed, publicly-known secret. Set SECRET_KEY in .env for real deployments
# so sessions survive app restarts.
_DEFAULT_SECRET_KEY = secrets.token_hex(32)

ALLOWED_UPLOAD_EXTENSIONS = {
    "pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx",
    "txt", "zip", "rar", "png", "jpg", "jpeg", "gif",
}


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", _DEFAULT_SECRET_KEY)
    WTF_CSRF_ENABLED = True
    database_url = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'student_learning_hub.db')}",
    )
    # Some hosted PostgreSQL providers still return the legacy postgres:// form.
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }

    # Reject uploads larger than 10 MB before they hit the view function.
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    ALLOWED_UPLOAD_EXTENSIONS = ALLOWED_UPLOAD_EXTENSIONS
