---
name: codex-like-app-design
description: Design, build, adapt, or review dense desktop AI workbenches using source-grounded patterns from Codex Desktop. Use for workbench shells, home launchers, thread/task views, intermediate progress timelines, task summaries, composers, command/search interactions, settings, side or bottom panels, component systems, responsive desktop behavior, keyboard and focus contracts, persistent long-running work, or source-accurate reproduction of covered Codex UI patterns.
metadata:
  version: "0.2.0"
  category: "Developer Tools"
---

# Codex-like App Design

Build desktop AI workbenches that keep long-running work continuous, visible, and controllable while users switch projects, threads, hosts, routes, and panels.

## Core Idea

Treat continuity as the through-line. A Codex-style workbench succeeds when users can always answer:

1. Where am I, and where will this work run?
2. What is active, queued, blocked, or waiting for approval?
3. What context will travel with the next action?
4. How can I stop, redirect, resume, or recover without losing state?
5. What changed, what was verified, and what remains unresolved?

Serve four human needs:

- **Orientation** — show project, host, cwd, selection, and active work clearly.
- **Continuity** — preserve drafts, task state, scroll, tabs, and live runtimes across navigation.
- **Control** — provide keyboard parity and explicit submit, stop, queue, steer, approve, and deny paths.
- **Recovery** — place errors beside the affected object, explain blocked actions, and preserve a route back to useful work.

Density, native chrome, panels, and motion support these needs; they are not goals by themselves.

## Scope And Evidence

Use this skill as a **core workbench guide**, not as a complete inventory of every Codex Desktop product surface. Automations, onboarding, mobile/remote setup, downloads, updates, notifications, and platform window lifecycle require separate product analysis when requested.

This is an interface-design skill, not a runtime protocol specification. Approval authorization, sandbox enforcement, terminal session durability, event replay, and process reconnection must come from the target runtime contract; label any proposed behavior Recommended rather than attributing it to Codex.

Classify concrete claims before using them:

- **Observed** — verified in the pinned remote restoration of Codex Desktop `26.623.70822`. Preserve it for exact reproduction.
- **Inferred** — generalized from several observed implementations. Adapt it to the target product.
- **Recommended** — a design improvement or portable default. Do not present it as Codex source behavior.

For exact reproduction, load `references/source-map.md` and verify the observed contract against its pinned remote commit. Do not depend on a local restored-source checkout. Treat the portable types in `references/state-models.md` as reference models, not source APIs.

## Five Workbench Principles

### 1. Start From Work Objects

Identify the real objects before choosing layout: project, thread, task, step, result, evidence, summary, artifact, file, browser tab, terminal, review, connector, setting, account, or environment.

Give each object only the state its behavior requires:

- Actions: enabled, disabled with reason, pending, destructive, or failed.
- Resources: loading, ready, unavailable, stale, or failed.
- Collections: empty, loading, populated, filtered-empty, or failed.
- Selections: idle, hover, focused, selected, or active.

Do not manufacture loading, empty, or error states for static objects that cannot enter them.

### 2. Keep State Local And Visible

Place status beside the object it affects. Put rate limits near the composer, process state near the process, host availability near the host selector, and validation beside the control.

Use banners and inline rows for primary status. Use toasts only as secondary confirmation. Keep disabled actions discoverable with a reason.

### 3. Preserve Continuity Across Navigation

Keep route state separate from shell and runtime lifetime. Route changes must not silently destroy active panel tabs, drafts, queued work, modal ownership, background work, or hidden runtimes that still serve live work.

Preserve focus intentionally. When a tab changes while its panel owns focus, move focus into the replacement panel. When a popover, menu, or modal closes, return focus to its trigger or the next valid work surface.

### 4. Make Control Keyboard-Complete

Cover composer focus, search, command menus, list navigation, panel toggles, tab movement, submit, stop, queue/steer, and Escape. Resolve shortcuts from current state; never bind a key to one unconditional action.

Use native shortcut labels: Cmd on macOS, Ctrl on Windows/Linux. Preserve text-editing behavior inside inputs, editors, dropdown search, terminals, and contenteditable regions.

### 5. Respect Native And Responsive Boundaries

Prefer system fonts, native context menus in Electron, platform menu conventions, drag/no-drag window regions, stable focus rings, resizable splits, and web fallbacks using the same action model.

Adapt the shell before hiding core work. Use the observed `960px` narrow and `720px` very-narrow thresholds as exact-reproduction anchors, not universal breakpoints. Keep the main work surface primary; float or collapse navigation before compressing work into unusable space.

## Task Router

Choose one path before loading references:

