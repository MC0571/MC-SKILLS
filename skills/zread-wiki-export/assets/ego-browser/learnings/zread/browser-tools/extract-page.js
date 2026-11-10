async function (args) {
  const current = new URL(location.href);
  const url = current.origin + current.pathname;
  if (/504|Gateway time-out/i.test(document.title)) {
    return { ok: false, reason: "gateway_timeout", url };
  }
  const parts = current.pathname.split("/").filter(Boolean);
  if (current.origin !== "https://zread.ai" || ![2, 3].includes(parts.length)) {
    return { ok: false, reason: "not_repository_page", url };
  }
  const repository = parts.slice(0, 2).join("/");
  const root = document.querySelector("#cgx-selectable-wiki");
  const article = document.querySelector("article#article-content");
  const heading = root?.querySelector(":scope > h1");
  if (!root || !article || !heading) {
    return { ok: false, reason: "wiki_content_unavailable", url, repository };
  }
  const clean = text => text.replace(/\s+/g, " ").trim();
  const titleNode = heading.cloneNode(true);
  titleNode.querySelectorAll("a,button").forEach(node => node.remove());
  const title = clean(titleNode.textContent);
  const chapterLink = anchor => {
    const target = new URL(anchor.getAttribute("href"), current.href);
    const path = target.pathname.split("/").filter(Boolean);
    if (target.origin !== current.origin || path.length !== 3 || path.slice(0, 2).join("/") !== repository) return null;
    return { url: target.origin + target.pathname, slug: decodeURIComponent(path[2]), title: clean(anchor.textContent) };
  };
  const directories = [...document.querySelectorAll('main [data-slot="scroll-area-viewport"]')]
    .map(element => ({ element, anchors: [...element.querySelectorAll("a[href]")].filter(anchor => chapterLink(anchor)) }))
    .filter(directory => directory.anchors.length);
  if (directories.length !== 1) {
    return { ok: false, reason: "wiki_directory_unavailable_or_ambiguous", url, repository };
  }
  const { element: viewport, anchors } = directories[0];
  const chapters = [];
  const seen = new Set();
  for (const anchor of anchors) {
    const entry = chapterLink(anchor);
    if (seen.has(entry.url)) continue;
    seen.add(entry.url);
    const groups = [];
    let section = null;
    for (let parent = anchor.parentElement; parent && parent !== viewport; parent = parent.parentElement) {
      if (parent.matches('[data-slot="accordion"]')) {
        const trigger = parent.querySelector('button[data-slot="accordion-trigger"]');
        if (trigger) groups.unshift(clean(trigger.textContent));
      }
      const label = parent.firstElementChild;
      if (!section && label?.tagName === "DIV" && !label.querySelector("a,button") && clean(label.textContent)) section = clean(label.textContent);
    }
    chapters.push({ ...entry, order: chapters.length + 1, section, groups, level: groups.length + 1 });
  }
  const active = chapters.filter(entry => parts.length === 3 ? entry.url === url : entry.title === title);
  if (active.length !== 1 || active[0].title !== title) {
    return { ok: false, reason: "active_chapter_mismatch", url, repository, title, chapters };
  }
  const chapter = active[0];
  const sourceLink = [...document.querySelectorAll("a[href]")].find(anchor => {
    if (article.contains(anchor)) return false;
    const target = new URL(anchor.href);
    return target.origin === "https://github.com" && new RegExp("^/" + repository.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "/tree/[a-f0-9]{40}/?$").test(target.pathname);
  });
  const candidates = new Set();
  let invalidPayload = false;
  let otherSlugs = false;
  for (const script of document.scripts) {
    const text = script.textContent.trim();
    if (!text.startsWith("self.__next_f.push(") || !text.includes("slug:")) continue;
    const call = text.match(/^self\.__next_f\.push\(([\s\S]*)\);?$/);
    if (!call) { invalidPayload = true; continue; }
    let record;
    try { record = JSON.parse(call[1]); }
    catch { invalidPayload = true; continue; }
    const markdown = record[1];
    if (typeof markdown !== "string") continue;
    const frontmatter = markdown.match(/^---\r?\nslug:\s*([^\r\n]+)\r?\n/);
    if (!frontmatter) continue;
    if (frontmatter[1] === chapter.slug) candidates.add(markdown);
    else otherSlugs = true;
  }
  const sourceMarkdown = candidates.size === 1 ? [...candidates][0] : null;
  const markdownState = sourceMarkdown ? "matching_candidate" : candidates.size > 1 ? "ambiguous_candidates" : invalidPayload ? "payload_format_changed" : otherSlugs ? "stale_dom_payload" : "not_embedded_in_current_dom";
  return {
    ok: true,
    url,
    repository,
    title,
    chapter,
    sourceIndex: sourceLink ? { label: clean(sourceLink.textContent), commit: new URL(sourceLink.href).pathname.split("/").filter(Boolean).at(-1), url: sourceLink.href } : null,
    catalog: {
      coverage: "current_dom",
      chapters,
      collapsedGroups: [...viewport.querySelectorAll('button[data-slot="accordion-trigger"][aria-expanded="false"]')].map(button => clean(button.textContent)),
      scrollable: viewport.scrollHeight > viewport.clientHeight,
      atBottom: viewport.scrollTop + viewport.clientHeight >= viewport.scrollHeight
    },
    article: {
      markdownState,
      sourceMarkdown,
      articleHtml: sourceMarkdown ? null : article.outerHTML,
      counts: { headings: article.querySelectorAll("h1,h2,h3,h4,h5,h6").length, paragraphs: article.querySelectorAll("p").length, listItems: article.querySelectorAll("li").length, tableCells: article.querySelectorAll("th,td").length, codeBlocks: article.querySelectorAll("pre").length, renderedDiagrams: article.querySelectorAll('svg[role*="graphics-document"]').length, formulas: article.querySelectorAll('annotation[encoding="application/x-tex"]').length, details: article.querySelectorAll("details").length },
      firstBlock: clean(article.firstElementChild?.textContent || ""),
      lastBlock: clean(article.lastElementChild?.textContent || ""),
      images: [...article.querySelectorAll("img")].map(image => ({ src: image.currentSrc || image.src, alt: image.alt }))
    }
  };
}
