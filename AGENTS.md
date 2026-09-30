# AGENTS.md

## 仓库级约束

- SKILL 和 plugin 文档、模板、说明默认中文优先；用户使用其他语言时可适配用户语言。协议字段、状态枚举、工具名、命令和日志可保留英文以保持机器可读。
- 任何仓库变更不得直接在 `main` 分支上修改或提交。先创建任务分支或独立 worktree，完成验证后通过 PR 合并。

## Agent 工程资产落位

- 跨 harness 通用的资产按类型放在仓库顶层；已有类型沿用 `skills/`、`plugins/` 等现有目录，新类型在加入首个实际资产时再创建目录。
- 独立 skills 放在 `skills/<skill-name>/`；plugin 内部 skills 留在所属 plugin 中，只随 plugin 分发，不列为独立 skill。维护安装说明时，独立 skill 命令指向 `skills/` 子路径并使用 `--full-depth`；Claude Code 使用 `--agent claude-code`。
- 仓库根目录的 `AGENTS.md` 和 `CLAUDE.md` 仅用于维护本仓库，不作为可分发 harness 资产。
- 不为规划预建空目录。

## Skill 与 Plugin 元数据和版本

- 独立 skill 与 plugin 各自维护 SemVer 版本，无需彼此一致；独立 skill 版本记在其 `SKILL.md` 的 `metadata.version`。
- 在 `0.x` 阶段，兼容修复升级 patch；新增能力或明确说明的破坏性调整升级 minor。进入 `1.0.0` 后使用标准 major/minor/patch 语义。
- 独立 skill 的 `metadata.category` 必须是 OpenAI plugin 提交分类中的单个英文值；[官方分类列表](https://developers.openai.com/plugins/deploy/submission-errors#listing-and-interface-errors)。
