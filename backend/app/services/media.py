"""Media storage: files live under settings.media_dir (a private volume), never a public
bucket, and are only ever served through an authenticated, access-checked endpoint.

Today: player profile photos. Uploads are re-encoded (EXIF - including GPS - stripped),
downsized, and stored as JPEG in two sizes.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import NotFoundError, ValidationError
from app.models import Media, MediaKind, MediaLink, Player, UserRole
from app.repositories.players import PlayerRepository
from app.services.access import Access

try:  # iPhone photos arrive as HEIC unless the phone converts them
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover
    pass

PROFILE_ROLE = "profile_photo"
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
SIZES = {"full": 1200, "thumb": 256}  # longest edge; thumb is square-cropped


def _media_dir() -> Path:
    return Path(get_settings().media_dir)


def _process(data: bytes) -> dict[str, bytes]:
    """Decode, fix orientation, drop metadata, produce full + thumb JPEGs."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as e:
        raise ValidationError(
            "That file isn't an image we can read (JPEG, PNG, WebP or HEIC)"
        ) from e
    img = ImageOps.exif_transpose(img)  # apply the rotation, then forget the EXIF entirely
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    out: dict[str, bytes] = {}
    full = img.copy()
    full.thumbnail((SIZES["full"], SIZES["full"]), Image.LANCZOS)
    buf = io.BytesIO()
    full.save(buf, "JPEG", quality=85, optimize=True)
    out["full"] = buf.getvalue()
    thumb = ImageOps.fit(img, (SIZES["thumb"], SIZES["thumb"]), Image.LANCZOS)
    buf = io.BytesIO()
    thumb.save(buf, "JPEG", quality=85, optimize=True)
    out["thumb"] = buf.getvalue()
    return out


class PlayerPhotoService:
    def __init__(self, db: Session, access: Access):
        self.db = db
        self.access = access
        self.players = PlayerRepository(db)

    def _player(self, player_id: int, minimum: UserRole) -> Player:
        player = self.players.get_or_404(player_id)
        self.access.require_player(self.db, player, minimum)
        return player

    def _link(self, player_id: int) -> MediaLink | None:
        return self.db.scalar(
            select(MediaLink).where(
                MediaLink.player_id == player_id, MediaLink.role == PROFILE_ROLE
            )
        )

    def set_photo(self, player_id: int, data: bytes, filename: str | None) -> Media:
        player = self._player(player_id, UserRole.COACH)
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValidationError("Photo is too large (15MB max)")
        versions = _process(data)

        key = f"players/{player.id}/{uuid.uuid4().hex}"
        folder = _media_dir() / "players" / str(player.id)
        folder.mkdir(parents=True, exist_ok=True)
        for size, blob in versions.items():
            path = _media_dir() / f"{key}-{size}.jpg"
            path.write_bytes(blob)
            path.chmod(0o600)

        old = self._link(player.id)
        if old is not None:
            self._remove_files(old.media.storage_key)
            self.db.delete(old.media)  # cascades to the link
            self.db.flush()

        media = Media(
            kind=MediaKind.PHOTO,
            storage_key=key,
            title=f"{player.display_name} profile photo",
            content_type="image/jpeg",
            size_bytes=len(versions["full"]),
            captured_at=datetime.now(),
        )
        media.links.append(MediaLink(player_id=player.id, role=PROFILE_ROLE))
        self.db.add(media)
        self.db.commit()
        self.db.refresh(media)
        self.db.refresh(player)  # profile_photo_link is viewonly: reload it
        return media

    def get_photo(self, player_id: int, size: str) -> tuple[bytes, str]:
        """(jpeg bytes, cache key) for the player's photo at 'full' or 'thumb'."""
        self._player(player_id, UserRole.VIEWER)
        if size not in SIZES:
            raise ValidationError("size must be full or thumb")
        link = self._link(player_id)
        if link is None:
            raise NotFoundError("No photo")
        path = _media_dir() / f"{link.media.storage_key}-{size}.jpg"
        if not path.exists():
            raise NotFoundError("Photo file missing")
        return path.read_bytes(), link.media.storage_key.rsplit("/", 1)[-1]

    def remove_photo(self, player_id: int) -> None:
        self._player(player_id, UserRole.COACH)
        link = self._link(player_id)
        if link is None:
            return
        self._remove_files(link.media.storage_key)
        self.db.delete(link.media)
        self.db.commit()
        self.db.expire_all()

    @staticmethod
    def _remove_files(key: str | None) -> None:
        if not key:
            return
        for size in SIZES:
            p = _media_dir() / f"{key}-{size}.jpg"
            if p.exists():
                p.unlink()
