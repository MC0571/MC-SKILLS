---
name: skill-release
description: 检查、预检、发布并配置手动、Tag 或按变更自动发布 Skill 到腾讯 SkillHub 或 ClawHub。用户要发布或更新本地 SKILL、为扁平或一层集合目录配置 GitHub Actions、同步多个 Skill，或排查 Token、slug、版本、许可和审核状态问题时使用。
metadata:
  version: "0.6.0"
  category: "Developer Tools"
---

# Skill Release

帮助用户把一个或一组本地 Skill 安全地发布到腾讯 SkillHub 或 ClawHub，并在需要时配置可审计的 CI/CD 流程。

## 先确认范围

- 手动或 Tag 模式只处理用户明确指定的 Skill 目录；目录根部必须有 `SKILL.md`。
- 变更自动模式只扫描用户确认的 Skill 根目录，支持 `skills/<skill>` 与 `skills/<collection>/<skill>`，不做任意深度递归。
- 多个 Skill 先全部预检；同一平台按确定性顺序发布，两个平台分别执行和报告。
- 先读目标 Skill 及其本地校验说明；不要改写与发布无关的文件。

## 选择发布模式

配置或执行前确认一种模式：

- **手动发布（默认）**：用户每次指定 Skill、平台和版本，正式调用前确认。
- **Tag 发布**：用户确认受保护 Tag 规则和固定 Skill 路径；推送匹配 Tag 即授权该次发布。
- **变更自动发布**：PR 自动检测并 dry-run；合并到已确认的分支后重新检测，再按已授权的平台和失败策略发布。

选择变更自动发布时，一次性确认目标平台、Skill 根目录、监听分支、发布者、统一版本来源、审批策略和失败策略。配置成功表示用户对该范围内未来运行作出持久授权。模板示例默认设置 GitHub Environment 审批；已有仓库的实际 workflow 应按其明确授权合同说明，不能假定 Environment 存在。具体模板与非技术用户配置步骤见 [GitHub Actions 发布指南](references/github-actions.md)。

## 选择发布平台

- 用户说 **Tencent SkillHub / SkillHub**：读取 [SkillHub 发布事实](references/skillhub-release.md)，使用 Tencent 流程。
- 用户说 **ClawHub**：读取 [ClawHub 发布事实](references/clawhub-release.md)，使用 ClawHub 流程。
- 用户要求同时发布：分别完成两套 dry-run 和授权确认；一次发布不会自动同步到另一平台。
- 平台未明确且两者行为会影响结果时，先询问平台，不要猜测。

## 授权与安全边界

本地读取、格式检查和 dry-run 可以直接执行。以下动作需要用户明确授权；如果当前请求已经明确要求执行该动作，仍要在执行前报告目标平台和写入范围：

- 安装或升级 CLI（会执行远程安装命令）。
- 修改 CI/CD 配置或新增 workflow。
- 调用任一平台的正式发布接口。

必须遵守：

- Tencent SkillHub Token 只从 `SKILLHUB_KEY` 读取；ClawHub Token 只从 `CLAWHUB_TOKEN` 读取。两者不能混用。
- Agent 不得把 Token 复制到文件、命令历史、workflow、日志或最终报告；允许各 CLI 按官方登录流程保存自己的凭据。
- 禁止 `echo`、`set -x` 或调试输出泄露 Token；报告中只写“已配置”或“未配置”。
- 默认先做 dry-run；除非用户明确授权，不执行正式发布。
- 自动模式只把已确认的 workflow 触发和审批视为正式发布授权，不把普通 PR、未受保护分支或 dry-run 当成授权。
- 不自动删除、下架、覆盖、转移或回滚 Skill。
- 不自动 push、创建 Release、创建 tag 或修改仓库保护规则。
- 发布到 ClawHub 前必须告知：ClawHub Skill 采用 MIT-0，平台不支持单 Skill 付费；用户不同意时停止。

## 发布工作流

### 1. 检查目标 Skill

确认 `SKILL.md` 位于目标目录根部，并按 YAML 解析 frontmatter。两平台共同检查：

