"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[]; totals?: Record<string, { count: number; amount: number }> };

/** Page-numbered admin list with filters held in state. */
export function useAdminList<T>(path: string, initialFilters: Record<string, string> = {}) {
  const [filters, setFilters] = useState(initialFilters);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<T> | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const query = new URLSearchParams({ ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)), page: String(page) });
    try { setData(await apiFetch<Page<T>>(`${path}?${query}`, {}, true)); setError(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not load."); }
  }, [path, filters, page]);

  useEffect(() => { void load(); }, [load]);
  return { data, error, filters, page, setPage, reload: load, setFilter: (key: string, value: string) => { setPage(1); setFilters((f) => ({ ...f, [key]: value })); } };
}

export function Pager({ page, data, setPage }: { page: number; data: Page<unknown> | null; setPage: (n: number) => void }) {
  if (!data || (!data.next && !data.previous)) return null;
  return <div className="pager">
    <button className="button-secondary button-small" disabled={!data.previous} onClick={() => setPage(page - 1)}>Previous</button>
    <span className="muted small">Page {page} · {data.count} total</span>
    <button className="button-secondary button-small" disabled={!data.next} onClick={() => setPage(page + 1)}>Next</button>
  </div>;
}
