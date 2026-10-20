"use client";

import { ChangeEvent, useRef, useState } from "react";
import {
  MAX_PHOTOS, MAX_PHOTO_BYTES, MAX_VIDEO_BYTES, PHOTO_ACCEPT, VIDEO_ACCEPT, megabytes, removeUnitMedia, uploadUnitMedia,
  validateMediaFile, validatePhotoBatch, type MediaItem,
} from "@/lib/mediaUpload";

type Props = { unitId: number; title: string; photos: MediaItem[]; video: MediaItem | null; onChanged: () => Promise<void> | void };

/** Add and remove a home's photos and its single video. Each file uploads straight to storage. */
export default function UnitMediaManager({ unitId, title, photos, video, onChanged }: Props) {
  const photoInput = useRef<HTMLInputElement>(null);
  const videoInput = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [notice, setNotice] = useState<{ kind: "error" | "ok"; text: string } | null>(null);

  async function addPhotos(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length) return;
    const problem = validatePhotoBatch(files, photos.length);
    if (problem) { setNotice({ kind: "error", text: problem }); return; }
    setNotice(null);
    let failed = 0; let lastError = "";
    for (const [index, file] of files.entries()) {
      setBusy(`Uploading photo ${index + 1} of ${files.length}…`);
      try { await uploadUnitMedia(unitId, file, "photo", { title }); }
      catch (error) { failed += 1; lastError = error instanceof Error ? error.message : "Upload failed."; }
    }
    setBusy(null);
    const added = files.length - failed;
    setNotice(failed ? { kind: "error", text: `${added} added, ${failed} failed. ${lastError}` } : { kind: "ok", text: `${added} ${added === 1 ? "photo" : "photos"} added.` });
    await onChanged();
  }

  async function addVideo(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const problem = validateMediaFile(file, "video");
    if (problem) { setNotice({ kind: "error", text: problem }); return; }
    setNotice(null); setProgress(0); setBusy(`Uploading video (${megabytes(file.size) || "<1"} MB)…`);
    try {
      await uploadUnitMedia(unitId, file, "video", { title, onProgress: setProgress });
      setNotice({ kind: "ok", text: video ? "Video replaced." : "Video added." });
    } catch (error) { setNotice({ kind: "error", text: error instanceof Error ? error.message : "The video could not be uploaded." }); }
    setBusy(null); setProgress(null);
    await onChanged();
  }

  async function remove(item: MediaItem) {
    const what = item.kind === "video" ? "the video" : "this photo";
    if (!window.confirm(`Remove ${what} from the listing?`)) return;
    setBusy("Removing…"); setNotice(null);
    try { await removeUnitMedia(item.id); setNotice({ kind: "ok", text: `Removed ${what}.` }); }
    catch (error) { setNotice({ kind: "error", text: error instanceof Error ? error.message : "We could not remove that." }); }
    setBusy(null);
    await onChanged();
  }

  const full = photos.length >= MAX_PHOTOS;
  return (
    <section className="media-manager" aria-label={`Photos and video for ${title}`}>
      <h4>Photos &amp; video</h4>

      <div className="media-block">
        <div className="media-head"><strong>Photos</strong><span className="muted">{photos.length} of {MAX_PHOTOS}</span></div>
        {photos.length > 0 ? (
          <ul className="media-grid">
            {photos.map((photo, index) => (
              <li key={photo.id}>
                <img src={photo.url} alt={photo.alt_text || `Photo ${index + 1}`} loading="lazy" />
                {index === 0 && <span className="media-cover">Cover</span>}
                <button type="button" className="media-remove" disabled={!!busy} onClick={() => void remove(photo)} aria-label={`Remove photo ${index + 1}`}>×</button>
              </li>
            ))}
          </ul>
        ) : <p className="muted">No photos yet. Homes with photos get far more viewing requests.</p>}
        <input ref={photoInput} type="file" accept={PHOTO_ACCEPT} multiple hidden onChange={event => void addPhotos(event)} />
        <button type="button" className="button-secondary" disabled={!!busy || full} onClick={() => photoInput.current?.click()}>{full ? "Photo limit reached" : "Add photos"}</button>
        <p className="muted">JPEG, PNG or WebP, up to {megabytes(MAX_PHOTO_BYTES)} MB each. The first photo is the cover. Location data is removed from photos before upload.</p>
      </div>

      <div className="media-block">
        <div className="media-head"><strong>Video tour</strong><span className="muted">{video ? "1 of 1" : "optional"}</span></div>
        {video && (
          <div className="media-video">
            <video src={video.url} controls preload="metadata" playsInline aria-label={`Video tour of ${title}`} />
            <button type="button" className="button-danger" disabled={!!busy} onClick={() => void remove(video)}>Remove video</button>
          </div>
        )}
        <input ref={videoInput} type="file" accept={VIDEO_ACCEPT} hidden onChange={event => void addVideo(event)} />
        <button type="button" className="button-secondary" disabled={!!busy} onClick={() => videoInput.current?.click()}>{video ? "Replace video" : "Add video"}</button>
        <p className="muted">MP4, WebM or MOV, up to {megabytes(MAX_VIDEO_BYTES)} MB. MP4 (H.264) plays on every phone; some iPhone HEVC .mov files will not play in all browsers. <strong>Videos are not cleaned</strong>: switch off location tagging in your camera settings before recording, and avoid showing house numbers or documents.</p>
      </div>

      {busy && (
        <div role="status" className="media-status">
          <span>{busy}</span>
          {progress !== null && <progress value={progress} max={1} aria-label="Upload progress" />}
        </div>
      )}
      {notice && <p role={notice.kind === "error" ? "alert" : "status"} className={`media-notice media-notice-${notice.kind}`}>{notice.text}</p>}
    </section>
  );
}
