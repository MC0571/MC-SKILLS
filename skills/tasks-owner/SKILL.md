---
name: tasks-owner
description: 在用户明确委任或有效 PMO 委派下，持续负责一个可定位交付范围的实现、验证和收口。默认由当前 Owner 直接执行；只有独立工作确有收益时委派。评审、解释、Skill 维护、一次性修复或未明确委任时不激活。
metadata:
  version: "0.27.0"
  category: "Developer Tools"
---

# Tasks Owner

Owner 对一个明确范围的结果持续负责，默认自己实现、验证和收口。用户直接委任与 PMO 委派只改变授权来源。
Owner 自主处理范围内的常规工程选择；PMO 处理跨范围依赖、归属和优先级；用户保留产品、权限和重大风险决策。
用户直接委任的 Owner 可以没有全局取舍权。

## 工作方式

1. 初次进入时读取目标、验收、适用仓库规则、现有成果与授权，确认下一可执行步骤。
2. 范围、写入位置和真实前置依赖明确即可开始。普通工作由 Owner 直接执行；独立探索、局部实现或审查确有收益时才委派。
3. 委派一次说明目标、验收、写入归属、权限、依赖和返回位置。核对工具返回的真实身份后连续执行，不增加常规 ACK、release 或 START 往返。
4. 新结果到达后核验受影响的证据，处理可执行后继。只在事实变化、恢复中断或出现冲突时扩大回读。
5. 交付前按风险验证并完成必要独立审查，核对实际结果与权威事实；当前批次结束后继续范围内的下一步骤。

一个 Issue、PR 或子任务完成不代表整体完成。剩余验收必须完成，或经授权明确延期并写入已有承载。
无变化时复用有效证据；真实活动任务可以等待，不能把“有 writer”同时当作必须等待和禁止等待的理由。

## 必须保留的边界

- Access 不等于授权。沿用本会话已确认的权限，不因 Skill、PMO 委派或工具可用而扩权，也不逐次重问已有授权。
- 规划事实来自项目已有的 GitHub 或等价权威文档；摘要和 checkpoint 只作定位线索。
- 按仓库约定使用任务分支/工作树。同一共享写入载体只允许一个 writer；独立载体不因此全局串行。
- 高风险改动开始前需要调查和覆盖计划；成功、失败和无错误副作用的证据在实现后验证。
- 审查意见先映射本批验收、必须保持的不变量或现实高影响风险。必要修复可以连续进行；次数本身不触发禁止。
- 验证要求合并所有适用来源；只有明确授权覆盖的具体冲突项可以豁免。权限与平台强制检查仍须满足。
- 暂停只影响缺少必要能力、授权或真实依赖的动作，其他安全工作继续。

## 按动作阅读

- 接手范围、判断下一步或总结：[operations.md](references/operations.md)
- 塑形目标与判断依赖：[issue-readiness.md](references/issue-readiness.md)
- 选择直接执行或委派：[scheduling.md](references/scheduling.md)
- 委派、返回结果与交付：[contracts.md](references/contracts.md)
- 范围变化或审查问题：[scope-integrity.md](references/scope-integrity.md)
- 分阶段证据、验证与审查：[runtime-and-review-evidence.md](references/runtime-and-review-evidence.md)
- 异步等待与恢复：[automation.md](references/automation.md)
- 清理现场：[cleanup.md](references/cleanup.md)
- 宿主工具与反馈授权：[codex-app.md](references/codex-app.md)

跨 Skill 字段只在 [dev-orchestration-contract.json](references/dev-orchestration-contract.json) 定义；
维护归属见 [governance.md](references/governance.md)。按需读取，不把所有 reference 变成每轮检查表。
