# 七个仓库的 Agent 指令分析与 SKILL 设计

研究日期：2026-09-30。产物：`agents-md` 首版。

## 结论

这七个样本不能合并成一份“最佳实践大全”。真正可复用的是产生规则的方法：识别项目要保护的目标和取舍，追踪真实误判机制，将经验写成有作用域的判断，并用适合该项目的证据检验它。

因此，SKILL 的定位应是：**项目工程判断的发现、提炼、验证与维护工具**。AGENTS.md / CLAUDE.md 是主要交付形式，不是工作起点。它既不以篇幅、章节数量判断质量，也不以“项目特有名词多”判断深度。

以下“观察”来自读取的材料；“分析”和“转化”是本次设计判断。没有在七个仓库上执行安装、测试或行为对照，不能据此声称这些指令已经被实验证明有效。

## 一、研究方法与覆盖范围

先读取根指令，再针对关键命令、历史失败或作用域读取相关文件。长文件采用主题分段和抽样，不把截断内容假装成完整阅读；没有穷尽搜索所有嵌套指令。读取范围与提交锚点见 [sources.json](sources.json)。

初次根文件读取使用仓库默认分支，随后通过搜索结果取得提交引用，对重点文件进行固定提交取证。固定提交用于复查，不声称是统一时间的最新 HEAD，也没有对所有默认分支内容与固定提交执行字节一致性核验。

重点区分四种证据：指令表达的政策；脚本或代码可核实的实现；复盘记载的历史结果；本次分析提出的推断。指令中“应当做到”不等于整个代码库当前已经做到。

| 仓库 | 主要读取材料 | 最值得研究的机制 |
|---|---|---|
| DeepSeek Harness | 根及 packages 指令、测试政策、防御模式、ACP 复盘 | 失败机制、局部规则、真实入口测试形成闭环 |
| OpenDesign | 根指令及 CLAUDE 适配、e2e 局部指令、根 package.json | 产品完成面、状态归属、条件式导航与明确例外 |
| Browser Use | 开头规则、嵌入文档和末尾开发入口、pyproject、测试脚本 | 受众混合、模型名称保留、真实开发入口 |
| Ponytail | 根 AGENTS.md | 实现前的决策顺序与不可牺牲的底线 |
| OpenCode | 根 AGENTS.md、package.json、经验提炼命令 | 架构不变量、命令入口硬约束与持续提炼 |
| Codex | 根指令主要章节、justfile | 双构建系统、受控测试入口、接口及快照要求 |
| Claude Cookbooks | 根 CLAUDE.md、Makefile；示例 CLAUDE 搜索片段 | Notebook 的特定完成标准与验证层级 |

## 二、逐仓库分析

### 1. DeepSeek Harness：把曾经做错的机制保留下来

**观察。** 根指令包含模型可见内容必须能从会话日志重建、行为通过插件扩展、注册具有可清理生命周期、不同输出面对应不同测试等要求。`packages/AGENTS.md` 把函数插件与服务类的导出方式区分开，并解释混用默认导出为何使 Loader 丢失函数插件的命名空间。[D1]、[D2]

这里不只是“禁止默认导出”的风格偏好。仓库复盘记载，ACP 在 178 个单元测试通过、行覆盖率 100% 时仍无法建立或加载会话：手工挂载插件绕过真实 Loader，另一个可选服务访问问题又被简化的调用拓扑掩盖。复盘还指出，带密钥测试被跳过、旧构建产物被解析到，都可能产生错误的成功印象。这些是来源记载的历史结果，本次没有复现。[D5]

对应测试政策要求检查外部文件、状态等实际结果，而不是仅相信 Agent 自称完成；要求经过真实组合、发布入口或构建产物验证。防御模式还区分“发起取消”和“等待退出完成”等容易混淆的生命周期事实。[D3]、[D4]

**分析。** 高价值来自可追溯的因果链：具体故障 → 错误机制 → 局部规则 → 对应验证。它解释了为什么一些十几行的约束比整页风格原则更值得保留。根文件同时含有大量包目录、流程和细节，存在持续控制导航与常驻内容比例的维护需求；但不能只因长就删去必要规则。

**转化。** SKILL 必须追踪实际入口、消费者和失败原因，并保留例外。“函数插件不得混用默认导出”不能变成“所有项目禁止 default”；真实 API 策略、覆盖率阈值、依赖偏好也都不是跨项目默认值。[D1]、[D2]、[D4]

### 2. OpenDesign：用交付面和所有权约束避免做错产品

