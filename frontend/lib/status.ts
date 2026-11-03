import type { ViewingRequest } from "./types";

export type Tone = "pending" | "approved" | "rejected" | "cancelled" | "completed" | "neutral";
export type Stage = { label: string; tone: Tone; next: string };

const DONE = ["completed", "outcome_pending", "rented", "did_not_rent", "still_deciding", "disputed", "no_show"];

/** One plain-language stage for a viewing request, so both sides always know where they are and what happens next. */
export function requestStage(item: Pick<ViewingRequest, "status" | "viewing" | "cancelled_by" | "my_role">): Stage {
  const { status, viewing } = item;
  const landlord = item.my_role === "landlord";
  if (status === "pending_landlord") {
    return landlord
      ? { label: "Needs your reply", tone: "pending", next: "Approve with a time or decline. Requests expire after 7 days without a reply." }
      : { label: "Waiting for landlord", tone: "pending", next: "The landlord will approve with a time or decline. Your credit is set aside and comes back if they decline or don't reply within 7 days." };
  }
  if (status === "rejected") return { label: "Declined", tone: "rejected", next: landlord ? "You declined this request." : "The landlord declined and your viewing credit was returned." };
  if (status === "expired") return { label: "Expired", tone: "cancelled", next: landlord ? "This request expired without a reply." : "The landlord did not reply in time. Your credit was returned." };
  if (status === "cancelled") {
    const by = item.cancelled_by;
    const text = by === "tenant" ? (landlord ? "The tenant cancelled." : "You cancelled this request.")
      : by === "landlord" ? (landlord ? "You cancelled this viewing. The tenant's credit was returned." : "The landlord cancelled. Your credit was returned.")
      : "Cancelled because the home is no longer available. Any reserved credit was returned.";
    return { label: "Cancelled", tone: "cancelled", next: text };
  }
  if (status === "approved" && viewing) {
    if (viewing.status === "scheduled") return { label: "Viewing booked", tone: "approved", next: landlord ? "Meet the tenant at the agreed time. Mark it done afterwards." : "The address and landlord contact are below. Arrive on time, or cancel here if plans change." };
    if (viewing.status === "rented") return { label: "Rented", tone: "completed", next: "This viewing led to a tenancy." };
    if (viewing.status === "disputed") return { label: "Under review", tone: "neutral", next: "The two reports differ, so our team will review and contact both sides." };
    if (viewing.status === "did_not_rent") return { label: "Not rented", tone: "completed", next: "Both sides reported that this viewing did not lead to a tenancy." };
    if (DONE.includes(viewing.status)) return { label: "Report outcome", tone: "pending", next: "Tell us how the viewing went so both sides have an accurate record." };
  }
  return { label: status.replaceAll("_", " "), tone: "neutral", next: "" };
}

export const ACTIVE = ["pending_landlord", "approved"];

/** A viewing whose time has passed and needs an outcome from me. */
export function outcomeDue(item: ViewingRequest) {
  const v = item.viewing;
  if (!v || item.status !== "approved") return false;
  const past = new Date(v.scheduled_at).getTime() <= Date.now();
  return (v.status === "scheduled" && past) || ((v.status === "outcome_pending" || v.status === "still_deciding") && item.my_outcome !== "rented" && item.my_outcome !== "did_not_rent");
}