- 目标路径明确、目录未越界，且没有密钥、个人凭据或不应上传的构建产物。
- 本地 lint、test、打包或仓库自带校验（如有）先通过。
- 目录大小与隐藏文件由目标平台规则检查；不要把 `.git`、缓存或临时文件当成发布内容。

独立手动发布到 Tencent SkillHub 时，目标至少要有：

- `slug`：kebab-case，长度 2–128，且在 SkillHub 上全局唯一。
- `version`：合法 SemVer，例如 `1.0.0`。
- `displayName`：对外显示名称。

ClawHub Skill 至少要有 `SKILL.md`；推荐 `name` 与父目录一致、使用小写字母/数字/连字符，`description` 作为目录摘要，并声明实际需要的环境变量、命令和权限。发布时必须显式确认 slug，不能把目录名或内部 `name` 自动当成远端条目身份。

CI/CD 使用统一显式 SemVer：本仓库 `metadata.version` 是版本源，两个平台收到同一版本；分发文件变化而版本未递增时停止。ClawHub-only 的手动发布可使用平台自动 patch，但不能把这种行为带入已选择统一版本的自动流程。

本仓库 CI 在临时发布 bundle 中由目录名生成 SkillHub `slug`、由 `metadata.version` 生成顶层 `version`、由 `SKILL.md` 首个 H1 生成 `displayName`；不要把这些派生字段复制到源 Skill。

不要把本仓库 Codex Skill 的 `name`/`description` 元数据误当成 Tencent SkillHub 的 `slug`/`displayName`；ClawHub 则应保留合法的 `name`/`description`，再用 CLI 参数覆盖展示名或 slug。发现必填项、版本、slug、许可或安全问题时停止，不调用正式发布接口。

### 2. 准备 CLI 与登录

#### Tencent SkillHub

检查 CLI：

```bash
command -v skillhub && skillhub --version
```

CLI 缺失时，展示官方安装命令并征得执行许可：

```bash
curl -fsSL https://skillhub.cn/install/install.sh | bash -s -- --cli-only
```

`SKILLHUB_KEY` 未配置时，读取 [SkillHub 发布事实](references/skillhub-release.md) 的“身份、认证与 Token”。先问用户是在本机终端发布还是配置 GitHub Actions，再一次只给一个操作：引导完成网页注册、实名认证、API Token 创建，以及隐藏输入或 GitHub Secret 配置。团队发布改用已完成团队认证的团队密钥。不要只说“自行配置”，也不要让用户把 Token 粘贴到对话或命令参数文本中。

登录并校验身份：

```bash
: "${SKILLHUB_KEY:?请先设置 SKILLHUB_KEY}"
SKILLHUB_HOST="${SKILLHUB_HOST:-https://api.skillhub.cn}"
skillhub login --key "$SKILLHUB_KEY" --host "$SKILLHUB_HOST"
skillhub auth whoami
```

`whoami` 失败时停止发布。遇到 `403` 时保留原始错误，根据个人实名认证、团队认证或团队成员权限逐项排查，不要一律猜成实名认证失败。

只有当前 CLI 明确不支持 `skillhub login --key` 时，才兼容旧命令 `skillhub auth login --token "$SKILLHUB_KEY" --host "$SKILLHUB_HOST"`。

#### ClawHub

检查 CLI：

```bash
command -v clawhub && clawhub --help
clawhub --cli-version
```

CLI 缺失时，展示安装命令并征得执行许可：

```bash
npm i -g clawhub
# 或：pnpm add -g clawhub
```

交互环境使用 GitHub OAuth：

```bash
clawhub login
clawhub whoami
```

无头环境使用 ClawHub 网页端生成的 Token：

```bash
: "${CLAWHUB_TOKEN:?请先设置 CLAWHUB_TOKEN}"
clawhub login --token "$CLAWHUB_TOKEN"
clawhub whoami
```