**观察。** 根文件自称跨仓库规则和导航入口，并要求进入相应目录后读取局部指令。`CLAUDE.md` 仅导入 `@AGENTS.md`。根指令区分历史归档与当前规范，定义守护进程数据根由 `OD_DATA_DIR` 一次解析为 `RUNTIME_DATA_DIR`，并列出合法例外和不应延续的旧路径模式。[O1]、[O2]

用户能力的交付不止 UI：指令要求 Web UI 与 `od` CLI 调用相同 HTTP 能力，内部能力可以有明确不适用理由。它还指出两套提示词组合实现会按运行条件选择，修改其中一处并不保证另一条路径得到相同规则。这是在防止“代码实现了，但交付面缺失”以及“只修一个分支”的失败。[O1]

根 `package.json` 确实提供 `tools-dev` 等控制入口，而没有根级 `build`、`test` 汇总脚本。e2e 局部规则进一步规定核心测试隔离外部服务、资源归属、并行分片与顺序独立；一次重试后通过也不能自动说明原失败无关紧要。[O3]、[O4]

**分析。** 这个样本的重要价值是把“谁拥有状态”“哪些面要一起完成”“什么是合法例外”写清楚。根文件又承载较多 UI、运行时和平台细节，部分内容值得按任务触发移入局部文档，但迁移必须保持跨目录约束仍然可见。开头声称自己是薄入口，并不自动意味着实际内容已经足够分层。

**转化。** SKILL 应先识别项目真正的完成条件，再决定测试和指令。不能把 UI+CLI 双面规则推广到所有产品，也不能把这里的隔离测试政策覆盖到其他项目的真实 Provider 验证要求。

### 3. Browser Use：有用规则可能被手册和推荐内容包围

**观察。** 开头包含 uv、Pydantic v2、提交前检查、结构化 ActionResult、不随意创建演示文件，以及不要仅因不认识就替换用户模型名称等要求。之后嵌入大量 SDK 快速入门、参数、生产使用和工具说明，也包含默认推荐自家模型、云浏览器的比较性主张。[B1]

这些并非全部无关：文件末尾还有本地开发入口，包含 `bin/lint.sh` 和 `bin/test.sh`。本次核对的 `bin/test.sh` 会切换到仓库根目录并通过 uv 调用 pytest 的 `tests/ci` 集合，所以不能把整份长文件简单描述为“只有营销、没有工程命令”。[B1]、[B3]

也不能制造伪冲突。开头开发示例使用 Python 3.11，快速入门使用 3.12；读取的 `pyproject.toml` 声明 `>=3.11,<4.0`，两者在所声明范围内可以同时成立。[B1]、[B2]

**分析。** 主要问题是受众和信息角色混合：仓库贡献指导、SDK 使用手册和产品推荐放在一个入口里。商业推荐是来源的主张，不是本次独立验证的性能结论。精简应该按角色分离，同时保留有用的开发命令和不熟悉模型名称时的谨慎要求。

**转化。** SKILL 在评价之前先判断内容服务谁、何时需要；区分政策与宣传，不按关键词或版本号差异直接报错。

### 4. Ponytail：不只有项目独有知识才有价值

**观察。** 该指令将“少做无用工作”写为选择顺序：先理解任务并追踪真实流程，再判断是否需要构建、是否已有实现、标准库或平台能力是否足够、现有依赖能否解决，最后才新增代码。它强调修共同根因而不是仅补工单提到的调用点，同时明确安全、数据完整性、可访问性等不能成为省代码的代价。[P1]

**分析。** 它的主体不是仓库架构清单，而是决策政策。仅以“缺少构建命令、缺少仓库特有名词”评价，会错过其主要目的。相反，直接复制“无请求不建抽象”“只留一个检查”等文字，也可能与目标仓库已有设计和测试实践冲突。

**转化。** SKILL 要保留维护者真实认可的取舍顺序，而不是强迫所有指导都变成技术禁令。可借鉴明确顺序和例外，不必借用人格角色，也不能让最短差异压过正确根因修复。

### 5. OpenCode：精确入口、架构语义和经验维护结合

**观察。** 根指令明确默认分支是 `dev`，生成 SDK 和客户端代码的入口、运行时依赖方向、测试和类型检查工作目录，以及 V2 会话持久接收、执行唤醒、排队与引导输入的不同语义。它也包含非常明确的代码风格偏好。[C1]

测试入口不是一句建议：根 `package.json` 的 `test` 脚本明确输出禁止在根运行的提示并退出失败。另一个 `.opencode/command/learn.md` 要求从会话提炼隐藏关系、非显然执行路径、误导性错误、环境细节和联动文件，将经验放在最接近实际作用域的位置。[C2]、[C3]

