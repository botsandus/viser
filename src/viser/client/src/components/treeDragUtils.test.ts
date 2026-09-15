import { describe, it, expect } from "vitest";
import { dropPositionFromPointerY, isSelfOrDescendant } from "./treeDragUtils";

describe("dropPositionFromPointerY", () => {
  it("reads the top quarter as before", () => {
    expect(dropPositionFromPointerY(0, 100)).toBe("before");
    expect(dropPositionFromPointerY(10, 100)).toBe("before");
    expect(dropPositionFromPointerY(25, 100)).toBe("before");
  });

  it("reads the bottom quarter as after", () => {
    expect(dropPositionFromPointerY(75, 100)).toBe("after");
    expect(dropPositionFromPointerY(90, 100)).toBe("after");
    expect(dropPositionFromPointerY(100, 100)).toBe("after");
  });

  it("reads the middle half as into", () => {
    expect(dropPositionFromPointerY(26, 100)).toBe("into");
    expect(dropPositionFromPointerY(50, 100)).toBe("into");
    expect(dropPositionFromPointerY(74, 100)).toBe("into");
  });

  it("scales with row height rather than assuming pixels", () => {
    expect(dropPositionFromPointerY(5, 20)).toBe("before"); // 25%
    expect(dropPositionFromPointerY(15, 20)).toBe("after"); // 75%
    expect(dropPositionFromPointerY(10, 20)).toBe("into"); // 50%
  });

  it("falls back to into for a not-yet-laid-out row", () => {
    expect(dropPositionFromPointerY(10, 0)).toBe("into");
    expect(dropPositionFromPointerY(10, -5)).toBe("into");
  });
});

describe("isSelfOrDescendant", () => {
  const rows = [
    { id: "root", parent_id: null },
    { id: "child", parent_id: "root" },
    { id: "grandchild", parent_id: "child" },
    { id: "sibling", parent_id: "root" },
    { id: "orphan", parent_id: "does-not-exist" },
  ];

  it("is true for the row itself", () => {
    expect(isSelfOrDescendant(rows, "child", "child")).toBe(true);
  });

  it("is true for a direct child", () => {
    expect(isSelfOrDescendant(rows, "root", "child")).toBe(true);
  });

  it("is true for a deeper descendant", () => {
    expect(isSelfOrDescendant(rows, "root", "grandchild")).toBe(true);
  });

  it("is false for an unrelated row", () => {
    expect(isSelfOrDescendant(rows, "child", "sibling")).toBe(false);
  });

  it("is false for a row's own ancestor (wrong direction)", () => {
    expect(isSelfOrDescendant(rows, "grandchild", "root")).toBe(false);
  });

  it("does not loop forever on a dangling parent_id chain", () => {
    expect(isSelfOrDescendant(rows, "root", "orphan")).toBe(false);
  });
});
