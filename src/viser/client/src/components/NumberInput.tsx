import * as React from "react";
import { GuiComponentContext } from "../ControlPanel/GuiComponentContext";
import { GuiNumberMessage } from "../WebsocketMessages";
import { ViserInputComponent } from "./common";
import { finiteNumberOrNull, snapToStepAndClamp } from "./numberInputUtils";
import { ActionIcon, Flex, NumberInput } from "@mantine/core";
import { IconMinus, IconPlus } from "@tabler/icons-react";

export default function NumberInputComponent({
  uuid,
  value,
  props: {
    visible,
    label,
    hint,
    disabled,
    precision,
    min,
    max,
    step,
    nudge_step: nudgeStep,
  },
}: GuiNumberMessage) {
  const { setValue } = React.useContext(GuiComponentContext)!;
  if (!visible) return null;
  const nudge = (direction: 1 | -1) => {
    if (nudgeStep == null) return;
    const raw = value + direction * nudgeStep;
    const preClamped = Math.min(
      max ?? Infinity,
      Math.max(min ?? -Infinity, raw),
    );
    const snapped = snapToStepAndClamp(
      preClamped,
      min ?? null,
      max ?? null,
      step,
    );
    // Match the input's own display precision -- avoids sending e.g.
    // 0.30000000004 from plain float addition.
    setValue(uuid, Number(snapped.toFixed(precision)));
  };
  const input = (
    <NumberInput
      id={uuid}
      value={value}
      // This was renamed in Mantine v7.
      decimalScale={precision}
      min={min ?? undefined}
      max={max ?? undefined}
      step={step}
      size="xs"
      onChange={(newValue) => {
        // Ignore empty / partial input (e.g. "-", "1e"); committing those
        // would send NaN or a raw string to the server.
        const parsed = finiteNumberOrNull(newValue);
        if (parsed !== null) setValue(uuid, parsed);
      }}
      styles={{
        input: {
          minHeight: "1.625rem",
          height: "1.625rem",
        },
        controls: {
          height: "1.625em",
          width: "0.825em",
        },
      }}
      disabled={disabled}
      stepHoldDelay={500}
      stepHoldInterval={(t) => Math.max(1000 / t ** 2, 25)}
      // Fills the remaining row space when the nudge buttons are present, so
      // the row's overall width doesn't change.
      style={nudgeStep != null ? { flexGrow: 1, minWidth: 0 } : undefined}
    />
  );
  return (
    <ViserInputComponent {...{ uuid, hint, label }}>
      {nudgeStep != null ? (
        // `align` stays unset (Mantine's default) unless nudge buttons are
        // actually present. Spacing around the nudge buttons is via their
        // own margins (below), not a `Flex` `gap`, matching the slider's
        // nudge_step layout.
        <Flex align="center">
          <ActionIcon
            variant="default"
            size="sm"
            disabled={disabled}
            onClick={() => nudge(-1)}
            aria-label="Decrease value"
            mr="xs"
          >
            <IconMinus size={12} />
          </ActionIcon>
          {input}
          <ActionIcon
            variant="default"
            size="sm"
            disabled={disabled}
            onClick={() => nudge(1)}
            aria-label="Increase value"
            ml="xs"
          >
            <IconPlus size={12} />
          </ActionIcon>
        </Flex>
      ) : (
        input
      )}
    </ViserInputComponent>
  );
}
