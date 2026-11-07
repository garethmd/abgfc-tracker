# 13. Parent access

Parents of the children get read access to the app. The design goal was the least
possible administrative work for the club: nothing for a coach to issue, nothing for a
coach to reset, and removal that is one tap and immediate.

A parent is an **ordinary account with an ordinary role** — `viewer` at cohort scope,
the same row the age-group coach holds at a higher level. Nothing in
`services/access.py` changed to support them. What marks them out is a
`player_guardians` link to their child. The link grants no extra permission; it says
whose parent this is, and it is what keeps the account alive (see **Who may invite, and
who may remove**).

## How they sign in

**A password, chosen when they accept the invitation.** Email is used only to recover
it. That distinction matters: [NIST SP 800-63B-4](https://pages.nist.gov/800-63-4/sp800-63b.html)
says *"Email SHALL NOT be used for out-of-band authentication"* — but it permits email
for recovery. A memorised secret is an approved authenticator; an emailed link used as
the routine way in is not.

This replaced two earlier attempts, and the reasons are worth keeping:

- **Emailed sign-in links** (the first design) are what NIST forbids, and the whole
  system quietly depended on them.
- **Passkeys as the only method** (the second) failed in the field. Registration depends
  on the device, the browser and the platform's state; one parent in five couldn't
  complete it, and each failure lands on a volunteer coach. In particular an invitation
  opened from WhatsApp runs in an in-app WebView, where passkey creation is unreliable
  or impossible.

A password works in every browser, including WhatsApp's, on every device, with nothing
to fail. The session lasts 30 days — see **Sessions** below for why not longer.

**Passkeys remain, as an optional extra** — see below. Better for devices that support
them, never required, never a blocker.

**Parents who joined before passwords existed** keep their emailed sign-in links until
they choose to set one in Settings → Account. Nothing forces them, and nobody was
locked out by the change.

## Passwords

**Eight characters minimum, no maximum, and nothing else required.** The authority is
[Cyber Essentials v3.3](https://www.ncsc.gov.uk/cyberessentials/overview) — UK,
government-backed, and the scheme a grassroots club would actually be measured against.
It offers three acceptable password policies; the one we meet is at least 8 characters
with no upper limit, **conditional on automatically blocking common passwords from a deny
list**. That deny list is not built yet, so today we have the short minimum without the
condition that licenses it. It is first on the [roadmap](12-roadmap.md#parent-onboarding-the-unfinished-half)
for that reason.

NIST SP 800-63B-4 would ask for 15 characters where a password is the only authenticator.
It is a US federal standard for federal systems, and 15 characters typed on a phone by
someone who has never used a password manager is how the password ends up pasted into the
WhatsApp group. Cyber Essentials is the standard that fits this club, and it is satisfied
with a deny list instead of with length.

What we deliberately **don't** do — NIST, NCSC and Cyber Essentials all agree here:

- **No composition rules.** No required capital, digit or symbol. They produce
  `Password1!` and buy nothing.
- **No expiry.** Forced rotation makes people pick weaker, more guessable passwords.
- **No lockout.** Brute force is answered by **throttling**: 10 attempts per 5 minutes,
  per account and per IP, which is the ceiling Cyber Essentials itself names. NCSC prefers
  throttling because *"account lockout can leave legitimate users unable to access their
  accounts"* — and a coach locked out at kick-off is a worse outcome than a slow one. A
  correct password clears the counter, so three fumbles cost nothing.

Hashing is **argon2id** (`argon2-cffi` defaults, ~50 ms). `password_hash` stays nullable
for the parents invited before any of this existed; `MeRead.has_password` tells the UI
which it is, so no screen has to guess.

## Passkeys

`services/passkeys.py`, following [OWASP's Passkey Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Passkey_Security_Cheat_Sheet.html).

- **Registration always happens for an account already signed in** — today that means
  Settings → Signing in, the only place the app offers it. That session is what binds the
  credential to the right person. FIDO's own guidance is to offer one at account creation
  and after a recovery as well; neither is built — see
  [Roadmap](12-roadmap.md#parent-onboarding-the-unfinished-half).
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

**Adding a passkey takes nothing away.** It sits beside the password, which every device
can manage; the passkey only replaces the typing. When passkeys were the *only* way in,
registering one retired that account's emailed links and a coach could re-open them for
one named parent — `users.allow_email_signin` is all that survives of that, and nothing
reads or writes it now. Don't revive the column: the password is the fallback, and a
passkey that can fall back to something weaker is what OWASP warns against.

**Losing the device is no longer a lockout.** The password still works, and if that has
gone too, "Forgotten your password?" sends a reset link. In practice it rarely comes up:
passkeys sync through iCloud Keychain and Google Password Manager, so a new phone usually
already has one.

## The flow

1. A coach opens **Settings → Parents**, picks a child and types an email.
2. `POST /invitations` creates a `login_tokens` row and emails a link to
   `/invite/<token>`. The response carries that link **once** so the coach can send it by
   hand — a bounced email, a spam folder, or a parent who only reads WhatsApp. It is
   never retrievable again; to replace a lost one, invite again (which revokes the old).
3. The parent opens the link and sees who invited them and which child. **Looking does
   not spend the token** — mail security scanners follow links, and consuming on `GET`
   would burn the invitation before the parent ever tapped it.
4. They type their name and **choose a password** — plus their email address, if the coach
   sent the link by hand and so never typed one. `POST /invitations/<token>/accept` creates
   the user, the guardian link and the role row, spends the token, sets the session cookie
   and lands them on the team.
5. The cookie lasts 30 days. After that they sign in with that password — or with one
   touch, if they have since added a passkey in Settings. **Nothing offers them a passkey
   on the way in**, which is the hole in this flow: a parent has to go looking for it. See
   [Roadmap](12-roadmap.md#parent-onboarding-the-unfinished-half).

**Coming back to the same link.** They will: the invitation sits in their WhatsApp history
and the obvious way back into the app is to tap it again. The token is spent by then, so
the page asks `GET /auth/me` before it says anything:

- **Signed in** (almost always — the cookie lasts 30 days) → straight into the app, no
  message. Nothing to read, nothing to understand.
- **Not signed in, invitation already accepted** (`410`) → "You're already set up", and a
  **Sign in** button.
- **Not signed in, link expired or unknown** (`404`) → "This link has expired", the same
  button, and only then "ask your coach for a new link".

Before this, every one of those showed *"Invitations last a fortnight… ask your coach to
send another one"*, with no way forward on the page — so a parent who was already signed in
was told to go and bother a volunteer, and coaches were talking people through deleting
`/invite/<token>` off the end of the URL by hand. The probe is a bare `fetch`, not
`fetchClient`: the client's middleware turns a 401 into a redirect to `/login`, which would
throw away the explanation and, for a genuinely expired invitation, park them on a sign-in
form for an account that does not exist.

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
- `POST /auth/forgot-password` answers `204` whether or not the address has an account; an
  unauthenticated caller doesn't get to learn who is registered. The link lands on
  `/reset/<token>` and is spent by `POST /auth/reset-password/<token>`, which also bumps
  `session_version` — if somebody else had got in, that is what removes them.
- Rate limited in process (`core/ratelimit.py`): 5 link requests and 20 token attempts per
  15 minutes, and 10 password attempts per 5 minutes, each keyed by address *and* by IP.

## Who may invite, and who may remove

Coaches, not just admins. The check reuses the one that already governs editing a child:
`access.require_player(db, player, COACH)` — coach+ on the cohort, or on a team whose
squad the child is in. A coach granting `viewer` grants strictly less than they hold, so
this is not an escalation, and `invited_by_user_id` records who did it.

The same rule governs removal: a coach may act on a parent exactly when they could have
invited them.

**An account exists exactly as long as it has a child linked.** That one rule is what
keeps this simple, and it was learned the hard way: guardian links, role rows and
`is_active` were three records of whether a parent had access, and the two worst bugs here
were simply those three disagreeing. Removing a parent's last child used to leave a row
that no coach could reach — not closeable, not deletable, holding its email address
forever — and a closed account could not be re-invited, because the error told the coach
to ask a coach.

| Action | Effect |
|---|---|
| `DELETE /parents/{id}/children/{player_id}` | The guardian link goes. **If it was their last child anywhere, the account goes with it** — links, role, passkeys and unused tokens, by cascade — and the address is free to invite again. |
| `DELETE /parents/{id}` | The same for every child at once: "take me off your system". Not a separate state, just a shortcut. |
| `POST /parents/{id}/sign-out` | Bumps `session_version` only — a phone left on a bus, where they keep their access. |

There is deliberately **no close and no re-open**. A parent account holds nothing of its
own — no notes, no uploads, no history; the child's record belongs to the child — so a
dormant row preserved nothing while costing two endpoints, a dead end and a third source
of truth. Re-inviting is one tap. `users.is_active` stays on the table because the admin
screens use it for coaches; a parent never sets it.

**Children who have left.** A guardian link outlives the child's time at the club on
purpose. Setting a player's `left_date` does *not* remove their parent's access; instead
the Parents tab grows a **Children who have left** section naming the accounts to remove,
so nobody has to remember. A parent with a second child still playing is not listed.

## The access log

Deleting the account is right for the account and wrong for the record: *"who used to be
able to see my child?"* is a safeguarding question, and a deleted row answers nothing.
So the answer lives in **`parent_access_log`** — one append-only line per grant and per
revocation, written by the same service calls that change access, never updated and never
deleted.

None of its user ids are foreign keys, which is the whole point: a cascade would delete
the history this exists to keep. The parent's name and address are copied in for the same
reason. The migration backfills a `granted` line for everyone who can see a child today,
so it starts out telling the truth rather than starting empty.

## Sessions

**30 days from the last authentication, and ordinary activity does not extend it.** NIST
SP 800-63B-4 says *"A definite reauthentication overall timeout SHALL be established,
which SHOULD be no more than 30 days at AAL1"*, and only *"successful reauthentication
resets both timeouts"* — so refreshing the cookie on every request would mean there was no
definite timeout at all. An inactivity timeout *"MAY be applied but is not required at
AAL1"*, so there isn't one: it would cost usability and buy nothing required.

This is what makes the optional passkey worth offering. Thirty days means roughly twelve
reauthentications a season; twelve passwords is friction, twelve thumbprints is nothing.

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
| `player_guardians` | `user_id` + `player_id`, unique together. Many-to-many: two parents per child, two children per parent. **This is what says the account exists**: remove the last link and the account goes. |
| `parent_access_log` | Append-only: `user_id`, `parent_name`, `parent_email`, `by_user_id`, `player_id`, `action` (`granted` \| `revoked`), `at`. Only `player_id` is a real FK — a cascade from `users` would delete the history it exists to keep. |
| `users` | gains `email` (nullable, unique), `session_version`; `password_hash` becomes nullable; `username` widened to 255 because a parent's username is their email. |
