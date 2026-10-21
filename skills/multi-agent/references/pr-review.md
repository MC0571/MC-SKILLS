# PR 审查

审查 PR 时，由未参与实现的 Reviewer 检查目标 base 与明确 head SHA 之间的完整差异，结论绑定所审查的 base 和完整 head SHA。

只有用户已授权公开发布 PR review 时，才由完成该次审查的 Reviewer 本人提交。提交前核对远端 head 仍为已审 SHA；如果已变化，先对新 head 与 base 的完整差异补审。使用 GitHub review API 显式设置 `commit_id` 为所审 head SHA；`COMMENT` event 可提交 review 正文，普通 PR conversation comment 不绑定审查 commit。提交后核对响应的 `commit_id` 与审查 SHA 一致、`html_url` 存在，并向目标负责人返回评论 URL、审查 SHA 和结论。若 head 后续变化，旧结论不代表新 head。[GitHub review API 文档](https://docs.github.com/en/rest/pulls/reviews#create-a-review-for-a-pull-request)

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
