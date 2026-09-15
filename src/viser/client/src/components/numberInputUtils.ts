/** Coerce a Mantine ``NumberInput`` onChange payload to a finite number, or
 * ``null`` when it should be ignored.
 *
 * Mantine's ``NumberInput.onChange`` emits ``number | string`` -- a string for
 * the empty field *and* for in-progress/partial input like ``"-"``, ``"1."``,
 * ``"1e"``, or ``"1.2.3"``. Committing those would send ``NaN`` (which becomes
 * ``null`` over JSON) or a raw string to the server, corrupting a numeric
 * handle. Callers should skip the update when this returns ``null``. */
export function finiteNumberOrNull(value: number | string): number | null {
  if (value === "") return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/** Snap `value` onto the `min + k*step` grid (the same grid a slider's own
 * track snaps a drag to), then clamp to `[min, max]`.
 *
 * The clamp runs AFTER the snap, not before: a `step` that doesn't evenly
 * divide `max - min` can round the top grid point past `max` (e.g. min=0,
 * max=10, step=6 rounds a value of 10 up to 12) -- a drag can't produce that,
 * since the track geometry itself bounds it to `[min, max]`, but a
 * programmatic nudge has no such backstop and needs the clamp to catch it.
 * `step <= 0` (a degenerate/absent step) skips snapping and only clamps. */
export function snapToStepAndClamp(
  value: number,
  min: number,
  max: number,
  step: number,
): number {
  const snapped =
    step > 0 ? min + Math.round((value - min) / step) * step : value;
  return Math.min(max, Math.max(min, snapped));
}