**分析。** 文档与工具入口相互支撑，可以防止 Agent 按熟悉的默认习惯跑错地方。经验提炼机制也展示了更新入口。但会话经验仍需复核：一次性绕过或未确认的推断，不应因为经历了一次调试就自动成为长期政策。“少用单次助手”与允许有清晰概念的复杂助手也应按条件理解，不能按相反关键词宣布冲突。[C1]、[C3]

**转化。** 保留项目偏好，同时核对真实脚本和条件。维护允许“本次没有值得新增的规则”，不做不断膨胀的对话记忆。

### 6. Codex：写清“另一种构建和执行方式会怎样失败”

**观察。** 根指令把 sandbox 相关环境边界、配置 schema 生成、Rust 依赖与 Bazel lock 联动、Cargo/Bazel 资源差异、UI 快照以及 Rust/TypeScript 协议字段同步写得具体。代码通过 Cargo 构建，不代表 Bazel 的资源声明已正确，这种跨工具路径差异具有明确决策价值。[X1]

本次核对的 `justfile` 显示，`just test` 使用 nextest，并设置项目运行环境；它不是可以随意替换成裸 `cargo test` 的装饰性别名。根指令还按受影响项目和共享层选择验证范围，并包含仓库自身的全量执行授权要求。[X1]、[X2]

**分析。** 强项在于揭示“技术上看似等价，实际不等价”的入口和验收。根文件同时混合编码惯例、review、UI 和协议细节，是否进一步分层需考虑实际任务和加载成本，而不是照搬固定行数标准。诸如全量测试审批、格式化后不重复测试等要求只能作为该仓库政策研究，不能成为本 SKILL 的通用规则。

**转化。** SKILL 要核对生成物、构建系统、运行入口和消费者联动；不因模型熟悉底层命令就替换已有封装。保留已确认安全边界，不用“修测试”作为绕过限制的理由。

### 7. Claude Cookbooks：工程完成应服务 Notebook 的用途

**观察。** 根 CLAUDE.md 要求保留用于展示的 Notebook 输出、一个 Notebook 一个概念、从上到下运行，并维护 `registry.yaml` 和作者信息；还说明 Notebook 的部分编码检查与普通 Python 文件不同。模型引用政策要求查当前资料，并区分提供方格式。[A1]

Makefile 把 `make check` 的格式与 lint、Notebook 结构测试，以及需要实际执行的 Notebook 测试分开。前者通过不能说明后者已经成功。本次仅核对入口定义，没有运行真实 API。[A2]

**分析。** 这里的目标是可阅读、可执行的教学示例，而不是普通应用的运行时。强行清除输出或按应用仓库套统一完成标准，会损害产物本身。示例目录中的另一份 CLAUDE.md 在搜索片段中是虚构公司的任务上下文，也说明文件名本身不足以确定其维护角色。[A3]

**转化。** SKILL 首先识别产物类型、受众与成功条件；不硬编码模型列表，不混淆静态检查和实际执行，不把所有同名文件都提升为仓库规范。

## 三、为什么不能求七个文件的并集或交集

| 取舍 | 样本呈现的不同方向 | 应提炼的问题，而不是统一的答案 |
|---|---|---|
| 依赖 | DeepSeek 允许用维护良好的依赖减少自有代码；Ponytail 优先避免新增依赖 | 总维护成本、已有能力、真实需要和项目政策是什么？ |
| 外部服务 | DeepSeek 有真实 API 验证；OpenDesign 核心 e2e 要隔离服务 | 当前测试证明哪一层，怎样避免不可重复或假通过？ |
| 测试入口 | OpenCode 在包目录运行；Codex 保留 just 封装；Browser Use 使用 bin 脚本 | 工作目录、环境、构建模式和真实测试集合是什么？ |
| 内容类型 | Cookbooks 保留展示输出；Ponytail 侧重取舍；OpenDesign 侧重交付面 | 这个项目的成功产物和主要误判分别是什么？ |
| 指令组织 | 薄 CLAUDE 适配与长根文件都存在 | 哪些内容必须常驻，哪些需要明确条件式阅读？ |

上述差异分别见各节来源。它们证明“普遍统一的规则集”不是合理目标；并不证明所有现有项目规则都没有缺陷。

一个词在不同环境中的含义也不同：测试中的 mock、构建中的 source、文件名中的 CLAUDE，必须结合谁在用、何时加载和证明什么来解释。

