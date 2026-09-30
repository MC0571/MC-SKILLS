---
name: write-a-goal
description: 起草、优化或设置符合 OpenAI《Follow a goal》指南的 Codex goal，并为 GitHub Issue 提供创建前草案、更新、修订、补全和校验。当用户直接要求，或 Agent、Owner 工作流、其他 Skill 正在创建或修改 feature、bug、Work Item、FR、milestone Issue，以及补写目标、验收、范围、依赖、验证或决策条件时使用。根据请求选择 copyable_goal_command、active_goal_api 或 github_issue；Issue 模式不输出 /goal 或运行态合同字段。默认使用用户语言，语言不明确时使用中文。
metadata:
  version: "0.2.2"
  category: "Productivity"
---

# 编写 Codex Goal 或 GitHub Issue

## 概览

把用户上下文整理成简洁、稳定、可执行的 Codex goal 契约或 GitHub Work Item Issue。优先保证一个目标、一个可验证终态、明确价值、约束与边界，以及可持续推进的验证循环。

`references/follow-goal-spec.md` 是 goal 契约的事实来源。用户要求符合官方规范、验证已有 goal，或任务高风险、模糊、长周期到需要精确结构时，读取该文件。

用户请求 GitHub Issue 的起草、优化或校验时，读取 `references/github-issue-spec.md`；该文件是 `github_issue` 模式的事实来源。Issue 是规划/执行入口，不是 Codex 运行态合同。

## 语言策略

默认使用用户的语言回复。用户使用中文、混合中英文，或语言不明确时，使用中文。命令、文件名、代码标识符、URL、issue ID 和精确引用文本保持原样。

## 语言门

在任何起草、解释、提问、创建 goal 或生成 Issue 之前，根据最新面向用户的请求设置 `output_language`；不要根据本 skill 文件、示例、路径、代码、日志或引用文本判断语言。

规则：

- 最新用户消息包含中文字符时，设置 `output_language = Chinese`。
- 最新用户消息中英文混合时，设置 `output_language = Chinese`。
- 语言不明确时，设置 `output_language = Chinese`。
- 所有生成内容都使用 `output_language`，包括 `/goal` 正文、Issue 标题/正文、解释、假设、自检和问题。
- 仅 shell 命令、文件路径、代码标识符、URL、issue ID 和精确引用原文保持不变。

## 输出模式门

起草或设置目标之前，必须且只能选择一种输出模式：

- `copyable_goal_command`：用户要求 goal 措辞、`/goal` 命令、可复制命令，要求起草/优化/分析并产出 goal，或没有明确要求 Codex 直接设置 active goal 时使用。可执行产物必须是一条以 `/goal ` 开头的物理单行。
- `active_goal_api`：用户明确要求设置、创建或开始一个 active goal，且当前有 goal 工具/API 可用时使用。通过工具/API 创建 goal。`objective` 可以多段，但必须自包含并包含完整 goal 契约。
- `github_issue`：用户要求起草、优化、校验或准备 GitHub Work Item Issue 时使用。输出 Issue 标题、正文和必要的 parent/milestone/blocked-by 元数据或修订建议；不输出 `/goal`，不调用 goal API，不把模型、thread、worktree、runtime lock、heartbeat、contract digest 等运行态字段写入 Issue。详细字段、校验门和父 FR/milestone 的轻量结构见 `references/github-issue-spec.md`。

如果选择 `active_goal_api` 但没有可用的 goal 工具/API，回退到 `copyable_goal_command`，并说明用户可以复制该命令使用；`github_issue` 不受此回退影响。

`github_issue` 是独立输出模式，不要求 goal 工具可用；默认只给出可复制的草案/修订建议，不直接写 GitHub。只有用户明确授权且存在已获准的写入能力时，才讨论外部写入，并报告动作证据。

## 命令形态契约

对 `copyable_goal_command`，最终可执行 goal 必须是一条以 `/goal ` 开头的物理单行，并且 `/goal ` 后必须包含完整 goal 契约。不要在命令中加入空行、Markdown 段落、项目符号或换行。

Desktop/CLI/IDE 的 slash command 解析可能只会把 `/goal ` 后第一个自然段设置为 goal 正文，所以可复制命令的所有必要指令都必须放在同一个自然段内。如果包含解释、分析或自检，把它们放在命令外，并且不要依赖这些正文承载必要 goal 细节。

