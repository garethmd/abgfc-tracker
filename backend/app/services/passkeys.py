"""Passkeys (WebAuthn) - what a parent signs in with.

Why this rather than the emailed link it replaces: NIST SP 800-63B-4 says plainly that
"Email SHALL NOT be used for out-of-band authentication" - an inbox is usually protected
by a password, messages can be intercepted, and delivery can be rerouted. A passkey is a
key pair bound to our domain. We hold only the public half, so a copy of the database is
worth nothing, and the browser will not offer the credential to any other origin, so a
convincing fake of this site cannot collect it. With user verification (Face ID, a
fingerprint, or the device PIN) it is a multi-factor authenticator.

The ceremonies follow OWASP's Passkey Security Cheat Sheet: a fresh random challenge per
attempt, held server-side and bound to its purpose and account, consumed once, with the
session rotated on success.
"""

import json
import logging
import secrets
from datetime import datetime, timedelta

import webauthn
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.config import Settings
from app.core.errors import AuthError, ConflictError, NotFoundError, ValidationError
from app.models import Passkey, User, WebAuthnChallenge
from app.repositories.users import UserRepository

log = logging.getLogger("abgfc.passkeys")

REGISTER = "register"
AUTHENTICATE = "authenticate"


def _now() -> datetime:
    return datetime.now()


class PasskeyService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.users = UserRepository(db)

    # --- registering a passkey (the user is already signed in) --------------------

    def registration_options(self, user: User) -> dict:
        """Called straight after accepting an invitation, or from Settings to add a
        second device. Always for an account we have already authenticated."""
        if user.webauthn_handle is None:
            user.webauthn_handle = secrets.token_bytes(32)
            self.db.flush()
        options = webauthn.generate_registration_options(
            rp_id=self.settings.rp_id,
            rp_name=self.settings.webauthn_rp_name,
            user_id=user.webauthn_handle,
            user_name=user.email or user.username,
            user_display_name=user.display_name or user.email or user.username,
            # A discoverable credential, so signing in needs no email typed first.
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.REQUIRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
            exclude_credentials=[
                PublicKeyCredentialDescriptor(id=p.credential_id) for p in user.passkeys
            ],
        )
        self._store_challenge(options.challenge, REGISTER, user.id)
        return json.loads(webauthn.options_to_json(options))

    def register(self, user: User, credential: dict, label: str | None) -> Passkey:
        challenge = self._take_challenge(REGISTER, user.id)
        try:
            verified = webauthn.verify_registration_response(
                credential=credential,
                expected_challenge=challenge,
                expected_rp_id=self.settings.rp_id,
                expected_origin=self.settings.public_base_url.rstrip("/"),
                require_user_verification=True,
            )
        except InvalidRegistrationResponse as e:
            raise ValidationError(f"That didn't work: {e}") from e

        if self._by_credential_id(verified.credential_id) is not None:
            raise ConflictError("That device is already registered")
        passkey = Passkey(
            credential_id=verified.credential_id,
            public_key=verified.credential_public_key,
            sign_count=verified.sign_count,
            label=(label or "").strip() or None,
        )
        # Through the relationship, so the user object we go on to serialise knows.
        user.passkeys.append(passkey)
        self.db.commit()
        self.db.refresh(passkey)
        log.info("passkey registered for user %s", user.id)
        return passkey

    # --- signing in with one (no session yet) -------------------------------------

    def authentication_options(self) -> dict:
        """No account named: the credential is discoverable, so the authenticator tells
        us which account it is. Nothing here reveals whether any given account exists."""
        options = webauthn.generate_authentication_options(
            rp_id=self.settings.rp_id,
            user_verification=UserVerificationRequirement.REQUIRED,
        )
        self._store_challenge(options.challenge, AUTHENTICATE, None)
        return json.loads(webauthn.options_to_json(options))

    def authenticate(self, credential: dict) -> User:
        challenge = self._take_challenge(AUTHENTICATE, None)
        raw_id = credential.get("rawId") or credential.get("id")
        if not raw_id:
            raise AuthError("Sign in failed")
        passkey = self._by_credential_id(base64url_to_bytes(raw_id))
        if passkey is None:
            raise AuthError("Sign in failed")

        try:
            verified = webauthn.verify_authentication_response(
                credential=credential,
                expected_challenge=challenge,
                expected_rp_id=self.settings.rp_id,
                expected_origin=self.settings.public_base_url.rstrip("/"),
                credential_public_key=passkey.public_key,
                credential_current_sign_count=passkey.sign_count,
                require_user_verification=True,
            )
        except InvalidAuthenticationResponse as e:
            raise AuthError("Sign in failed") from e

        user = self.users.get(passkey.user_id)
        if user is None or not user.is_active:
            raise AuthError("That account has been closed - ask your coach")
        # The user handle the authenticator returns must name the same account.
        handle = credential.get("response", {}).get("userHandle")
        if handle and user.webauthn_handle != base64url_to_bytes(handle):
            raise AuthError("Sign in failed")

        if verified.new_sign_count and verified.new_sign_count <= passkey.sign_count:
            # A counter that fails to climb can mean a cloned authenticator - but it is
            # also what several perfectly ordinary ones do, so log it, don't lock out.
            log.warning("passkey %s sign count did not increase", passkey.id)
        passkey.sign_count = verified.new_sign_count
        passkey.last_used_at = _now()
        self.db.commit()
        return user

    # --- managing them --------------------------------------------------------------

    def remove(self, user: User, passkey_id: int) -> None:
        passkey = self.db.get(Passkey, passkey_id)
        if passkey is None or passkey.user_id != user.id:
            raise NotFoundError("No such passkey")
        if len(user.passkeys) == 1 and not user.allow_email_signin:
            raise ValidationError(
                "That's your only way in. Add another device first, or ask your coach to "
                "turn email sign-in back on."
            )
        user.passkeys.remove(passkey)
        self.db.commit()

    # --- helpers ---------------------------------------------------------------------

    def _by_credential_id(self, credential_id: bytes) -> Passkey | None:
        return self.db.scalar(select(Passkey).where(Passkey.credential_id == credential_id))

    def _store_challenge(self, challenge: bytes, purpose: str, user_id: int | None) -> None:
        self.db.execute(delete(WebAuthnChallenge).where(WebAuthnChallenge.expires_at < _now()))
        self.db.add(
            WebAuthnChallenge(
                challenge=challenge,
                purpose=purpose,
                user_id=user_id,
                expires_at=_now() + timedelta(seconds=self.settings.webauthn_challenge_ttl_seconds),
            )
        )
        self.db.commit()

    def _take_challenge(self, purpose: str, user_id: int | None) -> bytes:
        """Consume the newest live challenge for this purpose and account. A challenge
        issued for registration can never be spent on an authentication."""
        row = self.db.scalar(
            select(WebAuthnChallenge)
            .where(
                WebAuthnChallenge.purpose == purpose,
                WebAuthnChallenge.user_id == user_id,
                WebAuthnChallenge.expires_at > _now(),
            )
            .order_by(WebAuthnChallenge.id.desc())
        )
        if row is None:
            # On the way in, say nothing useful: a stale or replayed challenge is an
            # authentication failure, not a hint about what went wrong.
            if purpose == AUTHENTICATE:
                raise AuthError("Sign in failed")
            raise ValidationError("That took too long - start again")
        challenge = row.challenge
        self.db.delete(row)
        self.db.commit()
        return challenge


def passkey_label(p: Passkey) -> str:
    return p.label or f"Device {bytes_to_base64url(p.credential_id)[:6]}"
