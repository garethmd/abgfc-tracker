import createFetchClient, { type Middleware } from "openapi-fetch";
import createClient from "openapi-react-query";
import type { components, paths } from "./schema";

export type Schema = components["schemas"];

const redirectOn401: Middleware = {
  async onResponse({ response }) {
    if (
      response.status === 401 &&
      typeof window !== "undefined" &&
      !window.location.pathname.startsWith("/login")
    ) {
      const next = window.location.pathname;
      // Full reload on purpose: drops all cached query state for the signed-out user.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign(`/login${next !== "/" ? `?next=${encodeURIComponent(next)}` : ""}`);
    }
    return response;
  },
};

export const fetchClient = createFetchClient<paths>({ baseUrl: "/", credentials: "include" });
fetchClient.use(redirectOn401);

/** Typed TanStack Query hooks: `$api.useQuery("get", "/api/v1/seasons")`. */
export const $api = createClient(fetchClient);

/** Pull a human-readable message out of a FastAPI error body. */
export function errorMessage(error: unknown, fallback = "Something went wrong"): string {
  if (!error || typeof error !== "object") return fallback;
  const detail = (error as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: string; loc?: unknown[] } | undefined;
    if (first?.msg) {
      const field = Array.isArray(first.loc) ? first.loc.slice(1).join(".") : "";
      return field ? `${field}: ${first.msg.replace(/^Value error, /, "")}` : first.msg;
    }
  }
  return fallback;
}
