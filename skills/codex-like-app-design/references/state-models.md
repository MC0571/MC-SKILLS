# State Models

Use these portable state models to describe mature behavior without copying Codex internals.

**These types are Recommended reference models, not restored source APIs.** Codex uses scoped signals, signal families, controllers, host persistence, and route/app/thread ownership that cannot be represented faithfully by one aggregate object.

## Contents

- Portable shell and composer models
- Suggestion and running-task lifecycle
- Panel-tab behavior contract
- Settings and native context-menu models
- Persistence contract

When exact reproduction matters, use the behavioral contracts and source locators in `source-map.md`; do not implement these type aliases verbatim.

## Shell State

```ts
type ShellState = {
  route: RouteState;
  sidebar: SidebarState;
  rightPanel: PanelState;
  bottomPanel: PanelState & { heightPx: number };
  hiddenRuntimeHosts: HiddenRuntimeHost[];
  modalStack: ModalDescriptor[];
  windowZoom: number;
};

type SidebarState = {
  mode: "codex" | "work" | "chatgpt" | string;
  scrollTopByMode: Record<string, number>;
  selectedThreadId?: string | null;
  selectedProjectId?: string | null;
  collapsedGroups: string[];
};

type PanelState = {
  open: boolean;
  activeTabId?: string | null;
  tabs: PanelTab[];
};

type PanelTab = {
  tabId: string;
  kind: "file" | "browser" | "terminal" | "review" | "artifact" | "side-chat" | "process" | string;
  title: string;
  isPreview?: boolean;
  isClosable: boolean;
  state?: unknown;
};
```

Rules:

- Shell state belongs above routes.
- Route changes can change main content but must not destroy panel tabs, modal stack, or hidden runtime hosts.
- Preview tabs pin on first keyboard or pointer interaction inside the tab panel.
- Bottom panel height is stateful and clamped.
- Sidebar scroll is restored by mode.

Observed Codex behavior is more granular:

- Panel controllers own thread-scoped tab ids, tab records, active id, activation history, and tab-local state separately.
- Opening a preview replaces the current preview unless the existing tab has already been pinned.
- Activating a tab may restore focus into the new panel.
- Reordering keeps tab identity and local state.
- Moving between right and bottom controllers transfers state, applies an optional move patch, and updates the active surface.

## Composer State

```ts
type ComposerState = {
  text: string;
  layout: "single-line" | "multiline" | "auto-single-line";
  mode: "local" | "cloud" | string;
  collaborationMode: "default" | "plan" | string;
  executionTarget: {
    hostId: string;
    cwd?: string | null;
    projectId?: string | null;
  };
  attachments: WorkContextAttachment[];
  pendingAttachments: WorkContextAttachment[];
  suggestionMenu?: SuggestionMenuState;
  submitState: SubmitState;
  voiceState: VoiceState;
  dragState: DragState;
  approval?: ApprovalState | null;
  banners: ComposerBanner[];
};

type SubmitState =
  | { kind: "empty"; blockedReason: "empty-message" }
  | { kind: "ready" }
  | { kind: "submitting" }
  | { kind: "running"; canStop: boolean; queueMode: "queue" | "steer" }
  | { kind: "stopping" }
  | { kind: "blocked"; reason: string };

type VoiceState =
  | { phase: "inactive"; supported: boolean }
  | { phase: "dictating"; durationMs: number }
  | { phase: "transcribing" }
  | { phase: "error"; canRetry: boolean };

type DragState = {
  active: boolean;
  counter: number;
  supported: boolean;
  showShiftOverlay: boolean;
};
```

Rules:

- Submit button derives entirely from `submitState`.
- Attachments and pending attachments render separately.
- Approval state can replace normal composer input.
- Banners render above composer and are local to the affected thread/task.
- Voice footer can replace normal footer while dictating.

## Suggestion Menu State

