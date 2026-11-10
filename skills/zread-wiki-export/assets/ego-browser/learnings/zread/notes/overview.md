# Zread Wiki 站点知识

Last verified: 2026-11-10

本包只读获取公开 Wiki 的目录、当前章节、来源索引及正文候选；不生成或刷新仓库，不登录、不提交表单。正文完整性验收、保存位置与 Git 历史由导出 skill 负责。

## 加载与工具

本包位于已安装 skill 的 `assets/ego-browser/learnings/zread/`。将 `EGO_BROWSER_AGENT_WORKSPACE` 指向其上层的 `assets/ego-browser/`，不是 `learnings/` 或 `zread/` 本身。

ego-browser 的 nodejs 脚本不继承启动 shell 的环境变量；需要在脚本内部给 `process.env.EGO_BROWSER_AGENT_WORKSPACE` 设置上述绝对路径，再调用 `siteSkillsForUrl(url)`、`learnContext(url)` 或站点工具。本轮还观察到 `Page.goto()` 将该值重置为运行时默认目录，因此导航后、调用包之前须重新设置。从当前 skill 的实际安装位置得到路径，不从浏览器脚本的工作目录猜测，也不把某台机器的路径写入本包。

- `open_and_extract({ url })`：Node 侧只读导航到仓库或章节，再读取 Wiki。参数仅接受 HTTPS `zread.ai` 的仓库/章节路径，不接受登录参数、查询或锚点。
- `extract_page({})`：浏览器侧只读取当前 DOM，不导航、不展开组、不滚动。返回当前章与目录、来源索引、Markdown 候选或明确标注的文章 HTML。
- `ok: true` 表示能识别当前 Wiki 页面，不能代替正文与图表完整性验收。`sourceIndex` 缺失时为 null，不由当前日期补造。

`open_and_extract` 会复用已有 URL 的托管页，新 URL 则可能新开托管页，适合少量对照。整库遍历按主 skill 复用一个 Page，站内跳转后调用 `extract_page`，不要用 Node 打开工具循环创建标签页。更新请求需先重新加载网页以取得当前数据，工具复用旧标签页本身不是刷新；网页 reload 与提交“刷新仓库”生成是不同动作。

## 站点地图与 URL

| 页面 | URL 模式 | 处理 |
| --- | --- | --- |
| 探索/搜索 | `/` | `main` 中的搜索输入；填入 GitHub URL 后等待匹配仓库链接。 |
| 趋势列表 | `/trending` | 仅记录首页实际链接，本轮未单独验证列表分页。 |
| 仓库 Wiki | `/<owner>/<repo>` | 通常展示某个概述章的别名；按可见标题与目录唯一匹配，不重复保存根页。 |
| 独立章节 | `/<owner>/<repo>/<slug>` | 使用真实目录 href，不根据数字猜连续 slug。 |
| 私有仓库/收藏/订阅 | `/private/repo`、`/library`、`/subscription` | 本轮未进入；遇登录、验证或付费边界交用户处理，不绕过。 |

首页已观察到 `main input[data-slot="input"]`；不要把中文 placeholder 写成所有语言下的固定契约。搜索结果出现实际仓库链接后再点击，不把输入框回显当成功。

## 已观察的稳定选择器

| 字段 | 定位依据 | 说明 |
| --- | --- | --- |
| Wiki 容器 | `#cgx-selectable-wiki` | 页面给出的语义 ID，包含章标题与文章。 |
| 章标题 | `#cgx-selectable-wiki > h1` | 排除标题内的反馈链接/按钮，避免“报告问题”混入标题。 |
| 正文 | `article#article-content` | 不取整个 main；全站导航、目录和右侧来源树不属于正文。 |
| 左侧目录 | `main [data-slot="scroll-area-viewport"]` 中含目标仓库章节链接的唯一容器 | 根据链接归属选择，不固定位置或 utility class。 |
| 折叠目录组 | 目录内 `button[data-slot="accordion-trigger"][aria-expanded]` | 按语义属性判断展开状态，不保存动态 Radix ID。 |
| 索引版本 | 正文外指向 `https://github.com/<owner>/<repo>/tree/<commit>` 的链接 | 同时保留可见日期和实际 commit；日期文字不保证代表最新代码。 |
| 图表 | 正文内 `svg[role*="graphics-document"]` | 只统计已渲染图表，不把放大按钮图标计入。 |