GitHub 登录只用于网页身份认证；`CLAWHUB_TOKEN` 必须是 ClawHub 签发的 Token，不能使用 GitHub Token。非技术用户在本机优先使用 `clawhub login`，让浏览器自动完成登录，不要求手工管理 Token；只有无头环境或 CI 才按 [ClawHub 发布事实](references/clawhub-release.md) 逐步配置 Token。个人名下发布时省略 `--owner`；发布到组织 publisher 前，确认当前账号已接受该组织的 `Publisher`、`Admin` 或 `Owner` 邀请。缺少权限时停止并引导组织 owner/admin 授权。

`clawhub whoami` 失败或返回账号与用户预期不符时立即停止，不执行正式发布。保留 `401` / `403` 原始错误，分别按 Token 状态和组织邀请排查，不要用 dry-run 成功代替身份或权限检查。

### 3. 平台 dry-run

#### Tencent SkillHub

```bash
skillhub publish "$SKILL_PATH" --host "$SKILLHUB_HOST" --dry-run
```

Tencent 的 dry-run 只做本地 metadata 与打包检查，不证明 slug 全局可用，也不证明安全或人工审核会通过。

#### ClawHub

现代 CLI 使用：

```bash
clawhub skill publish "$SKILL_PATH" --dry-run --json
```

如果当前 CLI 只有旧别名，才兼容 `clawhub publish "$SKILL_PATH" --dry-run`。ClawHub dry-run 不上传内容；它会解析本地 bundle，并在 JSON 可用时输出机器可读结果。需要发布多个目录且用户明确授权批量同步时，才考虑：

先按预期 publisher 作用域检查 `clawhub inspect "@$CLAWHUB_PUBLISHER/$CLAWHUB_SLUG" --json`。更新时远端条目必须属于预期 publisher；其他 publisher 下的同名 slug 是独立命名空间，不构成本目标的冲突。inspect 返回 404 本身不能证明目标不存在；只有经验证的 publisher 才能依赖服务端正式发布时按 publisher+slug 原子检查创建或更新。归属校验通过后，更新版本须高于该 publisher 条目的公开最新版本。

```bash
clawhub sync --root "$SKILLS_ROOT" --all --dry-run --json
```

### 4. 正式发布

#### Tencent SkillHub

在用户授权后执行：

```bash
skillhub publish "$SKILL_PATH" \
  --host "$SKILLHUB_HOST" \
  --changelog "$CHANGELOG"
```

保持 `slug` 不变并递增 `version`；收到 `pending_review` 时，只能报告“已提交，等待审核”。平台未返回 URL 时，提示用户从个人中心查看，不要自行拼接详情 URL。

#### ClawHub

先确定 `CLAWHUB_SLUG`、`CLAWHUB_NAME` 和 `VERSION`，再执行：

```bash
clawhub skill publish "$SKILL_PATH" \
  --slug "$CLAWHUB_SLUG" \
  --name "$CLAWHUB_NAME" \
  --version "$VERSION" \
  --changelog "$CHANGELOG"
```

只有用户要求组织发布且已确认权限时，才加入 `--owner "$CLAWHUB_OWNER"`；只有用户明确要求标签时才加入 `--tags`。ClawHub 新 Skill 默认从 `1.0.0` 开始，内容变更通常自动递增 patch；CI 为可复现发布时优先显式传入版本。

### 5. 处理多平台与失败

- 同一目录同时发布到两平台时，分别保存两个 CLI 的 JSON/状态结果，不能用一个平台的成功推断另一个平台成功。
- 手动模式或同一市场的多 Skill 发布遇到第一个权限、认证、网络或平台错误时，停止该市场后续发布并报告已完成项；不要循环重放。
- CI 同时发布两个市场时使用独立 job；一方失败不阻止另一方，但最终必须报告部分成功，且不能自动回滚或重复发布成功项。
- 优先保留 CLI 的关键错误文本，不打印 Token，不猜测审核结论。

## CI/CD

只有用户要求自动化或持续交付时才修改 CI 配置。读取 [GitHub Actions 发布指南](references/github-actions.md)，区分本仓库由 artifact ledger 与 `scripts/` 驱动的 workflow 和可复用的通用资产模板；模板需要针对目标仓库配置，不与本仓库实现等同。遵守：

