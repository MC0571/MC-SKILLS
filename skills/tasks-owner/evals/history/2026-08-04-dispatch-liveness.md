# 调度活性回归：worktree 已建立但任务未创建

- 事故：ready Work Item 有可用实现槽位，Owner 已建立 branch/worktree，却没有创建真实任务；Heartbeat 将其误报为 admission hold 并持续等待。
- 根因：调度、admission 与 Heartbeat 规则缺少统一的控制周期合法终态，worktree 事实被错误提升为任务等待。
- 修复：v0.15.0 增加 `owner_dispatch_required` 与控制周期活性门禁；`DONT_NOTIFY` 只允许用于有真实 locator 的等待。
- 回归：事故路径覆盖 `liveness-worktree-without-task`、`liveness-heartbeat-owner-action`、`liveness-post-closeout-wave`；边界覆盖合法任务/agent 等待和 pending 占满 host cap。
- 证据：`reports/output_quality_scorecard.md`；69 个 recorded fixtures 的 with-skill pass rate 为 100%。provider-backed 执行和人工盲审仍为 `missing evidence`。
