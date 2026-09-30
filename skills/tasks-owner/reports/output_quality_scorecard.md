# Output Quality Scorecard

> 证据边界：下列 119 项仅为关键词式 recorded fixture，不是 provider、模型或宿主运行时证据，不能单独作为生命周期发布门禁。
> v0.19 的独立门禁是 `evals/trajectory_cases.jsonl` 及标准库状态重放器；真实宿主证据另见对应 history 记录。

This v0 scorecard compares static without-skill and with-skill outputs using assertion grading.

- Cases: `119`
- Baseline pass rate: `0.0`
- With-skill pass rate: `100.0`
- Delta: `100.0`
- Regressions: `0`
- Blind A/B pairs: `111`（v0.19 新增 8 项尚未进入人工盲审包）
- Static fixture gate pass: `True`
- Structured trajectory gate: `24/24`（6 个规则均含正反例；review disposition/单轮修复预算另通过 mutation self-test）

Blind review artifacts are generated separately so reviewers can inspect A/B outputs without seeing the answer key.
Run output review adjudication after reviewer decisions are recorded; pending cases should stay pending rather than being counted as human agreement.

## Case Results

| Case | Baseline | With Skill | Delta | Winner | Failed With-Skill Assertions |
| --- | ---: | ---: | ---: | --- | --- |
| flat-mode-contract | 0.0 | 100.0 | 100.0 | with_skill | None |
| hierarchical-mode-contract | 0.0 | 100.0 | 100.0 | with_skill | None |
| missing-github-truth | 0.0 | 100.0 | 100.0 | with_skill | None |
| automation-consent | 0.0 | 100.0 | 100.0 | with_skill | None |
| file-backed-scheduling | 0.0 | 100.0 | 100.0 | with_skill | None |
| direct-mode-contract | 0.0 | 100.0 | 100.0 | with_skill | None |
| luna-v1-consent | 0.0 | 100.0 | 100.0 | with_skill | None |
| luna-adjustment | 0.0 | 100.0 | 100.0 | with_skill | None |
| luna-effective-v2-no-restart | 0.0 | 100.0 | 100.0 | with_skill | None |
| luna-config-reload-required | 0.0 | 100.0 | 100.0 | with_skill | None |
| existing-task-contract-gate | 0.0 | 100.0 | 100.0 | with_skill | None |
| inspection-owner-action-required | 0.0 | 100.0 | 100.0 | with_skill | None |
| stale-release-rejected | 0.0 | 100.0 | 100.0 | with_skill | None |
| event-key-dedup | 0.0 | 100.0 | 100.0 | with_skill | None |
| dynamic-ready-wave | 0.0 | 100.0 | 100.0 | with_skill | None |
| owner-budget-boundary | 0.0 | 100.0 | 100.0 | with_skill | None |
| workspace-entry-admission | 0.0 | 100.0 | 100.0 | with_skill | None |
| one-off-owner-perspective | 0.0 | 100.0 | 100.0 | with_skill | None |
| completed-closeout-gate | 0.0 | 100.0 | 100.0 | with_skill | None |
| automation-correction-cannot-dispatch | 0.0 | 100.0 | 100.0 | with_skill | None |
| release-ack-required | 0.0 | 100.0 | 100.0 | with_skill | None |
| max-inflight-cap-resolution | 0.0 | 100.0 | 100.0 | with_skill | None |
| non-actionable-delta-coalescing | 0.0 | 100.0 | 100.0 | with_skill | None |
| owner-ack-suppression | 0.0 | 100.0 | 100.0 | with_skill | None |
| single-convergence-lane | 0.0 | 100.0 | 100.0 | with_skill | None |
| legacy-owner-reporting-migration | 0.0 | 100.0 | 100.0 | with_skill | None |
| owner-handoff-drift | 0.0 | 100.0 | 100.0 | with_skill | None |
| pr-ready-pending-delivery | 0.0 | 100.0 | 100.0 | with_skill | None |
| owner-handoff-continuous-maintenance | 0.0 | 100.0 | 100.0 | with_skill | None |
| final-only-not-delivery | 0.0 | 100.0 | 100.0 | with_skill | None |
| admission-active-delivery | 0.0 | 100.0 | 100.0 | with_skill | None |
| runtime-lock-echo-gate | 0.0 | 100.0 | 100.0 | with_skill | None |
| ready-wave-single-without-reason | 0.0 | 100.0 | 100.0 | with_skill | None |
| convergence-not-implementation-lane | 0.0 | 100.0 | 100.0 | with_skill | None |
| target-cap-not-actual | 0.0 | 100.0 | 100.0 | with_skill | None |
| bootstrap-not-implementation | 0.0 | 100.0 | 100.0 | with_skill | None |
| blocked-idle-goal-blocked-not-active | 0.0 | 100.0 | 100.0 | with_skill | None |
| task-key-drift-isolated | 0.0 | 100.0 | 100.0 | with_skill | None |
| owner-cannot-lower-cap | 0.0 | 100.0 | 100.0 | with_skill | None |
| dependency-closed-local-conflict | 0.0 | 100.0 | 100.0 | with_skill | None |
| human-readable-two-layer-message | 0.0 | 100.0 | 100.0 | with_skill | None |
| runtime-routing-workspace-head-mismatch | 0.0 | 100.0 | 100.0 | with_skill | None |
| runtime-public-local-conflict | 0.0 | 100.0 | 100.0 | with_skill | None |
| implementation-packet-interface-verification | 0.0 | 100.0 | 100.0 | with_skill | None |
| fresh-review-head-invalidated | 0.0 | 100.0 | 100.0 | with_skill | None |
| requested-observed-isolation | 0.0 | 100.0 | 100.0 | with_skill | None |
| reviewer-mutated-files | 0.0 | 100.0 | 100.0 | with_skill | None |
| issue-readiness-standalone | 0.0 | 100.0 | 100.0 | with_skill | None |
| issue-readiness-goal-enhancement | 0.0 | 100.0 | 100.0 | with_skill | None |
| issue-readiness-blocks-dispatch | 0.0 | 100.0 | 100.0 | with_skill | None |
| issue-output-no-runtime-leak | 0.0 | 100.0 | 100.0 | with_skill | None |
| parent-fr-light-structure | 0.0 | 100.0 | 100.0 | with_skill | None |
| issue-readiness-legacy-no-capability | 0.0 | 100.0 | 100.0 | with_skill | None |
| post-closeout-cleanup-success | 0.0 | 100.0 | 100.0 | with_skill | None |
| cleanup-dirty-worktree-blocked | 0.0 | 100.0 | 100.0 | with_skill | None |
| cleanup-ref-drift-protected-blocked | 0.0 | 100.0 | 100.0 | with_skill | None |
| cleanup-subagent-cwd-target-blocked | 0.0 | 100.0 | 100.0 | with_skill | None |
| cleanup-partial-idempotent | 0.0 | 100.0 | 100.0 | with_skill | None |
| semantic-scope-hotcp-drift | 0.0 | 100.0 | 100.0 | with_skill | None |
| semantic-scope-thin-adapter | 0.0 | 100.0 | 100.0 | with_skill | None |
| semantic-scope-gate-matrix | 0.0 | 100.0 | 100.0 | with_skill | None |
| semantic-scope-circuit-breaker | 0.0 | 100.0 | 100.0 | with_skill | None |
| semantic-scope-downstream-reverse-signal | 0.0 | 100.0 | 100.0 | with_skill | None |
| liveness-worktree-without-task | 0.0 | 100.0 | 100.0 | with_skill | None |
| liveness-heartbeat-owner-action | 0.0 | 100.0 | 100.0 | with_skill | None |
| liveness-post-closeout-wave | 0.0 | 100.0 | 100.0 | with_skill | None |
| liveness-legitimate-task-wait | 0.0 | 100.0 | 100.0 | with_skill | None |
| liveness-direct-agent-wait | 0.0 | 100.0 | 100.0 | with_skill | None |
| liveness-pending-fills-host-cap | 0.0 | 100.0 | 100.0 | with_skill | None |
| outcome-recovery-shape-readiness-dispatch | 0.0 | 100.0 | 100.0 | with_skill | None |
| outcome-owner-actionable-over-external | 0.0 | 100.0 | 100.0 | with_skill | None |
| outcome-planning-not-ready-revise-authorized | 0.0 | 100.0 | 100.0 | with_skill | None |
| outcome-handoff-external-reclassified | 0.0 | 100.0 | 100.0 | with_skill | None |
| outcome-closeout-forms-successor | 0.0 | 100.0 | 100.0 | with_skill | None |
| outcome-all-external-quiet | 0.0 | 100.0 | 100.0 | with_skill | None |
| outcome-hotcp-heartbeat-recovery | 0.0 | 100.0 | 100.0 | with_skill | None |
| outcome-scorace-recovery-admission | 0.0 | 100.0 | 100.0 | with_skill | None |
| execution-ready-before-runtime-bootstrap | 0.0 | 100.0 | 100.0 | with_skill | None |
| heartbeat-owner-effectiveness-review | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-tight-batch-same-carrier | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-legal-split-evidence | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-acceptance-matrix-backlog | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-dependency-fanout-audit | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-premature-worksite | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-event-before-heartbeat | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-review-preflight-churn | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-owner-event-host-never-wakes | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-matrix-stale-holdout | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-scorace-bootstrap-route-sleep | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-hotcp-final-without-upstream-delivery | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-wrong-tool-local-final-not-delivery | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-owner-completion-summary-without-successor-fails | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-merge-closeout-successor-same-turn | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-owner-action-blocks-final | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-safe-wait-task-evidence | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-safe-wait-external-user-evidence | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-app-local-final-next-owner-not-event | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-app-wrong-tool-rejected | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-app-exact-send-success | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-pending-delivery-is-not-event | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-app-task-explicit-luna-max | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-direct-spawn-explicit-luna-max | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-runtime-omission-fallback-fails | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-runtime-unknown-model-fail-closed | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-task-specific-runtime-override | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-owner-runtime-isolated | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-runtime-audit-migration | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-neighbor-task-runtime-denial | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-neighbor-tool-list-without-locator | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-neighbor-final-does-not-restart-loop | 0.0 | 100.0 | 100.0 | with_skill | None |
| v017-neighbor-goal-complete-no-wait | 0.0 | 100.0 | 100.0 | with_skill | None |
| v019-issue108-blocked-by-not-hard | 0.0 | 100.0 | 100.0 | with_skill | None |
| v019-issue108-recorded-contract-thin-slice | 0.0 | 100.0 | 100.0 | with_skill | None |
| v019-issue108-real-safety-hard | 0.0 | 100.0 | 100.0 | with_skill | None |
| v019-issue108-legal-tight-batch | 0.0 | 100.0 | 100.0 | with_skill | None |
| v019-issue108-oversized-platform-no-shared-boundary | 0.0 | 100.0 | 100.0 | with_skill | None |
| v019-issue108-first-slice-field-missing | 0.0 | 100.0 | 100.0 | with_skill | None |
| v019-issue108-width-one-two-cycles-action | 0.0 | 100.0 | 100.0 | with_skill | None |
| v019-issue108-width-one-two-cycles-no-action | 0.0 | 100.0 | 100.0 | with_skill | None |

## Failure Taxonomy

- No with-skill assertion failures.

## Next Fixes

- Add holdout cases before using this as a release gate.
- Promote repeated failed assertions into the output-risk profile.
- Keep assertions tied to material deliverables, not phrasing trivia.
