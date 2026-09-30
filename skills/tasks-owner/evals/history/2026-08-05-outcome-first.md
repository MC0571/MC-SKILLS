# Outcome-first 回归记录（v0.16.0）

## 版本边界

- `v0.15.0` 的调度活性回归只覆盖 **existing-ready dispatch**：已有 GitHub ready Work Item、
  已有或待创建任务 locator、容量扣除和 `owner_dispatch_required`。它没有覆盖 backlog shaping、
  successor planning、planning readiness 修订、目标级 recovery 或 all-external 合法静默终态。
- `v0.16.0` 把 outcome-first 控制循环落到 `sync → gap/critical path → classify → owner action →
  readiness/admission → supervise/correct → converge/closeout/cleanup → replan`，并将容量/dispatch 与
  semantic scope 拆到 `references/scheduling.md`、`references/scope-integrity.md`。

## 行为轨迹

新增 8 个多回合 `recorded_fixture` 轨迹：可规划空 ready recovery、owner-actionable 优先于 external、
已确认 planning writes 时修订 Issue、stale handoff 重分类、closeout 后形成 successor、all-external
安静等待、HotCP backlog recovery、ScorAce recovery admission。每条轨迹断言动作顺序和禁止终态；
HotCP 的 forbidden 只匹配 baseline/unsafe 文本，不匹配 `with_skill` 标签。

`execution_ready` 只表达“可进入调度”，不要求预先存在由 dispatch/admission 才会产生的 branch、
worktree、合同、任务 locator 或 runtime evidence；否则新 Work Item 会在派发前形成循环依赖。
另有 1 个单回合回归夹具固定这条分类边界。
Heartbeat 再增加 1 个单回合轨迹，要求每次唤醒主动评估目标、调度、任务健康和交付质量，再纠偏、
收敛或补满无冲突槽位；没有紧急事件不能跳过 Owner 控制周期。

## 证据边界

- 当前 output scorecard、blind pack 和 answer key 来自工具的 `recorded_fixture` 输入；它们不是
  provider-backed model 运行证据。
- 本次 `output-eval` 实际输出为 79 cases、with-skill pass rate `100.0`、baseline `0.0`、
  `regression_count=0`、blind pair `79`；这些数字只描述断言夹具。
- 未执行真实 provider/model，也没有人工盲审决定；这些状态必须标记 `missing evidence`，不得把
  deterministic fixture 说成真实模型或人工结果。
- 运行命令：`python3 /Users/claw/.agents/skills/yao-meta-skill/scripts/yao.py output-eval ...`；
  具体输出路径和 case 数量以本次工具实际输出为准。
