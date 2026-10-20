import { apiFetch } from "@/lib/api";
import { stripImageMetadata } from "@/lib/images";

/** Keep these in step with the backend limits (MEDIA_MAX_* settings, backend/apps/properties/media.py). */
export const MAX_PHOTOS = 20;
export const MAX_PHOTO_BYTES = 10 * 1024 * 1024;
export const MAX_VIDEO_BYTES = 100 * 1024 * 1024;
export const PHOTO_ACCEPT = "image/jpeg,image/png,image/webp";
export const VIDEO_ACCEPT = "video/mp4,video/webm,video/quicktime,.mp4,.m4v,.webm,.mov";

const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];
const VIDEO_BY_EXTENSION: Record<string, string> = { mp4: "video/mp4", m4v: "video/mp4", webm: "video/webm", mov: "video/quicktime" };

export type MediaKind = "photo" | "video";
export type MediaItem = { id: number; url: string; kind: "image" | "video"; alt_text: string; media_type: string };
type UploadTicket = { asset_key: string; upload: { url: string; method: string; headers: Record<string, string> } };

/** Some browsers leave `type` empty for .mov/.mp4 files, so fall back to the extension. */
export function videoContentType(file: File): string {
  if (file.type) return file.type === "video/x-m4v" ? "video/mp4" : file.type;
  return VIDEO_BY_EXTENSION[file.name.split(".").pop()?.toLowerCase() ?? ""] ?? "";
}

export function megabytes(bytes: number): number {
  return Math.round(bytes / (1024 * 1024));
}

/** A plain-language reason the file cannot be used, or null when it is fine to upload. */
export function validateMediaFile(file: File, kind: MediaKind): string | null {
  if (kind === "photo") {
    if (!PHOTO_TYPES.includes(file.type)) return `${file.name}: photos must be JPEG, PNG or WebP files.`;
    if (file.size > MAX_PHOTO_BYTES) return `${file.name}: photos must be under ${megabytes(MAX_PHOTO_BYTES)} MB.`;
    return null;
  }
  if (!Object.values(VIDEO_BY_EXTENSION).includes(videoContentType(file))) return `${file.name}: the video must be an MP4, WebM or MOV file.`;
  if (file.size > MAX_VIDEO_BYTES) return `${file.name}: the video must be under ${megabytes(MAX_VIDEO_BYTES)} MB (${megabytes(file.size)} MB selected). Trim it or record at a lower quality.`;
  return null;
}

/** First problem with a batch of photos given how many the home already has, or null. */
export function validatePhotoBatch(files: File[], existing: number): string | null {
  if (existing + files.length > MAX_PHOTOS) {
    const room = Math.max(MAX_PHOTOS - existing, 0);
    return room === 0 ? `This home already has ${MAX_PHOTOS} photos. Remove one to add another.` : `You can add ${room} more ${room === 1 ? "photo" : "photos"} (up to ${MAX_PHOTOS} per home).`;
  }
  for (const file of files) { const problem = validateMediaFile(file, "photo"); if (problem) return problem; }
  return null;
}

/** PUT with progress; fetch cannot report upload progress and videos are slow on mobile data. */
function putFile(url: string, file: Blob, headers: Record<string, string>, onProgress?: (fraction: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("PUT", url);
    Object.entries(headers).forEach(([name, value]) => request.setRequestHeader(name, value));
    request.upload.onprogress = event => { if (event.lengthComputable && onProgress) onProgress(event.loaded / event.total); };
    request.onload = () => request.status >= 200 && request.status < 300 ? resolve() : reject(new Error("The upload was rejected. Check your connection and try again."));
    request.onerror = () => reject(new Error("The upload failed. Check your connection and try again."));
    request.onabort = () => reject(new Error("The upload was cancelled."));
    request.send(file);
  });
}

/**
 * Upload one photo or the video straight to storage, then register it with the listing.
 * Photos are re-encoded first so EXIF/GPS never leaves the device. Videos cannot be cleaned in the
 * browser, so landlords are warned about location data in the UI.
 */
export async function uploadUnitMedia(unitId: number, file: File, kind: MediaKind, options: { title: string; onProgress?: (fraction: number) => void }): Promise<MediaItem> {
  const problem = validateMediaFile(file, kind);
  if (problem) throw new Error(problem);
  const upload = kind === "photo" ? await stripImageMetadata(file) : file;
  const contentType = kind === "photo" ? upload.type : videoContentType(file);
  const ticket = await apiFetch<UploadTicket>(`/properties/units/${unitId}/media/presign/`, {
    method: "POST", body: JSON.stringify({ filename: upload.name, content_type: contentType, size: upload.size }),
  }, true);
  await putFile(ticket.upload.url, upload, ticket.upload.headers, options.onProgress);
  return apiFetch<MediaItem>(`/properties/units/${unitId}/media/`, {
    method: "POST",
    body: JSON.stringify({ asset_key: ticket.asset_key, alt_text: `${options.title}: ${file.name}`.slice(0, 180), media_type: kind === "video" ? "video" : "other" }),
  }, true);
}

export async function removeUnitMedia(mediaId: number): Promise<void> {
  await apiFetch(`/properties/media/${mediaId}/`, { method: "DELETE" }, true);
}
