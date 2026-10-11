/** Passkeys: the browser half of the two WebAuthn ceremonies.
 *
 *  The server sends options as base64url JSON and wants the result back the same way;
 *  the browser API deals in ArrayBuffers. These helpers do that conversion and nothing
 *  else - every security decision (challenge, origin, user verification, which account
 *  a credential belongs to) is made server-side, because anything decided here is
 *  decided by whoever controls the page.
 */

import { fetchClient } from "@/lib/api/client";

/** Passkeys need a secure context and a platform authenticator; both are universal on
 *  phones now, but an old desktop browser may have neither. */
export function passkeysSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.PublicKeyCredential === "function" &&
    !!navigator.credentials
  );
}

function fromBase64Url(s: string): Uint8Array {
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(b64 + "=".repeat((4 - (b64.length % 4)) % 4));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

function toBase64Url(b: ArrayBuffer): string {
  const bin = String.fromCharCode(...new Uint8Array(b));
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

type Options = Record<string, unknown>;

/** Walk the options the server sent, turning the base64url fields into buffers. */
function decodeOptions(options: Options): Options {
  const out: Options = { ...options };
  if (typeof out.challenge === "string") out.challenge = fromBase64Url(out.challenge);
  const user = out.user as { id?: string } | undefined;
  if (user?.id) out.user = { ...user, id: fromBase64Url(user.id) };
  for (const key of ["excludeCredentials", "allowCredentials"] as const) {
    const list = out[key] as { id: string }[] | undefined;
    if (list) out[key] = list.map((c) => ({ ...c, id: fromBase64Url(c.id) }));
  }
  return out;
}

function encodeCredential(credential: PublicKeyCredential): Record<string, unknown> {
  const response = credential.response as AuthenticatorAttestationResponse &
    AuthenticatorAssertionResponse;
  const encoded: Record<string, unknown> = {
    clientDataJSON: toBase64Url(response.clientDataJSON),
  };
  if (response.attestationObject) {
    encoded.attestationObject = toBase64Url(response.attestationObject);
  }
  if (response.authenticatorData) {
    encoded.authenticatorData = toBase64Url(response.authenticatorData);
    encoded.signature = toBase64Url(response.signature);
    encoded.userHandle = response.userHandle ? toBase64Url(response.userHandle) : null;
  }
  return {
    id: credential.id,
    rawId: toBase64Url(credential.rawId),
    type: credential.type,
    response: encoded,
  };
}

/** Thrown when the person dismissed the Face ID sheet - not an error worth shouting about. */
export class PasskeyCancelled extends Error {}

function wrap(err: unknown): never {
  const name = (err as { name?: string }).name;
  if (name === "NotAllowedError" || name === "AbortError") throw new PasskeyCancelled();
  throw err;
}

/** Register this device. Requires an existing session - the server binds the new
 *  credential to the account it has already authenticated. */
export async function registerPasskey(label?: string): Promise<void> {
  const { data: options, error } = await fetchClient.POST("/api/v1/auth/passkeys/options", {});
  if (error) throw error;

  let credential: PublicKeyCredential | null;
  try {
    credential = (await navigator.credentials.create({
      publicKey: decodeOptions(options as Options) as unknown as PublicKeyCredentialCreationOptions,
    })) as PublicKeyCredential | null;
  } catch (err) {
    wrap(err);
  }
  if (!credential) throw new PasskeyCancelled();

  const { error: saveError } = await fetchClient.POST("/api/v1/auth/passkeys", {
    body: { credential: encodeCredential(credential), label: label ?? null },
  });
  if (saveError) throw saveError;
}

/** Sign in. Nothing is typed: the credential is discoverable, so the authenticator
 *  tells the server which account it holds. */
export async function signInWithPasskey(): Promise<void> {
  const { data: options, error } = await fetchClient.POST(
    "/api/v1/auth/passkeys/signin/options",
    {},
  );
  if (error) throw error;

  let credential: PublicKeyCredential | null;
  try {
    credential = (await navigator.credentials.get({
      publicKey: decodeOptions(options as Options) as unknown as PublicKeyCredentialRequestOptions,
    })) as PublicKeyCredential | null;
  } catch (err) {
    wrap(err);
  }
  if (!credential) throw new PasskeyCancelled();

  const { error: signInError } = await fetchClient.POST("/api/v1/auth/passkeys/signin", {
    body: { credential: encodeCredential(credential) },
  });
  if (signInError) throw signInError;
}
