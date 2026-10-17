"""Passkeys: how a parent signs in once they have one.

Driven through a software authenticator, so these exercise the real ceremonies -
challenge, signature, origin and RP id checks - not a stub.
"""

import base64
from hashlib import sha256
from struct import pack

import pytest
from fastapi.testclient import TestClient
from soft_webauthn import SoftWebauthnDevice as _Device
from sqlalchemy import select

from app.config import get_settings
from app.core.ratelimit import signin_links, token_attempts
from app.models import Passkey, User
from app.services.bootstrap import DemoSeason

API = "/api/v1"
ORIGIN = "http://localhost:3000"


class SoftWebauthnDevice(_Device):
    """soft-webauthn hard-codes its flag byte and never sets user verification, which
    is exactly what we require. A real phone sets it after Face ID or the PIN, so the
    test device has to as well - otherwise these tests would only pass by us asking for
    less than the app does."""

    UV = 0x04

    def create(self, options, origin):
        credential = super().create(options, origin)
        from fido2 import cbor

        attestation = cbor.decode(credential["response"]["attestationObject"])
        data = bytearray(attestation["authData"])
        data[32] |= self.UV
        attestation["authData"] = bytes(data)
        credential["response"]["attestationObject"] = cbor.encode(attestation)
        return credential

    def get(self, options, origin):
        """Rebuilt rather than patched: the authenticator data is signed, so flipping a
        flag afterwards would invalidate the signature."""
        if self.rp_id != options["publicKey"]["rpId"]:
            raise ValueError("Requested rpID does not match current credential")
        import json as _json
        from base64 import urlsafe_b64encode

        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec

        self.sign_count += 1
        client_data = _json.dumps(
            {
                "type": "webauthn.get",
                "challenge": urlsafe_b64encode(options["publicKey"]["challenge"])
                .decode("ascii")
                .rstrip("="),
                "origin": origin,
            }
        ).encode()
        authenticator_data = (
            sha256(self.rp_id.encode("ascii")).digest()
            + bytes([0x01 | self.UV])
            + pack(">I", self.sign_count)
        )
        signature = self.private_key.sign(
            authenticator_data + sha256(client_data).digest(), ec.ECDSA(hashes.SHA256())
        )
        return {
            "id": urlsafe_b64encode(self.credential_id),
            "rawId": self.credential_id,
            "response": {
                "authenticatorData": authenticator_data,
                "clientDataJSON": client_data,
                "signature": signature,
                "userHandle": self.user_handle,
            },
            "type": "public-key",
        }


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _encode(credential: dict) -> dict:
    """The soft authenticator hands back raw bytes; a browser would send base64url."""
    out = {
        "id": _b64(credential["rawId"]),
        "rawId": _b64(credential["rawId"]),
        "type": credential["type"],
        "response": {},
    }
    for k, v in credential["response"].items():
        out["response"][k] = _b64(v) if isinstance(v, bytes) else v
    return out


def _options_for_device(options: dict) -> dict:
    """py_webauthn emits base64url JSON; the soft device wants bytes."""

    def pad(s: str) -> bytes:
        return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

    pk = {k: v for k, v in options.items()}
    pk["challenge"] = pad(pk["challenge"])
    if pk.get("user"):
        pk["user"] = {**pk["user"], "id": pad(pk["user"]["id"])}
    for key in ("excludeCredentials", "allowCredentials"):
        if pk.get(key):
            pk[key] = [{**c, "id": pad(c["id"])} for c in pk[key]]
    return {"publicKey": pk}


@pytest.fixture(autouse=True)
def _fresh_limits():
    """The limiters are module-level and would otherwise leak across this file."""
    signin_links.reset()
    token_attempts.reset()
    yield
    signin_links.reset()
    token_attempts.reset()


@pytest.fixture(autouse=True)
def _origin():
    """The app builds the expected origin and RP id from public_base_url."""
    s = get_settings()
    before = s.public_base_url
    s.public_base_url = ORIGIN
    yield
    s.public_base_url = before