## 四、对原研究报告的保留与补强

用户提供的《AGENTS.md 工程最佳实践研究报告》（2026-09-12）是本次研究基础，原文未复制进包。以下行号对应本次提供的 810 行文本。

**保留。** 入口与深层资料分工、局部作用域、单一内容源、命令及引用核实、自然语言政策不等于权限执行层，仍是有效的结构底线（原报告 L9–L21、L55–L87、L230–L253、L695–L755）。本次没有把报告中的所有生态统计和工具行为当作已重新验证的当前事实。

**补强一：先发现判断，再整理文档。** 原报告已提出信息价值和非显然陷阱，但上一版 SKILL 将其过早变成扫描、检查与精简。现在要求从真实工作路径、所有权、用户可见结果和历史失败中发现候选知识。

**补强二：不只接收“项目独有事实”。** Ponytail 提醒我们，已被维护者明确选择的决策顺序也可能有价值。判断标准是能否影响正确选择，而不是能否在其他项目出现。原报告的“三个问题至少回答一个”（L108–L121）不应被误读成排斥所有可从代码推断的内容。

**补强三：保留政策强度与例外。** 源代码当前实现不是唯一设计权威；历史事故不是当前缺陷证明；宣传不是独立性能测量。迁移时必须同时保存适用情境、约束强度、例外和读取入口。

**补强四：把行为检验与格式检查分开。** 在原报告的命令与 CI 核验基础上，加入错误方案、正确方案和删除检查。真正效果仍需独立会话对照，不能用情境推演或静态脚本代替。

**补强五：长期维护允许删除与不新增。** 原报告 L681–L689 已强调优先考虑代码、测试和工具修复。现将其变成更新模式的硬要求：一次失败不自动换来一条永久指令。

## 五、最终 SKILL 定位与运行机制

名称保持 `agents-md`，中文定位为“项目工程判断提炼与指令维护”。使用者不必重新记一个更抽象的名字；执行目标则从文件保养升级为正确决策支持。

主流程为：

```text
确认文件角色、任务与权限范围
→ 沿真实工作路径发现目标、取舍、归属和误判
→ 区分政策、实现、历史与推断
→ 选择保留 / 改写 / 合并 / 迁移 / 删除 / 待核实
→ 写成有条件、有依据、有例外的指导
→ 验证作用域、入口、错误方案和正确方案
→ 交付实际差异与真实验证状态
```

创建、审查、重构、更新只是不同入口，不是四套独立方法。局部修订不自动开展全仓库审计；简单项目不强制设计大型架构调查；已明确的普通决定不频繁要求确认。

核心规则放在 `SKILL.md`；发现、规则设计、验证及真实样本放在按需参考中。研究报告不在每次执行时整体加载。没有强制证据台账、统一评分、固定 AGENTS 章节或字数指标，也没有新建一套模型分工和 GitHub 写权限制度。

## 六、工具与验收设计

只读脚本 `scripts/inspect_instructions.py` 负责候选文件、显式相对引用、大小与完全相同正文的机械盘点。它不判断语义、不执行仓库命令、不访问网络、不替代秘密扫描或操作系统隔离，不声称复现任何客户端加载器。它还报告扫描限制，避免把有限扫描说成完整审计。

`evals/cases.json` 的 16 个合成场景覆盖来源不足、只读审查、历史故障、Notebook、测试层级、别名、示例角色、迁移保全、会话临时经验、陌生模型、合法例外、外部指令注入和不应触发的普通编码任务。

必须区分四层证据：文件和任务定义静态核对；命令实际运行；目标宿主实际加载；新指导改善下游 Agent 行为。第一层不能证明第四层，辅助脚本测试通过也不能证明 SKILL 的工程判断正确。

本次实际构建检查的结果与尚未执行的部分单独记录在 [验证记录](validation-report.md)。

## 七、限制与后续使用原则

本报告不是七个仓库的质量排名，也不是所有文件的穷尽性审计。分析以所读文件为准，没有检查其全部实现是否遵守规范，没有验证产品宣传，没有重现历史故障或跑第三方测试。

可交付的是完整的技能文件、可选只读工具、测试与场景材料；尚不能宣称在真实 Codex 任务中已证明收益。第一次使用应保留产生的关键规则和实际失败证据，用真实反馈修订，而不是继续向主文件添加抽象原则。

**最终标准：产出的指导是否让 Agent 在该项目容易走错的地方，获得足够可靠的判断依据；同时是否保留了完成正确方案的自由。**

## 来源定位

