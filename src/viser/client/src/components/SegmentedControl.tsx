import * as React from "react";
import { GuiComponentContext } from "../ControlPanel/GuiComponentContext";
import { ViserInputComponent } from "./common";
import { GuiSegmentedControlMessage } from "../WebsocketMessages";
import { SegmentedControl } from "@mantine/core";

export default function SegmentedControlComponent({
  uuid,
  value,
  props: { hint, label, disabled, visible, options },
}: GuiSegmentedControlMessage) {
  const { setValue } = React.useContext(GuiComponentContext)!;
  if (!visible) return null;
  return (
    <ViserInputComponent {...{ uuid, hint, label }}>
      <SegmentedControl
        id={uuid}
        radius="xs"
        size="xs"
        fullWidth
        value={value}
        data={options}
        onChange={(value) => setValue(uuid, value)}
        disabled={disabled}
        styles={{
          label: {
            padding: "0.3em 0.5em",
          },
        }}
      />
    </ViserInputComponent>
  );
}
