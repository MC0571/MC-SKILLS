export async function openAndExtract(ctx, args = {}) {
  if (typeof args.url !== "string") throw new Error("url must be a Zread repository or chapter URL");
  const target = new URL(args.url);
  const parts = target.pathname.split("/").filter(Boolean);
  if (target.origin !== "https://zread.ai" || target.username || target.password || target.search || target.hash || ![2, 3].includes(parts.length)) {
    throw new Error("url must be an HTTPS zread.ai repository or chapter URL without credentials, query or fragment");
  }
  await ctx.openOrReuseTab(target.href, { wait: true });
  await ctx.waitForLoad();
  return ctx.runSiteBrowserTool("zread", "extract_page", {});
}
