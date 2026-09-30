# Tasks Owner v0.17 效率与交付批次回归

## 来源与脱敏边界

- HotCP 轨迹 locator：`codex://threads/019fb0fc-de5f-76e2-ac69-a09e7e3a7b8a`
- ScorAce 轨迹 locator：`codex://threads/019fa7d9-3b87-72a1-bf4f-a2d51575542e`
- 仅保留本次确认的最小事实，不复制完整消息、prompt、token、环境或用户材料；provider/model 和人工盲审结果仍为 `missing evidence`。

## 已确认的最小事实

1. 共享 carrier、验证矩阵和 closeout lane 的候选应默认组成最小有效交付批次；只有独立价值、风险/权限/数据边界、ownership、真实 hard dependency 或独立回滚证据才拆分。
2. `hard` 依赖阻止安全开始，`soft` 只影响优先级/信息，`convergence` 只阻最终 merge/认证/closeout；父子关系不自动传播 external blocker。cap 仍由 `resolved_max_inflight` 决定。
3. 首次调度、重大 closeout/replan、用户效率复盘必须刷新 acceptance/backlog matrix；矩阵缺行不能声称 backlog 清空。
4. blocked successor 可提前只读做 readiness，但 hard dependency merge 前不能建立正式 execution branch/worktree、完整 contract 或 `START`；解除后同周期 admission。
5. 每个 App bootstrap/full prompt 必须带 upstream delivery contract；Owner 与独立 App task thread 双向通信只能使用精确工具 `codex_app__send_message_to_thread`。任务在 contract_ack 后、release/START 前一次主动投递 `DELIVERY_ROUTE_ACK`，Owner 核验 sender locator 后标记 `armed` 并继续 admission。`next_actor=owner` 事件必须有真实 message locator 和 received/verified/consumed 记录；pending/unconsumed 禁止 waiting 或 `DONT_NOTIFY`，direct 依赖 native agent completion/wait。Heartbeat 发现漏投只作 delivery violation 恢复。
6. 首次独立 review 前需要 acceptance-derived preflight；首次 fix-first 后做 sibling/systemic scan 和一个有界修复，第二次不同 blocker class 的实质 finding 触发 rethink/split/reassign/user decision。

## Per-trajectory 证据边界

下表把 HotCP/ScorAce locator 绑定到对应案例 metadata；既有回归是 `recorded_fixture`，本次两条事故是
`source_kind=thread_readback_observed`、`execution.mode=recorded_fixture`。`actual` 只表示确定性 fixture
assertion 的结果；没有 provider/model 运行或真实 runtime replay 时，不将其写成轨迹已复现。

| trajectory | locator | recorded fixture / case metadata | baseline | target | actual | failure classification |
| --- | --- | --- | --- | --- | --- | --- |
| HotCP | `codex://threads/019fb0fc-de5f-76e2-ac69-a09e7e3a7b8a` | `outcome-hotcp-heartbeat-recovery`; `source_kind=recorded_fixture` | 历史 `ready=0/DONT_NOTIFY` 吞掉未形成的 Work Item | 回读 backlog、形成/补 readiness 并在同周期 admission | deterministic fixture assertions pass；真实 trajectory replay: `missing evidence` | `missing_evidence: provider/model + runtime replay`；不是产品失败 |
| ScorAce | `codex://threads/019fa7d9-3b87-72a1-bf4f-a2d51575542e` | `outcome-scorace-recovery-admission`; `source_kind=recorded_fixture` | recovery contract 被误当作完成，7 个槽位未 admission | 识别 recovery、并行 readiness、完成 ACK/release/STARTED admission | deterministic fixture assertions pass；真实 trajectory replay: `missing evidence` | `missing_evidence: provider/model + runtime replay`；不是产品失败 |

## 新增真实回归的最小事实

下表只记录用户提供并回读的最小事实；`actual` 是本地 recorded fixture 断言，不是 provider/runtime replay。

| trajectory | owner/task locators | baseline | target | actual | failure classification |
| --- | --- | --- | --- | --- | --- |
| ScorAce bootstrap route | Owner `codex://threads/019fa7d9-3b87-72a1-bf4f-a2d51575542e`，turn prefix `019fcfce…`; #228 task prefix `019fcfd4…` (1785898450, +3s)，#167 prefix `019fcfd1…` (1785898577, +130s)；下一 Heartbeat 1785899973 | local final 被当作并行 bootstrap 完成，Owner 休眠约23–25分钟 | prompt 注入 upstream route；一次 `DELIVERY_ROUTE_ACK`，校验 sender locator，`armed` 后继续完整 admission | `v017-scorace-bootstrap-route-sleep` fixture assertions pass；provider/runtime replay `missing evidence` | `delivery_violation + missing_evidence: no codex_app__send_message_to_thread in observed finals` |
| HotCP owner-event route | Owner `codex://threads/019fb0fc-de5f-76e2-ac69-a09e7e3a7b8a`，turn prefix `019fcfe7…`; #267 (1785900298, +354s)，#269 (1785900309, +365s)，#200 SCOPE_DELTA/NEEDS_OWNER (1785900812, +868s) | readiness/final 无 upstream 消息却被当作完成/可等待 | 所有 next_actor=owner 事件主动投递并消费 locator；未 armed 保持 admission_pending | `v017-hotcp-final-without-upstream-delivery` fixture assertions pass；provider/runtime replay `missing evidence` | `delivery_violation + missing_evidence: no codex_app__send_message_to_thread in observed finals` |

本次新增的 `v017-host-permanent-no-wake`、`v017-matrix-stale-holdout`、`v017-scorace-bootstrap-route-sleep`、
`v017-hotcp-final-without-upstream-delivery` 与 `v017-wrong-tool-local-final-not-delivery` 也只有
`recorded_fixture` evidence，provider/model replay 和人工盲审均为 `missing evidence`。Output scorecard 的
`gate_pass` 仅表示静态 fixture assertions 通过，不表示 #63/#67 exit 已完成；真实轨迹和外部证据仍需单独补齐。

## 证据状态

本文件用于回归路线和最小事实定位，不是运行态数据库；真实 provider/model 执行、生产 runtime 轨迹和人工盲审结论尚未提供，均标记为 `missing evidence`。
