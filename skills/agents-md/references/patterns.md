# 从真实仓库提炼的模式

这些是研究样本，不是目标仓库默认政策。先确认相同问题和适用条件，再决定是否采用。完整证据、快照和限制见 [研究报告](../research/repository-analysis.md) 与 [来源记录](../research/sources.json)。

## 1. 把失败机制写成局部规则，而不是泛化警告

DeepSeek Harness 的复盘记载：手动挂载插件的测试绕过真实 Loader，默认导出使注入声明丢失。对应 `packages/AGENTS.md` 既规定导出方式，又说明失败机制并链接复盘；测试策略要求真实组合路径。

可复用的是 `失败机制 → 适用范围 → 禁止的错误选择 → 正确入口 → 回归证据`。不可照搬的是“所有项目都禁止默认导出”。

来源：[局部规则](https://github.com/deepseek-ai/deepseek-harness/blob/639ed015397290b3745d163aafe02ffee4aa3f84/packages/AGENTS.md)、[复盘](https://github.com/deepseek-ai/deepseek-harness/blob/639ed015397290b3745d163aafe02ffee4aa3f84/docs/postmortem/0001-acp-default-export-drops-inject.md)。

## 2. 用产品完成条件阻止实现偏离目标

OpenDesign 要求用户能力通过 UI 和 `od` CLI 访问相同 HTTP 能力，明确内部能力例外。根指令还定义守护进程数据根的单一来源与例外。

可复用的是“哪些交付面必须一起完成、谁拥有唯一状态、哪些例外合法”。不可照搬的是“任何项目的新功能都必须同时有 UI 和 CLI”。

来源：[根指令](https://github.com/nexu-io/open-design/blob/5b19dfa4351b3eed33826ee72746a7c653c23a54/AGENTS.md)。

## 3. 工程指导、产品手册与宣传主张分开

Browser Use 把开发规则与大量 SDK 使用说明放在同一文件。保留用户提供的新模型名称、采用明确工具输入输出结构，具有维护价值；默认推荐自家服务的比较性主张不能当作跨项目工程事实。

不要见到两种环境版本就直接宣布冲突：样本开发命令使用 Python 3.11，快速入门使用 3.12，而读取的依赖清单支持 `>=3.11,<4.0`。要先区分受众、工作情境和兼容范围。

来源：[指令](https://github.com/browser-use/browser-use/blob/4cbe921673b48a488f5415d9159249afd12a625b/AGENTS.md)、[依赖清单](https://github.com/browser-use/browser-use/blob/4cbe921673b48a488f5415d9159249afd12a625b/pyproject.toml)。

## 4. 取舍顺序也可以是高价值指令

Ponytail 在理解真实调用路径后，再依次考虑是否需要构建、已有实现、标准库、原生能力和现有依赖；同时排除安全、可访问性和数据完整性方面的偷工减料。

可复用的是“先理解问题，再按明确顺序选择，说明不可牺牲什么”。不要复制人格口号，也不要把少写文件、少用抽象转成不容例外的统一指标。

来源：[根指令](https://github.com/DietrichGebert/ponytail/blob/e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156/AGENTS.md)。

## 5. 指令要指向真实执行入口，并持续吸收已核实经验

OpenCode 要求在包目录测试，根 `test` 脚本确实会失败；其经验提炼命令关注隐藏关系、非显然路径和必须联动修改的文件。

可复用的是“把习惯性错误挡在已有工具入口，以及从返工中提炼长期知识”。不把一次会话中的临时路径、局部绕过、过期模型或猜测写成永久约束。

来源：[根指令](https://github.com/anomalyco/opencode/blob/7945de208964a49300d7f770d1a71d078db9a4c4/AGENTS.md)、[脚本](https://github.com/anomalyco/opencode/blob/7945de208964a49300d7f770d1a71d078db9a4c4/package.json)、[经验提炼命令](https://github.com/anomalyco/opencode/blob/7945de208964a49300d7f770d1a71d078db9a4c4/.opencode/command/learn.md)。

## 6. 识别一个检查不能证明的另一条路径

Codex 指令指出 Cargo 与 Bazel 的资源处理差异；其 `just test` 不是简单的 `cargo test` 别名，而封装了 nextest 与运行环境。不要因熟悉底层工具就替换项目入口。

DeepSeek Harness 的真实 API 验证与 OpenDesign 核心端到端测试的隔离要求并不应被合并成一句“总用真实服务”或“总用模拟”。先明确测试目标、边界、可重复性和可信观测。

来源：[Codex 指令](https://github.com/openai/codex/blob/d5e6526362f6efa322ca091b61eda495f16ffb30/AGENTS.md)、[justfile](https://github.com/openai/codex/blob/d5e6526362f6efa322ca091b61eda495f16ffb30/justfile)、[DeepSeek 测试政策](https://github.com/deepseek-ai/deepseek-harness/blob/639ed015397290b3745d163aafe02ffee4aa3f84/docs/testing.md)、[OpenDesign e2e 规则](https://github.com/nexu-io/open-design/blob/5b19dfa4351b3eed33826ee72746a7c653c23a54/e2e/AGENTS.md)。

## 7. 完成标准必须适合产物类型

Claude Cookbooks 有意保留 Notebook 输出，要求从上到下执行，并维护示例及作者注册信息。其 Makefile 将格式检查、结构检查和实际执行分开。

可复用的是识别“什么才是这种产物的成功”。不可套用应用仓库里清空所有输出、只要 lint 通过即完成等假设。

来源：[CLAUDE.md](https://github.com/anthropics/claude-cookbooks/blob/d7265d6ae994ccd8429db0594b000073b2f9ad43/CLAUDE.md)、[Makefile](https://github.com/anthropics/claude-cookbooks/blob/d7265d6ae994ccd8429db0594b000073b2f9ad43/Makefile)。

## 使用样本前的检查

问：目标项目是否有同类任务？来源是在表达政策、描述实现，还是给出产品推荐？有无例外？是否已有更适合的工具保证？迁移后什么行为会改变？

若这些问题没有答案，样本只负责启发调查，不负责替项目作决定。
