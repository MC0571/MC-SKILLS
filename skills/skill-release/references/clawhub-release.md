# ClawHub 发布指南

把以下内容作为 ClawHub 发布的最小事实集。ClawHub CLI 和 reusable workflow 会更新；联网时优先重新读取官方文档，发现冲突时以当前官方规范为准。

## 目录

[官方来源](#官方来源) · [Skill 格式](#skill-格式) · [CLI](#cli) · [官方 GitHub Actions](#官方-github-actions) · [发布状态](#发布状态)

## 官方来源

- [ClawHub quickstart](https://github.com/openclaw/clawhub/blob/main/docs/quickstart.md)
- [Authentication](https://github.com/openclaw/clawhub/blob/main/docs/auth.md)
- [ClawHub CLI reference](https://github.com/openclaw/clawhub/blob/main/docs/cli.md)
- [Publishing](https://github.com/openclaw/clawhub/blob/main/docs/publishing.md)
- [Skill format](https://github.com/openclaw/clawhub/blob/main/docs/skill-format.md)
- [官方 skill-publish.yml](https://github.com/openclaw/clawhub/blob/main/.github/workflows/skill-publish.yml)
- [Settings UI](https://github.com/openclaw/clawhub/blob/main/src/routes/settings.tsx)

## Skill 格式

- 目标是一个目录，必须包含 `SKILL.md`；支持可选 YAML frontmatter 和普通支持文件。
- 可移植 Skill 的 `name` 应与父目录一致，并使用 1–64 个小写字母、数字或连字符。
- `description` 会作为目录摘要；需要什么环境变量、命令和权限，就在 `metadata.openclaw` 中如实声明。
- 服务器限制总包大小为 50MB；发布前移除密钥、隐藏文件、缓存和临时产物。
- ClawHub 发布统一采用 MIT-0；不支持每个 Skill 自定义许可、付费或按次计费。若用户不能接受 MIT-0，停止发布。

## CLI

安装与检查：

```bash
npm i -g clawhub
clawhub --help
clawhub --cli-version
```

非技术用户在本机优先执行 `clawhub login`：CLI 会打开浏览器，用户完成 GitHub 登录后，ClawHub 自动签发并保存 Token。看到 `clawhub whoami` 返回正确账号即可，不需要用户复制 Token。

本地回调不可用时，执行 `clawhub login --device`，让用户在浏览器输入一次性代码。只有无头服务器才引导用户打开 [Settings → API tokens](https://clawhub.ai/settings?view=tokens) 创建 Token，并用隐藏输入配置：

```bash
printf '请粘贴 ClawHub Token（输入不会显示）: '
IFS= read -r -s CLAWHUB_TOKEN; printf '\n'
export CLAWHUB_TOKEN
clawhub login --token "$CLAWHUB_TOKEN"
clawhub whoami
unset CLAWHUB_TOKEN
```

配置 GitHub Actions 时，让用户在仓库依次打开 `Settings → Secrets and variables → Actions → New repository secret`，名称填写 `CLAWHUB_TOKEN`、值粘贴 Token，点击 `Add secret`。不要让 Agent 手工把 Token 写入配置文件、workflow 或对话；允许 CLI 按官方登录流程保存凭据。

`clawhub whoami` 失败或返回错误账号时立即停止，不执行正式发布。`401` 表示 Token 缺失、无效或已撤销，应重新登录或创建新 Token；`403` 和 owner 错误保留原文，再检查组织邀请与 publisher 权限。

### 身份与组织权限

- ClawHub 网页端使用 GitHub 登录，但 `CLAWHUB_TOKEN` 必须是 ClawHub 签发的 Token；不要使用 GitHub Token。
- 个人名下发布时省略 `--owner`。不要为了绕过权限随意更换 owner 或冒用组织名称。
- CI 把预期个人或组织 handle 写入非敏感静态 `CLAWHUB_PUBLISHER`；个人发布把 `CLAWHUB_OWNER` 留空，组织发布时让两者相同，并在 dry-run 和正式发布中一致传入 `--owner`。
- 创建新组织 publisher 时执行 `clawhub publisher create <handle> --display-name "<name>"`；创建者成为 owner，新组织默认不代表 trusted/official。
- 加入已有组织时，让组织 owner/admin 打开 [Settings → Organizations](https://clawhub.ai/settings?view=organizations)，用当前用户 handle 发送 `Publisher`、`Admin` 或 `Owner` 邀请；用户接受邀请后再使用 `--owner <handle>`。
- 合法组织或品牌 namespace 已被占用或保留时，提交 [Org / Namespace Claim issue](https://github.com/openclaw/clawhub/issues/new?template=org-namespace-claim.yml)，只提供公开、非敏感证明。
- `--dry-run` 可以不带 Token，只证明本地发布计划可解析；目标 publisher 权限由正式发布请求在服务端校验。

预检与发布：

```bash
clawhub inspect "@$CLAWHUB_PUBLISHER/$CLAWHUB_SLUG" --json
clawhub skill publish ./my-skill --slug "$CLAWHUB_SLUG" --dry-run --json
clawhub skill publish ./my-skill \
  --slug my-skill \
  --name "My Skill" \
  --version 1.0.0 \
  --changelog "Initial release"
```

`clawhub publish` 是旧别名；只有现代子命令不可用时才使用。不要从目录名或 Skill 内部 `name` 推断 slug。ClawHub 条目以 publisher+slug 标识；检查时使用 `@<publisher>/<slug>`，而非裸 slug。其他 publisher 下的同名 slug 不占用当前 publisher 的条目。`inspect` 返回 404 不能单独证明条目不存在；正式发布服务端会按 publisher+slug 原子校验创建或更新，CI 必须先验证登录账号属于预期 publisher，再依赖该服务器端约束。若 inspect 成功，更新必须确认 owner/publisher 正确。

归属校验通过后，更新模式检查目标 publisher 条目的公开 `latestVersion`，本地显式版本必须更高；新 Skill 默认从 `1.0.0` 开始；`--version` 用于显式指定可复现版本。修正配置或版本后只重跑失败的平台与 Skill，不要重放另一市场已成功的发布。

批量同步是单向发布动作，必须由用户明确授权并固定根目录：

```bash
clawhub sync --root ./skills --all --dry-run --json
clawhub sync --root ./skills --all --json
```

不要用 `sync --root` 或 reusable workflow 的 `root` 推断一层集合目录会被递归发现。集合仓库应先生成 `skills/<skill>` 与 `skills/<collection>/<skill>` 的显式路径清单，再逐个调用 `clawhub skill publish`。

## 官方 GitHub Actions

ClawHub 为 Skill 仓库和 catalog 仓库提供 reusable workflow：

```yaml
permissions:
  contents: read
  id-token: write

jobs:
  dry-run:
    if: github.event_name == 'pull_request'
    uses: openclaw/clawhub/.github/workflows/skill-publish.yml@v0.23.3
    with:
      root: skills
      skill_path: skills/my-skill
      dry_run: true

  publish:
    if: github.event_name == 'workflow_dispatch'
    uses: openclaw/clawhub/.github/workflows/skill-publish.yml@v0.23.3
    with:
      root: skills
      skill_path: skills/my-skill
      dry_run: false
    secrets:
      clawhub_token: ${{ secrets.CLAWHUB_TOKEN }}
```

`skill_path` 用于单个 Skill；不传时 workflow 只处理 `root` 下的直接子目录。调用方必须授予 `contents: read` 与 `id-token: write`，否则 `v0.23.3` 的 OIDC 前置检查会停止；真实 Skill 发布目前还需要 `clawhub_token`，不能把 OIDC trusted publishing 当成 Skill 的无 Token 方案。本文模板使用作者核验存在的 `v0.23.3`；官方文档虽然展示 `@v1`，使用前仍须验证该 ref 实际存在。生产环境优先固定到受审查的完整 commit SHA，不要使用 `@main`。

不要直接用该 reusable workflow 对多个显式路径建立 matrix：当前 workflow 每次调用上传固定名称的结果 artifact，多个调用可能冲突。变更自动发布按 [GitHub Actions 发布指南](github-actions.md) 使用固定版本 CLI、显式路径 matrix 和唯一 artifact 名称；单 Skill 手动或 Tag 发布仍可使用官方 reusable workflow。

## 发布状态

正式发布后可能先进入安全扫描或审核，暂时不出现在公开安装和搜索列表。报告应区分：dry-run、已提交、扫描/审核中、公开、失败或被阻断；不要把 CLI 成功提交等同于公开可安装。
