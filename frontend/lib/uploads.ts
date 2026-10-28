import { apiFetch } from "./api";
import { stripImageMetadata } from "./images";

type UploadTicket = { asset_key: string; upload: { url: string; headers: Record<string, string> } };

export const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const MAX_PHOTO_BYTES = 10 * 1024 * 1024;

export function photoProblem(files: File[], limit = 8) {
  if (files.length > limit) return `Choose up to ${limit} photos at a time.`;
  if (files.some((f) => !PHOTO_TYPES.includes(f.type) || f.size > MAX_PHOTO_BYTES)) return "Photos must be JPEG, PNG or WebP, under 10 MB each.";
  return null;
}

/** Strip location metadata in the browser, upload straight to storage, then register with the API (which re-checks it). */
export async function uploadPhotos(unitId: number, title: string, files: File[], onProgress?: (done: number) => void) {
  let done = 0;
  for (const file of files) {
    const clean = await stripImageMetadata(file);
    const ticket = await apiFetch<UploadTicket>(`/properties/units/${unitId}/media/presign/`, { method: "POST", body: JSON.stringify({ filename: clean.name, content_type: clean.type }) }, true);
    const uploaded = await fetch(ticket.upload.url, { method: "PUT", headers: ticket.upload.headers, body: clean });
    if (!uploaded.ok) throw new Error("A photo could not be uploaded to storage. Try again.");
    await apiFetch(`/properties/units/${unitId}/media/`, { method: "POST", body: JSON.stringify({ asset_key: ticket.asset_key, alt_text: `${title} — photo ${done + 1}`, media_type: "other" }) }, true);
    onProgress?.(++done);
  }
}
