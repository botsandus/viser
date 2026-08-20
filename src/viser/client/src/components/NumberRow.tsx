import * as React from "react";
import { Box, Flex, NumberInput, Text } from "@mantine/core";
import { GuiComponentContext } from "../ControlPanel/GuiComponentContext";
import { GuiNumberRowMessage } from "../WebsocketMessages";
import { finiteNumberOrNull } from "./numberInputUtils";

/** A generic, application-agnostic inline number row: N labelled number
 * inputs sharing a single row, instead of the one full-width row every
 * other GUI input gets (see `GuiApi.add_number_row` in the Python API).
 * Unlike the tree widget, this has a natural single value -- a tuple of
 * floats, one per label -- so it plugs into the same generic value-sync
 * machinery as Vector2/Vector3/MultiSlider (`setValue` -> `GuiUpdateMessage`)
 * rather than the tree's bespoke click/action messages: any edit here
 * reports the *entire* updated tuple back, not just the changed entry, so a
 * server-side `on_update` always sees every current value.
 *
 * Layout is a deliberate departure from Vector2/Vector3 (which put one
 * shared label to the left of the row): with up to N=6 short-labelled
 * inputs needing to fit a ~300px control panel, a left-side label would
 * either wrap badly or squeeze the inputs to unusable widths. Each label
 * instead sits directly above its own input, and the up/down spinner
 * buttons are hidden (arrow-key stepping still works while an input is
 * focused) to reclaim the couple of pixels their column costs -- worthwhile
 * at 6-wide, where every input is already under 50px. */
export default function NumberRowComponent({
  uuid,
  value,
  props: { visible, disabled, labels, step, precision },
}: GuiNumberRowMessage) {
  const { setValue } = React.useContext(GuiComponentContext)!;
  if (!visible) return null;

  return (
    <Box px="xs" pb="0.5em">
      <Flex columnGap="0.4em">
        {labels.map((label, i) => (
          <Box key={i} style={{ flex: "1 1 0", minWidth: 0 }}>
            <Text
              size="xs"
              c="dimmed"
              ta="center"
              unselectable="off"
              style={{
                lineHeight: 1.3,
                fontWeight: 450,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {label}
            </Text>
            <NumberInput
              id={i === 0 ? uuid : undefined}
              value={value[i]}
              onChange={(v) => {
                // Ignore empty / partial input (e.g. "-", "1e") while the
                // user is typing; committing those would send NaN, and
                // clearing to retype would momentarily commit 0.
                const parsed = finiteNumberOrNull(v);
                if (parsed === null) return;
                const updated = [...value];
                updated[i] = parsed;
                setValue(uuid, updated);
              }}
              size="xs"
              decimalScale={precision}
              step={step}
              hideControls
              styles={{
                input: {
                  paddingLeft: "0.4em",
                  paddingRight: "0.4em",
                  textAlign: "center",
                  height: "1.875em",
                  minHeight: "1.875em",
                },
              }}
              disabled={disabled}
            />
          </Box>
        ))}
      </Flex>
    </Box>
  );
}
