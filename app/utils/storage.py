import os
import uuid

from pathlib import Path
from fastapi import UploadFile

from app.core.config import settings

async def save_upload_to_disk(file: UploadFile) -> str:
    """
    Save uploaded file into MEDIA_ROOT/AUDIO_SUBDIR with random name.
    Returns absolute path as string.
    """
    media_root = Path(settings.MEDIA_ROOT) / settings.AUDIO_SUBDIR
    media_root.mkdir(parents=True, exist_ok=True)

    ext = os.path.splitext(file.filename or "")[1] or ".wav"
    fname = f"{uuid.uuid4().hex}{ext}"

    path = media_root / fname

    contents = await file.read()
    with path.open("wb") as f:
        f.write(contents)

    return str(path)


async def save_uploaded_file(file: UploadFile, subdirectory: str, filename: str = None) -> str:
    """
    Save uploaded file to specified subdirectory in media root.
    Returns relative path for storage in database.
    """
    media_root = Path(settings.MEDIA_ROOT) / subdirectory
    media_root.mkdir(parents=True, exist_ok=True)

    if filename is None:
        ext = os.path.splitext(file.filename or "")[1] or ""
        filename = f"{uuid.uuid4().hex}{ext}"

    path = media_root / filename

    contents = await file.read()
    with path.open("wb") as f:
        f.write(contents)

    # Return relative path for database storage
    return f"/{subdirectory}/{filename}"