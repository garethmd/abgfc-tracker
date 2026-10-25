"""Parent access: invitations and passwordless sign-in.

A parent is an ordinary account with one ordinary role - `viewer` at cohort scope, the
same row the age-group coach has - plus a `player_guardians` link recording whose parent
they are. Nothing new in `services/access.py`; the link is what will later let them add
a photo or a note to their own child, and what tells us whose access to close when a
child leaves.

A parent chooses a password when they accept; email only ever resets it. Tokens here -
invitation, reset, and the sign-in links that predate passwords - are all the same
mechanism: a 256-bit single-use value, stored only as a sha256 hash, that expires.

**An account exists exactly as long as it has a child linked.** Removing the last child
removes the account, so there is no closed or dormant parent to reason about: three
sources of truth that could disagree (links, roles, `is_active`) became one. What the
account can no longer tell us - who used to see a child - is kept in `parent_access_log`,
which is append-only and outlives it.
"""

from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.config import Settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.security import hash_login_token, hash_password, new_login_token
from app.models import (
    LoginToken,
    ParentAccessLog,
    Player,
    PlayerGuardian,
    RoleScope,
    SquadMember,
    TeamSeason,
    TokenPurpose,
    User,
    UserRole,
)
from app.models import UserRoleAssignment as RoleRow
from app.repositories.players import PlayerRepository
from app.repositories.users import UserRepository
from app.schemas.invite import (
    GuardianRead,
    InviteAccept,
    InviteCreate,
    InviteCreated,
    InvitePreview,
    InviteRead,
    LeaverRead,
    PlayerAccessRead,
    TeamParentsRead,
)
from app.schemas.player import PlayerSummary
from app.services.access import Access
from app.services.email import EmailError, EmailService
from app.services.messages import invite_message


def _now() -> datetime:
    return datetime.now()


