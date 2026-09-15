import { describe, it, expect } from "vitest";
import { finiteNumberOrNull, snapToStepAndClamp } from "./numberInputUtils";

describe("finiteNumberOrNull", () => {
  it("passes through finite numbers", () => {
    expect(finiteNumberOrNull(0)).toBe(0);
    expect(finiteNumberOrNull(-5)).toBe(-5);
    expect(finiteNumberOrNull(1.5)).toBe(1.5);
  });

  it("parses finite numeric strings", () => {
    expect(finiteNumberOrNull("42")).toBe(42);
    expect(finiteNumberOrNull("-3.5")).toBe(-3.5);
    expect(finiteNumberOrNull("1e3")).toBe(1000);
  });

  it("returns null for empty input", () => {
    expect(finiteNumberOrNull("")).toBeNull();
  });

  it("returns null for partial / invalid input Mantine emits while typing", () => {
    // These are the intermediate strings that previously leaked NaN / raw
    // strings to the server.
    for (const v of ["-", ".", "1e", "1.2.3", "abc", "-."]) {
      expect(finiteNumberOrNull(v), v).toBeNull();
    }
  });

  it("commits valid intermediate values that JS parses to a number", () => {
    // e.g. "1." parses to 1 -- a real number, so it's committed (unchanged
    // from the prior Number() behavior; the fix only blocks NaN/strings).
    expect(finiteNumberOrNull("1.")).toBe(1);
  });

  it("returns null for non-finite numbers", () => {
    expect(finiteNumberOrNull(NaN)).toBeNull();
    expect(finiteNumberOrNull(Infinity)).toBeNull();
    expect(finiteNumberOrNull(-Infinity)).toBeNull();
  });
});

describe("snapToStepAndClamp", () => {
  it("snaps onto the min + k*step grid", () => {
    expect(snapToStepAndClamp(2.6, 0, 10, 1)).toBe(3);
    expect(snapToStepAndClamp(2.4, 0, 10, 1)).toBe(2);
    // Grid is offset by min, not zero.
    expect(snapToStepAndClamp(3.6, 0.5, 9.5, 1)).toBe(3.5);
  });

  it("clamps to max even when step doesn't evenly divide the range", () => {
    // min=0, max=10, step=6 -> grid is {0, 6, 12, ...}; naive rounding of 10
    // lands on 12, which must be pulled back to max.
    expect(snapToStepAndClamp(10, 0, 10, 6)).toBe(10);
  });

  it("clamps to min", () => {
    expect(snapToStepAndClamp(-5, 0, 10, 1)).toBe(0);
  });

  it("clamps above max before snapping", () => {
    expect(snapToStepAndClamp(50, 0, 10, 3)).toBe(10);
  });

  it("passes through unsnapped when step is degenerate (<= 0)", () => {
    expect(snapToStepAndClamp(3.14159, 0, 10, 0)).toBe(3.14159);
    expect(snapToStepAndClamp(3.14159, 0, 10, -1)).toBe(3.14159);
  });

  it("is inert on a degenerate min === max range", () => {
    expect(snapToStepAndClamp(5, 5, 5, 1)).toBe(5);
  });
});