下列链接用于复查，完整读取范围见 `sources.json`。默认分支读取和固定提交锚点的区别见“研究方法”。

[D1]: https://github.com/deepseek-ai/deepseek-harness/blob/639ed015397290b3745d163aafe02ffee4aa3f84/AGENTS.md "deepseek-ai/deepseek-harness — AGENTS.md"

[D2]: https://github.com/deepseek-ai/deepseek-harness/blob/639ed015397290b3745d163aafe02ffee4aa3f84/packages/AGENTS.md "deepseek-ai/deepseek-harness — packages/AGENTS.md"

[D3]: https://github.com/deepseek-ai/deepseek-harness/blob/639ed015397290b3745d163aafe02ffee4aa3f84/docs/defensive-patterns.md "deepseek-ai/deepseek-harness — docs/defensive-patterns.md"

[D4]: https://github.com/deepseek-ai/deepseek-harness/blob/639ed015397290b3745d163aafe02ffee4aa3f84/docs/testing.md "deepseek-ai/deepseek-harness — docs/testing.md"

[D5]: https://github.com/deepseek-ai/deepseek-harness/blob/639ed015397290b3745d163aafe02ffee4aa3f84/docs/postmortem/0001-acp-default-export-drops-inject.md "deepseek-ai/deepseek-harness — docs/postmortem/0001-acp-default-export-drops-inject.md"

[O1]: https://github.com/nexu-io/open-design/blob/5b19dfa4351b3eed33826ee72746a7c653c23a54/AGENTS.md "nexu-io/open-design — AGENTS.md"

[O2]: https://github.com/nexu-io/open-design/blob/5b19dfa4351b3eed33826ee72746a7c653c23a54/CLAUDE.md "nexu-io/open-design — CLAUDE.md"

[O3]: https://github.com/nexu-io/open-design/blob/5b19dfa4351b3eed33826ee72746a7c653c23a54/e2e/AGENTS.md "nexu-io/open-design — e2e/AGENTS.md"

[O4]: https://github.com/nexu-io/open-design/blob/5b19dfa4351b3eed33826ee72746a7c653c23a54/package.json "nexu-io/open-design — package.json"

[B1]: https://github.com/browser-use/browser-use/blob/4cbe921673b48a488f5415d9159249afd12a625b/AGENTS.md "browser-use/browser-use — AGENTS.md"

[B2]: https://github.com/browser-use/browser-use/blob/4cbe921673b48a488f5415d9159249afd12a625b/pyproject.toml "browser-use/browser-use — pyproject.toml"

[B3]: https://github.com/browser-use/browser-use/blob/4cbe921673b48a488f5415d9159249afd12a625b/bin/test.sh "browser-use/browser-use — bin/test.sh"

[P1]: https://github.com/DietrichGebert/ponytail/blob/e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156/AGENTS.md "DietrichGebert/ponytail — AGENTS.md"

[C1]: https://github.com/anomalyco/opencode/blob/7945de208964a49300d7f770d1a71d078db9a4c4/AGENTS.md "anomalyco/opencode — AGENTS.md"

[C2]: https://github.com/anomalyco/opencode/blob/7945de208964a49300d7f770d1a71d078db9a4c4/package.json "anomalyco/opencode — package.json"

[C3]: https://github.com/anomalyco/opencode/blob/7945de208964a49300d7f770d1a71d078db9a4c4/.opencode/command/learn.md "anomalyco/opencode — .opencode/command/learn.md"

[X1]: https://github.com/openai/codex/blob/d5e6526362f6efa322ca091b61eda495f16ffb30/AGENTS.md "openai/codex — AGENTS.md"

[X2]: https://github.com/openai/codex/blob/d5e6526362f6efa322ca091b61eda495f16ffb30/justfile "openai/codex — justfile"

[A1]: https://github.com/anthropics/claude-cookbooks/blob/d7265d6ae994ccd8429db0594b000073b2f9ad43/CLAUDE.md "anthropics/claude-cookbooks — CLAUDE.md"

[A2]: https://github.com/anthropics/claude-cookbooks/blob/d7265d6ae994ccd8429db0594b000073b2f9ad43/Makefile "anthropics/claude-cookbooks — Makefile"

[A3]: https://github.com/anthropics/claude-cookbooks/blob/d7265d6ae994ccd8429db0594b000073b2f9ad43/claude_agent_sdk/chief_of_staff_agent/CLAUDE.md "anthropics/claude-cookbooks — claude_agent_sdk/chief_of_staff_agent/CLAUDE.md"
