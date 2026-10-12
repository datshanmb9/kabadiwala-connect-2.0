from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


MAX_IMAGE_BYTES = 10 * 1024 * 1024
_STORAGE_ROOT = Path(__file__).resolve().parents[2] / "uploads" / "ewaste"
_ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def storage_root() -> Path:
    return _STORAGE_ROOT


async def store_image(upload: UploadFile) -> str:
    extension = _ALLOWED_TYPES.get(upload.content_type or "")
    if extension is None:
        raise ValueError("Only JPEG, PNG, and WebP images are supported.")

    contents = await upload.read(MAX_IMAGE_BYTES + 1)
    if len(contents) > MAX_IMAGE_BYTES:
        raise ValueError("Image must be 10 MB or smaller.")

    _STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{extension}"
    path = _STORAGE_ROOT / filename
    path.write_bytes(contents)
    return f"uploaded-photo:{filename}"


def resolve_photo_reference(photo_file_id: str) -> Path:
    if not photo_file_id.startswith("uploaded-photo:"):
        return Path(photo_file_id)

    filename = photo_file_id.removeprefix("uploaded-photo:")
    path = (_STORAGE_ROOT / filename).resolve()
    if path.parent != _STORAGE_ROOT.resolve():
        raise ValueError("Invalid uploaded photo reference.")
    return path
