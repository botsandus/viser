import { GuiButtonMessage } from "../WebsocketMessages";
import { GuiComponentContext } from "../ControlPanel/GuiComponentContext";
import { Box } from "@mantine/core";

import { Button } from "@mantine/core";
import React, { useRef, useCallback, useEffect } from "react";
import { htmlIconWrapper } from "./ComponentStyles.css";
import { toMantineColor } from "./colorUtils";

export default function ButtonComponent({
  uuid,
  props: {
    visible,
    disabled,
    label,
    color,
    _icon_html: icon_html,
    _hold_callback_freqs: holdCallbackFreqs,
    hover_events: hoverEvents,
  },
}: GuiButtonMessage) {
  const { messageSender } = React.useContext(GuiComponentContext)!;
  const holdIntervalsRef = useRef<ReturnType<typeof setInterval>[]>([]);
  const isDisabled = disabled ?? false;

  // React's DOM event system silently drops `onMouseEnter` (though NOT
  // `onMouseLeave`) for any interactive host element whose `disabled` prop
  // is set -- see `shouldPreventMouseEvent` in react-dom, which special-cases
  // onMouseEnter/onClick/onMouseDown/etc. to mirror native disabled-button
  // semantics. That collides with hover_events' whole point ("looky no
  // touchy" -- a disabled button should still report hover): if we hand
  // Mantine's `disabled` prop straight to the underlying <button>, the
  // enter half of every hover pair goes missing while leave still fires,
  // which is worse than either firing or neither.
  //
  // So when hover_events is on AND the button is disabled, we withhold the
  // native `disabled` attribute (keeping React's mouse dispatch intact) and
  // reimplement disabled-ness ourselves: block the click/hold handlers
  // below, and fall back to manual disabled styling since Mantine's own
  // disabled look is keyed off that same prop. Ordinary buttons (no
  // hover_events) are untouched -- native `disabled` still applies.
  const suppressNativeDisabled = isDisabled && hoverEvents;

  const stopHoldTimers = useCallback(() => {
    holdIntervalsRef.current.forEach(clearInterval);
    holdIntervalsRef.current = [];
  }, []);

  // Clean up on unmount or when disabled.
  useEffect(() => stopHoldTimers, [stopHoldTimers]);
  useEffect(() => {
    if (isDisabled) stopHoldTimers();
  }, [isDisabled, stopHoldTimers]);

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      // Only handle left click. Also re-checked here (not just via the
      // native `disabled` attribute) since `suppressNativeDisabled` keeps
      // the button natively enabled.
      if (isDisabled) return;
      if (e.button !== 0) return;
      if (holdCallbackFreqs.length === 0) return;
      // Prevent duplicate timers from multiple pointers.
      if (holdIntervalsRef.current.length > 0) return;

      // Capture pointer to receive pointerup even if released outside element.
      // try/catch like every other capture site: browsers may throw when the
      // pointer is gone by the time this runs.
      try {
        (e.target as HTMLElement).setPointerCapture(e.pointerId);
      } catch {
        // Harmless: worst case the hold ends on pointer leave.
      }
      for (const freq of holdCallbackFreqs) {
        messageSender({ type: "GuiButtonHoldMessage", uuid, frequency: freq });
        holdIntervalsRef.current.push(
          setInterval(
            () =>
              messageSender({
                type: "GuiButtonHoldMessage",
                uuid,
                frequency: freq,
              }),
            1000 / freq,
          ),
        );
      }
    },
    [isDisabled, holdCallbackFreqs, messageSender, uuid],
  );

  if (!(visible ?? true)) return null;

  return (
    <Box mx="xs" pb="0.5em">
      <Button
        id={uuid}
        fullWidth
        color={toMantineColor(color)}
        onClick={() => {
          // Re-checked here for the `suppressNativeDisabled` case -- see
          // its comment above.
          if (isDisabled) return;
          messageSender({
            type: "GuiUpdateMessage",
            uuid: uuid,
            updates: { value: true },
          });
        }}
        onPointerDown={handlePointerDown}
        onPointerUp={stopHoldTimers}
        onPointerCancel={stopHoldTimers}
        onLostPointerCapture={stopHoldTimers}
        // Only wired up when the server asked for hover events (default
        // False), so an ordinary button generates no extra traffic. Fires
        // even when `disabled` -- hover is a notification ("looky no
        // touchy"), not an action the disabled state should gate, and a
        // native `disabled` button still delivers mouseenter/mouseleave.
        onMouseEnter={
          hoverEvents
            ? () =>
                messageSender({
                  type: "GuiButtonHoverMessage",
                  uuid,
                  hovering: true,
                })
            : undefined
        }
        onMouseLeave={
          hoverEvents
            ? () =>
                messageSender({
                  type: "GuiButtonHoverMessage",
                  uuid,
                  hovering: false,
                })
            : undefined
        }
        style={{
          height: "2em",
          // Manual stand-in for Mantine's own disabled look, only needed
          // when we've withheld the native `disabled` attribute above.
          ...(suppressNativeDisabled && {
            opacity: 0.6,
            cursor: "not-allowed",
          }),
        }}
        disabled={suppressNativeDisabled ? false : isDisabled}
        aria-disabled={isDisabled}
        size="sm"
        leftSection={
          icon_html === null ? undefined : (
            <div
              className={htmlIconWrapper}
              dangerouslySetInnerHTML={{ __html: icon_html }}
            />
          )
        }
      >
        {label}
      </Button>
    </Box>
  );
}