对 `active_goal_api`，不要强行把 `objective` 压成一行。多段 `objective` 在能提升清晰度时允许使用，但所有必要指令都必须写进传给 goal 工具/API 的 `objective` 内。不要依赖 `objective` 外的 assistant 正文承载结果、验证、约束、边界、迭代策略、阻塞条件或完成标准。

## 目标契约模型

每个最终命令或 API `objective` 都必须覆盖六个核心要素，可按任务需要压缩表达：

- 结果（Outcome）：要达成的最终状态，而不只是要执行的动作。
- 验证面（Verification surface）：能证明进展和完成的命令、产物、报告、截图、外部状态或其他证据。
- 约束（Constraints）：不能破坏的业务、安全、数据、权限、API、行为或质量属性。
- 边界（Boundaries）：允许和禁止触碰的文件、模块、系统、账号、动作或写入范围。
- 迭代策略（Iteration policy）：Codex 在多轮尝试之间如何推进、重跑检查、报告证据，并避免重复失败做法。
- 阻塞停止条件（Blocked stop condition）：Codex 必须暂停而不是继续猜的条件，包括缺少权限、需要人工决策、重复失败或存在不安全的歧义。

必要时加入两个辅助字段：

- 输入/上下文（Inputs/context）：定义起点的源文件、issue、日志、报告、URL、数据导出、截图或外部系统。只有当顺序确实重要时，才写“先阅读”或“先检查”。
- 完成条件（Completion condition）：允许 Codex 停止或标记 goal complete 的精确证据状态。

## 动作授权策略

不要一刀切禁止外部动作或高影响动作。如果用户目标需要发送、关闭、合并、部署、删除、改权限或写入外部系统等动作，在 goal 契约中加入动作授权策略：

- 允许动作（Allowed actions）：Codex 可以做什么、作用于哪些对象、范围到哪里。
- 禁止动作（Forbidden actions）：超出用户授权或超出目标范围的动作。
- 确认触发条件（Confirmation triggers）：仍需明确确认的不可逆、生产、安全、隐私、付款、权限、批量或歧义动作。
- 证据说明（Evidence）：Codex 对已执行、已起草、跳过或被阻塞的动作需要报告什么证明。

## 工作流程

1. 从用户上下文提取稳定目标。
2. 起草前先识别可验证终态。
3. 选择输出模式：`copyable_goal_command`、`active_goal_api` 或 `github_issue`；不要在同一产物中混用模式。
4. 若为 `github_issue`，按 `references/github-issue-spec.md` 检查结果/用户价值、完成标准、上下文入口、范围/非目标、依赖/约束、验证证据、暂停/决策条件和规划元数据，然后停止在 Issue 草案/修订建议。
5. 只有当输入/上下文能明确起点时才写入；不要默认加入“先阅读”这类流程噪音。
6. 定义验证方式：要运行的命令、要检查的产物、要对比的截图、要通过的测试、要达到的分数、要确认的外部状态或要更新的文档。
7. 设置约束和边界：Codex 可以改什么或做什么，必须保留什么，什么需要确认。
8. 涉及外部系统或高影响操作时，加入动作授权策略。
9. 加入迭代行为：聚焦尝试、验证节奏、要报告的证据，以及重复失败处理。
10. 加入暂停或阻塞条件：缺少凭据、决策不清、动作不安全、需要策略判断、需求不清或重复验证失败。
11. 对 `copyable_goal_command`，把契约压缩为一条 `/goal ` 命令；辅助说明可选且不能承载必要信息。
12. 对 `active_goal_api`，用完整自包含的 `objective` 创建 active goal，然后简要说明已设置的内容。
13. 检查每句生成内容是否符合 `output_language`；如果意外回落为英文，先修正再回复。

## 起草形态

命令或 `objective` 应遵循规范起手式，并翻译为 `output_language`：持续完成一个目标，直到一个可验证终态成立。

对 `copyable_goal_command`，默认使用 `output_language` 的单行模板，除非用户环境需要更短命令。中文输出优先使用：

```text
/goal 完成[结果]。输入/上下文：[输入和上下文]。验证：[验证面]。约束：[约束]。边界：[边界]。迭代：[迭代策略]。阻塞：[阻塞停止条件]。完成：[完成条件]。
```

非中文的可复制命令输出，应把同一单行结构翻译为 `output_language`；只有 `output_language` 是英文时才直接使用英文结构。

英文输出优先使用：

```text
/goal Achieve [Outcome]. Inputs/context: [Inputs]. Verification: [Verification surface]. Constraints: [Constraints]. Boundaries: [Boundaries]. Iteration: [Iteration policy]. Blocked: [Blocked stop condition]. Done: [Completion condition].
```

