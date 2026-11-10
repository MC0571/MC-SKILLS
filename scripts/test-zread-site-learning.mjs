import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { runInNewContext } from "node:vm";

const pack = new URL("../skills/zread-wiki-export/assets/ego-browser/learnings/zread/", import.meta.url);
const manifest = JSON.parse(await readFile(new URL("manifest.json", pack), "utf8"));
const nodeTool = manifest.nodeTools.open_and_extract;
const { [nodeTool.callable]: openAndExtract } = await import(new URL(nodeTool.path, pack));
const browserSource = await readFile(new URL(manifest.browserTools.extract_page.path, pack), "utf8");

const chapterUrl = "https://zread.ai/example/project/current-chapter";
const markdown = "---\r\nslug: current-chapter\r\nblog_type: wiki\r\n---\r\n\r\n# Current Chapter\r\n\r\n"
  + "Synthetic text.\r\n\r\n```js\r\n  const text = \"\\n\";  \r\n\r\n  console.log(text);\r\n```\r\n\r\n";
const previousMarkdown = "---\nslug: previous-chapter\n---\n\n# Previous Chapter\n\nSynthetic old chapter.\n";
const articleHtml = '<article id="article-content"><p>Synthetic text.</p></article>';

async function extractPage({
  url = chapterUrl,
  pageTitle = "Current Chapter - Zread",
  headingTitle = "Current Chapter",
  contentReady = true,
  payloads = [],
} = {}) {
  const paragraph = { textContent: "Synthetic text." };
  const article = {
    outerHTML: articleHtml,
    textContent: paragraph.textContent,
    firstElementChild: paragraph,
    lastElementChild: paragraph,
    contains: () => false,
    querySelectorAll: selector => selector === "p" ? [paragraph] : [],
  };
  const heading = {
    cloneNode: () => ({ textContent: headingTitle, querySelectorAll: () => [] }),
  };
  const root = { querySelector: selector => selector === ":scope > h1" ? heading : null };
  const viewport = {
    scrollHeight: 100,
    clientHeight: 100,
    scrollTop: 0,
    querySelectorAll: selector => selector === "a[href]" ? [anchor] : [],
  };
  const anchor = {
    href: chapterUrl,
    textContent: "Current Chapter",
    parentElement: viewport,
    getAttribute: () => "/example/project/current-chapter",
  };
  const document = {
    title: pageTitle,
    scripts: payloads.map(text => ({ textContent: `self.__next_f.push(${JSON.stringify([1, text])});` })),
    querySelector: selector => ({
      "#cgx-selectable-wiki": root,
      "article#article-content": contentReady ? article : null,
    })[selector] ?? null,
    querySelectorAll: selector => ({
      'main [data-slot="scroll-area-viewport"]': [viewport],
      "a[href]": [anchor],
    })[selector] ?? [],
  };
  return runInNewContext(`(${browserSource})`, { URL, location: { href: url }, document })({});
}

test("Node 工具拒绝错误站点和登录参数，且不触发浏览器调用", async () => {
  const calls = [];
  const ctx = {
    openOrReuseTab: (...args) => calls.push(["open", ...args]),
    waitForLoad: () => calls.push(["wait"]),
    runSiteBrowserTool: (...args) => calls.push(["extract", ...args]),
  };
  for (const url of [
    "https://example.invalid/example/project",
    "https://zread.ai.example.invalid/example/project",
    "http://zread.ai/example/project",
    "https://synthetic:synthetic@zread.ai/example/project",
    "https://zread.ai/example/project?login=synthetic",
    "https://zread.ai/example/project#login",
  ]) {
    await assert.rejects(openAndExtract(ctx, { url }), /url must be/, url);
  }
  assert.deepEqual(calls, []);
});

test("Node 工具按序导航、等待并原样返回 browser 工具结果", async () => {
  for (const url of ["https://zread.ai/example/project", chapterUrl]) {
    const calls = [];
    const expected = { ok: true, url, article: { sourceMarkdown: markdown } };
    const ctx = {
      openOrReuseTab: async (...args) => {
        await Promise.resolve();
        calls.push(["open", ...args]);
      },
      waitForLoad: async () => {
        await Promise.resolve();
        calls.push(["wait"]);
      },
      runSiteBrowserTool: async (...args) => {
        calls.push(["extract", ...args]);
        return expected;
      },
    };
    assert.equal(await openAndExtract(ctx, { url }), expected);
    assert.deepEqual(calls, [
      ["open", url, { wait: true }],
      ["wait"],
      ["extract", "zread", "extract_page", {}],
    ]);
  }
});

test("首页、504 和正文未就绪返回具体失败身份", async () => {
  for (const [options, reason] of [
    [{ url: "https://zread.ai/", pageTitle: "Zread" }, "not_repository_page"],
    [{ pageTitle: "504 Gateway time-out" }, "gateway_timeout"],
    [{ contentReady: false, payloads: [markdown] }, "wiki_content_unavailable"],
  ]) {
    const result = await extractPage(options);
    assert.equal(result.ok, false);
    assert.equal(result.reason, reason);
    assert.equal(result.url, options.url ?? chapterUrl);
    assert.equal(result.article, undefined);
  }
});

test("重复当前 slug 的 payload 去重，保留代码、空白和换行原文", async () => {
  const result = await extractPage({ payloads: [previousMarkdown, markdown, markdown] });
  assert.equal(result.ok, true);
  assert.equal(result.chapter.url, chapterUrl);
  assert.equal(result.chapter.slug, "current-chapter");
  assert.equal(result.article.markdownState, "matching_candidate");
  assert.equal(result.article.sourceMarkdown, markdown);
  assert.equal(result.article.articleHtml, null);
});

test("SPA 残留上一章和同 slug 冲突均不冒充本章 Markdown", async () => {
  for (const [payloads, state] of [
    [[previousMarkdown], "stale_dom_payload"],
    [[markdown, markdown + "Another synthetic paragraph.\r\n"], "ambiguous_candidates"],
  ]) {
    const result = await extractPage({ payloads });
    assert.equal(result.ok, true);
    assert.equal(result.chapter.slug, "current-chapter");
    assert.equal(result.article.markdownState, state);
    assert.equal(result.article.sourceMarkdown, null);
    assert.equal(result.article.articleHtml, articleHtml);
  }
});

test("当前 URL 和 payload 不能掩盖可见标题与目录的冲突", async () => {
  const result = await extractPage({ headingTitle: "Previous Chapter", payloads: [markdown] });
  assert.equal(result.ok, false);
  assert.equal(result.reason, "active_chapter_mismatch");
  assert.equal(result.title, "Previous Chapter");
  assert.equal(result.article, undefined);
});
