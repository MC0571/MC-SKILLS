# Implementation QA

Use this before finalizing any UI built with this skill.

## Contents

- Build preflight and implementation order
- State and keyboard checks
- Progress and task-summary checks
- Visual, native, performance, and accessibility checks
- Source-accurate contract checks
- Evidence format

Write important checks as `setup → action → expected state → negative assertion → evidence`. A checklist item without an observable result is not verification.

## Build Preflight

Confirm:

- Target platform and shell: macOS, Windows, or cross-platform desktop.
- Surface type: home, primary workbench, settings, side panel, bottom panel, utility.
- Density: calm, standard, dense, or control-room.
- Primary input path: keyboard-first, mouse-first, command-first, drag/drop, multi-pane.
- Existing project component library and tokens.
- Required states: empty, loading, running, disabled, selected, error, rate-limited, approval, offline.

## Implementation Order

1. Build layout zones.
2. Reuse or confirm primitive components; add only what the flow proves missing.
3. Build domain rows/panels.
4. Add keyboard and focus behavior.
5. Add real data states.
6. Add native platform bridges or fallbacks.
7. Verify visually and interactively.

Do not style a page before the zone map is correct.

## Required States Checklist

For each main object list or panel, implement and verify every state the object can actually enter. Do not manufacture impossible loading, empty, permission, or error states. Common applicable states are:

- empty
- loading
- loaded with one item
- loaded with many items
- selected
- disabled/unavailable
- error with recovery
- long text overflow
- no permissions or unavailable host if relevant

Composer-like surfaces must include:

- empty submit
- text submit
- attachments
- drag active
- response in progress
- stop
- queue/steer
- approval pending
- blocked submit reason
- rate limit or quota banner

## Keyboard QA

Check manually or with tests:

- Tab order enters toolbar, sidebar, main list, composer, side panel.
- Arrow keys navigate menus/lists where expected.
- Enter/Space activates rows.
- Escape follows state hierarchy.
- Cmd/Ctrl+Enter or Enter follows configured submit policy.
- Search input keeps focus while results update.
- Dropdown search ArrowDown moves to first menu item.
- Context menu opens from keyboard where supported.
- Focus returns after popover/modal/menu closes.
- In a running local task, `enter` mode uses Cmd/Ctrl+Enter for queue/steer.
- In a running local task, `cmdIfMultiline` and `cmdAlways` use Cmd/Ctrl+Shift+Enter for queue/steer.

## Visual QA

Check at minimum:

- 1440x900 desktop.
- 1024x768 compact desktop.
- A narrow side panel state.
- Widths immediately above and below `960px` and `720px` for exact reproduction.
- Dark mode if supported.
- Long project/thread/file names.
- 100+ rows in sidebar/list/table.
- Empty settings section.
- Error banner and disabled controls.

Fail conditions:

- text overlaps or escapes controls.
- buttons resize layout when loading.
- selected row only visible on hover.
- toolbar labels crowd out search/status.
- nested cards or decorative page sections dominate.
- main workspace is visually smaller than navigation/decor.

## Native Feel QA

- Window drag regions are not broken by controls.
- `no-drag` is applied to interactive controls inside draggable chrome.
- Context menus are native in Electron when bridge exists.
- Web fallback context menu works without Electron.
- Popovers respect window zoom and viewport bounds.
- Splitters/resizable panels have visible hover/active states.
- Platform shortcut labels use Cmd on macOS and Ctrl on Windows.
- System font stack and theme tokens are used.

## Performance And Robustness

- Lazy load heavy panels and hidden runtime hosts.
- Keep hidden webviews only for live runtime continuity.
- Do not unmount long-running background state on route change.
- Keep row components cheap; lists may need virtualization for large data.
- Avoid animation on every row update.
- Preserve scroll position where users return often.

## Accessibility QA

- Every icon-only action has an accessible name; tooltips are supplementary.
- Focus remains visible and returns after menu, popover, modal, tab, approval, and stop transitions.
- Reduced motion removes large movement and bounce without hiding progress or selection.
- The `system | on | off` reduced-motion preference overrides or follows the OS setting correctly.
- Increased text size and window zoom preserve primary actions and readable metadata.
- High-contrast and reduced-transparency modes do not erase shell or state hierarchy.
- Streaming, approval, error, and completion changes are announced where screen-reader users need them.

## Progress And Summary QA

- A stable intermediate step updates in place instead of appending duplicate rows for every status event.
- Running, waiting, failed, cancelled, and completed states remain distinguishable without color alone.
- Raw logs and repetitive operations stay available but do not overpower meaningful milestones and results.
- Scrolling away from the live edge stops auto-follow and exposes a new-activity action.
- Completion, partial completion, failure, cancellation, and blocking each produce an honest terminal summary.
- A summary leads with outcome and omits empty changes, evidence, risk, or next-action sections.

## Source-Accurate Contract Checks

Run these only for exact Codex reproduction:

| Setup | Action | Expected | Negative assertion |
| --- | --- | --- | --- |
| viewport above/below `960px` | resize across threshold | sidebar changes docked/floating behavior | main action does not disappear |
| viewport above/below `720px` | resize across threshold | very-narrow shell behavior activates | work surface is not compressed below use |
| sidebar collapsed | enter left `0–12px` edge zone or hover trigger | floating sidebar reveals and remains while pointer is inside | docked sidebar state does not change |
| main bottom panel open | drag resize handle | height follows `max(160, min(height, availableHeight × 0.5))` and persists | utility `200px…80vh` contract is not applied |
| one preview tab open | open another preview | prior preview closes | pinned tabs remain |
| preview tab active | pointer/key interaction | preview pins | pin-exempt interaction does not pin |
| panel owns focus | activate another tab | focus moves to new panel | focus is not lost to document body |
| running local task | use follow-up shortcut | queue or steer follows current state | primary submit binding is not triggered |

## Evidence Format

Report:

```text
Done:
- <implemented surfaces/components>

Evidence:
- <command, test, or screenshot path>
- <viewport/state checked>
- <Codex version/source locator for Observed claims>

Risks:
- <unverified platform/state, or none>
```

For design-only deliverables, replace command evidence with:

```text
Design QA:
- layout zones checked
- component inventory checked
- interaction contract checked
- long-data stress cases checked
```
