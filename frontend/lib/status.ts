export type Tone = "pending" | "approved" | "rejected" | "cancelled" | "completed" | "neutral";
export type Stage = { label: string; tone: Tone; next: string };
type ViewingLite = { status: string; scheduled_at: string } | null | undefined;

const DONE = ["completed", "outcome_pending", "rented", "did_not_rent", "still_deciding", "disputed", "no_show"];

/** One plain-language stage for a viewing request, so tenants always know where they are and what happens next. */
export function requestStage(status: string, viewing?: ViewingLite): Stage {
  if (status === "pending_landlord") {
    return { label: "Pending", tone: "pending", next: "Waiting for the landlord to approve or decline. We will text you when they reply. Your viewing credit is set aside and returns to you if the request is declined." };
  }
  if (status === "rejected") return { label: "Rejected", tone: "rejected", next: "The landlord declined this request and your viewing credit was returned. Browse other homes in the area." };
  if (status === "cancelled") return { label: "Cancelled", tone: "cancelled", next: "This request was cancelled." };
  if (status === "expired") return { label: "Expired", tone: "cancelled", next: "The landlord did not reply in time and your viewing credit was returned." };
  if (status === "approved") {
    if (viewing && DONE.includes(viewing.status)) {
      if (viewing.status === "outcome_pending") return { label: "Completed", tone: "completed", next: "Please tell us how the viewing went so both sides have an accurate record." };
      if (viewing.status === "rented") return { label: "Completed", tone: "completed", next: "A rental was confirmed for this home." };
      if (viewing.status === "disputed") return { label: "Completed", tone: "completed", next: "You and the landlord reported different outcomes, so our team may review it." };
      return { label: "Completed", tone: "completed", next: "This viewing is done. Thank you for reporting the outcome." };
    }
    if (viewing?.status === "cancelled") return { label: "Cancelled", tone: "cancelled", next: "This viewing was cancelled." };
    return { label: "Approved", tone: "approved", next: "Your viewing is scheduled. Arrive on time, or cancel here if your plans change." };
  }
  return { label: status.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase()), tone: "neutral", next: "" };
}
