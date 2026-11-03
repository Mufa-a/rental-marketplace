"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "./api";
import type { Payment } from "./types";

/**
 * Follow a payment after the STK prompt is sent. The status always comes from the
 * server, which confirms it with M-Pesa; the browser never decides a payment succeeded.
 */
export function usePaymentStatus(onSettled?: (payment: Payment) => void) {
  const [payment, setPayment] = useState<Payment | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const settled = useRef(onSettled);
  settled.current = onSettled;

  const stop = useCallback(() => { if (timer.current) clearTimeout(timer.current); timer.current = null; }, []);

  const track = useCallback((initial: Payment) => {
    stop();
    setPayment(initial);
    const started = Date.now();
    const poll = async () => {
      try {
        const latest = await apiFetch<Payment>(`/payments/${initial.id}/`, {}, true);
        setPayment(latest);
        if (latest.status !== "pending") { settled.current?.(latest); return; }
      } catch { /* keep polling; a transient network error is not a payment result */ }
      // Poll every 4 s for 3 minutes, then hand over to the "check again" button.
      if (Date.now() - started < 180_000) timer.current = setTimeout(poll, 4000);
    };
    if (initial.status === "pending") timer.current = setTimeout(poll, 4000);
    else settled.current?.(initial);
  }, [stop]);

  const refresh = useCallback(async () => {
    if (!payment) return;
    const latest = await apiFetch<Payment>(`/payments/${payment.id}/`, {}, true);
    setPayment(latest);
    if (latest.status === "pending") track(latest); else settled.current?.(latest);
  }, [payment, track]);

  useEffect(() => stop, [stop]);
  return { payment, track, refresh, reset: () => { stop(); setPayment(null); } };
}

export const newIdempotencyKey = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
