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