class InviteService:
    def __init__(self, db: Session, access: Access | None, settings: Settings):
        self.db = db
        self.access = access
        self.settings = settings
        self.users = UserRepository(db)

    # --- making an invitation ---------------------------------------------------

    def create(self, data: InviteCreate) -> InviteCreated:
        """Coaches and admins may invite. The check is the one that already exists for
        editing a child: coach+ on their cohort, or on a team whose squad they are in."""
        player = PlayerRepository(self.db).get_or_404(data.player_id)
        self._access.require_player(self.db, player, UserRole.COACH)
        if player.left_date is not None:
            raise ValidationError(f"{player.display_name} has left the club")

        if data.email:
            existing = self.users.get_by_email(data.email)
            if existing and any(g.player_id == player.id for g in existing.guardian_of):
                raise ConflictError(f"{data.email} can already see {player.display_name}")

        # One live link per address and child: re-inviting replaces the old one. With no
        # address there is nothing to match on, so each link stands on its own - the coach
        # may be sending to two parents of the same child.
        if data.email:
            self.db.execute(
                update(LoginToken)
                .where(
                    LoginToken.purpose == TokenPurpose.INVITE,
                    LoginToken.email == data.email,
                    LoginToken.player_id == player.id,
                    LoginToken.used_at.is_(None),
                    LoginToken.revoked_at.is_(None),
                )
                .values(revoked_at=_now())
            )
        raw, token_hash = new_login_token()
        token = LoginToken(
            token_hash=token_hash,
            purpose=TokenPurpose.INVITE,
            email=data.email,
            player_id=player.id,
            invited_by_user_id=self._access.user.id,
            expires_at=_now() + timedelta(hours=self.settings.invite_expiry_hours),
        )
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)

        link = f"{self.settings.public_base_url.rstrip('/')}/invite/{raw}"
        emailed = self._send_invite(data.email, player, link) if data.email else False
        return InviteCreated(
            **_invite_read(token).model_dump(),
            link=link,
            emailed=emailed,
            share_text=invite_message(player.display_name, link, _who(self._access.user)),
        )

    def list_for_team_season(self, team_season_id: int) -> TeamParentsRead:
        """Who can see the club because of each child in this squad - the Parents tab."""
        ts = self.db.get(TeamSeason, team_season_id)
        if ts is None:
            raise NotFoundError(f"Team season {team_season_id} not found")
        self._access.require_team_season(ts, UserRole.COACH)
        members = self.db.scalars(
            select(SquadMember)
            .where(SquadMember.team_season_id == team_season_id, SquadMember.left_at.is_(None))
            .options(
                selectinload(SquadMember.player)
                .selectinload(Player.guardians)
                .selectinload(PlayerGuardian.user)
            )
        ).all()
        pending: dict[int, list[InviteRead]] = {}
        for t in self._live_invites([m.player_id for m in members]):
            pending.setdefault(t.player_id, []).append(_invite_read(t))
        players = [
            PlayerAccessRead(
                player=PlayerSummary.model_validate(m.player),
                guardians=[_guardian_read(g) for g in m.player.guardians],
                pending=pending.get(m.player_id, []),
            )
            for m in members
        ]
        return TeamParentsRead(players=players, leavers=self._leavers(ts))

    def _leavers(self, ts: TeamSeason) -> list[LeaverRead]:
        """Parents of children who have left. A guardian link outlives the child's time
        at the club - deliberately, so the account can be found and closed rather than
        quietly keeping access."""
        gone = self.db.scalars(
            select(PlayerGuardian)
            .join(Player, Player.id == PlayerGuardian.player_id)
            .where(Player.cohort_id == ts.club_team.cohort_id, Player.left_date.is_not(None))
            .options(
                selectinload(PlayerGuardian.user).selectinload(User.guardian_of),
                selectinload(PlayerGuardian.player),
            )
        ).all()
        out: dict[int, LeaverRead] = {}
        for g in gone:
            # Only if *every* child of theirs has gone - a second child still playing
            # is reason enough to keep the account.
            if any(link.player.left_date is None for link in g.user.guardian_of):
                continue
            row = out.setdefault(
                g.user_id,
                LeaverRead(
                    user_id=g.user_id,
                    display_name=g.user.display_name,
                    email=g.user.email,
                    children=[],
                ),
            )
            row.children.append(g.player.display_name)
        return list(out.values())

    # --- removing access ---------------------------------------------------------

    def unlink(self, user_id: int, player_id: int) -> None:
        """Take away this parent's access to this child.

        If that was their last child anywhere, the account goes too: an account is its
        links, and one with none would be a ghost that no coach could reach - every
        management call here needs a child to prove the coach's authority over.
        """
        user = self._manageable_parent(user_id)
        link = next((g for g in user.guardian_of if g.player_id == player_id), None)
        if link is None:
            raise NotFoundError("They aren't linked to that child")
        self._access.require_player(self.db, link.player, UserRole.COACH)
        cohort_id = link.player.cohort_id
        self._log(user, player_id, "revoked")
        user.guardian_of.remove(link)
        self.db.flush()
        # Asked of the database, not of the loaded collection: a link added by another
        # request in this session may not be on the object we are holding.
        still_here = self.db.scalar(
            select(func.count())
            .select_from(PlayerGuardian)
            .join(Player, Player.id == PlayerGuardian.player_id)
            .where(PlayerGuardian.user_id == user.id, Player.cohort_id == cohort_id)
        )
        if not still_here:
            # No child left in that age group: the viewer role has nothing to stand on.
            for role in [
                r
                for r in user.roles
                if r.scope_type == RoleScope.COHORT and r.scope_id == cohort_id
            ]:
                user.roles.remove(role)
            user.session_version += 1  # whatever they have open stops working now
        # Asked of the database for the same reason as above.
        any_child_left = self.db.scalar(
            select(func.count())
            .select_from(PlayerGuardian)
            .where(PlayerGuardian.user_id == user.id)
        )
        if not any_child_left:
            self.db.delete(user)
        self.db.commit()

    def delete_parent(self, user_id: int) -> None:
        """Remove the account outright - every guardian link, role, passkey and unused
        link goes with it (FK cascades).

        This is the shortcut for every child at once - "take me off your system" - and
        the address is free to invite again afterwards. Only a parent account can go this
        way; anything holding more than the cohort viewer row is a coach's and is managed
        in /admin.
        """
        user = self._manageable_parent(user_id)
        # Parents have passwords now, so a password no longer tells a parent from a
        # coach. What does is the roles they hold: a parent has exactly the cohort
        # viewer row. Anything more belongs to a coach and is managed in /admin.
        if any(r.role != UserRole.VIEWER or r.scope_type != RoleScope.COHORT for r in user.roles):
            raise ValidationError("That account is a coach's - manage it in Coaches")
        for link in user.guardian_of:
            self._log(user, link.player_id, "revoked")
        self.db.delete(user)
        self.db.commit()

    def sign_out_everywhere(self, user_id: int) -> None:
        """A lost or stolen phone, where the parent should keep their access."""
        user = self._manageable_parent(user_id)
        user.session_version += 1
        self.db.commit()

    def _log(self, user: User, player_id: int, action: str, by: int | None = None) -> None:
        """One append-only line per grant or revocation. The parent's name and address are
        copied in because the account they describe is meant to be deletable.

        `by` is passed where the acting user isn't the caller: accepting an invitation
        happens unauthenticated, so the coach on record is the one who invited them.
        """
        self.db.add(
            ParentAccessLog(
                user_id=user.id,
                parent_name=user.display_name,
                parent_email=user.email,
                # self.access, not self._access: accepting an invitation has no caller,
                # and the property raises rather than returning None.
                by_user_id=by if by is not None else (self.access.user.id if self.access else None),
                player_id=player_id,
                action=action,
            )
        )

    def _manageable_parent(self, user_id: int) -> User:
        """A coach may manage a parent if they could have invited them - that is, if they
        are coach+ on at least one of that parent's children."""
        user = self.users.get(user_id)
        if user is None or not user.guardian_of:
            raise NotFoundError("No such parent")
        for link in user.guardian_of:
            try:
                self._access.require_player(self.db, link.player, UserRole.COACH)
                return user
            except ForbiddenError:
                continue
        raise ForbiddenError("That parent is outside your teams")

    def revoke(self, invite_id: int) -> None:
        token = self.db.get(LoginToken, invite_id)
        if token is None or token.purpose != TokenPurpose.INVITE or not token.is_live:
            raise NotFoundError("No such invitation")
        self._access.require_player(self.db, token.player, UserRole.COACH)
        token.revoked_at = _now()
        self.db.commit()

    # --- the parent's side (no session yet) --------------------------------------

    def preview(self, raw: str) -> InvitePreview:
        """Shown on the landing page. Reading does not consume the token - mail scanners
        follow links, so the token is only spent when the parent posts the form."""
        token = self._find_live(raw, TokenPurpose.INVITE)
        teams = self.db.scalars(
            select(TeamSeason)
            .join(SquadMember, SquadMember.team_season_id == TeamSeason.id)
            .where(SquadMember.player_id == token.player_id, SquadMember.left_at.is_(None))
            .options(selectinload(TeamSeason.club_team))
        ).all()
        return InvitePreview(
            player_name=token.player.display_name,
            team_names=sorted({ts.club_team.name for ts in teams}),
            invited_by=_who(token.invited_by),
            email=token.email,
        )

    def accept(self, raw: str, data: InviteAccept) -> User:
        """Create the parent's account and sign them in.

        The address is whichever the coach put on the invitation, or - when they sent
        the link by hand - the one the parent types here. An address that already has an
        account is **not** simply adopted: whoever holds this link would otherwise be
        signed in as that person. See `_claim_existing`.
        """
        email = (self._find_live(raw, TokenPurpose.INVITE).email or data.email or "").strip()
        if not email:
            raise ValidationError("We need your email address so you can sign in again")

        existing = self.users.get_by_email(email)
        if existing is not None:
            return self._claim_existing(raw, existing, email)

        token = self._consume(raw, TokenPurpose.INVITE)
        player = token.player
        if player.cohort_id is None:
            raise ValidationError("That child is not in an age group yet")
        user = User(
            username=email,
            email=email,
            display_name=data.display_name,
            password_hash=hash_password(data.password),
        )
        self.db.add(user)
        self.db.flush()

        _grant(user, player)
        self._log(user, player.id, "granted", by=token.invited_by_user_id)
        self.db.commit()
        return self.users.get(user.id)

    def _claim_existing(self, raw: str, user: User, email: str) -> User:
        """That address already has an account - a second child, or a mistyped address.

        Signing in on the spot would mean anyone holding an invitation link could take
        over any account by typing its address, so instead we prove the address: the
        invitation is spent, and a sign-in link carrying the child goes to the inbox.
        A coach's account is never adopted at all - that would hand a parent a login
        with write access.
        """
        if any(r.role != UserRole.VIEWER or r.scope_type != RoleScope.COHORT for r in user.roles):
            raise ConflictError(
                "That address is already a coach's login here - ask your coach to invite "
                "a different address"
            )
        token = self._consume(raw, TokenPurpose.INVITE)
        self._issue_signin(user, email, player_id=token.player_id)
        raise ConflictError(
            f"{email} already has an account here - we've emailed a link to sign in "
            "and add this child"
        )

    def forgot_password(self, email: str) -> None:
        """One door for "I can't get in", whichever kind of account it is.

        A parent with a password gets a reset link - email used to recover, which is
        what the standards permit. A parent from before passwords existed gets the
        sign-in link they have always had, so this change disturbs nobody.

        Always succeeds from the caller's point of view: whether an address has an
        account is not something an unauthenticated request gets to learn.
        """
        user = self.users.get_by_email(email)
        if user is None or not user.is_active:
            return
        if user.password_hash is None:
            self._issue_signin(user, email)
        else:
            self._issue_reset(user, email)

    def _issue_reset(self, user: User, email: str) -> None:
        raw, token_hash = new_login_token()
        self.db.add(
            LoginToken(
                token_hash=token_hash,
                purpose=TokenPurpose.RESET,
                email=email,
                user_id=user.id,
                expires_at=_now() + timedelta(minutes=self.settings.reset_link_expiry_minutes),
            )
        )
        self.db.commit()
        link = f"{self.settings.public_base_url.rstrip('/')}/reset/{raw}"
        try:
            EmailService(self.settings).send(
                email,
                "Reset your ABGFC password",
                f"Hello{' ' + user.display_name if user.display_name else ''},\n\n"
                f"Choose a new password for the ABGFC app here:\n\n{link}\n\n"
                f"It works once and lasts {self.settings.reset_link_expiry_minutes} "
                "minutes. If you didn't ask for it, ignore this email - your password "
                "has not changed.\n",
            )
        except EmailError:
            pass  # they can ask for another

    def reset_password(self, raw: str, new_password: str) -> User:
        """Spend the reset link and set the new password. Every other session ends:
        if somebody else had got in, this is what removes them."""
        token = self._consume(raw, TokenPurpose.RESET)
        user = self.users.get(token.user_id)
        if user is None or not user.is_active:
            raise ForbiddenError("That account has been closed - ask your coach")
        user.password_hash = hash_password(new_password)
        user.session_version += 1
        self.db.commit()
        self.db.refresh(user)
        return user

    def set_first_password(self, user: User, new_password: str) -> None:
        """For a parent who joined before passwords. No current password to check -
        they are already signed in, which is the proof."""
        if user.password_hash is not None:
            raise ValidationError("You already have a password - change it instead")
        user.password_hash = hash_password(new_password)
        self.db.commit()

    def _issue_signin(self, user: User, email: str, player_id: int | None = None) -> None:
        """Email a sign-in link. `player_id` rides along when the link also proves the
        address so a second child can be added to an account that already exists."""
        raw, token_hash = new_login_token()
        self.db.add(
            LoginToken(
                token_hash=token_hash,
                purpose=TokenPurpose.SIGNIN,
                email=email,
                user_id=user.id,
                player_id=player_id,
                expires_at=_now() + timedelta(minutes=self.settings.signin_link_expiry_minutes),
            )
        )
        self.db.commit()
        link = f"{self.settings.public_base_url.rstrip('/')}/signin/{raw}"
        child = f" and add {self.db.get(Player, player_id).display_name}" if player_id else ""
        try:
            EmailService(self.settings).send(
                email,
                "Your ABGFC sign-in link",
                f"Hello{' ' + user.display_name if user.display_name else ''},\n\n"
                f"Here is your link to sign in to the ABGFC app{child}:\n\n{link}\n\n"
                f"It works once and lasts {self.settings.signin_link_expiry_minutes} "
                "minutes. If you didn't ask for it, ignore this email.\n",
            )
        except EmailError:
            pass  # the parent can ask for another

    def consume_signin(self, raw: str) -> User:
        token = self._consume(raw, TokenPurpose.SIGNIN)
        user = self.users.get(token.user_id)
        if user is None or not user.is_active:
            raise ForbiddenError("That account has been closed - ask your coach")
        if token.player_id is not None:
            # Following this link is the proof that the address is theirs.
            _grant(user, token.player)
            self._log(user, token.player_id, "granted", by=token.invited_by_user_id)
            self.db.commit()
            self.db.refresh(user)
        return user

    # --- helpers -----------------------------------------------------------------

    @property
    def _access(self) -> Access:
        if self.access is None:  # pragma: no cover - programming error
            raise RuntimeError("This operation needs a signed-in caller")
        return self.access

    def _live_invites(self, player_ids: list[int]) -> list[LoginToken]:
        if not player_ids:
            return []
        return list(
            self.db.scalars(
                select(LoginToken)
                .where(
                    LoginToken.purpose == TokenPurpose.INVITE,
                    LoginToken.player_id.in_(player_ids),
                    LoginToken.used_at.is_(None),
                    LoginToken.revoked_at.is_(None),
                    LoginToken.expires_at > _now(),
                )
                .options(selectinload(LoginToken.player), selectinload(LoginToken.invited_by))
                .order_by(LoginToken.created_at)
            )
        )

    def _find_live(self, raw: str, purpose: TokenPurpose) -> LoginToken:
        token = self.db.scalar(
            select(LoginToken)
            .where(LoginToken.token_hash == hash_login_token(raw), LoginToken.purpose == purpose)
            .options(selectinload(LoginToken.player), selectinload(LoginToken.invited_by))
        )
        if token is None or not token.is_live:
            raise NotFoundError("That link has expired or has already been used")
        return token

    def _consume(self, raw: str, purpose: TokenPurpose) -> LoginToken:
        """Spend the token. One conditional UPDATE, so two simultaneous clicks can't both
        win: the second matches no rows because used_at is no longer NULL."""
        now = _now()
        row = self.db.execute(
            update(LoginToken)
            .where(
                LoginToken.token_hash == hash_login_token(raw),
                LoginToken.purpose == purpose,
                LoginToken.used_at.is_(None),
                LoginToken.revoked_at.is_(None),
                LoginToken.expires_at > now,
            )
            .values(used_at=now)
            .returning(LoginToken.id)
        ).first()
        if row is None:
            raise NotFoundError("That link has expired or has already been used")
        self.db.commit()
        return self.db.get(LoginToken, row[0])

    def _send_invite(self, email: str, player: Player, link: str) -> bool:
        who = _who(self._access.user) or "Your coach"
        try:
            EmailService(self.settings).send(
                email,
                f"{who} has invited you to the ABGFC app",
                f"Hello,\n\n{who} has invited you to see {player.display_name}'s team on "
                "the Aldershot Boys & Girls FC app - fixtures, results and who's "
                "available each week.\n\n"
                f"Open this link to get started:\n\n{link}\n\n"
                "You'll choose a password on the way in, and we'll only ever email you "
                "if you need to set a new one.\n\n"
                f"The invitation lasts {self.settings.invite_expiry_hours // 24} days.\n",
            )
            return True
        except EmailError:
            return False  # the coach still has the link to send by hand


