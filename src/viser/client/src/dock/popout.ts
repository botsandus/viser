// Pop-out group identity (Dexory fork) -- pure logic, kept out of
// TabGroupFrame.tsx so it is testable without the vite CSS pipeline (the same
// reason layoutOps and friends are plain .ts modules).

import { PaneSpec } from "./types";

/** The group's pop-out identity: defined iff the group is non-empty and every
 * pane in it belongs to the SAME keyed standalone panel (`popoutKey` on the
 * specs). After a user re-mixes tabs across panels the group loses one honest
 * identity and the affordance disappears with it. */
export function groupPopoutKey(
  paneIds: readonly string[],
  panes: Record<string, PaneSpec | undefined>,
): string | undefined {
  if (paneIds.length === 0) return undefined;
  const first = panes[paneIds[0]]?.popoutKey;
  if (first === undefined) return undefined;
  return paneIds.every((p) => panes[p]?.popoutKey === first)
    ? first
    : undefined;
}

/** Builds the same-origin pop-out URL for a panel key: the given page
 * location with the search replaced by `?panel=<key>` (other params
 * deliberately dropped -- a pop-out is a fresh, minimal client). Location is
 * a parameter so this stays a pure, node-testable function. */
export function popoutUrl(
  key: string,
  location: { origin: string; pathname: string },
): string {
  return `${location.origin}${location.pathname}?panel=${encodeURIComponent(key)}`;
}
