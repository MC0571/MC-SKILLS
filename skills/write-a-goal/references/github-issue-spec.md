# GitHub Issue 模式规范

本参考用于 `github_issue`：起草、优化或校验可执行的 GitHub Work Item Issue。它与
`copyable_goal_command`、`active_goal_api` 互斥；Issue 是供人和项目规划读取的事实载体，
不是 Codex goal，也不是任务线程的运行态合同。

## 目录

- [适用范围与输出](#适用范围与输出)
- [Work Item 最小结构](#work-item-最小结构)
- [父 FR / milestone 的轻量结构](#父-fr--milestone-的轻量结构)
- [校验与修订流程](#校验与修订流程)
- [最小修订建议](#最小修订建议)

## 适用范围与输出

- 默认面向一个可独立交付和收口的 Work Item Issue；保留已有 issue、FR、milestone、URL 和
  用户指定的精确引用，不凭空创建 GitHub 事实。
- 用户要求“写/改/补全/检查 issue”时输出 `github_issue`。根据输入选择 `draft`、`revise` 或
  `validate`，并给出 `ready` 或 `planning_not_ready` 及缺口/修订建议。
- 默认只输出标题、Issue 正文、规划元数据和校验结论；不调用 goal API、不输出 `/goal`，也不
  直接创建或更新 GitHub。只有用户明确授权并且存在获准的写入能力时，才可另行执行外部写入，
  并报告实际动作和证据。

## Work Item 最小结构

除非输入明确说明不适用，Issue 草案或修订建议必须覆盖以下内容。字段名可保持英文，正文按
`output_language` 输出。

```text
Title: <短、可行动、描述结果的标题>

Outcome / User value
<要改变的最终状态，以及谁为什么受益>

Context / Entry points
<权威 issue/FR/milestone、代码/文档入口、现状证据或复现入口；未知项标为待补事实>

Done when / Acceptance
- <可观察、可验证的完成标准；包括成功、失败或不可用状态>

Scope
- In: <本 Issue 允许交付的文件、模块、接口或外部事实>
- Out / Non-goals: <明确不做的内容>

Dependencies / Constraints
- Hard dependencies: <未完成即不能开始的依赖>
- Soft or convergence dependencies: <影响顺序但不改变目标的依赖>
- Constraints: <兼容性、安全、数据、权限、质量或成本边界>

Verification evidence
- Check: <准确命令、测试、报告、截图或外部状态>
  Success: <可观察的通过判据>

Pause / Decision conditions
- <缺少事实/权限、语义歧义、需要产品/安全决策或重复失败时暂停并请求谁决定>

Planning metadata
- parent: <父 FR/Issue URL 或 none；不猜测>
- milestone: <milestone URL/名称或 none；不猜测>
- blocked-by: <Issue URL/编号列表或 none/unknown>
```

“完成标准”必须描述证据可观察的终态，而不是“实现功能”或“没有问题”。上下文入口
应能让执行者定位事实；如果核心事实仍未知，保留缺口并标记 `planning_not_ready`，不要用
运行态信息填空。

Issue 不得把 Agent 执行环境的运行时编排或 admission 元数据写成 Issue 合同字段。禁止的
是这类上下文中的明确键或控制块，例如 `owner_thread_id`、`task_thread_id`、
`workspace_entry`、`owner_runtime_lock`、`contract_revision`、`contract_digest`、
`execution_generation`、`event_key`、`execution_hold`、`<control>`，以及带有运行时命名空间的
`model`、`agent`、`subagent`、`thread`、`worktree`、`cwd` 或 head 值（例如
`runtime.model`、`admission.worktree`）。不要把这些词本身当作禁词：它们可以合法地表示
产品域目标、代码/接口术语、验证对象或用户明确要求实现的功能。验证证据可以链接 PR、CI、
测试结果或代码术语，但不能把运行时编排值变成 Issue 的合同字段。

## 父 FR / milestone 的轻量结构

父 FR 或 milestone 只需表达规划关系，不强制套用完整 Work Item 六项结构：

```text
Parent: <FR 或 milestone URL/名称>
Intent / Value: <要推动的用户结果>
Children / Exit signal: <子 Work Item 或阶段性结果>
Known constraints or dependencies: <已知项；可省略>
```

仅在用户要求父项本身可执行时，才补完整 Work Item 结构。父项未知或关系冲突时暂停并
请求确认，不能把子 Issue 的运行态合同字段复制到父项。

## 校验与修订流程

1. 先锁定 `output_language`，再读取用户给出的 GitHub/仓库事实；区分“未提供”和“已确认
   没有”，不把聊天摘要升级为 GitHub truth。
2. 对 Work Item 逐项检查结果/价值、完成标准、范围/非目标、依赖/约束、验证证据、暂停/决策
   条件，并检查 parent/milestone/blocked-by 是否与已知规划一致。
3. 缺少任何核心项或 GitHub truth 不足时，输出 `planning_not_ready`、精确缺口和最小修订
   建议；不得建议 admission、派发或未经授权的 GitHub 写入。
4. 全部核心项有证据且关系无冲突时输出 `ready`；仍只提供 Issue 产物，不因此作出运行态决策
   或创建运行态状态。
5. 最终做一次泄漏检查：Issue 产物不得出现 `/goal` 或 goal API 调用，也不得把运行时编排
   键/控制块写入 Issue；产品域、代码术语和验证对象中的同名词仍可保留。父 FR/milestone
   保持轻量。

## 最小修订建议

资料不完整时，用短而可执行的建议补齐，而不是重写整个项目计划：

```text
Readiness: planning_not_ready | ready
Missing: <缺失的核心项或规划事实>
Suggested revision:
- Outcome / User value: ...
- Done when / Acceptance: ...
- Scope / Non-goals: ...
- Dependencies / Constraints: ...
- Verification evidence: ...
- Pause / Decision conditions: ...
- parent / milestone / blocked-by: <仅填已确认项>
```
