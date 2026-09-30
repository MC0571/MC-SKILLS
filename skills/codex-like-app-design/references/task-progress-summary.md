# Task Progress And Summary

Use this contract to present meaningful intermediate work and terminal outcomes for any long-running task. A step may represent analysis, generation, validation, review, an external operation, a human decision, or a tool call; do not couple the UI model to one execution mechanism.

## Contents

- Evidence boundary
- Timeline hierarchy
- Intermediate-step contract
- Task-summary contract
- Streaming, scroll, and focus
- Failure and recovery
- QA scenarios

## Evidence Boundary

Observed in Codex Desktop `26.623.70822`:

- Visible entries filter renderable turns, group requests by turn, and retain stable turn/search identity.
- Turns carry items, status, duration, error, diff, and start/final timestamps.
- Turn rows support per-turn collapse, generated outputs, completed-goal attachment, and fixed current-progress content.
- Long histories use virtualization, auto-follow, and restored scroll state.
- The summary-panel model derives artifacts, plans, background work, side chats, tool sources, and web sources from conversation state.

The generic information hierarchy and summary format below are Recommended. Do not present them as exact Codex component APIs.

Never expose private chain-of-thought. Show only user-facing progress, concise rationale, decisions, uncertainty, and evidence that the product is allowed to reveal.

## Timeline Hierarchy

Treat a task timeline as an ordered sequence of meaningful work objects:

```text
request
  intermediate step(s)
    operation or decision
    result or evidence
  terminal task summary
```

Primary items:

- user requests and steering
- meaningful milestones and decisions
- approvals, blockers, and failures requiring attention
- produced artifacts or changed resources
- terminal task summary

Secondary, collapsible detail:

- raw commands and arguments
- logs, traces, and repetitive operations
- verbose evidence, diffs, and machine metadata
- successful low-level actions that do not change the user's understanding

Keep chronological truth, but group related low-level events under the step they serve. Do not turn every event into an equal-weight card.

## Intermediate-Step Contract

Use one stable item identity and update it through applicable states:

```text
queued -> running <-> waiting
queued/running/waiting -> succeeded | failed | cancelled | skipped
```

Each visible step may contain:

- concise verb-led label
- status icon and text
- affected object or scope
- short current-progress or result line
- elapsed time when useful
- expandable evidence and raw output
- recovery or inspection action when applicable

Rules:

- Update the same row in place as state changes; do not append near-duplicate rows.
- Use present-tense activity while running and outcome language after completion.
- Keep success visually quiet. Give waiting, failure, and blocked states enough contrast and explanation.
- Keep the latest meaningful running step visible without pinning a large overlay over the timeline.
- Group parallel work by owner or objective and show aggregate progress before child detail.
- Link files, artifacts, tests, logs, or output panels from the step that produced them.
- Mask secrets and omit unsafe inputs even when raw operation detail is expandable.
- Preserve cancelled and failed steps when they explain the final outcome; collapse noise rather than deleting history.

## Task-Summary Contract

Render a terminal summary as the final high-level item for completed, partial, blocked, failed, or cancelled work. Keep it visually distinct from intermediate steps without presenting it as an unrelated card.

Lead with one outcome sentence, then include only relevant sections:

1. **Changed or produced** — files, artifacts, decisions, or external state.
2. **Verified** — checks, evidence, screenshots, or observed behavior.
3. **Unresolved** — blockers, failures, uncertainty, or remaining risk.
4. **Next action** — only when the user must act or a natural continuation remains.

Rules:

- Omit empty sections; a read-only or advisory task may have no "Changed" section.
- Distinguish complete, partial, blocked, failed, and cancelled outcomes explicitly.
- Link summary claims back to the relevant step, artifact, or evidence when the UI supports it.
- Do not repeat the full timeline, raw logs, or every successful operation.
- Keep the summary available after navigation and restart whenever the task record persists.
- If work is still active, show a progress snapshot rather than a misleading terminal summary.

## Streaming, Scroll, And Focus

- Follow new content only when the viewport is already at the live edge.
- When the user scrolls away, preserve position and show a new-activity action or count.
- Coalesce streaming updates by stable item id to prevent layout churn.
- Preserve per-task scroll position, collapsed steps, and expanded evidence where useful.
- Navigating away must not convert running steps into failures or discard their latest visible state.
- Opening evidence may move focus into its panel; closing it returns focus to the originating step.
- Announce approvals, blockers, failures, and completion. Do not announce every token, log line, or progress tick.

## Failure And Recovery

- Put a step-local error beside the failed step and provide retry, inspect, replace, or dismiss only when valid.
- Distinguish operation failure from task failure; later work may recover successfully.
- Keep partial evidence when safe so the user can understand what completed before failure.
- A blocked summary must name the missing decision, permission, input, or unavailable dependency.
- A cancelled summary must say what was preserved and what did not run.

## QA Scenarios

Write each check as `setup -> action -> expected state -> negative assertion -> evidence`.

| Setup | Action | Expected | Negative assertion |
| --- | --- | --- | --- |
| one stable step | emit queued, running, and success updates | one row changes state and retains identity | three duplicate rows do not appear |
| several low-level operations | complete a meaningful milestone | operations group under a readable step | raw events do not dominate the timeline |
| user scrolled upward | stream more progress | position remains stable and new activity appears | viewport does not jump to bottom |
| task completes with changes and checks | render summary | outcome, changes, and evidence appear with links | full timeline is not repeated |
| task produces advice only | render summary | outcome and evidence appear | empty Changed section does not appear |
| task blocks or is cancelled | terminate work | honest status, preserved work, and required next action appear | UI does not claim success |
| keyboard and screen reader | expand evidence and receive updates | focus returns and meaningful states are announced | every stream tick is not announced |
