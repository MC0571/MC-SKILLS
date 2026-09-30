---
name: multi-agent
description: 在用户要求多 Agent 协作、委派或并行工作时，协调主 Agent 与 subagent 的职责、模型路由、交接、审查和集成；普通单 Agent 任务不因此启动委派。
metadata:
  version: 0.3.0
  category: "Productivity"
---

# 多 Agent 协作

仅在任务需要且已获准使用 subagent 时应用。使用本技能不扩大代码、GitHub、合并或发布授权；用户和仓库规则仍决定工作范围与停止位置。

## 职责与模型

- 主 Agent 是唯一集成者，负责目标与范围、依赖和共享状态、接口及仓库不变量、任务分配、冲突裁决、最终验收与合并决定；除用户明确授权并由对应 Reviewer 本人提交的该 PR 审查外，GitHub 写入仅由主 Agent 执行；原则上不承担已委派的实质实现。
- 承担探索、研究、实现、调试、测试、迁移、验证或事实收集的 subagent 是执行型，使用 `gpt-6-luna`/max。按实际职责分类，不靠 agent 名称规避路由，也不静默继承主 Agent 模型。
- 只做独立审查的 subagent 是 Reviewer，使用 `gpt-6.1-sol`/xhigh。Reviewer 检查正确性、回归、契约与仓库不变量、测试覆盖、边界和副作用，返回有依据的 findings；不参与实现。若 Reviewer 修改了代码，该修改须由另一独立 Reviewer 或主 Agent 审查。
- 不为这些职责选择其他模型或推理强度；指定模型不可用时，说明受影响的委派，不能悄悄换模型。

## PR 审查

审查 PR 时，由未参与实现的 Reviewer 检查目标 base 与明确 head SHA 之间的完整差异，结论绑定所审查的 base 和完整 head SHA。

只有用户已授权公开发布 PR review 时，才由完成该次审查的 Reviewer 本人提交。提交前核对远端 head 仍为已审 SHA；如果已变化，先对新 head 与 base 的完整差异补审。使用 GitHub review API 显式设置 `commit_id` 为所审 head SHA；`COMMENT` event 可提交 review 正文，普通 PR conversation comment 不绑定审查 commit。提交后核对响应的 `commit_id` 与审查 SHA 一致、`html_url` 存在，并向主 Agent 返回评论 URL、审查 SHA 和结论。若 head 后续变化，旧结论不代表新 head。[GitHub review API 文档](https://docs.github.com/en/rest/pulls/reviews#create-a-review-for-a-pull-request)

公开 review 可用以下短模板；提交时按实际审查证据替换占位符：

```markdown
### PR 审查
- Base: `<base-ref>` (`<base-sha>`)
- Reviewed head: `<full-head-sha>`
- 结论：`<无阻断发现 / 存在阻断问题及摘要>`

### 发现
- <按优先级列问题、位置、影响、证据与建议；没有则写“未发现问题”>

### 检查
- 已执行：<检查及结果>
- 未执行与限制：<未执行事项及限制；没有则写“无”>
```

## 分解、派发与集成

1. 开始时由主 Agent 理解整体目标与关键约束，识别关键未知、依赖与可并行工作单元。可委派探索和局部方案分析，但由主 Agent 根据证据决定任务边界、跨单元接口与关键方案。明确独立、低冲突、可单独验证的工作优先并行；紧密耦合、共享文件冲突或接口尚未稳定时串行，不为增加 agent 数机械拆分。每个实质实现单元只有一个 owner，优化最短关键路径。
2. 每项委派写明目标、范围、仓库基线、相关约束、禁止修改范围（如有）和验收标准。委派同时传递影响本任务的已知决定、依赖、必要输入及待探索问题（如有），明确预期产出；影响范围、共享契约或验收的未知返回主 Agent 裁决。执行型 subagent 完成自身局部验证后，报告修改或发现、实际检查结果及剩余风险；最终集成决定留给主 Agent。
3. 主 Agent 核对返回的实际改动与证据，整合为一个候选；每轮返回后重估新的安全并行机会。优先在候选初步收敛后安排独立审查，不机械地为每个执行型 subagent 配一个 Reviewer；高风险区域可单独加审。
4. 执行型 subagent 与 Reviewer 意见不一致时，主 Agent 依据目标、有效规格、实际代码、测试、接口契约、仓库不变量及可复现证据裁决，不按模型强弱或作者身份裁决。

## 会话复用

可以复用已有 subagent 会话，但每个新任务重新注入目标、边界、仓库基线、约束和已知决定。任务域明显变化、上下文污染或错误假设持续影响判断时，启用新会话。
