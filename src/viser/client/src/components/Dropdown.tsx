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
  const { setValue, messageSender } = React.useContext(GuiComponentContext)!;
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
        //
        // onMouseEnter/onMouseLeave here send GuiDropdownOptionHoverMessage,
        // enabled or disabled options alike -- the ghost-preview behaviour
        // the predecessor per-branch buttons had (GuiButtonHoverMessage).
        // Unlike Button.tsx's own hover_events workaround, no native
        // `disabled` attribute is in play to swallow onMouseEnter here:
        // Mantine's `ComboboxOption` (what actually wraps this renderOption
        // output) marks a disabled option via a `data-combobox-disabled`
        // attribute for CSS only (opacity/cursor), never a real DOM
        // `disabled` prop -- confirmed in
        // node_modules/@mantine/core/.../ComboboxOption.cjs and its
        // stylesheet (no `pointer-events` rule on `[data-combobox-disabled]`
        // either), so this `Group`'s mouse events fire normally regardless
        // of `checked`/disabled state and need no extra wrapper workaround.
        renderOption={({ option, checked }) => (
          <Group
            gap={4}
            wrap="nowrap"
            title={(option as DropdownItem).title}
            onMouseEnter={() =>
              messageSender({
                type: "GuiDropdownOptionHoverMessage",
                uuid,
                option: option.value,
              })
            }
            onMouseLeave={() =>
              messageSender({
                type: "GuiDropdownOptionHoverMessage",
                uuid,
                option: null,
              })
            }
          >
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
