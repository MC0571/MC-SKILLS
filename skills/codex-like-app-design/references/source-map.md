# Source Map

Use this provenance appendix for exact reproduction, source audits, or updating Observed claims.

## Contents

- Baseline and evidence labels
- Core shell
- Composer and interaction
- Thread progress and results
- UI components
- Design signals and contract distinctions

Baseline:

- Codex Desktop package: `openai-codex-electron` `26.623.70822`.
- Remote repository: [JimLiu/decode-codex](https://github.com/JimLiu/decode-codex).
- Pinned restored-source commit: [`d0540b9f25c639a53cb14be9c0036981761e9aac`](https://github.com/JimLiu/decode-codex/tree/d0540b9f25c639a53cb14be9c0036981761e9aac/restored).
- Review date: `2026-07-16`.

All source paths below are relative to the pinned remote `restored/` directory. Resolve a path with:

```text
https://raw.githubusercontent.com/JimLiu/decode-codex/d0540b9f25c639a53cb14be9c0036981761e9aac/restored/<path>
```

Do not assume a local `decode-codex` or `restored` checkout exists.

Evidence labels used by this skill:

- **Observed** — verified against a locator below in the baseline build.
- **Inferred** — generalized across observed implementations.
- **Recommended** — portable design guidance; not a source claim.

The remote restored source is a reverse-engineered artifact and may contain semantic renaming or partial reconstruction. Re-verify exact values when the app build or pinned commit changes.

## Core Shell

| Pattern | Source |
| --- | --- |
| Home page as work launcher | `home/home-page/home-page-body.tsx` |
| Thread chrome entry | `app-shell/thread-app-shell-chrome/index.tsx` |
| Right panel chrome | `app-shell/thread-app-shell-chrome/right-panel-chrome.tsx` |
| Bottom panel chrome | `app-shell/thread-app-shell-chrome/bottom-panel-chrome.tsx` |
| Panel tab list / new tab model | `app-shell/thread-app-shell-chrome/panel-tab-list.tsx`, `app-shell/thread-app-shell-chrome/new-tab-model.tsx` |
| App shell tabs and preview pinning | `app-shell/app-shell-tabs.tsx` |
| Tab controller lifecycle, history, move/reorder | `app-shell/app-shell-tab-controller/controller.ts` |
| App shell slot system | `app-shell/app-shell-slots/**`, `app-shell/side-panel-slots.tsx` |
| Responsive shell thresholds and floating sidebar | `app-shell/app-shell-layout.tsx` |
| Main bottom-panel clamp and persistence | `app-shell/bottom-panel-height.ts` |
| Sidebar thread/project list | `sidebar/sidebar-thread-list.tsx` |
| Hidden webview hosts | `sidebar/hidden-webviews.tsx` |
| Settings split page | `settings/settings-page-current/settings-page.tsx` |
| Settings navigation groups | `settings/settings-page-current/navigation-groups.ts` |
| Settings search targets | `settings/settings-page-current/settings-search-targets.ts` |

## Composer And Interaction

| Pattern | Source |
| --- | --- |
| Composer compound component | `composer/composer.tsx` |
| New thread composer body | `composer/new-thread-composer-body-view.tsx` |
| Composer footer controls | `composer/composer-footer-controls.tsx` |
| Composer keyboard state machine | `composer/use-new-thread-composer-keyboard.ts` |
| Composer follow-up queue/steer mode | `composer/composer-runtime-controls/follow-up-mode.ts` |
| Escape guards in raw restored backing | `appgen/library-hot-current-runtime-backing.ts` |
| Mention autocomplete | `composer/mention-autocomplete.ts` |
| Suggestion list | `composer/composer-suggestion-list/composer-suggestion-list.tsx` |
| Drag/drop/paste context actions | `composer/use-composer-context-actions.ts` |
| Project selector | `composer/project-selector/project-selector.tsx` |
| Attachment pills | `composer/attachment-pill.tsx`, `composer/composer-attachment-pills.tsx` |

## Thread Progress And Results

| Pattern | Source |
| --- | --- |
| Visible turn filtering, request grouping, and merged display turns | `conversations/local-conversation-thread-parts/local-conversation-visible-turn-entries.ts` |
| Stable turn-row assembly, collapse state, generated output, and completed-goal attachment | `conversations/local-conversation-thread-parts/local-conversation-turn-list-entries.ts` |
| Thread content, virtualization integration, and current-turn placement | `conversations/local-conversation-thread-parts/local-conversation-thread-content.tsx` |
| Auto-follow and scroll restoration | `conversations/local-conversation-thread-parts/local-conversation-auto-follow-turn-list.tsx` |
| Artifact and rendered output collection | `runtime/conversation-artifact-runtime.ts` |
| Summary-panel artifacts, plans, background work, side chats, and tool sources | `conversations/local-conversation-thread-parts/local-conversation-summary-panel-model.ts` |

## UI Components

| Pattern | Source |
| --- | --- |
| Button variants | `ui/button.tsx` |
| Popover wrapper | `ui/popover.tsx` |
| Modal host | `ui/modal-renderer.tsx` |
| Context menu native/fallback | `ui/context-menu.tsx` |
| Selectable list row | `ui/selectable-list-row.tsx` |
| Thread resource card | `ui/thread-resource-card.tsx` |
| Page search input | `ui/page-search-input.tsx` |
| Dropdown search input | `ui/dropdown/search.tsx` |
| Slash command item | `ui/slash-command-item/index.tsx` |
| Keyboard keycap | `ui/keyboard-shortcut-keycap.tsx` |
| Diff stats | `ui/diff-stats.tsx` |
| Utility portal bottom panel | `ui/resizable-bottom-panel.tsx` |
| Settings row/content layout | `ui/settings-row.tsx`, `ui/settings-content-layout.tsx` |

## Design Signals To Preserve

- `token-*` colors for surfaces, text, border, input, list hover/selection, git diff, status.
- `icon-*` sizes instead of arbitrary SVG dimensions.
- `min-w-0`, `truncate`, `shrink-0`, `tabular-nums`, `focus-visible:*`, `select-none`, `no-drag`.
- `electron:*` and `extension:*` platform modifiers at shell/component boundaries.
- Radix-style primitives for popover/dropdown/context menu when native platform API is unavailable.
- App-scope or shell-scope state for modals, panels, tabs, scroll positions, and hidden webviews.

## Known Contract Distinctions

- Main App Shell bottom panel: `app-shell/bottom-panel-height.ts`, default `280px`, clamped with `max(160, min(height, availableHeight × 0.5))`, persisted.
- Portal utility bottom panel: `ui/resizable-bottom-panel.tsx`, initialized at half the viewport and clamped to `200px…80vh` while mounted.
- `SelectableListRow` currently uses the active-selection background token for both selected and hover; stronger persistent selection is Recommended, not Observed.
- Running queue/steer shortcuts differ by Enter behavior: Cmd/Ctrl+Enter for `enter`; Cmd/Ctrl+Shift+Enter for `cmdIfMultiline` and `cmdAlways`.
- The Button API includes compatibility forms `variant` and `icon-sm` in addition to the primary documented props.
- Exact Escape reproduction must check `appgen/library-hot-current-runtime-backing.ts`; the semantic keyboard helper omits some raw guards such as `canStopFromEscape`.