- PR 只做本地检查和 dry-run，不读取发布 Token。
- 手动和 Tag 模式使用明确路径；变更自动模式使用受限检测器生成显式 matrix，不依赖平台隐式递归。
- 优先复用目标仓库已有 artifact ledger；没有等价能力时，才复制 `assets/github-actions/` 下通用检测器、ClawHub 目标辅助脚本、SkillHub 结果投影 filter 和 workflow 模板，并配置新建/更新目标。
- 正式 job 使用平台对应的 Secret 和 publisher 身份前置检查。是否使用 GitHub Environment 审批按该 workflow 的已确认策略配置；不要把模板要求写成现有 workflow 已有的行为。
- ClawHub 使用 publisher+slug 作为目标身份并设置预期 `CLAWHUB_PUBLISHER`；组织发布时 `CLAWHUB_OWNER` 与其相同，个人发布留空。通用资产模板另需为每条路径配置 `new`/`update`；本仓库 workflow 以目录名生成裸 slug，并在 publisher 命名空间内 inspect/校验。Tencent SkillHub 的 slug 全局唯一，本仓库仍使用 `mc0571-<目录名>`。
- 复制检测器时保留固定的 `PyYAML==6.0.3` 安装；双市场共享检测只校验共同版本规则，Tencent 专属顶层 `version` 交给 Tencent dry-run 阻断。
- 同一市场 `max-parallel: 1` 并在首个失败后停止；Tencent 与 ClawHub job 相互独立。
- 固定 CLI、reusable workflow 和 Action 版本；不使用 `@main`，不自动创建 Tag、Release、Environment、Secret 或保护规则。
- 本仓库 workflow 在 `main` push 中只发布新增或版本递增的 Skill，不回填历史资产。`workflow_dispatch` 仅接受当前 `main` HEAD；可用 `scope=changed` 选择变更，或用 `scope=all` 和 `skill_name` 重试当前 Skill。全量快照、Tencent 首发前提与 404 核实、版本跳过规则见 [GitHub Actions 发布指南](references/github-actions.md)。Tencent 发布前会跳过已被 `origin/main` 较高版本取代或已删除的目标；取消 workflow 会停止发布，最终报告仍会运行。
- 只保存不含 Token 的结构化发布结果；不要上传完整原始日志。

## 故障排查

### Tencent SkillHub

- `command not found: skillhub`：重新加载 `PATH`，或检查 `~/.local/bin/skillhub`。
- `401 invalid api key`：重新创建 SkillHub Token 并更新 `SKILLHUB_KEY`。
- `403`：保留原始错误；个人账号检查实名认证，团队账号检查团队认证和成员权限，按网页提示完成对应步骤后重试。
- `409` / slug 冲突：换用全局唯一 slug。
- `429`：等待限频窗口结束，不循环重放。
- 发布后详情页未找到：先检查审核状态，不重复发布同一版本。

### ClawHub

- `command not found: clawhub`：安装或升级 npm/pnpm CLI。
- OAuth 无法打开：使用 `CLAWHUB_TOKEN` 执行 `clawhub login --token`。
- owner/权限错误：个人发布省略 `--owner`；新组织可创建 publisher，已有组织由 owner/admin 在 Settings 邀请当前账号为 `Publisher`、`Admin` 或 `Owner`；不要使用未经授权的 `--owner`。
- slug 或 frontmatter 错误：检查 publisher-scoped slug、`name`、`description`、版本和 `metadata.openclaw` 声明。
- 包大小、隐藏文件或敏感信息错误：清理目录后重新 dry-run。
- 已发布但搜索不到：检查 ClawHub 安全扫描和审核状态；不要重复提交相同内容。

## 报告格式

对每个平台分别报告：

- 平台与目标路径
- slug、显示名和版本
- 本地校验与 dry-run 结果
- 正式发布是否执行
- CLI 返回的状态、审核状态和 URL（若有）
- 失败或审核中的下一步

始终明确区分“本地预检通过”“已提交审核”和“审核后公开”。
