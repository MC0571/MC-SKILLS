# Visual Tokens And Density

Use this to reproduce the Codex Desktop visual grammar: compact, neutral, stateful, and readable under real data.

## Contents

- Semantic tokens and density
- Typography and sizing
- Shape, overflow, and icons
- State colors
- Motion and accessibility
- Visual QA

Separate Observed Codex values from Recommended adaptation rules. Visual similarity never overrides orientation, continuity, control, or recovery.

## Token Categories

Use semantic tokens instead of raw one-off colors.

| Token family | Purpose |
| --- | --- |
| `token-main-surface-primary` | primary window/content background |
| `token-side-bar-background` | sidebar or side shell background |
| `token-dropdown-background` | popover/menu/card shell |
| `token-input-background` | composer/search/input surface |
| `token-foreground` | primary foreground and strong button fill |
| `token-text-secondary` | secondary text |
| `token-text-tertiary` | tertiary icons/text |
| `token-description-foreground` | metadata and descriptions |
| `token-border` | normal borders/rings |
| `token-input-border` | input border |
| `token-focus-border` | focus ring |
| `token-list-hover-background` | hover row background |
| `token-list-active-selection-background` | selected row background |
| `token-git-decoration-added-resource-foreground` | additions |
| `token-git-decoration-deleted-resource-foreground` | deletions |
| `token-charts-red` | danger/destructive |

Rules:

- Neutral surfaces dominate.
- Semantic colors are sparse and meaningful.
- Hover and selected use list tokens, not arbitrary accent fills.
- Dark mode must use the same semantic categories.

## Density Defaults

| Surface | Default density |
| --- | --- |
| Developer workbench | dense |
| General AI workspace | standard |
| Settings | standard with dense navigation |
| Logs/terminal/process table | dense/control-room |
| Reading/writing only | calm |

## Typography Roles

Use few roles:

| Role | Treatment |
| --- | --- |
| app/window title | compact, medium, never hero-scale |
| toolbar label | short, base or small, usually icon + tooltip |
| section label | small, muted/medium, used for scanning |
| row title | base, medium or normal, truncate |
| row metadata | small, muted, truncate |
| body/help | base or small, short paragraphs only |
| code/log/path | monospace, preserve alignment, copyable |
| keycap | xs, inline, kbd |
| diff/metric | tabular nums |
| error | readable, close to failed control |

Avoid:

- giant H1 in app workspace.
- three or more title sizes in one panel.
- body-copy explanations where a status row would do.
- metadata below readable contrast.

## Sizing Grammar

Use stable compact sizes:

```text
icon-2xs: tiny trailing chevrons or inline metadata
icon-xs: list/action icons
icon-sm: toolbar/panel icons
icon-md+: rare, empty states only

button composer: 28-32px high
button composerSm: 24-28px high
row dense: 32-40px
row standard: 40-48px
toolbar row: 32-40px
popover default: about 288px wide
popover large: about 384px wide
main bottom panel: 280px default; max(160, min(height, availableHeight * 0.5))
utility portal panel: 200px min, 80vh max
```

Spacing:

- Use `gap-1`, `gap-1.5`, `gap-2`, `gap-2.5`, `gap-3` for dense UI.
- Use row padding variables for dropdowns/menus.
- Use `px-2`, `px-2.5`, `px-3` for compact rows and inputs.
- Use larger spacing only between major shell zones.

## Shape And Surface

Rules:

- Buttons: pill for primary/default composer controls; md/lg for icon/toolbars.
- Rows: 8px radius.
- Resource cards: 8px radius.
- Popovers/context menus: 12px radius is acceptable due floating layer.
- Avoid nested cards.
- Avoid decorative gradient/orb backgrounds.
- Use thin borders/rings and subtle backdrop blur for floating surfaces.
- Use real shell separation instead of heavy shadows.

## Text Overflow

Every horizontal workbench component needs:

- parent `min-w-0`
- text `truncate`
- fixed/trailing items `shrink-0`
- tooltip for important overflow
- full value available via title, tooltip, side panel, or copy affordance

Apply to:

- project names
- paths
- branch names
- thread titles
- command descriptions
- plugin/tool names
- host names
- PR titles
- file names

## Icon Rules

- Icons use `currentColor`.
- Icon size comes from `icon-*` class, not inline arbitrary sizes.
- Icon-only buttons require tooltip and aria-label.
- Use chevrons consistently for dropdown/expand.
- Use spinner only where work is local to that control or row.
- Use semantic icons for object type: folder, git, terminal, browser, review, plugin, file, warning.

## State Colors

Do not invent a new accent for every state.

| State | Visual treatment |
| --- | --- |
| hover | transient list background |
| selected | persistent selection; observed `SelectableListRow` may share the active-selection token with hover |
| active/open | open-state background on trigger |
| disabled | opacity + cursor + reason tooltip where useful |
| loading | spinner/progress near object |
| danger | red token with low-opacity background |
| warning | warning icon + inline message |
| success | object state or subtle confirmation, not celebration |
| diff added | git added token |
| diff removed | git removed token |

## Motion

Use motion to preserve spatial continuity, not to decorate state changes:

- external home footer slides in/out quickly.
- panel reveal shows source direction.
- selected command scrolls into view.
- diff numbers may roll.
- resizers track the pointer continuously.
- reversible panels start from their current on-screen state and remain interruptible.
- opening and closing follow the same spatial path.

Avoid:

- page route fades.
- scroll reveal.
- decorative bouncing.
- motion that hides state changes.

Reduced motion:

- Observed app preference is `system | on | off`; `system` follows `(prefers-reduced-motion: reduce)`.
- keep state changes.
- remove large movement and bounce.
- use direct opacity/border/text changes.
- preserve focus, selection, progress, and completion feedback.

Reduced transparency and contrast:

- Honor `prefers-reduced-transparency` where the platform exposes it; replace blur with a more opaque surface.
- Honor `prefers-contrast: more`; strengthen borders and text without introducing decorative color.
- Do not make essential hierarchy depend on blur, transparency, or motion.

## Typography Accessibility

- Prefer the platform system font and enable optical sizing when supported.
- Define tracking and leading by text role; do not apply one letter-spacing value to every size.
- Use relative units where text scaling must reflow the layout.
- Keep dense metadata readable under user zoom and increased text size.
- Preserve full values through tooltip, copy, or inspector when truncation is necessary.

## Visual QA

- No page reads as a single-hue theme.
- Main work area is not drowned by decorative color.
- Text in controls does not overflow.
- Long paths and branch names truncate predictably.
- Hover, selected, active, disabled differ.
- Dark mode keeps contrast for metadata and borders.
- Real data still fits without card sprawl.
- Reduced motion removes large movement without hiding state feedback.
- Increased text size and window zoom do not make primary actions unreachable.
