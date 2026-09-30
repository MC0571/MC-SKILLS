# Interaction Patterns

Use these patterns for prompt input, command menus, search, keyboard handling, drag/drop, context menus, and long-running task control.

## Contents

- Composer command center and states
- Keyboard state machine
- Mentions, suggestions, and command rows
- Search and native context menus
- Drag/drop and paste
- Long-running task controls
- Interaction QA

Treat shortcut details as Observed for Codex Desktop `26.623.70822`; adapt them only when the target platform or editor contract requires it.

## Composer As Command Center

The composer owns five decisions:

1. What the user asks.
2. Where it runs: project, cwd, host, local/remote/cloud.
3. What context is attached: files, selected text, images, appshots, plugins, prior threads, PR checks.
4. What mode is active: default, plan, cloud/local, reasoning/service tier, permissions.
5. What happens now: submit, stop, queue, steer, approve, resume goal.

Required composer zones:

```text
above tray: queued messages, goal banner, background threads, approval, rate limit, plugin suggestions
surface: attachments + prompt input + inline controls
footer: context button, project/host, permissions, mode/runtime controls, dictation, submit/stop
external footer: extra home controls or templates
below: optional templates/suggestions/artifact actions
```

## Composer States

Implement these states explicitly:

| State | UI requirement |
| --- | --- |
| empty | submit disabled with tooltip or blocked reason |
| has text | submit enabled, shortcut visible |
| drag active | surface highlight plus drop overlay |
| attachments present | pills above input, removable and openable |
| response in progress | submit becomes stop, or queue/steer option appears |
| queue available | running task accepts queued message |
| approval pending | approval panel replaces normal composer input |
| rate limited | banner near composer, not global modal |
| dictating | recording footer replaces normal controls |
| transcribing | dictation button/loading state |
| goal active | goal banner above composer |
| blocked submit | show reason close to submit button |

## Keyboard State Machine

Do not bind keys directly to one action without state checks.

Escape priority:

1. Abort dictation if dictating.
2. Close active mention/search/menu popover.
3. Confirm stop if stop confirmation is visible.
4. Stop running turn if response is in progress and composer owns focus.
5. Focus composer if focus is elsewhere in the thread.
6. Navigate back only on settings or modal-free pages and only if target is not text-editing.

Primary submission policy:

- `enter`: Enter submits according to the editor contract.
- `cmdIfMultiline`: Enter submits single-line content; Cmd/Ctrl+Enter submits multiline content.
- `cmdAlways`: Cmd/Ctrl+Enter submits.

Running local follow-up policy:

| Enter behavior | Queue/steer shortcut |
| --- | --- |
| `enter` | Cmd/Ctrl+Enter |
| `cmdIfMultiline` | Cmd/Ctrl+Shift+Enter |
| `cmdAlways` | Cmd/Ctrl+Shift+Enter |

Map the running follow-up action from current queueing state. Keep this separate from the primary submission keymap.

Other keys:

- Tab respects active mention/menu first.
- Arrow keys in suggestion/search lists move highlight.
- Cmd/Ctrl+A inside dropdown search selects input text, not menu items.
- Escape in search clears query before closing parent.

## Mention And Context Model

Treat `@` as "add context", not only people mention.

Supported mention kinds:

- file or folder
- skill
- plugin
- app / MCP app
- MCP resource
- previous conversation
- background agent/thread

Mention behavior:

- Menu state belongs to the editor plugin.
- Selection stores highlighted item separately from query text.
- Selecting an item can insert mention, replace query, open submenu, or complete query.
- Activating an existing mention opens the target: file side panel, skill file, plugin route.
- Query range and replacement range must be tracked so insertion is precise.

## Suggestion List Pattern

Required:

- Sectioned results.
- Disabled rows excluded from keyboard navigation.
- First item can auto-highlight, but do not steal focus from text input.
- Selected item scrolls into view.
- Loading pulse at edge of list.
- No-results row only after loading resolves.
- Home composer menu has viewport-aware max height.

Row grammar:

```text
[left icon/accessory] [title with highlighted query] [description/right accessory]
                      [secondary content if needed]
```

## Slash Command / Command Row Pattern

Command rows must support:

- title
- description
- left icon/accessory
- right icon/accessory
- secondary content
- search highlight
- overflow tooltip
- selected-row scroll into view

Search matching:

- Dim non-matching title segments when there is a match.
- Truncate visible title/description near 100 chars.
- Use tooltip only when overflow or explicit tooltip content exists.

## Search Pattern

Page search:

- icon at leading edge.
- sr-only label.
- clear button appears only when query is non-empty.
- trailing control allowed but always `shrink-0`.
- input uses `min-w-0 flex-1`.

Dropdown search:

- autofocus on open.
- stop propagation for text editing keys.
- Cmd/Ctrl+A selects input text.
- ArrowDown/ArrowUp moves focus to menu item if possible.
- Search row uses same menu row padding variables as items.

Settings search:

- Search visible only in grouped, expanded navigation.
- Results use keyboard list navigation.
- Escape clears search.
- Only visible settings sections are searchable.

## Native Context Menu Pattern

Use one menu item data model and render it through native or web:

```text
id
type: item | checkbox | separator
message/nativeLabel
enabled
checked
icon
tooltip
submenu
onSelect
```

Electron behavior:

- Prefer `window.electronBridge.showContextMenu`.
- Resolve localized labels before sending native menu.
- Await `onBeforeOpen` when menu items depend on current state.
- Dispatch pointercancel before native menu opens.
- After native selection, find item by id and run `onSelect`.

Web fallback:

- Use Radix context menu.
- Same items and disabled rules.
- Support submenu, checkbox, tooltip, separator.
- Apply window zoom.

## Drag And Drop / Paste

Composer drag/drop must handle:

- file drops
- directory entries
- images
- browser dragged images from hidden/side browser
- pasted image files
- pasted non-image files

Rules:

- Detect supported drag before changing UI.
- Increment/decrement a drag counter to avoid flicker.
- Show copy drop effect.
- Shift can alter overlay/instruction if supported.
- Reset drag state on drop.
- Add images to image attachments; other files become file mentions.
- Directory-only drops still trigger file mention flow.

## Long-Running Task Controls

A desktop AI task may continue while the user types.

Required:

- Stop button when response is streaming.
- Stop confirmation for destructive interruption if needed.
- Queue mode when new input should run after current turn.
- Steer mode when input should influence current turn.
- Background thread rows if subagents/background tasks exist.
- Approval surface replaces input when action requires permission.
- Toast is secondary; main status must be inline.

Behavior contract:

| State | Event | Guard | Effect |
| --- | --- | --- | --- |
| running | stop | stoppable | enter stopping; preserve draft |
| running | submit follow-up | queue mode | queue next work |
| running | submit follow-up | steer mode | steer current work |
| approval pending | approve/deny | request still current | resolve request; return focus |
| interrupted queue | resume | host/task available | continue queued work |

Do not infer queue/steer semantics from a button label alone; bind them to the actual running-task state.

## Interaction QA

- Can the user complete the primary flow without mouse?
- Does Escape do the least surprising state-specific action?
- Can a running task be stopped, queued, or steered?
- Does search keep focus and still allow arrow navigation?
- Are disabled commands discoverable with reasons?
- Does right-click show native menus in Electron?
- Does drag/drop show valid target and clear state after failure?
- Do running shortcuts match the configured Enter behavior, including the Shift modifier?
- Does focus return to the composer or active work surface after stop, approval, menu close, and tab change?
