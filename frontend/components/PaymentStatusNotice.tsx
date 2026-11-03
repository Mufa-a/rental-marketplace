"use client";

import type { Payment } from "@/lib/types";
import { money } from "@/lib/format";

const TONE: Record<Payment["status"], string> = {
  pending: "notice-info", successful: "notice-success", failed: "notice-error", cancelled: "notice-error", refunded: "notice-info", disputed: "notice-warning",
};

export default function PaymentStatusNotice({ payment, onRefresh }: { payment: Payment; onRefresh?: () => void }) {
  return (
    <div className={`notice ${TONE[payment.status]}`} role="status" aria-live="polite">
      <strong>
        {payment.status === "pending" ? "Waiting for M-Pesa…" : payment.status === "successful" ? "Payment confirmed" : `Payment ${payment.status}`}
        {" · "}{money(payment.amount, payment.currency)}
      </strong>
      <p>{payment.message}</p>
      {payment.provider_receipt && <p className="muted">M-Pesa receipt {payment.provider_receipt}</p>}
      {payment.status === "pending" && onRefresh && <button type="button" className="button-secondary button-small" onClick={onRefresh}>Check again</button>}
    </div>
  );
}
