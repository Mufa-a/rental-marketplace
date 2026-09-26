const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export type ApiError = Error & { status?: number; code?: string };

function token(name: string) {
  return typeof window === "undefined" ? null : window.localStorage.getItem(name);
}

function clearSession() {
  localStorage.removeItem("rental_access");
  localStorage.removeItem("rental_refresh");
  localStorage.removeItem("rental_user");
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = token("rental_refresh");
  if (!refresh) return null;
  const response = await fetch(`${API_BASE_URL}/auth/token/refresh/`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh }),
  });
  if (!response.ok) { clearSession(); return null; }
  const body = await response.json();
  localStorage.setItem("rental_access", body.access);
  if (body.refresh) localStorage.setItem("rental_refresh", body.refresh);
  return body.access;
}

export async function apiFetch<T>(path: string, options: RequestInit = {}, authenticated = false): Promise<T> {
  const makeRequest = (access?: string | null) => fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body && !(typeof FormData !== "undefined" && options.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
      ...(authenticated && access ? { Authorization: `Bearer ${access}` } : {}),
      ...options.headers,
    },
  });

  let access = authenticated ? token("rental_access") : null;
  let response = await makeRequest(access);
  if (authenticated && response.status === 401) {
    access = await refreshAccessToken();
    if (access) response = await makeRequest(access);
  }
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
  if (token("rental_refresh")) {
    const access = await refreshAccessToken();
    const refresh = token("rental_refresh");
    if (access && refresh) {
      await apiFetch("/auth/logout/", { method: "POST", body: JSON.stringify({ refresh }) }, true).catch(() => undefined);
    }
  }
  clearSession();
  window.location.assign("/");
}
