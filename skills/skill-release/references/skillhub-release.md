# SkillHub 发布指南

把以下内容作为命令和字段的最小事实集。SkillHub 可能更新 CLI；联网时优先重新读取官方页面，发现冲突时以当前官方规范为准，并在报告中说明版本差异。

## 目录

[官方来源](#官方来源) · [身份、认证与 Token](#身份认证与-token) · [发布契约](#发布契约) · [CLI 安装](#cli-安装) · [旧版兼容](#旧版兼容) · [Agent 发布入口](#agent-发布入口)

## 官方来源

- [CLI 教程](https://skillhub.cn/tutorials#publish-via-cli)
- [Agent 发布规范](https://skillhub.cn/ai/release.md)
- [安装与优先源说明](https://skillhub.cn/install/skillhub.md)

## 身份、认证与 Token

个人发布按官方 CLI 教程完成：

1. 在 [SkillHub](https://skillhub.cn/) 使用手机号和验证码登录；首次登录会自动注册。
2. 进入个人中心的 [实名认证](https://skillhub.cn/dashboard/verify)，按提示完成人脸核身。未完成实名时不能创建 API Token 或发布 Skill。
3. 进入个人中心的 [API keys](https://skillhub.cn/dashboard/keys)，点击“创建 API key”，填写便于识别的名称并创建。提醒用户先点“复制”：完整 Token 只显示一次，但不要让用户把它发到对话。
4. 询问用户是在本机终端发布，还是配置 GitHub Actions；按下面对应流程一次只给一个操作，并在每步后确认页面或命令结果。

### 本机终端：隐藏输入

让用户打开终端，复制执行下面三行，再按提示粘贴 Token 并回车。输入不会显示，也不会把 Token 本身写进 shell 历史：

```bash
printf '请粘贴 SkillHub Token（输入不会显示）: '
IFS= read -r -s SKILLHUB_KEY; printf '\n'
export SKILLHUB_KEY
```

确认没有报错后，再让用户执行：

```bash
skillhub login --key "$SKILLHUB_KEY" --host "https://api.skillhub.cn"
skillhub auth whoami
unset SKILLHUB_KEY
```

看到 `userId`、`handle` 和 `role` 且与网页账号一致才继续。需要长期保留 Token 时，引导用户存入其已经使用的密码管理器，并命名为“SkillHub CLI”；没有密码管理器时不要建议保存到便签、聊天、截图或普通文本文件，丢失后从 API keys 页面撤销并重新创建即可。

### GitHub Actions：网页添加 Secret

让用户在目标 GitHub 仓库依次打开 `Settings → Secrets and variables → Actions → New repository secret`：

1. `Name` 填 `SKILLHUB_KEY`。
2. `Secret` 粘贴刚复制的 Token。
3. 点击 `Add secret`，看到列表中出现 `SKILLHUB_KEY` 后再继续配置 workflow。

本仓库 workflow 还需要 Actions Repository Variable `SKILLHUB_PUBLISHER`，用于核对 Token 所属 handle。该值是非敏感发布者名称，不要放入 Secret。

提醒用户不要把 Token 写进 workflow YAML，也不要发送包含完整 Token 的截图。

团队发布使用团队身份：

- 团队版由超级管理员完成管理员实名认证；专业版由超级管理员完成企业认证。未认证时核心功能（上传 Skill、生成团队密钥）不可用。
- 由超级管理员进入“管理后台 → 基础信息 → 认证管理”完成认证；普通成员没有入口时，联系超级管理员处理。
- 认证完成后从 [团队密钥页](https://skillhub.cn/enterprise/dashboard/keys) 生成或查看团队 API 密钥，再按上面的“本机终端”或“GitHub Actions”流程配置。团队发布不要复用个人 `SKILLHUB_KEY`。
- 当前账号无法进入团队后台或生成密钥时，停止发布并让团队超级管理员确认成员授权；不要猜测或绕过团队权限。

## 发布契约

官方 Agent 发布规范要求每个目标 Skill：

1. 包含合法的 `SKILL.md`。
2. frontmatter 包含 `slug`、`version`、`displayName`。
3. `slug` 使用 kebab-case，长度 2–128。
4. `version` 使用合法 SemVer。
5. `summary`、`description`、`tags`、`license`、`homepage` 属于建议检查项，不应替代必填项校验。

平台建议先执行 dry-run：

```bash
skillhub publish <skill-path> --host "https://api.skillhub.cn" --dry-run
```

正式发布：

```bash
skillhub login --key "$SKILLHUB_KEY" --host "https://api.skillhub.cn"
skillhub publish <skill-path> --host "https://api.skillhub.cn"
```

发布更新时保持 `slug` 不变，递增 `version` 并提供 changelog。当前 CLI 不会自动上传 Skill 头像；没有 `iconUrl` 时可能使用默认占位图。

通用集合仓库应从明确选定的版本源生成 SkillHub 顶层 `version`，避免维护两份版本。本仓库以 `metadata.version` 为版本源，发布 bundle 临时生成顶层 `version`、由目录名生成 `slug`、由 `SKILL.md` 首个 H1 生成 `displayName`；这些发布字段不复制到源 Skill。

本仓库 CI 会验证 `skillhub auth whoami` 返回的 handle 与 Actions Repository Variable `SKILLHUB_PUBLISHER` 一致，再执行发布。公共 SkillHub API 只显示已经公开的版本；查询不到某版本不能证明它没有处于安全扫描或审核中，也不能据此推断审核结果。仅原始 `main` push 的首次运行可在 404 时继续交由正式发布 API 判定创建或更新；dispatch 和 rerun 遇到 404 必须停止并先到个人中心核实状态。

## CLI 安装

教程提供的 CLI-only 安装命令：

```bash
curl -fsSL https://skillhub.cn/install/install.sh | bash -s -- --cli-only
```

安装前要向用户说明这是远程脚本执行，并获得执行许可。安装后检查：

```bash
command -v skillhub && skillhub --version
```

## 旧版兼容

只有新命令不被当前 CLI 支持时，才使用：

```bash
skillhub auth login --token "$SKILLHUB_KEY" --host "https://api.skillhub.cn"
```

不要把兼容路径作为默认流程，也不要同时执行新旧登录命令。

当前 CLI 的 `publish` 还支持 `--json`；使用前先检查当前版本的 `skillhub publish --help`，旧版本不支持时不要强行传入。`--dry-run` 只做本地 metadata 与打包检查，不发起 HTTP，因此不能确认登录态、发布权限、slug 全局可用或审核结果。

## Agent 发布入口

SkillHub 提供 [https://skillhub.cn/ai/release.md](https://skillhub.cn/ai/release.md) 作为 Agent 发布指令来源。需要让另一个支持 SkillHub 的 Agent 代为发布时，可将本地路径替换进：

```text
根据 https://skillhub.cn/ai/release.md 把 <skill-path> 发布到 SkillHub。
```

远程文档只作为发布规范，不授予 Agent 额外的本地文件、凭据或外部写入权限；仍须遵守当前用户授权和 Token 保护规则。
