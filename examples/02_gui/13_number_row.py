"""Number row

A generic, application-agnostic widget: N labelled number inputs sharing a
single row, instead of the one full-width row every other GUI input gets.
Useful for compact Unity-style groups -- e.g. a position or rotation -- but
the widget itself carries no such concept; it's just N floats with N short
labels.

**Key methods:**

* :meth:`viser.GuiApi.add_number_row` to create the widget from a sequence of
  labels and a matching sequence of initial values
* :attr:`viser.GuiNumberRowHandle.values` to read or push a full replacement
  of every value in the row (`.value` is equivalent -- `.values` just reads
  better for a widget that's inherently plural)
* :meth:`viser.GuiInputHandle.on_update` to be notified of edits; the
  callback's `event.target.values` is always the *entire* current tuple, not
  just the entry that changed

**Features demonstrated:**

* A 3-input row (`X` / `Y` / `Z`), e.g. for a compact position control
* A 6-input row (`X` / `Y` / `Z` / `Roll` / `Pitch` / `Yaw`), e.g. for a
  compact 6-DOF transform -- the motivating case for this widget
* Printing callbacks on every edit
* Server-side `.values` assignment (a "reset" button) round-tripping back to
  the client
"""

import time

import viser


def main() -> None:
    server = viser.ViserServer()

    server.gui.add_markdown("### Position (compact 3-row)")
    position = server.gui.add_number_row(
        ("X", "Y", "Z"),
        (0.0, 0.0, 0.0),
        step=0.1,
    )

    @position.on_update
    def _(event: viser.GuiEvent) -> None:
        print(f"[number_row] position updated: {event.target.values}")

    server.gui.add_markdown("### Transform (compact 6-row)")
    transform = server.gui.add_number_row(
        ("X", "Y", "Z", "Roll", "Pitch", "Yaw"),
        (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        step=0.1,
    )

    @transform.on_update
    def _(event: viser.GuiEvent) -> None:
        print(f"[number_row] transform updated: {event.target.values}")

    reset_button = server.gui.add_button("Reset both to zero")

    @reset_button.on_click
    def _(_) -> None:
        position.values = (0.0, 0.0, 0.0)
        transform.values = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    while True:
        time.sleep(1.0)


if __name__ == "__main__":
    main()
