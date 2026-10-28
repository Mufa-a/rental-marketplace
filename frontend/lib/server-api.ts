import "server-only";

/** Server-side API base. Inside Docker/private networks set API_INTERNAL_URL to skip the public round trip. */
export const SERVER_API = (process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1").replace(/\/$/, "");

export async function serverGet<T>(path: string, revalidate = 60): Promise<T | null> {
  try {
    const response = await fetch(`${SERVER_API}${path}`, { next: { revalidate }, headers: { Accept: "application/json" } });
    return response.ok ? ((await response.json()) as T) : null;
  } catch {
    return null;
  }
}
