import * as React from "react";
import { GuiComponentContext } from "../ControlPanel/GuiComponentContext";
import { ViserInputComponent } from "./common";
import { GuiDropdownMessage } from "../WebsocketMessages";
import { CheckIcon, ComboboxItem, Group, Select } from "@mantine/core";

// The Mantine `Select` this renders onto only supports per-option `disabled`
// via its `data` items (`ComboboxItem`), which carries no `title` field --
// so a disabled-but-viewable option (amri-connected-chrome's own ask: a
// filtered-out choice stays visible and hoverable, carrying the reason it's
// filtered) needs one extra field threaded through here, read back in
// `renderOption` below. Widening `ComboboxItem` this way is additive: every
// existing consumer that never sets `title` gets `undefined`, identical to
// before this type existed.
interface DropdownItem extends ComboboxItem {
  title?: string;
}

export default function DropdownComponent({
  uuid,
  value,
  props: {
    hint,
    label,
    disabled,
    visible,
    options,
    options_disabled,
    options_title,
  },
}: GuiDropdownMessage) {
  const { setValue } = React.useContext(GuiComponentContext)!;
  if (!visible) return null;
  const data: DropdownItem[] = options.map((option, i) => ({
    value: option,
    label: option,
    disabled: options_disabled?.[i] ?? false,
    title: options_title?.[i] ?? undefined,
  }));
  return (
    <ViserInputComponent {...{ uuid, hint, label }}>
      <Select
        id={uuid}
        radius="xs"
        value={value}
        data={data}
        onChange={(value) => value !== null && setValue(uuid, value)}
        disabled={disabled}
        searchable
        maxDropdownHeight={400}
        size="xs"
        rightSectionWidth="1.2em"
        // Only touches presentation: the checked icon + label the DEFAULT
        // renderOption already draws (Select's own `withCheckIcon: true`,
        // `checkIconPosition: "left"` defaults), plus a `title` attribute for
        // the native hover tooltip a disabled option needs -- the wrapping
        // `Combobox.Option` this renders INTO still gets `disabled` straight
        // off `data` regardless of `renderOption` (see OptionsDropdown.tsx
        // upstream), so disabling/enabling behaves exactly as it always has.
        renderOption={({ option, checked }) => (
          <Group gap={4} wrap="nowrap" title={(option as DropdownItem).title}>
            {checked && <CheckIcon size={12} />}
            <span>{option.label}</span>
          </Group>
        )}
        styles={{
          input: {
            padding: "0.5em",
            letterSpacing: "-0.5px",
            minHeight: "1.625rem",
            height: "1.625rem",
          },
        }}
        // zIndex of dropdown should be >modal zIndex.
        // On edge cases: it seems like existing dropdowns are always closed when a new modal is opened.
        comboboxProps={{ zIndex: 1000 }}
      />
    </ViserInputComponent>
  );
}