def _parent(auth_client: TestClient, demo: DemoSeason, email="mum@example.com") -> TestClient:
    r = auth_client.post(
        f"{API}/invitations", json={"player_id": demo.players["Archie"].id, "email": email}
    )
    token = r.json()["link"].rsplit("/", 1)[1]
    parent = TestClient(auth_client.app)
    parent.post(
        f"{API}/auth/invitations/{token}/accept",
        json={"display_name": "Jo", "password": "correct horse"},
    )
    return parent


def _register(client: TestClient, device: SoftWebauthnDevice, label="iPhone"):
    options = client.post(f"{API}/auth/passkeys/options").json()
    created = device.create(_options_for_device(options), ORIGIN)
    return client.post(
        f"{API}/auth/passkeys", json={"credential": _encode(created), "label": label}
    )


def _signin(client: TestClient, device: SoftWebauthnDevice):
    options = client.post(f"{API}/auth/passkeys/signin/options").json()
    assertion = device.get(_options_for_device(options), ORIGIN)
    return client.post(f"{API}/auth/passkeys/signin", json={"credential": _encode(assertion)})


# --- the happy path -------------------------------------------------------------------


def test_register_a_passkey_then_sign_in_with_it(auth_client: TestClient, db, demo: DemoSeason):
    parent = _parent(auth_client, demo)
    device = SoftWebauthnDevice()

    r = _register(parent, device)
    assert r.status_code == 201, r.text
    assert r.json()["label"] == "iPhone"
    assert parent.get(f"{API}/auth/me").json()["passkey_count"] == 1

    # A fresh client with no cookie signs in with the device alone - no email typed
    fresh = TestClient(auth_client.app)
    assert fresh.get(f"{API}/auth/me").status_code == 401
    r = _signin(fresh, device)
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "mum@example.com"
    assert fresh.get(f"{API}/auth/me").status_code == 200

    stored = db.scalar(select(Passkey))
    assert stored.last_used_at is not None
    # Only the public half of the credential is kept, and the handle, which travels
    # to the authenticator, carries nothing personal
    user = db.scalar(select(User).where(User.email == "mum@example.com"))
    assert b"mum@example.com" not in user.webauthn_handle


def test_a_second_device_can_be_added(auth_client: TestClient, demo: DemoSeason):
    parent = _parent(auth_client, demo)
    phone, laptop = SoftWebauthnDevice(), SoftWebauthnDevice()
    assert _register(parent, phone, "iPhone").status_code == 201
    assert _register(parent, laptop, "Laptop").status_code == 201
    assert len(parent.get(f"{API}/auth/passkeys").json()) == 2
    # Either gets you in
    for device in (phone, laptop):
        assert _signin(TestClient(auth_client.app), device).status_code == 200


# --- the ceremony rules ---------------------------------------------------------------


def test_a_challenge_is_single_use(auth_client: TestClient, demo: DemoSeason):
    parent = _parent(auth_client, demo)
    device = SoftWebauthnDevice()
    _register(parent, device)

    fresh = TestClient(auth_client.app)
    options = fresh.post(f"{API}/auth/passkeys/signin/options").json()
    assertion = _encode(device.get(_options_for_device(options), ORIGIN))
    assert (
        fresh.post(f"{API}/auth/passkeys/signin", json={"credential": assertion}).status_code == 200
    )
    # Replaying the very same assertion fails: the challenge is gone
    again = TestClient(auth_client.app)
    assert (
        again.post(f"{API}/auth/passkeys/signin", json={"credential": assertion}).status_code == 401
    )


def test_a_passkey_from_another_origin_is_refused(auth_client: TestClient, demo: DemoSeason):
    """The phishing resistance: a credential made for another site cannot be used here."""
    parent = _parent(auth_client, demo)
    device = SoftWebauthnDevice()
    options = parent.post(f"{API}/auth/passkeys/options").json()
    created = device.create(_options_for_device(options), "https://evil.example.com")
    r = parent.post(f"{API}/auth/passkeys", json={"credential": _encode(created)})
    assert r.status_code == 422


