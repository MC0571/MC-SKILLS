# Component System

Use this catalog to fill proven component gaps in a desktop AI workbench. Reuse the target project's existing primitives first; do not recreate the entire catalog for a smaller surface.

## Contents

- Component layers
- Button, popover, modal, and context menu
- Selectable rows and resource cards
- Command and search inputs
- Keycaps, diff stats, banners, toasts, and spinners
- Settings rows and component QA

API shapes are Observed from Codex Desktop `26.623.70822` unless labeled Recommended. Reuse an existing project component before creating one from this catalog.

## Component Layers

1. Primitive controls:
   - Button
   - IconButton
   - SearchInput
   - Popover
   - ContextMenu
   - ModalHost
   - Tooltip
   - Spinner
2. Workbench primitives:
   - SelectableListRow
   - CommandMenuItem
   - ResourceCard
   - Keycap
   - DiffStats
   - Banner
   - Toast
   - ResizablePanel
3. Domain components:
   - ThreadRow
   - ProjectRow
   - AttachmentPill
   - ComposerFooterControl
   - PanelTab
   - SettingsRow
   - ApprovalPanel
   - RateLimitBanner

## Button

API:

```ts
type ButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "color"> & {
  size?: "default" | "large" | "medium" | "composer" | "composerSm" | "toolbar" | "icon" | "iconMd" | "iconSm" | "icon-sm";
  color?: "primary" | "secondary" | "ghost" | "ghostActive" | "ghostMuted" | "ghostTertiary" | "outline" | "outlineActive" | "danger";
  variant?: ButtonProps["color"];
  loading?: boolean;
  uniform?: boolean;
  allowShrink?: boolean;
}
```

Rules:

- `type="button"` by default.
- `loading` disables the button and shows a small spinner before children.
- `uniform` makes square icon buttons without extra horizontal padding.
- `allowShrink` adds `min-w-0` for toolbar/composer controls.
- `variant` overrides `color`; prefer `color` in new call sites unless compatibility requires `variant`.
- Composer buttons are compact and pill-shaped.
- Electron icon buttons can use slightly squarer radius than web.

Do not:

- create one-off button colors.
- put long labels inside tight toolbar controls.
- rely only on opacity for disabled reason; pair with tooltip when needed.

## Popover

Rules:

- Wrap platform primitive, usually Radix.
- Default width: about 18rem.
- Large width: about 24rem.
- Use portal by default.
- Support `disablePortal` only for nested shell constraints.
- Apply collision padding around viewport.
- Apply window zoom to content.
- Limit max width and height to available viewport minus 16px.
- Use background blur and 0.5px border/ring for desktop layering.

Required behavior:

- Escape closes.
- Focus returns to trigger.
- Trigger state reflects open state.

## Modal Host

Rules:

- Modals are stack descriptors in app/shell scope.
- Descriptor includes key, component, props.
- Modal renderer wraps lazy modal in Suspense.
- Close first runs supplied `onClose`, then removes descriptor from stack.
- Do not manage important global modal state inside leaf pages.

Use modal only for blocking decisions. Use popover/sheet/panel for lightweight choices.

## Context Menu

See `interaction-patterns.md` for full behavior.

Component contract:

- Accept static `items` or async `getItems`.
- Accept `onBeforeOpen`.
- Prefer native Electron menu unless disabled.
- Web fallback keeps same item data model.
- Supports item, checkbox, separator, submenu, disabled, tooltip.

## SelectableListRow

API shape:

```ts
type SelectableListRowProps = {
  ariaDescribedBy?: string;
  ariaLabel?: string;
  className?: string;
  icon?: ReactNode;
  title?: ReactNode;
  secondaryTitle?: ReactNode;
  titleAdornment?: ReactNode;
  rightText?: ReactNode;
  secondLine?: ReactNode;
  secondLineRightText?: ReactNode;
  isSelected?: boolean;
  compactSecondLine?: boolean;
  hasInteractiveContent?: boolean;
  onSelect?: () => void;
  onContextMenu?: MouseEventHandler;
}
```

Rules:

- Root min height about 40px.
- Use `role="button"` with `tabIndex=0` when selectable.
- Enter and Space select the row.
- Row uses `min-w-0`, `truncate`, `shrink-0` consistently.
- Observed `SelectableListRow` uses `token-list-active-selection-background` for both selected and hover states.
- Recommended: make persistent selection unmistakable through an additional foreground, indicator, or intensity difference when adapting the pattern.
- Right text is compact metadata/status, not primary content.
- If row contains child interactive controls, use an absolute overlay button and make content pointer-events none only when appropriate.

Row density:

- Standard row: 40-48px.
- Dense row: 32-40px.
- Second line is small and muted.

## Resource Card

Use for file/thread/artifact/resource summaries near composer or thread content.

Parts:

- Card shell.
- Header with icon, title, subtitle, trailing.
- Pill for compact value.
- Expand button.

Rules:

- Shell max-width 100%, overflow hidden, rounded 8px.
- Header uses compact padding variants.
- Title and subtitle truncate.
- Reserve trailing space when expand/close button overlays.
- Pills are non-wrapping and shrink-safe.
- For dropdown-aligned pill widths, use invisible label in same grid cell to reserve width.

Do not use resource cards as page sections.

## Command Menu Item

Rules:

- Reuse slash command item for command palette rows.
- Left accessory or icon is optional but fixed width.
- Title truncates; description sits on right when present.
- Secondary content is one small muted line.
- Query highlights matching text.
- Selected item scrolls into view.
- Tooltip appears only for overflow or explicit tooltip.

## Search Input

Page search rules:

- Leading search icon.
- sr-only label.
- clear button only when non-empty.
- optional trailing control.
- `min-w-0 flex-1` input.
- no drag in Electron chrome.

Dropdown search rules:

- same padding variables as dropdown item.
- autofocus.
- Arrow keys can move into menu.
- Cmd/Ctrl+A selects input text.

## Keycap

Rules:

- Use `<kbd>`.
- Inline flex.
- Small font.
- Rounded 6px.
- Background `currentColor / 10%`.
- No shadow.
- Use `button` variant for tight button tooltips.

## Diff Stats

Rules:

- Use tabular numbers.
- Added and removed numbers are separate spans.
- Support color and monochrome variants.
- Format values with locale-aware number formatter.
- Animated version may roll digits, but must expose stable aria-label.
- Exclude from thread search when needed.

## Banner / Toast / Spinner

Banner:

- Use for inline blocking or contextual warnings.
- Place near affected surface.
- Include recovery action when possible.

Toast:

- Use for secondary confirmation only.
- Do not rely on toast as sole error or loading state.

Spinner:

- Small inline spinner for loading controls.
- Centered spinner only for a local empty/loading region.

## Settings Row

Settings rows must include:

- label
- short description
- control
- optional inline error
- optional host/scope note

Use grouped right-panel forms, not cards inside cards.

## Component QA

- Props express real states; no hidden state guesses.
- Text truncates inside every row/button/pill.
- Every icon-only button has accessible label and tooltip.
- Every row works with keyboard.
- Every popover/context menu handles Escape and focus return.
- Loading/disabled states cannot be confused with selected/active states.
- Exact-reproduction API docs include compatibility aliases such as `variant` and `icon-sm`.
