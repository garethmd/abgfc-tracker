from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFoundError
from app.models import MatchNote, UserRole
from app.schemas.note import MatchNoteCreate, MatchNoteRead, MatchNoteUpdate
from app.services.access import Access
from app.services.fixtures import FixtureService


def _read(n: MatchNote) -> MatchNoteRead:
    who = n.created_by.display_name or n.created_by.username if n.created_by else None
    return MatchNoteRead(
        id=n.id,
        fixture_id=n.fixture_id,
        body=n.body,
        author=n.author,
        sent_at=n.sent_at,
        created_at=n.created_at,
        added_by=who,
    )


class MatchNoteService:
    """Match reports pasted in from WhatsApp. Reading follows the fixture's team access;
    writing needs coach."""

    def __init__(self, db: Session, access: Access):
        self.db = db
        self.access = access
        self.fixtures = FixtureService(db, access)

    def list_for(self, fixture_id: int) -> list[MatchNoteRead]:
        self.fixtures.get(fixture_id)  # access check
        notes = self.db.scalars(
            select(MatchNote)
            .where(MatchNote.fixture_id == fixture_id)
            .options(selectinload(MatchNote.created_by))
        ).all()
        notes.sort(key=lambda n: (n.sent_at or n.created_at, n.id))
        return [_read(n) for n in notes]

    def add(self, fixture_id: int, data: MatchNoteCreate) -> MatchNoteRead:
        fixture = self.fixtures.get(fixture_id, UserRole.COACH)
        note = MatchNote(
            body=data.body.strip(),
            author=data.author,
            sent_at=data.sent_at,
            created_by_user_id=self.access.user.id,
        )
        fixture.match_notes.append(note)
        self.db.commit()
        self.db.refresh(note)
        return _read(note)

    def update(self, fixture_id: int, note_id: int, data: MatchNoteUpdate) -> MatchNoteRead:
        note = self._get(fixture_id, note_id)
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(note, k, v.strip() if k == "body" and v else v)
        self.db.commit()
        self.db.refresh(note)
        return _read(note)

    def delete(self, fixture_id: int, note_id: int) -> None:
        note = self._get(fixture_id, note_id)
        self.db.delete(note)
        self.db.commit()

    def _get(self, fixture_id: int, note_id: int) -> MatchNote:
        self.fixtures.get(fixture_id, UserRole.COACH)  # access check
        note = self.db.get(MatchNote, note_id)
        if note is None or note.fixture_id != fixture_id:
            raise NotFoundError(f"Note {note_id} not found on this fixture")
        return note
