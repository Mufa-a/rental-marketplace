import { describe, expect, it } from "vitest";
import { listingPath } from "./listingPath";

describe("listingPath", () => {
  it("lowercases and joins city, area and slug", () => {
    expect(listingPath("Nairobi", "Westlands", "studio-a1")).toBe("/listings/nairobi/westlands/studio-a1");
  });

  it("turns spaces into dashes instead of %20, so every caller produces the same URL", () => {
    expect(listingPath("Nairobi", "Kilimani West", "x")).toBe("/listings/nairobi/kilimani-west/x");
    expect(listingPath(" Nairobi ", "Kilimani   West", "x")).toBe("/listings/nairobi/kilimani-west/x");
  });

  it("escapes characters that are not URL-safe", () => {
    expect(listingPath("Nairobi", "Parklands/Highridge", "x")).toBe("/listings/nairobi/parklands%2Fhighridge/x");
    expect(listingPath("Nairobi", "Westlands", "a b?c")).toBe("/listings/nairobi/westlands/a%20b%3Fc");
  });
});
