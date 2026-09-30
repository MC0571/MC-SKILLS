# GitHub Actions 发布指南

仅在用户明确要求配置 CI/CD 时读取。先确认发布模式、平台、Skill 根目录、版本来源、发布者、审批策略和失败策略；优先复用目标仓库已有的 artifact 清单或 workflow。

本文的模式、YAML 示例、资产复制与 Environment 步骤说明可复用模板。已配置仓库的行为请看其实际 workflow；MC-SKILLS 当前实现单列于下文。

## 目录

[模式选择](#模式选择) · [共同安全规则](#共同安全规则) · [手动发布](#手动发布) · [Tag 发布](#tag-发布) · [变更自动发布](#变更自动发布) · [非技术用户配置](#非技术用户配置)

## 模式选择

| 模式 | 触发 | 正式发布授权 |
|---|---|---|
| 手动发布 | `workflow_dispatch` | 每次手动运行即授权本次目标 |
| Tag 发布 | 受保护版本 Tag | 配置时确认 Tag 规则，推送 Tag 即授权 |
| 变更自动发布 | PR dry-run；`main` push 发布 | 配置时确认持久范围，默认再经过 Environment 审批 |

配置前逐项向用户复述并确认：目标平台、Skill 根目录、监听分支或 Tag、发布者、统一版本字段、是否保留人工审批，以及两个市场独立失败的行为。通用变更自动发布模板默认经过 Environment 审批；已配置 workflow 则以其持久授权和真实审批配置为准。

## 共同安全规则

- PR 只执行本地检查和 dry-run，不读取发布 Secret。
- 正式发布只处理用户确认的明确路径或检测器生成的受限路径。
- Tencent 只读取 `SKILLHUB_KEY`；ClawHub 只读取 `CLAWHUB_TOKEN`。
- 正式 job 先执行 `whoami` 并核验预期 publisher；认证失败或账号不符立即停止。
- 不自动创建 Secret、Environment、Tag、Release、保护规则或下架请求。
- CLI、reusable workflow 和第三方 Action 使用前重新核验版本；正式发布固定到稳定版本或完整 commit SHA，不使用 `@main`。
- 两个平台使用独立 job 和结果；一方失败不推断另一方失败或成功。

## 手动发布

对单个或少量固定 Skill 使用 `workflow_dispatch` 输入或静态 matrix。嵌套目录必须传完整路径，例如 `skills/dev/nested-skill`，不能只传 Skill 名。

```yaml
on:
  workflow_dispatch:
    inputs:
      skill_path:
        description: Repository-relative Skill directory
        required: true
        type: string

jobs:
  dry-run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate Skill path
        id: skill
        env:
          SKILLS_ROOT: skills
          SKILL_PATH_INPUT: ${{ inputs.skill_path }}
        run: |
          python3 - <<'PY'
          import os
          import re
          from pathlib import Path

          repository = Path.cwd().resolve()
          root = (repository / os.environ["SKILLS_ROOT"]).resolve()
          skill = (repository / os.environ["SKILL_PATH_INPUT"]).resolve()
          try:
              root.relative_to(repository)
              relative = skill.relative_to(root)
          except ValueError as exc:
              raise SystemExit("SKILLS_ROOT and Skill path must stay inside the repository") from exc
          if len(relative.parts) not in {1, 2} or any(
              not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", part)
              for part in relative.parts
          ):
              raise SystemExit("Skill path must use one or two safe kebab-case components")
          if not skill.is_dir() or not (skill / "SKILL.md").is_file():
              raise SystemExit("Skill path must be a directory containing SKILL.md")
          with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
              output.write(f"path={skill.relative_to(repository).as_posix()}\n")
          PY
```

后续发布步骤继续通过 `env` 传递 `SKILL_PATH: ${{ steps.skill.outputs.path }}`，shell 中只使用 `"$SKILL_PATH"`。输入先由 Python 规范化并限制在用户确认的 Skill 根目录；不要把表达式或未经校验的输入直接插入 shell。平台安装、认证和发布命令沿用主 Skill 的对应流程。

## Tag 发布

Tag 模式只发布配置时明确列出的路径，不从 Tag 名猜测 Skill。为单 Skill 仓库使用 `skill-v*`；集合仓库为每个受控路径建立静态 matrix，或使用仓库已有的 release ledger 生成 matrix。

```yaml
on:
  push:
    tags:
      - "skill-v*"

jobs:
  publish:
    if: startsWith(github.ref, 'refs/tags/skill-v')
    strategy:
      matrix:
        include:
          - path: skills/my-skill
            name: my-skill
            version: 1.0.0
          - path: skills/dev/another-skill
            name: another-skill
            version: 1.2.0
```

为 Tag 配置保护规则。不要由 Skill 自动创建 Tag；版本和路径必须来自受审查的仓库事实，不能从用户可控字符串拼接。

单个 ClawHub Skill 可调用官方 reusable workflow，并显式传入 `skill_path`。当前已核验存在的稳定 ref 为 `v0.23.3`；官方文档展示的 `@v1` 在使用前仍须确认实际 ref 存在，生产配置优先固定完整 commit SHA。

```yaml
jobs:
  clawhub:
    permissions:
      contents: read
      id-token: write
    uses: openclaw/clawhub/.github/workflows/skill-publish.yml@v0.23.3
    with:
      skill_path: skills/dev/another-skill
      dry_run: false
    secrets:
      clawhub_token: ${{ secrets.CLAWHUB_TOKEN }}
```

ClawHub reusable workflow 不传 `skill_path` 时只扫描 `root` 的直接子目录，不能发现 `skills/<collection>/<skill>`。不要对多个显式路径直接建立 reusable workflow matrix：当前 workflow 会为每次调用上传同名结果 artifact，可能发生冲突；集合自动发布使用下一节的直接 CLI 模板。

## 变更自动发布

从 Skill 资产复制：

```text
assets/github-actions/detect_changed_skills.py
  → .github/scripts/detect_changed_skills.py
assets/github-actions/clawhub_target.py
  → .github/scripts/clawhub_target.py
assets/github-actions/skillhub_publish_result.jq
  → .github/scripts/skillhub_publish_result.jq
assets/github-actions/changed-skill-release.yml
  → .github/workflows/skill-release.yml
```

复制后按用户确认结果执行以下裁剪：

1. 保留 Tencent、ClawHub 或两者对应的 dry-run/publish job。
2. 修改 `SKILLS_ROOT`、监听分支和 Environment 名称。
3. 为 ClawHub 设置预期 publisher 和逐路径目标；个人发布把 `CLAWHUB_OWNER` 留空，组织发布时让它与 `CLAWHUB_PUBLISHER` 相同。
4. 保留模板固定的 `PyYAML==6.0.3` 安装；检测器使用 `safe_load` 解析完整 YAML frontmatter。
5. 核验并固定当前 CLI 版本；不要静默升级。
6. 先执行两个脚本的 `--self-test`、仓库本地校验和 `actionlint`，再提交 workflow。

ClawHub 配置示例：

```yaml
env:
  CLAWHUB_PUBLISHER: "your-personal-or-organization-handle"
  CLAWHUB_OWNER: "" # 组织发布时填写与 CLAWHUB_PUBLISHER 相同的值
  CLAWHUB_TARGETS_JSON: >-
    {"skills/my-skill":{"slug":"my-unique-skill","mode":"new"},"skills/dev/nested-skill":{"slug":"nested-skill","mode":"update"}}
```

每个进入 ClawHub matrix 的路径都必须有配置。ClawHub 身份是 publisher+slug；查询使用 scoped slug `@<publisher>/<slug>`，另一个 publisher 下的同名 slug 不构成本目标的冲突。`new` 表示向当前 publisher 命名空间创建目标，`update` 表示更新该 publisher 的现有目标。`inspect` 返回 404 不足以证明不存在；经验证的 publisher 可依赖正式发布服务端按 publisher+slug 原子检查创建或更新。若 `inspect` 成功，`update` 必须确认条目属于 `CLAWHUB_PUBLISHER`。目录名、Skill 内部 `name` 和远端 slug 是三个独立字段，不得互相推断。

检测器仅接受 Git 已跟踪的普通文件，并支持：

```text
skills/<skill>/SKILL.md
skills/<collection>/<skill>/SKILL.md
```

它比较 base/target Git 快照，而不是使用 ClawHub 的单层 `root` 扫描。新增和内容已变化且版本递增的 Skill 进入 matrix；无变化安全跳过；删除、移动、重复名称、非法路径、符号链接、版本缺失或未递增均阻断自动发布。顶层 `version` 与 `metadata.version` 同时存在时必须相同。`--require-top-level-version` 只检查本次新增或更新的 Skill，适用于 Tencent-only 检测；双市场模板不启用它，由 Tencent dry-run 独立校验平台字段，避免阻断 ClawHub。

```bash
python3 .github/scripts/detect_changed_skills.py \
  --root skills --base <base-ref> --target <target-ref> \
  --github-output "$GITHUB_OUTPUT"
```

标准输出为包含 `schema_version`、base/target commit、`matrix.include` 和 `removed` 的 JSON；GitHub output 追加 `matrix`、`has_changes` 与 `count`。

模板行为：

- PR：检测并分别执行两个市场 dry-run，不读取 Secret。
- `main` push：重新检测和 dry-run；正式 job 等待 `skill-release-production` Environment 审批。
- 同一市场按确定性路径顺序、`max-parallel: 1` 发布并在首个失败后停止；两个市场互不依赖。
- ClawHub 在 dry-run 和正式发布前都按 `@<publisher>/<slug>` 执行 `inspect`；若成功，更新必须确认 publisher 匹配。更新版本必须严格高于目标 publisher 条目的公开 `latestVersion`。
- `CLAWHUB_OWNER` 在 dry-run 与正式发布中保持一致；空值表示个人 publisher，非空时必须与 `CLAWHUB_PUBLISHER` 相同。
- 每个 Skill/平台使用唯一 artifact 名称，只保存结构化结果，不上传 Token 或完整调试日志。
- 删除或移动只报告，不调用删除、转移或发布接口。

若目标仓库已有等价 artifact ledger，复用它输出相同 matrix，不复制检测器或维护第二份版本规则。

### MC-SKILLS 当前 workflow

本仓库 `.github/workflows/skill-release.yml` 使用 repository artifact ledger 和 `scripts/`，仅发布 `skills/<skill>` 下的独立 Skill。PR 执行检测与 dry-run；监听到 `main` 上分发文件有变化时，发布新增或版本递增的 Skill。文件变化但版本未递增会阻断发布；不变的 Skill 跳过，删除或移动报错；不会回填历史资产。CI 使用 `metadata.version` 作为两平台共同版本源，SkillHub 的 `slug`、顶层 `version` 和 `displayName` 在临时 bundle 生成，不重复保存在 Skill 源目录。Tencent 发布前会查询公开条目：若能看到条目，需确认 owner 与预期发布者一致，且本地版本高于公开 latest。公开 API 不会显示安全扫描或审核中的版本，因此 404 不能证明该版本尚未提交或已通过审核；只有原始 `main` push 的首次运行可在状态未验证时继续交给授权发布 API 判定创建或更新，dispatch 或重跑遇到 404 会停止，先到个人中心核实状态后再重试。

此 workflow 没有 GitHub Environment 审批；`main` push 是配置的持续发布授权范围。发布 job 分别使用 Tencent SkillHub 与 ClawHub，ClawHub slug 使用 `mc0571-` 前缀。

在 Actions Repository Variables 中配置：`SKILLHUB_PUBLISHER`（预期 Tencent handle）、`CLAWHUB_PUBLISHER`（预期 ClawHub publisher）和 `CLAWHUB_OWNER`（个人发布留空，组织发布填写与 publisher 相同的 handle）。在 Repository Secrets 中配置 `SKILLHUB_KEY` 和 `CLAWHUB_TOKEN`。

失败后从 `workflow_dispatch` 选择 `commit_sha`、`market`，并可填写 `skill_name`。SHA 必须是 `main` 历史中的完整 40 位 commit；工作流只允许从 `main` 调度，并比较目标 commit 与其父提交。`market` 可选 `both`、`skillhub` 或 `clawhub`；填写的 Skill 名须在检测出的变化矩阵中，留空时选择该 commit 的所有变更 Skill。Tencent 重试或手动 rerun 时若公开检查返回 404，必须停下并先人工核实个人中心，不能盲目重发。腾讯正式发布前还会将目标版本与 `origin/main` 上同一 Skill 的当前版本比较；若目标已被较高版本取代，记录 `superseded` 并跳过，Skill 已不存在时不发布。取消 workflow 会停止正式发布；最终报告 job 仍会执行。

## 非技术用户配置

### 填写 ClawHub 发布目标

这三项不是 Secret，可以直接写在复制后的 workflow 顶部 `env`：

1. `CLAWHUB_PUBLISHER` 填网页显示的个人或组织 handle，不填显示名称。
2. 个人发布把 `CLAWHUB_OWNER` 留空；组织发布填写与 `CLAWHUB_PUBLISHER` 相同的 handle。
3. 在 `CLAWHUB_TARGETS_JSON` 中为每个 Skill 路径填写一个不会混淆的 slug，并选择 `new` 或 `update`。
4. 首次开 PR 后检查 scoped target `@<publisher>/<slug>`。若能查看到条目，更新目标的 publisher 必须匹配；若返回 404，状态仍未验证，正式发布 API 会按 publisher+slug 执行原子所有权检查。其他 publisher 下的同名 slug 本身不是冲突。

### 创建审批 Environment

让用户打开目标仓库：

1. 进入 `Settings → Environments → New environment`。
2. 名称填写 `skill-release-production`。
3. 在 Deployment protection rules 中启用 Required reviewers，并选择负责发布的人。
4. 保存后确认 Environment 列表中已出现该名称。

没有对应入口或权限时停止，让仓库管理员完成；不要擅自改用无审批发布。

### 添加 Secret

如果 Secret 只用于正式发布，优先放入上述 Environment：

1. 打开 `Settings → Environments → skill-release-production`。
2. 在 Environment secrets 中点击 `Add secret`。
3. Tencent 名称填写 `SKILLHUB_KEY`；ClawHub 名称填写 `CLAWHUB_TOKEN`。
4. 将对应平台刚生成的 Token 粘贴到 Value 并保存。
5. 只确认 Secret 名称已经出现；不要让用户发送 Token 或包含 Token 的截图。

配置完成不代表立即发布。先在 PR 查看检测清单和 dry-run；合并 `main` 后，由 reviewer 在 Actions 待审批页面核对 commit、Skill 路径、版本和平台，再批准正式 job。
