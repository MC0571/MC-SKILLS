# Mature Capability Map

Use this as a core-workbench capability map, not a complete Codex Desktop product inventory. Select capabilities because the target product has the matching work object or lifecycle; do not implement the matrix as a feature checklist.

## Contents

- Capability matrix
- Minimum coherent surfaces
- Capability dependencies
- Portable product object model
- Mature behavior by surface
- Maturity rubric
- Coverage boundary

## Capability Matrix

| Capability | User value | Required surface | Mature behavior |
| --- | --- | --- | --- |
| Work launcher | Start useful work immediately | home/start composer | project-aware composer, suggestions, project switch, announcements, upgrade/quota banner if relevant |
| Project memory | Return to known work context | sidebar + project selector | local/remote project grouping, host label, cwd/repo display, pinning, clear/switch, loading state |
| Thread/task memory | Resume prior tasks | sidebar thread list | pinned/recent groups, running/error/PR chips, drag/drop assignment, scroll restore, keyboard shortcuts |
| Composer command center | Create and steer work | composer surface | prompt, attachments, context, permissions, modes, model/runtime controls, submit/stop/queue/steer |
| Context attachment | Give the agent useful local state | composer pills + mention menu | files, folders, images, selected text, appshots, prior threads, plugin context, PR checks |
| Runtime targeting | Decide where work executes | composer footer + settings | local/cloud/remote host, cwd, project, permissions, sandbox warnings, unavailable-state reasons |
| Long-running work | Keep tasks alive while user navigates | inline banners + background rows + panels | running state, stop, queue, steer, background thread rows, approval surfaces |
| Progress timeline | Understand what happened and what is active | main thread/task timeline | stable step identity, meaningful status transitions, grouped evidence, collapse, auto-follow without scroll theft |
| Task summary | Understand the outcome without rereading the timeline | terminal summary item | outcome first, relevant changes/artifacts, verification, unresolved risk, next action when needed |
| Approval and permission | Keep risky actions explicit | composer tray / request panel | pending request cards, clear actor, approve/deny/follow-up, host/cwd context |
| Right panel workspace | Inspect parallel objects | right side panel tabs | files, browser, review, side chat, artifact, inspector; empty state and new-tab menu |
| Bottom output panel | Observe execution outputs | bottom panel tabs | terminal, logs, process monitor, test output, diagnostics; resize and scroll sync |
| Browser/runtime continuity | Preserve live automation | hidden runtime hosts + panel tabs | per-conversation hidden webviews, persisted tabs, title sync, visible side panel control |
| Command/search layer | Jump and operate quickly | command palette/search inputs | sectioned results, keyboard navigation, overflow tooltips, file search, settings search |
| Native context actions | Operate on current object | native/web context menu | shared data model, async items, submenu, checkbox, disabled reason, native Electron bridge |
| Settings governance | Configure product safely | settings split view | grouped nav, search, host filter, scoped settings, inline validation, return route |
| Extension/plugin system | Add external capabilities | plugins/connectors/settings/composer | OAuth/connect states, installed state, tool labels, context suggestions, uninstall dialog |
| Review/diff workflow | Understand code changes | diff stats + review panels | added/removed counts, changed files panel, PR/review tabs, status chips |
| Artifact workflow | Inspect generated outputs | right panel / resource cards | file/image/app/website artifacts, preview/open/download/comment actions |
| Feedback and errors | Recover from failure | banners, inline errors, dialogs | local error placement, retry, blocked reason, rate-limit summary, no toast-only failures |
| Internationalization | Keep UI scalable | message descriptors + truncation | labels via i18n, locale-aware numbers, text overflow strategy |

## Minimum Coherent Surfaces

A coherent first release starts with the zones required by its primary flow:

```text
navigation, when work must be revisited:
  projects, pinned work, recent threads/tasks, running/error indicators

main workspace:
  active task timeline with intermediate steps, results, and terminal summary; or primary editor

composer:
  prompt, context attachments, project/host, permissions, runtime controls, submit/stop/queue

right panel, when parallel inspectable objects exist:
  files, artifacts, browser, review, side chat, or inspector

bottom panel, when ongoing output exists:
  terminal, logs, test output, diagnostics, or process monitor

settings, when configuration exceeds a local control:
  grouped settings, search, account/host/runtime/integrations/data controls
```

