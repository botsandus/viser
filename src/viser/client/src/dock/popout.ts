// Pop-out and close group identity (Dexory fork / AMRI fork) -- pure logic,
// kept out of TabGroupFrame.tsx so it is testable without the vite CSS
// pipeline (the same reason layoutOps and friends are plain .ts modules).

import { PaneSpec } from "./types";

/** A group-wide identity is defined iff the group is non-empty and every
 * pane in it shares the SAME defined value of one PaneSpec field. After a
 * user re-mixes tabs across panels (or panels of different identity), the
 * group loses one honest identity and whatever affordance keyed on it
 * disappears with it -- the shared shape behind `groupPopoutKey` and
 * `groupCloseTarget` below. */
function groupSharedIdentity(
  paneIds: readonly string[],
  panes: Record<string, PaneSpec | undefined>,
  field: "popoutKey" | "closeTarget",
): string | undefined {
  if (paneIds.length === 0) return undefined;
  const first = panes[paneIds[0]]?.[field];
  if (first === undefined) return undefined;
  return paneIds.every((p) => panes[p]?.[field] === first) ? first : undefined;
}

/** The group's pop-out identity: defined iff the group is non-empty and every
 * pane in it belongs to the SAME keyed standalone panel (`popoutKey` on the
 * specs). After a user re-mixes tabs across panels the group loses one honest
 * identity and the affordance disappears with it. */
export function groupPopoutKey(
  paneIds: readonly string[],
  panes: Record<string, PaneSpec | undefined>,
): string | undefined {
  return groupSharedIdentity(paneIds, panes, "popoutKey");
}

/** The group's close identity (AMRI fork): defined iff the group is
 * non-empty and every pane in it belongs to the SAME closable standalone
 * panel (`closeTarget` on the specs -- that panel's own uuid). Mirrors
 * `groupPopoutKey`'s mixed-group fallback exactly: mix a closable panel's
 * tabs with another group's and the close affordance disappears rather than
 * closing a panel other than the one the click looked like it targeted. */
export function groupCloseTarget(
  paneIds: readonly string[],
  panes: Record<string, PaneSpec | undefined>,
): string | undefined {
  return groupSharedIdentity(paneIds, panes, "closeTarget");
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
