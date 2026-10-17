import { describe, expect, it } from "vitest";
import { requestStage } from "./status";

describe("requestStage", () => {
  it("tells a tenant with a pending request that the credit is held and returns on decline", () => {
    const stage = requestStage("pending_landlord");
    expect(stage.label).toBe("Pending");
    expect(stage.tone).toBe("pending");
    expect(stage.next).toMatch(/credit/i);
  });

  it.each([
    ["rejected", "Rejected", /returned/i],
    ["expired", "Expired", /returned/i],
    ["cancelled", "Cancelled", /cancelled/i],
  ])("describes a %s request", (status, label, next) => {
    const stage = requestStage(status);
    expect(stage.label).toBe(label);
    expect(stage.next).toMatch(next);
  });

  it("shows an approved request with no viewing outcome yet as approved", () => {
    expect(requestStage("approved", { status: "scheduled", scheduled_at: "2026-10-20T10:00:00Z" }).label).toBe("Approved");
  });

  it("asks for the outcome once the viewing is awaiting one", () => {
    const stage = requestStage("approved", { status: "outcome_pending", scheduled_at: "2026-10-01T10:00:00Z" });
    expect(stage.label).toBe("Completed");
    expect(stage.next).toMatch(/how the viewing went/i);
  });

  it("reports a confirmed rental and a dispute distinctly", () => {
    expect(requestStage("approved", { status: "rented", scheduled_at: "x" }).next).toMatch(/rental was confirmed/i);
    expect(requestStage("approved", { status: "disputed", scheduled_at: "x" }).next).toMatch(/different outcomes/i);
  });

  it("treats a cancelled viewing under an approved request as cancelled", () => {
    expect(requestStage("approved", { status: "cancelled", scheduled_at: "x" }).tone).toBe("cancelled");
  });

  it("falls back to a readable label for an unknown status", () => {
    const stage = requestStage("something_new");
    expect(stage.label).toBe("Something new");
    expect(stage.tone).toBe("neutral");
  });
});