```ts
type SuggestionMenuState = {
  active: boolean;
  kind: "at-mention" | "skill-mention" | "slash-command" | "project-search" | string;
  query: string;
  range: { from: number; to: number };
  source?: string;
  highlightedKey?: string | null;
  sections: SuggestionSection[];
};

type SuggestionSection = {
  id: string;
  title?: string;
  isLoading?: boolean;
  showTitle?: boolean;
  items: SuggestionItem[];
  emptyState?: string;
};

type SuggestionItem = {
  key: string;
  content: unknown;
  disabled?: boolean;
  action: "insert" | "complete-query" | "open-submenu" | "navigate";
};
```

Rules:

- Disabled items render but are skipped by keyboard navigation.
- Query range and replacement range must be stable.
- Highlighted item is cleared when menu closes.
- No-results state waits until loading sections resolve.

## Running Task Lifecycle

```text
idle
  -> submitting
  -> running
running
  -> stopping -> idle
  -> approval-pending -> running
  -> queued-input -> running
  -> error -> idle/retry
  -> complete -> idle
```

UI mapping:

- `submitting`: submit button spinner, composer disabled only where needed.
- `running`: stop button, queue/steer shortcuts, background rows if any.
- `approval-pending`: approval panel with actor, request, host/cwd, approve/deny/follow-up.
- `queued-input`: queued message tray with edit/delete/send-now/reorder.
- `error`: inline banner or panel row with retry.
- `complete`: update object state, do not rely only on toast.

## Panel Tab Lifecycle

```text
closed
  -> preview(opened by hover/search/quick open)
preview
  -> pinned(on interaction)
  -> closed(on blur/replacement)
pinned
  -> active
  -> inactive
  -> moved(right <-> bottom if supported)
  -> closed
```

Rules:

- Preview tabs reduce clutter but must pin on meaningful interaction.
- Active tab content has error boundary.
- Workspace-dependent content shows "available when ready" placeholder.
- Empty panel shows new-tab menu or suggested actions.

Behavior contract:

| State | Event | Guard | Effect | Focus |
| --- | --- | --- | --- | --- |
| closed | open preview | no same-id tab | replace current preview; activate panel | focus panel |
| preview | pointer/key interaction | not pin-exempt | pin tab | keep current focus |
| active | activate another | target exists | update activation history | refocus if panel owned focus |
| active | close | close allowed | choose history or neighboring tab | focus replacement |
| open | reorder | both ids exist | reorder ids only | preserve focus |
| open | move controller | target lacks id | transfer record and local state | activate target when requested |

## Settings State

```ts
type SettingsState = {
  activeSection: SettingsSectionSlug;
  visibleSections: SettingsSection[];
  selectedHostId: string | null;
  searchQuery: string;
  searchResults: SettingsSearchResult[];
  returnRoute: unknown;
  splitLeftPanelVisible: boolean;
};
```

Rules:

- A recognized section that is currently hidden redirects to the first visible section. Do not claim that unknown routes share this behavior unless the target router proves it.
- Host filter changes visible/available settings.
- Search only returns visible sections.
- Escape returns to `returnRoute` unless target is input, textarea, select, contenteditable, or open dialog.
- Profile image picker or native actions may intercept section selection.

## Native Context Menu State

```ts
type ContextMenuItem =
  | { type?: "item"; id: string; label: string; enabled?: boolean; icon?: string; tooltip?: string; onSelect?: () => void; submenu?: ContextMenuItem[] }
  | { type: "checkbox"; id: string; label: string; checked: boolean; enabled?: boolean; onSelect?: () => void }
  | { type: "separator"; id: string };
```

Rules:

- Resolve labels before native menu open.
- Preserve ids across native and web rendering.
- Async `getItems` may temporarily show empty web menu; native should await if configured.
- Disabled items do not run `onSelect`.

## Persistence Contract

Treat this list as a Recommended product contract. Verify each item against the target application and storage owner; not every value belongs in one persisted object.

Persist:

- sidebar scroll by mode
- selected project/thread
- panel open/closed
- active panel tabs and tab-local state
- bottom panel height
- composer drafts by route/thread
- hidden runtime host ownership
- settings return route and selected host

Do not persist:

- transient hover
- current pointer drag coordinates
- popover open state after route change unless it is a command palette/search workflow
- stale errors after user changes the input that caused them
