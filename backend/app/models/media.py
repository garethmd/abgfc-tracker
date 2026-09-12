from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import MediaKind, check_in


class Media(TimestampMixin, Base):
    """Designed now, written later. Uploaded files live under a private storage_key,
    served only through an authenticated endpoint - never a public bucket."""

    __tablename__ = "media"
    __table_args__ = (
        CheckConstraint(check_in("kind", MediaKind), name="kind"),
        CheckConstraint(
            "(kind = 'youtube' AND url IS NOT NULL) "
            "OR (kind <> 'youtube' AND storage_key IS NOT NULL)",
            name="source_present",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[MediaKind] = mapped_column(String(20))
    url: Mapped[str | None] = mapped_column(String(500))
    storage_key: Mapped[str | None] = mapped_column(String(500))
    title: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime)
    content_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(Integer)

    links: Mapped[list["MediaLink"]] = relationship(
        back_populates="media", cascade="all, delete-orphan"
    )


class MediaLink(Base):
    """Attaches media to exactly one of: fixture, player, match event.
    Real FKs (not target_type/target_id) so cascades and integrity hold."""

    __tablename__ = "media_links"
    __table_args__ = (
        CheckConstraint(
            "(fixture_id IS NOT NULL) + (player_id IS NOT NULL) + (match_event_id IS NOT NULL) = 1",
            name="exactly_one_target",
        ),
        UniqueConstraint("media_id", "fixture_id", "player_id", "match_event_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media.id", ondelete="CASCADE"), index=True)
    fixture_id: Mapped[int | None] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    match_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("match_events.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str | None] = mapped_column(
        String(50)
    )  # full_match / highlights / goal_clip / profile_photo
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    media: Mapped[Media] = relationship(back_populates="links")
