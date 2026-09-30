# Shell Layout

Use these patterns when building the desktop window, sidebar, settings page, side panel, bottom panel, or task workspace.

## Contents

- Desktop read defaults
- Primary workbench zones
- Responsive shell behavior
- Home/start and sidebar
- Right and bottom panels
- Settings and app-shell tabs
- Hidden runtime hosts
- Reproduction checklist

Unless marked Recommended, concrete Codex dimensions in this file are Observed in desktop build `26.623.70822`.

## Desktop Read Defaults

```text
platform: cross-platform desktop, with Electron-native affordances where available
app_archetype: AI developer workbench
session_context: long-running work, frequent switching, background execution
density: dense
primary_interaction: keyboard-first with mouse and drag/drop support
anti_pattern: web dashboard, landing page, card grid, route-only app
```

## Primary Workbench Zone Map

Build the primary window as zones, not as pages:

| Zone | Purpose | Rules |
| --- | --- | --- |
| Title/toolbar | window identity, global actions, panel toggles | short labels, icons with tooltips, no hero text |
| Left sidebar | projects, threads, pinned work, cloud/local groups | persistent selection, scroll memory, drag/drop, keyboard shortcuts |
| Main workspace | conversation, task timeline, editor, artifact preview, current object | widest zone, no decorative cards, states inline |
| Composer/footer | task input, context, mode, permissions, submit/stop | sticky near bottom or primary work area |
| Right panel | files, browser, review, side chat, artifacts, inspector | tabbed, closable, may be empty with new-tab affordance |
| Bottom panel | terminal, logs, output, background processes, diagnostics | add only for ongoing output; resizable, stateful, tabbed when needed |
| Status area | host, project, sync, background work, rate limit, errors | compact and close to affected object |

## Responsive Shell Behavior

Observed shell thresholds:

- Narrow shell: `960px`.
- Very narrow shell: `720px`.
- At `960px`, collapse competing chrome only when the left panel is docked and a right panel exists.
- At `720px`, return right-panel focus to main, exit right-panel maximization, close the review file tree, and close an open sidebar.
- Preserve the main work surface before navigation width.
- Support docked and floating sidebar lifecycles instead of treating collapse as a Boolean visual toggle.
- Reveal the collapsed floating sidebar from the left `0–12px` edge zone or trigger hover; keep it visible while the pointer remains inside the panel.
- Persist user-resized panel widths; clamp them again when available width changes.
- Keep full-width right-panel mode distinct from regular split mode.
- Respect title-bar safe areas, window zoom, application-menu chrome, and reduced motion.

Use these thresholds only for exact reproduction. For adaptation, choose breakpoints from the target content and verify the same lifecycle transitions.

## Home/Start Surface

Use for starting a task, not explaining the product.

Required:

- Center the composer as the primary action.
- Show current project/workspace context in or near the composer.
- Provide suggestions below or above the composer, but keep focus on input.
- Keep announcements and plan/upgrade notices as banners, not main content.
- If a side panel is open full-width, move composer to the side-panel footer or compact overlay.

Avoid:

- hero copy, split marketing layout, giant logo-only first screen.
- unrelated feature cards.
- forcing project selection before the user can type unless execution truly requires it.

## Sidebar Pattern

The sidebar is long-term work memory.

Required structure:

- Pinned work at top.
- Project or connection groups next.
- Projectless chats or recent threads after grouped work.
- Cloud/remote work separated when it has different lifecycle.
- Footer for account/settings/status only.

Required behavior:

- Persist scroll by sidebar mode.
- Allow keyboard shortcuts for top threads.
- Recommended: persistent selected state must remain unmistakable after hover ends.
- Dragging between containers must confirm if it changes worktree/project ownership.
- Loading state is inline spinner inside the list body, not full-window takeover.

Row grammar:

```text
[icon/status] [title truncated]
              [secondary metadata: project/host/time/status]
                                        [trailing chip: PR, running, error]
```

## Right Panel Pattern

Use the right panel for inspectable or parallel work:

- Files and file previews.
- Browser tabs and browser automation state.
- Review panels and changed files.
- Side chat.
- Artifact preview.
- Current-object inspector.

Rules:

- Right panel is tabbed when more than one object type can be open.
- Empty state must show what can be opened next.
- The panel toggle is part of header chrome, not buried in content.
- Local threads can open many panel types; remote threads may expose fewer actions.
- Browser tab titles may sync asynchronously; keep fallback titles.

## Bottom Panel Pattern

Use the bottom panel for output that belongs below the main work:

- terminal
- logs
- background processes
- test output
- diagnostics
- queue/process monitor

Rules:

- Default collapsed unless there is active output or user opened it.
- Resizable with visible drag handle.
- For the main App Shell, default height is `280px`; clamp with `max(160, min(height, availableHeight × 0.5))` and persist the result.
- A separate portal-style utility panel uses `200px…80vh`; do not apply that contract to the main App Shell.
- Opening/closing must not lose scroll context in the main thread.
- If panel height changes, synchronize main scroll enough to keep recent content visible.

## Settings Window Pattern

Settings is a governance surface.

Required structure:

- Left navigation grouped by intent: Personal, Integrations, Coding, Archived.
- Optional host filter at top when local/remote settings differ.
- Search input in the navigation panel.
- Right content panel with focused forms.
- Escape returns to previous app route unless focus is inside text editing or dialog.
- A recognized settings section that is currently hidden redirects to the first visible section after visibility checks finish.

Settings row grammar:

```text
[label]                    [control]
[short description or risk]
[inline error/recovery if needed]
```

Do not:

- turn settings into card walls.
- hide dangerous actions among normal preferences.
- mix host-scoped settings with global settings without a visible host selector.

## App Shell Tabs

Use tabs for persistent parallel work inside side/bottom panels or project previews.

Required:

- Active tab id.
- Stable tab id.
- Preview tab support.
- Pin preview on first pointer or keyboard interaction.
- Error boundary per panel, with retry.
- Workspace-not-ready placeholder if content depends on provisioning.
- Tab context menu for close, close others, close right, move when supported.
- One preview tab per controller; opening a new preview replaces the current preview.
- Preserve activation history so closing or moving the active tab selects the most useful remaining tab.
- Preserve tab-local state when moving a tab between right and bottom panels.
- Restore panel focus after activation when the previous active tab owned focus.

Do not use tabs to replace simple filters or a small segmented control.

## Hidden Runtime Hosts

Use hidden hosts only when a live runtime must survive navigation:

- browser-use automation tabs
- background browsing
- long-running preview/runtime frame

Rules:

- Key hidden hosts by owning conversation or tab id.
- Mount lazily.
- Keep visible UI state separate from runtime lifetime.
- Do not add hidden hosts for static content.

## Layout Reproduction Checklist

- The primary workspace is the largest visible zone.
- The user can start a task without navigating away.
- Sidebar selection and panel tabs survive normal navigation.
- Empty states are local to the zone that is empty.
- Every resizable area has min/max and narrow-window behavior.
- The shell changes correctly at `960px` and `720px` without hiding the primary action.
- Docked and floating sidebar states preserve width, focus, and open/close intent.
- Main bottom-panel height follows `max(160, min(height, availableHeight × 0.5))`, persists, and re-clamps after resize.
- Remote/local host differences are visible where actions are affected.
- There is no route-only mental model: tabs, panels, and hidden hosts have their own lifecycle.
