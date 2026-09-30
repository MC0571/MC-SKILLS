# Tasks Owner v0.17.1 控制循环、可靠交付与运行时回归

## 变更范围

- `operations.md` 现在是统一 control loop 和 `pre_final_gate` 的唯一行为入口。用户事件、App task 事件、
  native Subagent completion、Heartbeat、merge/closeout、依赖解除和 gate 前的总结尝试都只是 trigger；Owner 必须在
  同一回合消费/核验、更新 gap/matrix、执行全部已授权 `owner_action`、重算 ready/successor/cap，并派发
  successor 或逐项记录带 locator/wake condition 的合法等待。native completion 后不能先总结或等 Heartbeat。
- `contracts.md`、`operations.md` 和 `automation.md` 统一 App task delivery：双向控制消息唯一使用
  `codex_app__send_message_to_thread({threadId, model, thinking, prompt})`；read/wait/local final/泛称工具不算
  投递或唤醒。canonical `event` 与 `delivery_state`/`route_status` 分离，`*_PENDING_DELIVERY` 只能是失败状态。
- 独立任务线程和每个派生 Subagent 默认显式 `gpt-5.6-luna/max`；用户 task-specific override 仅按 locator
  和明确传播范围生效。创建/恢复/消息/接受结果前回读目标 `turn_context`；缺失、漂移、Unknown model 或
  reasoning 拒绝 fail closed，保留 attempted runtime/error evidence，不污染 Owner runtime。

## 回归证据

`evals/output/cases.jsonl` 共 111 个 `recorded_fixture` cases；由 Yao Output Eval 生成的 scorecard 显示
baseline `0.0`、with-skill `100.0`、regression `0`、blind pair `111`、gate `True`。这些是确定性夹具断言，
不是 provider/model replay 或人工盲审证据；真实 runtime/provider 证据仍标记 `missing evidence`。

另以独立 Luna/max Subagent 对 completion successor、App local-only `PR_READY` 和 hierarchical
`Unknown model` 三个场景做了只读 forward-test；结果符合新合同，但仍属于场景演练，不是宿主 provider
调用、真实跨线程投递或人工盲审证据。

新增覆盖：completion/merge/closeout 同回合 successor、owner_action 禁止 final、合法 task/external/user
等待、App local-only/wrong tool/exact send、PENDING_DELIVERY 分离、App task 默认 Luna/max、direct spawn
显式 Luna/max、参数省略/宿主拒绝 fail closed、task-specific override、Owner runtime 隔离和活动任务 runtime
audit/migration。
