import * as React from "react";
import { Box, Tooltip } from "@mantine/core";
import {
  IconBox,
  IconCaretDown,
  IconCaretRight,
  IconEye,
  IconEyeOff,
  IconLock,
  IconLockOpen,
  IconMapPin,
  IconRobot,
  IconRoute,
  IconTool,
  IconTrash,
} from "@tabler/icons-react";
import { GuiComponentContext } from "../ControlPanel/GuiComponentContext";
import {
  tableHierarchyLine,
  tableRow,
  tableWrapper,
} from "../ControlPanel/SceneTreeTable.css";
import { GuiTreeMessage } from "../WebsocketMessages";
import {
  dropPositionFromPointerY,
  isSelfOrDescendant,
  TreeRowDropPosition,
} from "./treeDragUtils";

/** How long (ms) a collapsed, droppable row must be dragged over -- with the
 * pointer in its "into" zone -- before it auto-expands, so a drag can reach
 * into a currently-collapsed subtree without a separate click first. */
const AUTO_EXPAND_HOVER_MS = 700;

/** Row/icon shapes are generated as anonymous inline object types (not named
 * interfaces) inside `GuiTreeMessage["props"]["rows"]` -- pull them back out
 * via indexed access instead of duplicating the shape here. */
type TreeRowData = GuiTreeMessage["props"]["rows"][number];
type TreeIconData = TreeRowData["icons"][number];

/** Fixed mapping from the small server-driven icon vocabulary (see
 * `TreeIcon`/`TreeIconName` in `_messages.py`) to a concrete glyph. `"none"`
 * reserves the slot's width without drawing anything, so icon columns stay
 * aligned across sibling rows that don't all carry the same icons.
 *
 * `robot`/`waypoint`/`path`/`tool`/`fixture` are the leading-icon vocabulary
 * (see `TreeRow.leading_icon`) -- they share this map with the trailing
 * action icons since both draw from the same `TreeIconName` literal. Glyph
 * choices: `IconRobot` (unambiguous), `IconMapPin` for waypoint (a single
 * pose in space -- clearer at this size than an axis triad), `IconRoute`
 * for a path/trajectory, `IconTool` for an end effector/tool, `IconBox` for
 * a fixture/jig. */
const ICON_COMPONENTS: Record<
  TreeIconData["name"],
  React.ComponentType<{
    style?: React.CSSProperties;
    onClick?: (evt: React.MouseEvent) => void;
  }> | null
> = {
  eye: IconEye,
  "eye-off": IconEyeOff,
  lock: IconLock,
  "lock-open": IconLockOpen,
  trash: IconTrash,
  none: null,
  robot: IconRobot,
  waypoint: IconMapPin,
  path: IconRoute,
  tool: IconTool,
  fixture: IconBox,
};

/** A server-driven tree widget: rows (id/parent_id/label/icons/selected/
 * expanded) are pushed wholesale by the server (see `GuiApi.add_tree` and
 * `GuiTreeHandle.rows` in the Python API). The client reconstructs hierarchy
 * from `parent_id`, and holds exactly one piece of state of its own --
 * per-row expand/collapse -- which it both applies locally (for a responsive
 * caret) and reports back via `GuiTreeExpandMessage` so the server can
 * persist it into the next `rows` push if it wants to. Label clicks and icon
 * clicks are pure notifications; the server decides what (if anything)
 * changes, and pushes new `rows` if so -- this widget never mutates its own
 * row data other than the expand flag. The one exception is an icon whose
 * `state === "disabled"`: the client renders it (same glyph, same slot) at
 * reduced opacity but never reports a click for it, so the server-driven
 * "pure notification" contract only applies to icons that aren't disabled.
 *
 * When `props.rows_draggable` opts in, rows also accept native HTML5 drag:
 * dragging one over another reports a `GuiTreeRowDropMessage` (position
 * "into"/"before"/"after" from where the pointer sits within the target
 * row -- see `treeDragUtils.dropPositionFromPointerY`) and shows a drop
 * indicator; a collapsed row auto-expands after a hover in its "into" zone.
 * Same pure-notification contract as clicks: the client refuses a drop onto
 * the dragged row itself or its own descendants as a UI nicety, but doesn't
 * otherwise mutate `rows` -- the server decides what happens and pushes a
 * new `rows` if it does. Defaults to `False`, so an existing tree that
 * doesn't pass it renders and behaves exactly as before. */
