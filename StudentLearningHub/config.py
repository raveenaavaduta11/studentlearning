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
    DATABASE_URL = os.getenv("DATABASE_URL")
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
    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME)
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1").lower() in {"1", "true", "yes"}
    SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "0").lower() in {"1", "true", "yes"}

    # Vercel rejects function requests above roughly 4.5 MB before Flask runs.
    MAX_CONTENT_LENGTH = (4 * 1024 * 1024) if os.getenv("VERCEL") else (10 * 1024 * 1024)
    ALLOWED_UPLOAD_EXTENSIONS = ALLOWED_UPLOAD_EXTENSIONS