目录 section 的文字目前位于组容器内第一个非交互 div；这是本轮观察到的结构依据。层级还使用 `data-slot="accordion"` 的祖先组名；结构不再匹配时须重新观察，不能改为按像素或硬编码标题匹配。

## 完整目录的边界

`catalog.coverage` 始终为 `current_dom`。一次返回所有当前 DOM 链接，不保证它已经覆盖虚拟化或未展开的目录。调用方应先展开返回的 `collapsedGroups`，再沿实际目录滚动区域到末尾，累计不同源 URL，直到没有新条目。

滚动后等待实际 `scrollTop` 到达目标再读取，避免滚动动画尚未结束时误判。`scrollable` 和 `atBottom` 只说明当前视图状态；即使在底部，也不能据此跳过逐屏累计。已保存的文件映射保持稳定，目录顺序变化不应重命名正文。

## 原始 Markdown 与 DOM 的差异

公开章节的完整 HTML 可含 `self.__next_f.push(...)` script 数据。已观察到其中字符串以 `---`、`slug:<当前 slug>`、`blog_type` 的 frontmatter 开头，同一正文可能重复出现。

只把参数当 JSON 解码，按当前 slug 筛选并去重；不执行 script，不调用 eval。工具将唯一匹配项返回为 `article.sourceMarkdown`，保留 frontmatter 和原文。它仍是待比对候选，不因为 JSON 可解析就宣称正文完整。

SPA 站内跳转后，当前 DOM 的 script 不一定携带新章 Markdown，甚至可能仍携带上一章数据。工具用 URL、可见标题和目录项核对当前章，并明确返回 `markdownState`：

- `matching_candidate`：当前 slug 有唯一去重候选。
- `not_embedded_in_current_dom` / `stale_dom_payload`：当前 DOM 没有本章原文；可用文章 HTML 转换，或用浏览器能力读取同一公开章节 URL 的完整 HTML 再观察其 JSON 数据。
- `ambiguous_candidates` / `payload_format_changed`：不能盲选最长候选；定位变化并按主 skill 修复与复验。

`articleHtml` 仅在缺少唯一 Markdown 候选时返回，是原始文章 HTML，不是 Markdown。转换时沿用主 skill 的成熟转换器和逐块比对规则，排除复制等控件，保存代码换行、表格、公式、折叠内容和图表。`counts`、`firstBlock`、`lastBlock` 只是核对辅助，不是完整性证明。

已观察到代码高亮 DOM 将原始空行显示为一个空格，以及遗漏行内注释和其后的换行、造成相邻命令拼接的情况。不能把 `pre code.textContent` 当作可靠原文，也不能为匹配显示结果而删改原始 Markdown。优先核对公开文档中的原始 Markdown；只有 DOM 时，无法核对或补齐的代码应计为缺失，保持 `failed`，不把损坏的显示文本声明为完整代码。

本轮未验证独立文章 API；读取来源是公开页面、当前 DOM 以及同一页面返回的 JSON 数据。源码引用可能使用根相对文件链接，必须与 Wiki 章节链接区分，不能加入目录清单或猜测引用目标。

## 状态与停止条件

- 首页不是仓库页：返回 `not_repository_page`。
- Cloudflare 504：返回 `gateway_timeout`。已观察到直接导航失败而站内导航可读；检查当前状态后只作一次正常重试，不把错误页当正文或结构变更。
- 正文/目录尚不可读：返回具体 unavailable 原因，先等待并重新观察，不自动生成 Wiki。
- URL、目录及标题不对应：返回 `active_chapter_mismatch`，防止 SPA 切换时保存上一章。
- 登录、CAPTCHA 或付费边界未回放；一旦出现须交用户处理。不要因页面存在“登录”按钮就认定公开正文不可读。

## 维护

页面变化时先复验，只修正已失效的 DOM/数据定位，再更新本笔记日期与实际覆盖范围。保留主 skill 的原文验收标准和创建共享修复 PR 前的用户同意要求，不把现场文章、账号、机器路径或会话数据写入包内。