Do not add right/bottom panels, tabs, hidden runtimes, or global settings before their work objects require them.

## Capability Dependencies

For the capabilities selected by the target product, respect this dependency order and skip unselected branches:

1. Shell state and layout zones.
2. Project/thread object model.
3. Composer and submit lifecycle.
4. Context attachment model.
5. Running task lifecycle: idle, submitting, running, stopping, approval, error, complete.
6. Intermediate-step and task-summary presentation.
7. Right/bottom panels and tab state.
8. Search/command/context menu layer.
9. Settings governance.
10. Plugin/connector integration.
11. QA hardening: long text, dark mode, keyboard, empty/error, persistence.

## Product Object Model

Use this as a portable reference model even if names differ. It is not a restored Codex source API:

```ts
type WorkProject = {
  id: string;
  kind: "local" | "remote" | "cloud";
  label: string;
  hostLabel?: string;
  path?: string;
  repo?: string;
  pinned?: boolean;
  status?: "ready" | "loading" | "unavailable" | "error";
};

type WorkThread = {
  id: string;
  title: string;
  projectId?: string | null;
  hostId?: string | null;
  cwd?: string | null;
  pinned?: boolean;
  status: "idle" | "running" | "queued" | "approval" | "error" | "complete";
  updatedAt?: string;
  chips?: Array<"pr" | "review" | "terminal" | "browser" | "rate-limit" | "error">;
};

type WorkContextAttachment =
  | { kind: "file"; path: string; hostId?: string; line?: number }
  | { kind: "folder"; path: string; hostId?: string }
  | { kind: "image"; id: string; title?: string }
  | { kind: "selected-text"; source: string; text: string }
  | { kind: "appshot"; id: string; appName?: string }
  | { kind: "prior-thread"; threadId: string; title: string }
  | { kind: "plugin-context"; pluginId: string; label: string }
  | { kind: "pull-request"; repo: string; number: number; status?: string };
```

## Mature Behavior By Surface

### Sidebar

- Shows both identity and status.
- Supports pinned, grouped, and projectless work.
- Can display local and remote sources without mixing them silently.
- Preserves scroll and selected item.
- Supports context menu and drag/drop moves.

### Composer

- Can be used while work is running.
- Has explicit stop and queue/steer behavior.
- Shows blocked submit reason near submit.
- Accepts context by search, mention, paste, drag/drop, selected text, appshot.
- Keeps permissions and runtime target visible.

### Panels

- Right panel is for inspect/parallel objects.
- Bottom panel is for outputs/processes.
- Both are tabbed when multiple objects can exist.
- Empty panel tells the user what can be opened.
- Panel state persists across route changes.

### Settings

- Groups by user intent, not source folder.
- Searches across static and dynamic terms.
- Separates host-scoped settings from global settings.
- Has inline errors and dangerous action separation.

## Maturity Rubric

Score each product surface:

```text
0 absent: capability missing
1 visible: static UI exists, no full state model
2 usable: normal path works
3 mature: applicable empty/loading/error/disabled/keyboard/native/persistence behavior covered
4 Codex-grade: integrates with shell, context, settings, panels, and long-running tasks
```

Do not call a present surface mature until it reaches level 3. Target level 4 only for the composer, navigation, panels, settings, or command/search surfaces that the product actually includes.

## Coverage Boundary

This map covers the core launcher, project/thread memory, composer, context, panels, settings, extensions, review/artifacts, and recovery UI patterns. It does not define backend authorization, sandbox, terminal durability, event-replay, or process-reconnection guarantees. It also does not fully specify Automations, onboarding, Codex Mobile/Remote setup, downloads, desktop updates, notifications/inbox, OS-level window lifecycle, or every product route. Analyze those contracts or surfaces separately when they enter scope.
