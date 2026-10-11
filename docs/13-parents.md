# 13. Parent access

Parents of the children get read access to the app. The design goal was the least
possible administrative work for the club: no passwords to issue, no passwords to reset,
and removal that is one tap and immediate.

A parent is an **ordinary account with an ordinary role** — `viewer` at cohort scope,
the same row the age-group coach holds at a higher level. Nothing in
`services/access.py` changed to support them. What marks them out is a
`player_guardians` link to their child, which grants nothing today.

## Why no password — and why not an emailed link either

A parent opens this app twice a month. A password set in September is forgotten by
October, and there is no self-service reset, so every forgotten password becomes a
message to the club.

Emailed sign-in links were the first answer and are **not** the answer.
[NIST SP 800-63B-4](https://pages.nist.gov/800-63-4/sp800-63b.html) is explicit: *"Email
SHALL NOT be used for out-of-band authentication"* — an inbox is usually guarded by a
password, mail can be intercepted, and delivery can be rerouted. It permits email only
for confirming an address or as a recovery artifact.

So a parent signs in with a **passkey**: a key pair bound to this domain, unlocked by
Face ID, a fingerprint or the device PIN. We hold the public half only, so a copy of the
database is worth nothing; and the browser will not offer the credential to any other
origin, so a convincing fake of this site cannot collect it. With user verification it is
a multi-factor authenticator at AAL2 — stronger than the password this replaced, and
less work for the parent.

Coaches keep passwords: they sign in constantly, often on bad signal at the pitch.

The two paths can't cross. A parent account has `password_hash = NULL`, so
`POST /auth/login` can never authenticate one. A coach has no `email`, so
`POST /auth/signin-link` never issues a link for them. `tests/test_invites.py` pins both.

## Passkeys

`services/passkeys.py`, following [OWASP's Passkey Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Passkey_Security_Cheat_Sheet.html).

- **Registration always happens for an account already signed in** — straight after
  accepting an invitation, or from Settings → Signing in to add a second device. That is
  what binds the credential to the right person.
- **Sign-in names no account.** The credential is discoverable, so the authenticator says
  which account it holds; nothing typed, and nothing reveals whether an account exists.
- **Challenges live server-side** in `webauthn_challenges`, bound to purpose and account,
  consumed by deletion. A registration challenge can never be spent on an authentication.
- **User verification is required** on both ceremonies — a passkey without it would be
  single-factor.
- `users.webauthn_handle` is 32 random bytes. It travels to the authenticator, so it
  carries nothing personal.
- **Several per parent is encouraged** (phone and laptop); the last one can't be removed
  unless there's another way in.

**Registering a passkey retires that account's emailed links** — otherwise a failed
passkey could quietly fall back to something weaker, which is exactly what OWASP warns
against. A coach can re-open them for one named parent whose device can't hold a passkey
(no screen lock, or iOS before 16 / Android before 10) from the Parents tab. Deliberate,
per account, visible — never automatic.

Recovery for a lost device is a **new invitation from the coach**, not an email link.
They know the parent personally, which is stronger proofing than any inbox check. In
practice it rarely comes up: passkeys sync through iCloud Keychain and Google Password
Manager, so a new phone usually already has one.

## The flow

1. A coach opens **Settings → Parents**, picks a child and types an email.
2. `POST /invitations` creates a `login_tokens` row and emails a link to
   `/invite/<token>`. The response carries that link **once** so the coach can send it by
   hand — a bounced email, a spam folder, or a parent who only reads WhatsApp. It is
   never retrievable again; to replace a lost one, invite again (which revokes the old).
3. The parent opens the link and sees who invited them and which child. **Looking does
   not spend the token** — mail security scanners follow links, and consuming on `GET`
   would burn the invitation before the parent ever tapped it.
4. They type their name and press the button. `POST /invitations/<token>/accept` creates
   the user, the guardian link and the role row, spends the token, sets the session
   cookie and lands them on the team.
5. The cookie lasts 30 days. After that, `/login` → *Parent? Email me a sign-in link* →
   `/signin/<token>`, which again only signs in on the button press.

`proxy.ts` exempts `/invite/` and `/signin/` from the cookie gate: an emailed link must
not be bounced to the coaches' sign-in page.

## The tokens

`core/security.py`. 256 bits from `secrets.token_urlsafe(32)`, stored **only** as a
SHA-256 hash — the raw value exists in the email and nowhere else. A fast hash is correct
here, unlike for passwords: the input is already high-entropy, so there is nothing to
brute-force, and verification needs an indexed lookup.

- Invitations last 14 days, sign-in links 15 minutes (`invite_expiry_hours`,
  `signin_link_expiry_minutes`).
- Single use is enforced by **one conditional `UPDATE … WHERE used_at IS NULL`** with
  `RETURNING`, not a read-then-write, so two simultaneous taps can't both win.
- `POST /auth/signin-link` answers `204` whether or not the address has an account; an
  unauthenticated caller doesn't get to learn who is registered.
- Rate limited in process (`core/ratelimit.py`): 5 link requests and 20 token attempts
  per 15 minutes, keyed by email *and* by IP.

## Who may invite, and who may remove

Coaches, not just admins. The check reuses the one that already governs editing a child:
`access.require_player(db, player, COACH)` — coach+ on the cohort, or on a team whose
squad the child is in. A coach granting `viewer` grants strictly less than they hold, so
this is not an escalation, and `invited_by_user_id` records who did it.

The same rule governs removal: a coach may act on a parent exactly when they could have
invited them.

| Action | Effect |
|---|---|
| `POST /parents/{id}/close` | `is_active = false` **and** `session_version + 1`. Dead on the next request, every device. |
| `POST /parents/{id}/reopen` | Lets them back in; they ask for a new link. |
| `POST /parents/{id}/sign-out` | Bumps the version only — a phone left on a bus, where they keep their access. |

**Children who have left.** A guardian link outlives the child's time at the club on
purpose. Setting a player's `left_date` does *not* remove their parent's access; instead
the Parents tab grows a **Children who have left** section naming the accounts to close,
so nobody has to remember. A parent with a second child still playing is not listed.

## Sessions

`users.session_version` goes into the signed cookie as `sv` and is compared on every
request. A cookie minted before this existed carries no `sv` and is accepted as-is —
adding the column signed nobody out, which mattered because a coach suddenly locked out
is a coach who stops trusting the app.

## Email

`services/email.py`. Three backends:

- **console** (default, development and tests) — logs the message, link included, and
  sends nothing. `main.py` attaches a handler to the `abgfc` logger because uvicorn only
  configures its own; without it the dev links go nowhere.
- **resend** / **mailgun** — the provider's HTTPS API. Never SMTP: DigitalOcean blocks
  outbound SMTP on droplets, so a relay would hang rather than fail cleanly. `httpx` is
  already a dependency.

Settings (`ABGFC_*`): `email_backend`, `email_from`, `email_reply_to`, `email_api_key`,
`mailgun_domain`, `public_base_url`. In production the app refuses to start if a real
backend is selected with no key. Sending failures are **not** fatal for an invitation —
the coach still has the link.

`email_reply_to` matters: `abgfc.neuralaspect.com` has an A record and no MX, so a reply
to `noreply@` falls back to the droplet, finds no SMTP server and hangs. Point it at a
mailbox somebody reads. The root domain's DMARC is `p=quarantine` and subdomains inherit
it, so the sending subdomain needs its own SPF, DKIM and (initially `p=none`) DMARC
records or mail is silently binned.

## What a parent sees

Everything a `viewer` can, across every team in the age group: fixtures, results, stats,
squads, photos, match notes, availability. The head coach decided in Oct 2026 that
nothing needs withholding. The exceptions are the two coach-only reports (the matchday
PDF and the season spreadsheet) and every write in the app.

## Tables

| Table | |
|---|---|
| `login_tokens` | `token_hash` (unique), `purpose` (`invite` \| `signin`), `email`, `player_id` (invites), `user_id` (sign-ins), `invited_by_user_id`, `expires_at`, `used_at`, `revoked_at`. A CHECK keeps the two shapes honest. |
| `player_guardians` | `user_id` + `player_id`, unique together. Many-to-many: two parents per child, two children per parent. |
| `users` | gains `email` (nullable, unique), `session_version`; `password_hash` becomes nullable; `username` widened to 255 because a parent's username is their email. |
