import * as React from "react";
import { Box, Tooltip } from "@mantine/core";
import {
  IconCaretDown,
  IconCaretRight,
  IconEye,
  IconEyeOff,
  IconLock,
  IconLockOpen,
  IconTrash,
} from "@tabler/icons-react";
import { GuiComponentContext } from "../ControlPanel/GuiComponentContext";
import {
  tableHierarchyLine,
  tableRow,
  tableWrapper,
} from "../ControlPanel/SceneTreeTable.css";
import { GuiTreeMessage } from "../WebsocketMessages";

/** Row/icon shapes are generated as anonymous inline object types (not named
 * interfaces) inside `GuiTreeMessage["props"]["rows"]` -- pull them back out
 * via indexed access instead of duplicating the shape here. */
type TreeRowData = GuiTreeMessage["props"]["rows"][number];
type TreeIconData = TreeRowData["icons"][number];

/** Fixed mapping from the small server-driven icon vocabulary (see
 * `TreeIcon`/`TreeIconName` in `_messages.py`) to a concrete glyph. `"none"`
 * reserves the slot's width without drawing anything, so icon columns stay
 * aligned across sibling rows that don't all carry the same icons. */
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
 * "pure notification" contract only applies to icons that aren't disabled. */
export default function TreeComponent({ uuid, props }: GuiTreeMessage) {
  const { messageSender } = React.useContext(GuiComponentContext)!;
  const { visible, rows } = props;

  const [expandedOverride, setExpandedOverride] = React.useState<
    Record<string, boolean>
  >({});

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

    return (
      <React.Fragment key={row.id}>
        <Box className={tableRow}>
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