export default function TreeComponent({ uuid, props }: GuiTreeMessage) {
  const { messageSender } = React.useContext(GuiComponentContext)!;
  const { visible, rows, rows_draggable: rowsDraggable } = props;

  const [expandedOverride, setExpandedOverride] = React.useState<
    Record<string, boolean>
  >({});

  // Drag-and-drop state (only touched when `rowsDraggable`): which row is
  // currently being dragged, and where it would land if dropped right now
  // (drives the drop indicator). Both reset on `dragend`, which fires
  // whether the drag ended in a drop or was cancelled (e.g. Escape).
  const [draggingRowId, setDraggingRowId] = React.useState<string | null>(null);
  const [dropTarget, setDropTarget] = React.useState<{
    rowId: string;
    position: TreeRowDropPosition;
  } | null>(null);
  // The pending auto-expand timer for whichever collapsed row is currently
  // being dragged over in its "into" zone -- at most one at a time, cleared
  // whenever the hovered row/zone changes or the drag ends.
  const autoExpandTimerRef = React.useRef<{
    rowId: string;
    timer: ReturnType<typeof setTimeout>;
  } | null>(null);

  function clearAutoExpandTimer() {
    if (autoExpandTimerRef.current !== null) {
      clearTimeout(autoExpandTimerRef.current.timer);
      autoExpandTimerRef.current = null;
    }
  }

  // Drop overrides for rows that no longer exist, so a removed-then-reused
  // row id doesn't inherit a stale local expand flag forever.
  React.useEffect(() => {
    setExpandedOverride((prev) => {
      const ids = new Set(rows.map((r) => r.id));
      let changed = false;
      const next: Record<string, boolean> = {};
      for (const [id, val] of Object.entries(prev)) {
        if (ids.has(id)) {
          next[id] = val;
        } else {
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [rows]);

  // Clear any in-flight drag state on unmount, so a stale timer can't fire
  // an expand message after the tree is gone.
  React.useEffect(() => clearAutoExpandTimer, []);

  if (!visible) return null;

  const childrenByParent = new Map<string | null, TreeRowData[]>();
  for (const row of rows) {
    const key = row.parent_id;
    const list = childrenByParent.get(key);
    if (list === undefined) childrenByParent.set(key, [row]);
    else list.push(row);
  }

  function isExpanded(row: TreeRowData): boolean {
    return expandedOverride[row.id] ?? row.expanded;
  }

  function renderRow(row: TreeRowData, depth: number): React.ReactNode {
    const children = childrenByParent.get(row.id) ?? [];
    const expandable = children.length > 0;
    const expanded = isExpanded(row);

    function toggleExpanded(evt: React.MouseEvent) {
      evt.stopPropagation();
      const next = !expanded;
      setExpandedOverride((prev) => ({ ...prev, [row.id]: next }));
      messageSender({
        type: "GuiTreeExpandMessage",
        uuid,
        row_id: row.id,
        expanded: next,
      });
    }

    // Drag handlers below are only wired up when `rowsDraggable`; the row
    // click and expand-caret handlers above are untouched by any of this --
    // a plain click never fires `dragstart` (the browser only starts a drag
    // once the pointer moves past its own drag threshold), so click and drag
    // stay naturally distinct with no bookkeeping of our own.

    function handleDragStart(evt: React.DragEvent) {
      evt.dataTransfer.effectAllowed = "move";
      evt.dataTransfer.setData("text/plain", row.id);
      setDraggingRowId(row.id);
    }

    function handleDragOver(evt: React.DragEvent) {
      if (draggingRowId === null) return;
      // Refuse a drop onto the dragged row itself or one of its own
      // descendants (would be a no-op or a hierarchy cycle): don't
      // preventDefault, so the browser shows its native "no drop" cursor,
      // and clear any indicator left over from a row we've since left.
      if (isSelfOrDescendant(rows, draggingRowId, row.id)) {
        if (dropTarget?.rowId === row.id) setDropTarget(null);
        if (autoExpandTimerRef.current?.rowId === row.id) {
          clearAutoExpandTimer();
        }
        return;
      }
      evt.preventDefault();
      evt.dataTransfer.dropEffect = "move";

      const rect = evt.currentTarget.getBoundingClientRect();
      const position = dropPositionFromPointerY(
        evt.clientY - rect.top,
        rect.height,
      );
      setDropTarget((prev) =>
        prev?.rowId === row.id && prev.position === position
          ? prev
          : { rowId: row.id, position },
      );

      // Auto-expand: only for a collapsed, expandable row being hovered in
      // its "into" zone -- "before"/"after" are about becoming a sibling,
      // which doesn't call for revealing this row's children.
      const shouldSchedule = position === "into" && expandable && !expanded;
      if (!shouldSchedule) {
        if (autoExpandTimerRef.current?.rowId === row.id) {
          clearAutoExpandTimer();
        }
        return;
      }
      if (autoExpandTimerRef.current?.rowId === row.id) return; // already scheduled
      clearAutoExpandTimer();
      const timer = setTimeout(() => {
        setExpandedOverride((prev) => ({ ...prev, [row.id]: true }));
        messageSender({
          type: "GuiTreeExpandMessage",
          uuid,
          row_id: row.id,
          expanded: true,
        });
        autoExpandTimerRef.current = null;
      }, AUTO_EXPAND_HOVER_MS);
      autoExpandTimerRef.current = { rowId: row.id, timer };
    }

    function handleDrop(evt: React.DragEvent) {
      evt.preventDefault();
      clearAutoExpandTimer();
      const dragging = draggingRowId;
      setDraggingRowId(null);
      setDropTarget(null);
      if (dragging === null) return;
      if (isSelfOrDescendant(rows, dragging, row.id)) return;

      const rect = evt.currentTarget.getBoundingClientRect();
      const position = dropPositionFromPointerY(
        evt.clientY - rect.top,
        rect.height,
      );
      messageSender({
        type: "GuiTreeRowDropMessage",
        uuid,
        row_id: dragging,
        target_row_id: row.id,
        position,
      });
    }

    function handleDragEnd() {
      clearAutoExpandTimer();
      setDraggingRowId(null);
      setDropTarget(null);
    }

    const dropIndicator = dropTarget?.rowId === row.id ? dropTarget : null;

    return (
      <React.Fragment key={row.id}>
        <Box
          className={tableRow}
          draggable={rowsDraggable}
          onDragStart={rowsDraggable ? handleDragStart : undefined}
          onDragOver={rowsDraggable ? handleDragOver : undefined}
          onDrop={rowsDraggable ? handleDrop : undefined}
          onDragEnd={rowsDraggable ? handleDragEnd : undefined}
          style={{
            position: "relative",
            ...(dropIndicator?.position === "into" && {
              outline: "2px solid var(--mantine-primary-color-filled)",
              outlineOffset: "-2px",
              backgroundColor: "var(--mantine-primary-color-light)",
            }),
          }}
        >
          {dropIndicator?.position === "before" && (
            <Box
              style={{
                position: "absolute",
                left: 0,
                right: 0,
                top: -1,
                height: "2px",
                backgroundColor: "var(--mantine-primary-color-filled)",
                pointerEvents: "none",
              }}
            />
          )}
          {dropIndicator?.position === "after" && (
            <Box
              style={{
                position: "absolute",
                left: 0,
                right: 0,
                bottom: -1,
                height: "2px",
                backgroundColor: "var(--mantine-primary-color-filled)",
                pointerEvents: "none",
              }}
            />
          )}
          {new Array(depth).fill(null).map((_, i) => (
            <Box className={tableHierarchyLine} key={i} />
          ))}
          <Box
            style={{
              opacity: expandable ? 0.7 : 0.1,
              cursor: expandable ? "pointer" : "default",
            }}
            onClick={expandable ? toggleExpanded : undefined}
          >
            {expanded ? (
              <IconCaretDown
                style={{
                  height: "1em",
                  width: "1em",
                  transform: "translateY(0.1em)",
                }}
              />
            ) : (
              <IconCaretRight
                style={{
                  height: "1em",
                  width: "1em",
                  transform: "translateY(0.1em)",
                }}
              />
            )}
          </Box>
          {row.leading_icon !== null &&
            (() => {
              const LeadingIconComp = ICON_COMPONENTS[row.leading_icon.name];
              return LeadingIconComp === null ? null : (
                <Box
                  style={{ width: "1.4em", height: "1.4em", display: "block" }}
                >
                  <Tooltip
                    label={row.leading_icon.state}
                    disabled={row.leading_icon.state === ""}
                  >
                    {/* Non-clickable, unlike the trailing `icons` -- purely
                    identifies what kind of thing this row represents. */}
                    <LeadingIconComp
                      style={{
                        width: "1.2em",
                        height: "1.2em",
                        display: "block",
                        opacity:
                          row.leading_icon.state === "disabled" ? 0.3 : 0.75,
                      }}
                    />
                  </Tooltip>
                </Box>
              );
            })()}
          <Box
            style={{
              flexGrow: 1,
              userSelect: "none",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              cursor: "pointer",
              ...(row.selected && { fontWeight: 600, opacity: 1 }),
            }}
            onClick={() =>
              messageSender({
                type: "GuiTreeRowClickMessage",
                uuid,
                row_id: row.id,
              })
            }
          >
            {row.label}
          </Box>
          {row.icons.map((icon, index) => {
            const IconComp = ICON_COMPONENTS[icon.name];
            // `state === "disabled"` is the one icon state the client
            // interprets itself: the glyph still renders (same slot, same
            // icon) but at reduced opacity and with clicks suppressed. Any
            // other string in `state` remains purely a tooltip label, per
            // `TreeIcon.state` in `_messages.py`.
            const disabled = icon.state === "disabled";
            return (
              <Box
                key={index}
                style={{ width: "1.4em", height: "1.4em", display: "block" }}
              >
                {IconComp === null ? null : (
                  <Tooltip label={icon.state} disabled={icon.state === ""}>
                    <IconComp
                      style={{
                        cursor: disabled ? "default" : "pointer",
                        width: "1.2em",
                        height: "1.2em",
                        display: "block",
                        opacity: disabled ? 0.3 : 0.75,
                      }}
                      onClick={
                        disabled
                          ? undefined
                          : (evt) => {
                              evt.stopPropagation();
                              messageSender({
                                type: "GuiTreeIconClickMessage",
                                uuid,
                                row_id: row.id,
                                icon_index: index,
                              });
                            }
                      }
                    />
                  </Tooltip>
                )}
              </Box>
            );
          })}
        </Box>
        {expanded ? children.map((child) => renderRow(child, depth + 1)) : null}
      </React.Fragment>
    );
  }

  const roots = childrenByParent.get(null) ?? [];

  return (
    <Box className={tableWrapper} px="xs" pb="0.5em">
      {roots.map((row) => renderRow(row, 0))}
    </Box>
  );
}
