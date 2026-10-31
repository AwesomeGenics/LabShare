"""
app/services/upload_service.py

File upload validation and secure saving.
Checks: allowed extension whitelist, file size limit, basic MIME sniffing via magic bytes.
"""

import os
import secrets
import mimetypes
from datetime import datetime, timezone
from flask import current_app

# Allowed extensions and their expected MIME types
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MIME_SIGNATURES = {
    "jpg": b"\xff\xd8\xff",
    "jpeg": b"\xff\xd8\xff",
    "png": b"\x89PNG\r\n\x1a\n",
    "webp": b"RIFF",
    "pdf": b"%PDF-",
}


def _check_magic_bytes(file_bytes: bytes, ext: str) -> bool:
    """Check that file content matches the claimed extension."""
    signature = MIME_SIGNATURES.get(ext)
    if not signature or not file_bytes.startswith(signature):
        return False
    if ext == "webp":
        return file_bytes[8:12] == b"WEBP"
    return True


def validate_and_save(
    file_storage,
    upload_folder: str,
    prefix: str = "upload",
    allowed_extensions: set[str] | None = None,
) -> tuple[str | None, str | None]:
    """
    Validate and save an uploaded FileStorage object.

    Returns:
        (relative_url, None) on success
        (None, error_message) on failure
    """
    if file_storage is None or not file_storage.filename:
        return None, "No file provided."

    # Extension check
    filename = file_storage.filename
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = allowed_extensions or ALLOWED_EXTENSIONS
    if ext not in allowed:
        return None, f"File type '.{ext}' not allowed. Allowed: {', '.join(sorted(allowed))}."

    # Size check
    max_bytes = current_app.config.get("MAX_UPLOAD_BYTES", 5 * 1024 * 1024)
    file_storage.stream.seek(0, 2)  # seek to end
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > max_bytes:
        return None, f"File size {size // 1024}KB exceeds limit of {max_bytes // 1024}KB."

    # Magic byte check
    header = file_storage.stream.read(16)
    file_storage.stream.seek(0)
    if not _check_magic_bytes(header, ext):
        return None, "File content does not match a supported image format."

    # Generate safe unique filename
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    unique = secrets.token_hex(6)
    safe_name = f"{prefix}_{ts}_{unique}.{ext}"

    os.makedirs(upload_folder, exist_ok=True)
    save_path = os.path.join(upload_folder, safe_name)
    file_storage.save(save_path)

    return f"/static/uploads/{safe_name}", None