不要机械填满每个标签；更短的表达更清楚时可以压缩，但不能遗漏六个核心要素。对 `copyable_goal_command`，不要把可执行命令输出成多行块。如果使用 Markdown 代码块承载可复制命令，代码块里必须只有一条命令行。

对 `active_goal_api`，`objective` 可以使用多个段落。标签或紧凑段落都可以，只要更便于审计契约完整性。

## 质量标准

好的 goal 必须满足：

- 比普通单次 prompt 更大，但小于开放式待办列表。
- 围绕一个目标，而不是一组无关请求。
- 在 Codex 开始前就清楚说明什么叫完成。
- 明确验证产物或验证命令。
- 明确约束、边界和非目标。
- 具体到另一个 Codex 实例在上下文压缩后也能继续。

避免使用“看起来不错”“直到全部完成”“直到没有问题”这类模糊停止条件，除非它们绑定了具体检查。

不要把每个任务都转成 goal。如果用户请求只是一行修改、简单解释、松散脑暴，或主要依赖人工判断的决策，说明普通 prompt 或规划讨论更合适，除非用户仍然想要 goal。对模糊 goal，最多问一个简短问题，或做保守假设。

不要默认输出 `/plan`。如果目标明显缺少完成条件或验证面，可以建议先澄清或先做规划讨论；只有用户明确要求 `/plan` 时，才输出 `/plan` 命令。

## 对话处理

只有当缺失信息会实质改变 goal，且无法安全推断时，才最多问一个简短问题。否则做保守假设，并把假设写进 goal。

当用户说“set the goal”“create an active goal”“start this goal”“帮我设置目标”“创建 active goal”“开始执行这个 goal”或等价表达时，如果有可用 goal 工具，就用该工具创建 goal。用户只要求措辞、草稿、分析或可复制命令时，只提供 `/goal` 文本，不激活目标。

默认命令 token 始终是 `/goal`。不要因为用户使用中文就输出 `/目标`；除非用户明确要求且当前客户端已验证支持，否则不推荐 `/目标`。

## 示例

用户：帮我写一个 /goal，让 Codex 持续修复 CI，直到 PR 可合并。

输出语言：中文

```text
/goal 修复当前 PR 的 CI 失败。输入/上下文：PR 描述、失败 CI 日志、相关测试和最近 diff。验证：本地复现命令、对应测试、最终 PR checks 全绿。约束：不跳过、不删除、不弱化测试，不做无关重构。边界：只改导致 CI 失败的代码、测试或配置。迭代：按失败项分组修复，每修一类重跑最小相关验证，完成前跑全量必需检查。阻塞：缺少权限、外部凭据、同类失败重复 3 次仍无法定位或需要产品/安全决策。完成：所有必需 checks 通过，PR 无阻塞性 review finding，并在最终摘要中列出修复内容与验证证据。
```

## 验证检查

最终输出前，按所选模式检查产物是否回答了以下问题：

- 输出模式：这是可复制 slash command、active goal API 请求，还是 GitHub Issue 草案/修订建议？
- 结果：Codex 要达成什么最终状态？
- 验证面：哪些命令、产物、外部状态或报告能证明进展和完成？
- 约束：哪些行为、数据、权限、安全、质量或业务规则不能被破坏？
- 边界：哪些文件、系统、账号、动作或写入范围允许或禁止？
- 迭代策略：Codex 应如何尝试、验证、报告证据并避免重复失败？
- 阻塞停止条件：什么情况下 Codex 应暂停并询问？
- 完成条件：什么精确证据允许 Codex 停止或标记 complete？
- 动作授权策略：如果涉及外部或高影响动作，哪些允许、哪些禁止、哪些需要确认、哪些需要记录？
- 命令/API 形态：对 `copyable_goal_command`，可执行 goal 是否正好是一条以 `/goal ` 开头的物理单行？对 `active_goal_api`，`objective` 即使多段是否仍然自包含？
- Issue 形态：对 `github_issue`，是否覆盖 Issue 的结果/价值、完成、上下文、范围/非目标、依赖/约束、验证、暂停/决策和必要规划元数据？是否没有 `/goal` 和运行态合同字段？父 FR/milestone 是否保持轻量？
- 规范契约：命令或 `objective` 是否说明了要达成什么、不能改变什么、如何验证进展、何时停止？
- 语言：包括 `/goal` 正文在内的每句生成内容是否符合 `output_language`？

如果任何答案缺失，先修正 goal 再返回。
