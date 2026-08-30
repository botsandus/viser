// Contract tests for the pop-out group-identity resolution (Dexory fork):
// the tab strip offers "open in a new window" exactly when every pane in the
// group belongs to ONE keyed standalone panel. See TabGroupFrame.tsx.

import { describe, expect, it } from "vitest";
import { groupPopoutKey, popoutUrl } from "./popout";
import { PaneSpec } from "./types";

function spec(id: string, popoutKey?: string): PaneSpec {
  return { id, title: id, render: () => null, popoutKey };
}

describe("groupPopoutKey", () => {
  it("resolves when every pane shares one defined key", () => {
    const panes = { a: spec("a", "k"), b: spec("b", "k") };
    expect(groupPopoutKey(["a", "b"], panes)).toBe("k");
  });

  it("is undefined for an empty group", () => {
    expect(groupPopoutKey([], {})).toBeUndefined();
  });

  it("is undefined when any pane is keyless", () => {
    const panes = { a: spec("a", "k"), b: spec("b") };
    expect(groupPopoutKey(["a", "b"], panes)).toBeUndefined();
    expect(groupPopoutKey(["b", "a"], panes)).toBeUndefined();
  });

  it("is undefined when keys differ (a user re-mixed tabs across panels)", () => {
    const panes = { a: spec("a", "k1"), b: spec("b", "k2") };
    expect(groupPopoutKey(["a", "b"], panes)).toBeUndefined();
  });

  it("is undefined for a pane missing from the registry", () => {
    const panes = { a: spec("a", "k") };
    expect(groupPopoutKey(["a", "ghost"], panes)).toBeUndefined();
  });
});

describe("popoutUrl", () => {
  it("keeps the origin+path and replaces the search with the encoded key", () => {
    const location = { origin: "http://cell:8080", pathname: "/" };
    expect(popoutUrl("demo", location)).toBe("http://cell:8080/?panel=demo");
    expect(popoutUrl("a b/c", location)).toContain("?panel=a%20b%2Fc");
  });
});
