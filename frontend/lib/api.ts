const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export type ApiError = Error & { status?: number; code?: string };

/*
 * Session model: the refresh token is an HttpOnly cookie that JavaScript can never read. The short-lived
 * access token is kept only in this module's memory, so a page reload simply refreshes it. The
 * "rental_user" entry in localStorage holds non-secret details (id, role, phone) for routing only.
 */
let accessToken: string | null = null;
let refreshing: Promise<string | null> | null = null;

const USER_KEY = "rental_user";

export function storeSession(access: string, user: object) {
  accessToken = access;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function clearSession() {
  accessToken = null;
  try { localStorage.removeItem(USER_KEY); localStorage.removeItem("rental_access"); localStorage.removeItem("rental_refresh"); } catch { /* storage blocked */ }
}

async function requestNewAccessToken(): Promise<string | null> {
  const response = await fetch(`${API_BASE_URL}/auth/token/refresh/`, { method: "POST", credentials: "include" });
  if (response.status === 401) { clearSession(); return null; }
  if (!response.ok) return null; // transient failure: keep the session, let the caller retry later
  accessToken = (await response.json()).access;
  return accessToken;
}

/** One refresh at a time, also across browser tabs, so rotated cookies never race each other. */
function refreshAccessToken(): Promise<string | null> {
  if (!refreshing) {
    const locks = typeof navigator !== "undefined" ? (navigator as Navigator & { locks?: LockManager }).locks : undefined;
    const run = () => requestNewAccessToken();
    // `await` flattens the lock's promise-of-a-promise (the callback itself is async).
    const pending: Promise<string | null> = locks ? (async () => await locks.request("nyumbani-token-refresh", run))() : run();
    refreshing = pending.finally(() => { refreshing = null; });
  }
  return refreshing;
}

async function currentAccess(): Promise<string | null> {
  return accessToken ?? (await refreshAccessToken());
}

/** fetch() against the API with the user's access token, refreshing it once on 401. */
export async function authorizedFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const send = (access: string | null) => fetch(`${API_BASE_URL}${path}`, {
    ...options, credentials: "include",
    headers: { ...(access ? { Authorization: `Bearer ${access}` } : {}), ...options.headers },
  });
  let response = await send(await currentAccess());
  if (response.status === 401) {
    accessToken = null;
    const renewed = await refreshAccessToken();
    if (renewed) response = await send(renewed);
  }
  return response;
}

export async function apiFetch<T>(path: string, options: RequestInit = {}, authenticated = false): Promise<T> {
  const jsonBody = options.body && !(typeof FormData !== "undefined" && options.body instanceof FormData);
  const init: RequestInit = { ...options, headers: { ...(jsonBody ? { "Content-Type": "application/json" } : {}), ...options.headers } };
  const response = authenticated
    ? await authorizedFetch(path, init)
    : await fetch(`${API_BASE_URL}${path}`, { ...init, credentials: "include" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const err = new Error(body?.error?.message ?? "We could not complete that request. Please try again.") as ApiError;
    err.status = response.status;
    err.code = body?.error?.code;
    throw err;
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function signOut() {
  if (typeof window === "undefined") return;
  // The server blacklists the refresh token from the cookie and clears it; works even if the access token expired.
  await fetch(`${API_BASE_URL}/auth/logout/`, { method: "POST", credentials: "include" }).catch(() => undefined);
  clearSession();
  window.location.assign("/");
}

/** Download an authenticated file (e.g. an admin CSV export) without putting the token in a URL. */
export async function downloadFile(path: string, filename: string) {
  const response = await authorizedFetch(path);
  if (!response.ok) throw new Error("The export could not be downloaded.");
  const url = URL.createObjectURL(await response.blob());
  const link = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