- **Build or adapt** — inspect the existing component library first, select a surface, then load only the relevant shell, interaction, component, state, and QA references.
- **Review** — identify the intended surface and work objects, then report violations against observable behavior and QA contracts. Separate source mismatches from design recommendations.
- **Exact reproduction** — load `references/source-map.md`, use only Observed values, preserve platform branches, and record the Codex build used.
- **Design specification** — describe behavior, state, persistence, focus, failure, and responsive rules. Do not invent implementation APIs unless marked Recommended.

## Surface Router

- **Primary workbench** — use sidebar, progress/result timeline, main work, and composer. Add right or bottom panels only when their work objects exist.
- **Home/start** — center the composer as the launch action; show project/host context and compact suggestions.
- **Settings** — use grouped navigation, search, optional host scope, focused forms, inline validation, and a reliable return route.
- **Utility** — keep only the command, picker, confirmation, import, or setup flow required for the decision.

Add zones by capability trigger:

- Add a right panel for inspectable or parallel objects such as files, browser, review, side chat, or artifacts.
- Add a bottom panel for terminal, logs, diagnostics, tests, or running processes.
- Add tabs only when multiple persistent objects can occupy the same panel.
- Add a hidden runtime host only when a live runtime must survive navigation.
- Add a modal only for a blocking decision; prefer popover, sheet, panel, or inline UI for lightweight choices.

## Workflow

1. **Read the target** — determine platform, shell, surface, density, primary input, existing components, and business constraints.
2. **Name the work objects** — define identity, status, actions, ownership, loading/error boundaries, and persistence needs.
3. **Choose the minimum zones** — map each required object to navigation, main work, composer, right panel, bottom panel, toolbar, or status area.
4. **Reuse before creating** — reuse project primitives and installed dependencies. Add a primitive only after a real surface proves it is missing.
5. **Define behavior before styling** — specify state, event, guard, effect, persistence, focus return, intermediate-step updates, task-summary fields, and responsive change.
6. **Implement the complete primary flow** — include only relevant empty, loading, disabled, running, approval, error, and recovery states.
7. **Verify with real data** — test long paths, long titles, 0/1/10/100+ rows as relevant, remote/local hosts, narrow windows, dark mode, keyboard-only use, and reduced motion.

## Reference Routing

Load only the files required by the chosen path:

- Core capability coverage and exclusions: `references/mature-capability-map.md`
- Shell, responsive layout, sidebar, tabs, and panels: `references/shell-layout.md`
- Composer, keyboard, search, drag/drop, menus, and long-running work: `references/interaction-patterns.md`
- Intermediate steps, result hierarchy, streaming, and task summaries: `references/task-progress-summary.md`
- Component contracts and exact API shapes: `references/component-system.md`
- Density, typography, tokens, motion, and accessibility: `references/visual-tokens-density.md`
- Portable state models, lifecycle, persistence, and focus: `references/state-models.md`
- Executable review and implementation checks: `references/implementation-qa.md`
- Observed build provenance and pinned remote-source locators: `references/source-map.md`

## Quick Reference

| Need | Contract | Evidence |
| --- | --- | --- |
| Narrow shell | `960px`; very narrow `720px` | Observed |
| Main bottom panel | default `280px`; clamp with `max(160, min(height, availableHeight × 0.5))`; persist height | Observed |
| Floating sidebar reveal | reveal from the left `0–12px` edge zone or trigger hover; keep open while pointer remains inside | Observed |
| Preview tab | replace the current preview; pin on meaningful pointer or keyboard interaction | Observed |
| Tab activation | keep activation history; restore focus when the prior panel owned it | Observed |
| Running follow-up, `enter` mode | Cmd/Ctrl+Enter | Observed |
| Running follow-up, `cmdIfMultiline` or `cmdAlways` | Cmd/Ctrl+Shift+Enter | Observed |
| Popover | portal by default; `18rem` or `24rem`; zoom and viewport bounds | Observed |
| Context menu | native Electron bridge when available; shared Radix fallback model | Observed |
| Intermediate step | update one stable row through queued/running/waiting/terminal states; expand evidence on demand | Recommended |
| Task summary | lead with outcome; include only relevant changes, evidence, unresolved risk, and next action | Recommended |
| Selected vs hover | make selected unmistakable even if adapting from a source component that shares a token | Recommended |
| Motion | preserve spatial continuity; remove large movement and bounce under reduced motion | Inferred |
| Reduced motion | app setting `system | on | off`; `system` follows `prefers-reduced-motion` | Observed |

## Skill Delivery Contract

Lead with the implemented or reviewed outcome. Include only artifacts useful to the task:

- For implementation: changed surfaces, verified commands/screenshots, and remaining risk.
- For review: findings ordered by user impact, each with a locator and violated contract.
- For specification: work objects, zone map, behavior/state contract, responsive/native rules, and acceptance checks.
- For exact reproduction: Codex version, source locators, Observed values used, and unverified gaps.

Do not emit a component inventory or zone map when the task does not need one. Keep the result proportional to the surface.
