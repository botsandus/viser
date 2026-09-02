import { describe, expect, it } from "vitest";
import { connectionBadgeVisual } from "./connectionBadge";

describe("connectionBadgeVisual", () => {
  it("connected -> green", () => {
    expect(connectionBadgeVisual("connected")).toEqual({
      color: "green",
      label: "Connected",
    });
  });

  it("reconnecting -> yellow (amber)", () => {
    expect(connectionBadgeVisual("reconnecting")).toEqual({
      color: "yellow",
      label: "Reconnecting…",
    });
  });

  it("inactive -> gray", () => {
    expect(connectionBadgeVisual("inactive")).toEqual({
      color: "gray",
      label: "Inactive",
    });
  });

  it("the three states map to three distinct colors", () => {
    const colors = new Set(
      (["connected", "reconnecting", "inactive"] as const).map(
        (s) => connectionBadgeVisual(s).color,
      ),
    );
    expect(colors.size).toBe(3);
  });
});