def _grant(user: User, player: Player) -> None:
    """Make this user a guardian of this child, and a viewer of the age group. Appended
    through the relationships so the object handed back has them loaded."""
    if not any(g.player_id == player.id for g in user.guardian_of):
        user.guardian_of.append(PlayerGuardian(player_id=player.id))
    if not any(
        r.scope_type == RoleScope.COHORT and r.scope_id == player.cohort_id for r in user.roles
    ):
        user.roles.append(
            RoleRow(role=UserRole.VIEWER, scope_type=RoleScope.COHORT, scope_id=player.cohort_id)
        )


def _guardian_read(g: PlayerGuardian) -> GuardianRead:
    return GuardianRead(
        id=g.id,
        user_id=g.user_id,
        display_name=g.user.display_name,
        email=g.user.email,
        last_signed_in=None,
        passkey_count=len(g.user.passkeys),
        has_password=g.user.password_hash is not None,
    )


def _who(user: User | None) -> str | None:
    return (user.display_name or user.username) if user else None


def _invite_read(token: LoginToken) -> InviteRead:
    return InviteRead(
        id=token.id,
        email=token.email,
        player=PlayerSummary.model_validate(token.player),
        invited_by=_who(token.invited_by),
        expires_at=token.expires_at,
        created_at=token.created_at,
    )
