import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, type ApiError } from "./api";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  localStorage.clear();
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => { vi.unstubAllGlobals(); });

describe("apiFetch", () => {
  it("sends the bearer token only for authenticated calls", async () => {
    localStorage.setItem("rental_access", "tok");
    fetchMock.mockImplementation(() => Promise.resolve(json({ ok: true })));
    await apiFetch("/public/");
    await apiFetch("/private/", {}, true);
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBeUndefined();
    expect(fetchMock.mock.calls[1][1].headers.Authorization).toBe("Bearer tok");
  });

  it("refreshes an expired access token once and retries the request", async () => {
    localStorage.setItem("rental_access", "old");
    localStorage.setItem("rental_refresh", "refresh-1");
    fetchMock
      .mockResolvedValueOnce(json({ error: { code: "token_not_valid", message: "expired" } }, 401))
      .mockResolvedValueOnce(json({ access: "new", refresh: "refresh-2" }))
      .mockResolvedValueOnce(json({ hello: "world" }));
    const result = await apiFetch<{ hello: string }>("/me/", {}, true);
    expect(result).toEqual({ hello: "world" });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[2][1].headers.Authorization).toBe("Bearer new");
    expect(localStorage.getItem("rental_access")).toBe("new");
    expect(localStorage.getItem("rental_refresh")).toBe("refresh-2");
  });

  it("clears the saved session and surfaces the error when the refresh token is rejected", async () => {
    localStorage.setItem("rental_access", "old");
    localStorage.setItem("rental_refresh", "dead");
    localStorage.setItem("rental_user", "{}");
    fetchMock
      .mockResolvedValueOnce(json({ error: { message: "expired" } }, 401))
      .mockResolvedValueOnce(json({}, 401));
    await expect(apiFetch("/me/", {}, true)).rejects.toMatchObject({ status: 401 });
    expect(localStorage.getItem("rental_access")).toBeNull();
    expect(localStorage.getItem("rental_refresh")).toBeNull();
    expect(localStorage.getItem("rental_user")).toBeNull();
  });

  it("does not try to refresh for unauthenticated calls", async () => {
    localStorage.setItem("rental_refresh", "r");
    fetchMock.mockResolvedValue(json({ error: { message: "nope" } }, 401));
    await expect(apiFetch("/public/")).rejects.toThrow("nope");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("raises an error carrying the API's message, code and status", async () => {
    fetchMock.mockResolvedValue(json({ error: { code: "bundle_payment_pending", message: "Wait for your prompt." } }, 409));
    const error = (await apiFetch("/pay/", {}, false).catch((e: ApiError) => e)) as ApiError;
    expect(error.message).toBe("Wait for your prompt.");
    expect(error.code).toBe("bundle_payment_pending");
    expect(error.status).toBe(409);
  });

  it("falls back to a friendly message when the error body is not JSON", async () => {
    fetchMock.mockResolvedValue(new Response("<html>502</html>", { status: 502 }));
    await expect(apiFetch("/x/")).rejects.toThrow(/could not complete that request/i);
  });

  it("returns undefined for 204 responses", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await expect(apiFetch("/gone/", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("sets a JSON content type when a body is sent", async () => {
    fetchMock.mockResolvedValue(json({}));
    await apiFetch("/x/", { method: "POST", body: JSON.stringify({ a: 1 }) });
    expect(fetchMock.mock.calls[0][1].headers["Content-Type"]).toBe("application/json");
  });
});
