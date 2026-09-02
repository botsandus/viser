// Pure mapping from websocket connection state to the tab-strip badge's dot
// color and tooltip label. Split out from ConnectionBadge (TabGroupFrame.tsx)
// so it's testable without a DOM (vitest's dock suite runs in a Node
// environment; see vitest.config.ts) and reusable if another surface ever
// wants the same color/label pairing.

import { GuiState } from "../ControlPanel/GuiState";

export type WebsocketState = GuiState["websocketState"];

export interface ConnectionBadgeVisual {
  /** Mantine theme color token for the dot (see Mantine's CSS var scheme:
   * `var(--mantine-color-{color}-6)` at the default shade). */
  color: string;
  /** Tooltip / accessible label. */
  label: string;
}

/** The badge's dot color + label for one websocket state. Green/amber/grey
 * reads as a universal traffic-light idiom independent of ConnectionStatus's
 * existing red-for-both-reconnecting-and-inactive scheme (that component
 * distinguishes the two states by ICON instead, not color) -- the badge has
 * no room for an icon, so color carries the full distinction here. */
export function connectionBadgeVisual(
  state: WebsocketState,
): ConnectionBadgeVisual {
  switch (state) {
    case "connected":
      return { color: "green", label: "Connected" };
    case "reconnecting":
      return { color: "yellow", label: "Reconnecting…" };
    case "inactive":
      return { color: "gray", label: "Inactive" };
  }
}
