import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Allowed institutional email domain suffixes (India: .ac.in, .edu.in, .res.in, .ernet.in, .edu)
    ALLOWED_EMAIL_DOMAINS = os.environ.get(
        "ALLOWED_EMAIL_DOMAINS", ".ac.in,.edu.in,.res.in,.edu,.ernet.in"
    ).split(",")

    # Session cookie settings (compatible with local network HTTP e.g. 192.168.1.x)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False

    # Upload settings
    MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
    ALLOWED_UPLOAD_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
    UPLOAD_FOLDER = os.path.join(basedir, "static", "uploads")

    # Platform take-rate bounds (percentage as decimal)
    TAKE_RATE_MIN = 0.05
    TAKE_RATE_MAX = 0.15

    # Free tier resource cap
    FREE_TIER_RESOURCE_LIMIT = 5

    # Per-user weekly booking quota (hours) per high-demand resource
    WEEKLY_QUOTA_HOURS = 8


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(basedir, '..', 'campus.db')}"
    )


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///campus.db")


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
