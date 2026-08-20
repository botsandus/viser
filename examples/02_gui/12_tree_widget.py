"""Tree widget

A server-driven tree widget: rows carry an id, a parent id, a label, and a
small set of per-row icons (eye/eye-off, lock/lock-open, trash). The server
owns all row state and pushes complete updates; the client only tracks
expand/collapse locally (and reports it back so the server can persist it).

**Key methods:**

* :meth:`viser.GuiApi.add_tree` to create the widget from a flat sequence of
  :class:`viser.TreeRow`
* :attr:`viser.GuiTreeHandle.rows` to push a full replacement of every row
* :meth:`viser.GuiTreeHandle.on_click` for row-label clicks
* :meth:`viser.GuiTreeHandle.on_icon_click` for per-row icon clicks
* :meth:`viser.GuiTreeHandle.on_expand_change` for client-side expand/collapse
  notifications

**Features demonstrated:**

* A 3-level hierarchy (scene -> {robot, environment} -> leaves)
* Mixed icon sets per row (visibility, lock, delete)
* Toggling an icon's glyph server-side in response to a click, by pushing a
  new `rows` value
* Printing callbacks for clicks, icon clicks, and expand/collapse
* A `state="disabled"` icon (see the "Grid" row's trash icon), which the
  client renders at reduced opacity and never reports clicks for
"""

import time

import viser


def _icon(name: str, state: str = "active") -> viser.TreeIcon:
    return viser.TreeIcon(name=name, state=state)


def build_rows() -> list[viser.TreeRow]:
    return [
        viser.TreeRow(
            id="scene",
            parent_id=None,
            label="Scene",
            icons=(_icon("eye"),),
        ),
        viser.TreeRow(
            id="robot",
            parent_id="scene",
            label="Robot",
            icons=(_icon("eye"), _icon("lock-open")),
        ),
        viser.TreeRow(
            id="link1",
            parent_id="robot",
            label="link_1",
            icons=(_icon("eye"),),
        ),
        viser.TreeRow(
            id="link2",
            parent_id="robot",
            label="link_2",
            icons=(_icon("eye"),),
        ),
        viser.TreeRow(
            id="environment",
            parent_id="scene",
            label="Environment",
            icons=(_icon("eye"), _icon("lock-open"), _icon("trash")),
        ),
        viser.TreeRow(
            id="grid",
            parent_id="environment",
            label="Grid",
            # The grid can't be deleted, so its trash icon is disabled: it
            # still renders (dimmed) but clicking it is a no-op on the
            # client and never reaches `on_icon_click`.
            icons=(_icon("eye"), _icon("trash", state="disabled")),
            expanded=False,
        ),
    ]


def main() -> None:
    server = viser.ViserServer()

    rows_by_id = {row.id: row for row in build_rows()}
    tree = server.gui.add_tree(list(rows_by_id.values()))

    def push_rows() -> None:
        tree.rows = list(rows_by_id.values())

    @tree.on_click
    def _(row_id: str) -> None:
        print(f"[tree] row clicked: {row_id}")

    @tree.on_icon_click
    def _(row_id: str, icon_index: int) -> None:
        row = rows_by_id[row_id]
        icon = row.icons[icon_index]
        print(f"[tree] icon clicked: row={row_id} index={icon_index} icon={icon.name}")

        # Toggle eye/eye-off and lock/lock-open in place, to demonstrate a
        # server-driven icon-state change round-tripping back to the client.
        toggled = {
            "eye": "eye-off",
            "eye-off": "eye",
            "lock": "lock-open",
            "lock-open": "lock",
        }.get(icon.name)
        if toggled is not None:
            new_icons = list(row.icons)
            new_icons[icon_index] = viser.TreeIcon(name=toggled, state=icon.state)
            rows_by_id[row_id] = viser.TreeRow(
                id=row.id,
                parent_id=row.parent_id,
                label=row.label,
                icons=tuple(new_icons),
                selected=row.selected,
                expanded=row.expanded,
            )
            push_rows()
        elif icon.name == "trash":
            print(f"[tree] (example only) would remove: {row_id}")

    @tree.on_expand_change
    def _(row_id: str, expanded: bool) -> None:
        print(f"[tree] expand changed: row={row_id} expanded={expanded}")
        # Persist the client's expand/collapse choice into our own row state,
        # so the next `push_rows()` re-asserts it instead of snapping back.
        row = rows_by_id[row_id]
        rows_by_id[row_id] = viser.TreeRow(
            id=row.id,
            parent_id=row.parent_id,
            label=row.label,
            icons=row.icons,
            selected=row.selected,
            expanded=expanded,
        )

    while True:
        time.sleep(1.0)


if __name__ == "__main__":
    main()
