import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MAX_PHOTOS, MAX_VIDEO_BYTES, uploadUnitMedia, validateMediaFile, validatePhotoBatch, videoContentType } from "./mediaUpload";

vi.mock("@/lib/images", () => ({ stripImageMetadata: vi.fn(async (file: File) => new File(["clean"], file.name, { type: file.type })) }));

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const file = (name: string, type: string, size = 10) => { const f = new File(["x"], name, { type }); Object.defineProperty(f, "size", { value: size }); return f; };

describe("validateMediaFile", () => {
  it("accepts supported photos and videos", () => {
    expect(validateMediaFile(file("a.jpg", "image/jpeg"), "photo")).toBeNull();
    expect(validateMediaFile(file("tour.mp4", "video/mp4"), "video")).toBeNull();
    expect(validateMediaFile(file("tour.webm", "video/webm"), "video")).toBeNull();
  });
  it("accepts a .mov whose browser reported no type", () => {
    expect(videoContentType(file("tour.MOV", ""))).toBe("video/quicktime");
    expect(validateMediaFile(file("tour.MOV", ""), "video")).toBeNull();
  });
  it("rejects other types and wrong kinds", () => {
    expect(validateMediaFile(file("a.gif", "image/gif"), "photo")).toMatch(/JPEG, PNG or WebP/);
    expect(validateMediaFile(file("tour.mp4", "video/mp4"), "photo")).not.toBeNull();
    expect(validateMediaFile(file("a.jpg", "image/jpeg"), "video")).toMatch(/MP4, WebM or MOV/);
    expect(validateMediaFile(file("tour.avi", "video/x-msvideo"), "video")).not.toBeNull();
  });
  it("rejects oversize files and says how big the video was", () => {
    expect(validateMediaFile(file("a.jpg", "image/jpeg", 11 * 1024 * 1024), "photo")).toMatch(/under 10 MB/);
    expect(validateMediaFile(file("tour.mp4", "video/mp4", MAX_VIDEO_BYTES + 1), "video")).toMatch(/under 100 MB \(100 MB selected\)/);
  });
});

describe("validatePhotoBatch", () => {
  const photos = (n: number) => Array.from({ length: n }, (_, i) => file(`p${i}.jpg`, "image/jpeg"));
  it("allows up to the limit counting photos already on the home", () => {
    expect(validatePhotoBatch(photos(MAX_PHOTOS), 0)).toBeNull();
    expect(validatePhotoBatch(photos(2), MAX_PHOTOS - 2)).toBeNull();
  });
  it("says how many more can be added, or that the home is full", () => {
    expect(validatePhotoBatch(photos(3), MAX_PHOTOS - 1)).toBe("You can add 1 more photo (up to 20 per home).");
    expect(validatePhotoBatch(photos(1), MAX_PHOTOS)).toMatch(/already has 20 photos/);
  });
  it("reports the first invalid file", () => {
    expect(validatePhotoBatch([file("a.jpg", "image/jpeg"), file("b.gif", "image/gif")], 0)).toMatch(/b\.gif/);
  });
});

describe("uploadUnitMedia", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let sent: { method: string; url: string; headers: Record<string, string>; body: unknown }[];
  let putStatus: number;

  beforeEach(() => {
    localStorage.setItem("rental_access", "tok");
    sent = []; putStatus = 200;
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    class FakeXhr {
      status = 0; headers: Record<string, string> = {}; method = ""; url = "";
      upload: { onprogress?: (e: { lengthComputable: boolean; loaded: number; total: number }) => void } = {};
      onload?: () => void; onerror?: () => void; onabort?: () => void;
      open(method: string, url: string) { this.method = method; this.url = url; }
      setRequestHeader(name: string, value: string) { this.headers[name] = value; }
      send(body: unknown) { sent.push({ method: this.method, url: this.url, headers: this.headers, body }); this.upload.onprogress?.({ lengthComputable: true, loaded: 1, total: 2 }); this.status = putStatus; this.onload?.(); }
    }
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
  });
  afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); });

  const ticket = { asset_key: "properties/7/abc.mp4", upload: { url: "https://r2.example/put", method: "PUT", headers: { "Content-Type": "video/mp4" } } };

  it("presigns, PUTs the file with the signed headers, then registers it as the video", async () => {
    fetchMock.mockImplementation((url: string) => Promise.resolve(url.endsWith("/presign/") ? json(ticket) : json({ id: 1, url: "https://cdn/x.mp4", kind: "video" }, 201)));
    const progress = vi.fn();
    const result = await uploadUnitMedia(7, file("tour.mp4", "video/mp4", 5000), "video", { title: "Studio", onProgress: progress });
    expect(result.kind).toBe("video");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ filename: "tour.mp4", content_type: "video/mp4", size: 5000 });
    expect(sent).toHaveLength(1);
    expect(sent[0]).toMatchObject({ method: "PUT", url: "https://r2.example/put", headers: { "Content-Type": "video/mp4" } });
    expect(progress).toHaveBeenCalledWith(0.5);
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({ asset_key: "properties/7/abc.mp4", media_type: "video" });
  });

  it("re-encodes photos before upload so GPS data is not sent", async () => {
    const { stripImageMetadata } = await import("@/lib/images");
    fetchMock.mockImplementation((url: string) => Promise.resolve(url.endsWith("/presign/") ? json({ ...ticket, asset_key: "properties/7/p.jpg" }) : json({ id: 2, kind: "image" }, 201)));
    const original = file("room.jpg", "image/jpeg");
    await uploadUnitMedia(7, original, "photo", { title: "Studio" });
    expect(stripImageMetadata).toHaveBeenCalledWith(original);
    expect(sent[0].body).not.toBe(original);
    expect(JSON.parse(fetchMock.mock.calls[1][1].body).media_type).toBe("other");
  });

  it("does not register anything when the storage upload fails", async () => {
    putStatus = 403;
    fetchMock.mockImplementation(() => Promise.resolve(json(ticket)));
    await expect(uploadUnitMedia(7, file("tour.mp4", "video/mp4"), "video", { title: "Studio" })).rejects.toThrow(/rejected/);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("refuses an invalid file without calling the API", async () => {
    await expect(uploadUnitMedia(7, file("tour.mp4", "video/mp4", MAX_VIDEO_BYTES + 1), "video", { title: "Studio" })).rejects.toThrow(/under 100 MB/);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