def test_an_unknown_device_cannot_sign_in(auth_client: TestClient, demo: DemoSeason):
    _parent(auth_client, demo)
    stranger = SoftWebauthnDevice()
    stranger.cred_init(get_settings().rp_id, b"whoever")
    fresh = TestClient(auth_client.app)
    options = fresh.post(f"{API}/auth/passkeys/signin/options").json()
    assertion = stranger.get(_options_for_device(options), ORIGIN)
    assert (
        fresh.post(
            f"{API}/auth/passkeys/signin", json={"credential": _encode(assertion)}
        ).status_code
        == 401
    )


def test_registering_needs_a_session(auth_client: TestClient):
    """A passkey is only ever bound to an account we have already authenticated."""
    anon = TestClient(auth_client.app)
    assert anon.post(f"{API}/auth/passkeys/options").status_code == 401
    assert anon.post(f"{API}/auth/passkeys", json={"credential": {}}).status_code == 401


# --- a passkey alongside a password ------------------------------------------------


def test_a_passkey_is_an_extra_not_a_replacement(
    auth_client: TestClient, db, demo: DemoSeason, caplog
):
    """Both ways in keep working. The password is the baseline every device can manage;
    the passkey is the better one for devices that can."""
    parent = _parent(auth_client, demo)
    device = SoftWebauthnDevice()
    _register(parent, device)

    # The passkey signs them in
    assert _signin(TestClient(auth_client.app), device).status_code == 200
    # ...and so does the password
    assert (
        TestClient(auth_client.app)
        .post(
            f"{API}/auth/login",
            json={"username": "mum@example.com", "password": "correct horse"},
        )
        .status_code
        == 200
    )
    # ...and a forgotten password still reaches them, because email now only recovers
    client = TestClient(auth_client.app)
    with caplog.at_level("INFO", logger="abgfc.email"):
        assert (
            client.post(
                f"{API}/auth/forgot-password", json={"email": "mum@example.com"}
            ).status_code
            == 204
        )
    assert "/reset/" in "\n".join(r.getMessage() for r in caplog.records if r.name == "abgfc.email")


# --- removing them ----------------------------------------------------------------------


def test_the_last_passkey_can_go_when_a_password_remains(
    auth_client: TestClient, db, demo: DemoSeason
):
    parent = _parent(auth_client, demo)
    _register(parent, SoftWebauthnDevice(), "iPhone")
    only = parent.get(f"{API}/auth/passkeys").json()[0]["id"]
    # Their password is still a way in, so removing the last device is fine
    assert parent.delete(f"{API}/auth/passkeys/{only}").status_code == 204
    assert parent.get(f"{API}/auth/passkeys").json() == []


def test_a_passwordless_parent_cannot_remove_their_only_passkey(
    auth_client: TestClient, db, demo: DemoSeason
):
    """Someone who joined before passwords and then added a passkey has one way in."""
    parent = _parent(auth_client, demo)
    _register(parent, SoftWebauthnDevice(), "iPhone")
    user = db.scalar(select(User).where(User.email == "mum@example.com"))
    user.password_hash = None
    db.commit()
    only = parent.get(f"{API}/auth/passkeys").json()[0]["id"]
    r = parent.delete(f"{API}/auth/passkeys/{only}")
    assert r.status_code == 422 and "only way in" in r.json()["detail"]


def test_one_parent_cannot_remove_anothers(auth_client: TestClient, demo: DemoSeason):
    first = _parent(auth_client, demo, "mum@example.com")
    _register(first, SoftWebauthnDevice())
    theirs = first.get(f"{API}/auth/passkeys").json()[0]["id"]

    second = _parent(auth_client, demo, "dad@example.com")
    _register(second, SoftWebauthnDevice())
    assert second.delete(f"{API}/auth/passkeys/{theirs}").status_code == 404
