/** Pure helpers for tree-row drag-and-drop, split out of `Tree.tsx` so the
 * Fast Refresh (HMR) module boundary only contains components -- React warns
 * when a component file also exports non-components (see `dragUtils.ts` for
 * the same rationale on the scene-node drag side). */

import { GuiTreeRowDropMessage } from "../WebsocketMessages";

/** Where a dragged row lands relative to the row it's dropped on. Pulled
 * back out of the generated message type (rather than duplicated as a
 * literal here) via indexed access, same convention as `TreeRowData`/
 * `TreeIconData` in `Tree.tsx`. */
export type TreeRowDropPosition = GuiTreeRowDropMessage["position"];

/** Classify a pointer's vertical position within a row into a drop
 * position: the top quarter is `"before"` (insert as a sibling above this
 * row), the bottom quarter is `"after"` (insert as a sibling below this
 * row), and the middle half is `"into"` (nest as this row's child) -- the
 * standard tree-view / file-manager drop affordance.
 *
 * `offsetY`/`rowHeight` are both in CSS pixels, `offsetY` measured from the
 * row's own top edge (i.e. `event.clientY - row.getBoundingClientRect().top`).
 * The quarter boundaries are inclusive on the "before"/"after" side (a
 * pointer sitting exactly on the boundary reads as sibling, not nest) so the
 * "into" zone is the open interval `(0.25, 0.75)` of the row's height. A
 * non-positive `rowHeight` (a row not yet laid out) can't be split into
 * quarters, so it falls back to `"into"`. */
export function dropPositionFromPointerY(
  offsetY: number,
  rowHeight: number,
): TreeRowDropPosition {
  if (rowHeight <= 0) return "into";
  const fraction = offsetY / rowHeight;
  if (fraction <= 0.25) return "before";
  if (fraction >= 0.75) return "after";
  return "into";
}

/** True if `candidateId` is `ancestorId` itself, or a descendant of it,
 * per the flat `rows` list's `parent_id` links.
 *
 * Used to refuse dropping a row onto itself or into its own subtree:
 * dropping a row onto itself is a no-op, and dropping it into a descendant
 * would create a cycle in the hierarchy -- both are worth catching
 * client-side rather than round-tripping to the server to find out. Guards
 * against a malformed cyclic `parent_id` chain (shouldn't happen, but would
 * otherwise loop forever) by bailing out the moment a node is revisited. */
export function isSelfOrDescendant(
  rows: readonly { id: string; parent_id: string | null }[],
  ancestorId: string,
  candidateId: string,
): boolean {
  if (ancestorId === candidateId) return true;
  const parentById = new Map(rows.map((r) => [r.id, r.parent_id]));
  const seen = new Set<string>();
  let current: string | null = candidateId;
  while (current !== null) {
    if (current === ancestorId) return true;
    if (seen.has(current)) return false;
    seen.add(current);
    current = parentById.get(current) ?? null;
  }
  return false;
}
