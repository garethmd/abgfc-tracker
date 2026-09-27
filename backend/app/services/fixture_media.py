"""YouTube videos attached to a fixture.

No new tables: a `media` row (kind=youtube) plus a `media_links` row carrying
`fixture_id`, which is what media_links was built for. Reading follows the fixture's team
access; writing needs coach - the same rules as match notes.
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFoundError, ValidationError
from app.models import Media, MediaKind, MediaLink, UserRole
from app.schemas.media import FixtureVideoCreate, FixtureVideoRead, FixtureVideoUpdate
from app.services.access import Access
from app.services.fixtures import FixtureService

VIDEO_ROLE = "match_video"
_ID = r"[A-Za-z0-9_-]{11}"
# Every form a coach might paste: the share sheet's youtu.be, the address bar's watch?v=,
# a Shorts link, or an embed URL someone copied out of a page.
_PATTERNS = (
    re.compile(rf"(?:youtube\.com|youtube-nocookie\.com)/watch\?(?:.*&)?v=({_ID})"),
    re.compile(rf"youtu\.be/({_ID})"),
    re.compile(rf"(?:youtube\.com|youtube-nocookie\.com)/(?:embed|v|shorts|live)/({_ID})"),
)


def parse_youtube_id(url: str) -> str:
    """The 11-character video id, whatever shape the link arrived in.

    Raises ValidationError for anything that isn't a YouTube link, so a coach finds out
    while pasting rather than when a card fails to play a week later.
    """
    text = url.strip()
    for pattern in _PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    # A bare id pasted on its own is unambiguous enough to accept.
    if re.fullmatch(_ID, text):
        return text
    raise ValidationError("That doesn't look like a YouTube link")


def canonical_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _read(link: MediaLink) -> FixtureVideoRead:
    video_id = parse_youtube_id(link.media.url or "")
    return FixtureVideoRead(
        id=link.media_id,
        fixture_id=link.fixture_id,
        video_id=video_id,
        url=link.media.url,
        title=link.media.title,
        sort_order=link.sort_order,
    )


class FixtureVideoService:
    def __init__(self, db: Session, access: Access):
        self.db = db
        self.access = access
        self.fixtures = FixtureService(db, access)

    def list_for(self, fixture_id: int) -> list[FixtureVideoRead]:
        self.fixtures.get(fixture_id)  # access check
        links = self.db.scalars(
            select(MediaLink)
            .where(MediaLink.fixture_id == fixture_id, MediaLink.role == VIDEO_ROLE)
            .options(selectinload(MediaLink.media))
        ).all()
        return [_read(link) for link in sorted(links, key=lambda x: (x.sort_order, x.id))]

    def add(self, fixture_id: int, data: FixtureVideoCreate) -> FixtureVideoRead:
        self.fixtures.get(fixture_id, UserRole.COACH)
        video_id = parse_youtube_id(data.url)
        existing = self.list_for(fixture_id)
        if any(v.video_id == video_id for v in existing):
            raise ValidationError("That video is already on this fixture")
        media = Media(
            kind=MediaKind.YOUTUBE,
            url=canonical_url(video_id),
            title=data.title or None,
        )
        link = MediaLink(
            media=media,
            fixture_id=fixture_id,
            role=VIDEO_ROLE,
            sort_order=max((v.sort_order for v in existing), default=-1) + 1,
        )
        self.db.add(link)
        self.db.commit()
        self.db.refresh(link)
        return _read(link)

    def update(self, fixture_id: int, media_id: int, data: FixtureVideoUpdate) -> FixtureVideoRead:
        link = self._get(fixture_id, media_id)
        changes = data.model_dump(exclude_unset=True)
        if "url" in changes and changes["url"]:
            link.media.url = canonical_url(parse_youtube_id(changes["url"]))
        if "title" in changes:
            link.media.title = changes["title"] or None
        if changes.get("sort_order") is not None:
            link.sort_order = changes["sort_order"]
        self.db.commit()
        self.db.refresh(link)
        return _read(link)

    def delete(self, fixture_id: int, media_id: int) -> None:
        link = self._get(fixture_id, media_id)
        self.db.delete(link.media)  # the link cascades with it
        self.db.commit()

    def _get(self, fixture_id: int, media_id: int) -> MediaLink:
        self.fixtures.get(fixture_id, UserRole.COACH)  # access check
        link = self.db.scalar(
            select(MediaLink)
            .where(
                MediaLink.fixture_id == fixture_id,
                MediaLink.media_id == media_id,
                MediaLink.role == VIDEO_ROLE,
            )
            .options(selectinload(MediaLink.media))
        )
        if link is None:
            raise NotFoundError(f"Video {media_id} not found on this fixture")
        return link
