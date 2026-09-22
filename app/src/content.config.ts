import { defineCollection, z } from 'astro:content';
import type { Loader } from 'astro/loaders';
import { readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// The methodology documents live at the repo root so they are the same files the public
// repository shows. They link to each other as repository files (SHUTDOWN.md, ../spec/SCHEMA.md);
// on the site those are /docs/<slug>, so links are rewritten as the files are loaded. Rendered
// read-only; nothing here is editable from the site.
const slug = (name: string) => name.replace(/\.md$/, '').toLowerCase().replace(/_/g, '-');
// Documents that now live inside another page. A repository link to the file lands on the section.
const HOME: Record<string, string> = {
  'what-we-can-and-cannot-promise': '/docs/privacy-protocol#cannot-promise',
  'threat-model': '/docs/privacy-protocol#threat-model',
  'shutdown': '/docs/privacy-protocol#shutdown',
  'release-spec': '/docs/release-spec#full-spec',
  'release-spec-summary': '/docs/release-spec',
  'how-we-count-reports': '/docs/release-spec#how-we-count',
  'analyses-we-will-never-run': '/docs/release-spec#never-run',
  'privacy': '/legal#doc-privacy',
  'terms': '/legal#doc-terms',
  'legal-process': '/legal#doc-legal-process',
  'subprocessors': '/legal#doc-subprocessors',
};
const target = (s: string, hash?: string) => {
  const home = HOME[s];
  if (!home) return `/docs/${s}${hash ?? ''}`;
  if (!hash) return home;
  // The section ids of a document survive on the page it now lives in, so a link to a section
  // beats the page's default anchor.
  return `${home.split('#')[0]}${hash}`;
};
const LINK = /\]\((?:\.\.\/(?:docs|spec)\/|\.\/)?([A-Za-z0-9_-]+)\.md(#[^)]*)?\)/g;
// `## Heading {#anchor}` gives a heading a stable, human id so pages can link to a section.
const ANCHOR = /^(#{1,6} .*?) \{#([a-z0-9-]+)\}[ \t]*$/gm;

// Long methodology documents fold each H2 section into a native <details> so a reader can scan
// the headings and open what they want — no script involved. Every section starts closed; the
// page's table of contents links into the bodies, which opens the fold.
// The privacy statement and terms are never folded: a contract must be conspicuous in full.
const NEVER_FOLD = new Set(['privacy', 'terms', 'legal-process', 'subprocessors']);
function collapsible(id: string, html: string): string {
  if (NEVER_FOLD.has(id)) return html;
  const parts = html.split(/(?=<h2\b)/);
  if (parts.length < 4) return html;
  return parts.map((part, i) => {
    if (i === 0) return part;
    const m = part.match(/^<h2\b([^>]*)>([\s\S]*?)<\/h2>([\s\S]*)$/);
    if (!m) return part;
    const id = m[1].match(/ id="([^"]*)"/)?.[1];
    const attrs = id ? m[1].replace(/ id="[^"]*"/, ` id="${id}-heading"`) : m[1];
    const anchor = id ? `<span id="${id}" class="anchor"></span>` : '';
    return `<details class="sec"><summary><h2${attrs}>${m[2]}</h2></summary><div class="sec-body">${anchor}${m[3]}</div></details>`;
  }).join('');
}

function docs(base: string): Loader {
  return {
    name: `docs:${base}`,
    async load({ store, renderMarkdown, logger }) {
      store.clear();
      const dir = resolve(process.cwd(), base);
      for (const name of readdirSync(dir).filter((n) => n.endsWith('.md')).sort()) {
        const body = readFileSync(resolve(dir, name), 'utf8')
          .replace(LINK, (_, f, h) => `](${target(slug(f), h)})`)
          .replace(ANCHOR, (_, heading, id) => `<a id="${id}"></a>\n\n${heading}`);
        const rendered = await renderMarkdown(body);
        // The anchor paragraph the ANCHOR rewrite produced sits just before its heading; put the
        // id on the heading itself so a fragment link lands inside the right (auto-opened) section.
        const html = rendered.html.replace(/<p><a id="([a-z0-9-]+)"><\/a><\/p>\s*(<h[1-6])( id="[^"]*")?/g, '$2 id="$1"');
        // (collapsible() moves the id into the section body: a fragment target inside a <summary>
        // does not open its <details>, one inside the body does.)
        const toc = Array.from(html.matchAll(/<h2 id="([^"]+)"[^>]*>([\s\S]*?)<\/h2>/g)).map((m) => ({ id: m[1], text: m[2].replace(/<[^>]+>/g, '').trim() }));
        // The document's own H1 is lifted out: pages render the title themselves, then the
        // table of contents, then the body.
        const h1 = html.match(/^\s*<h1\b[^>]*>([\s\S]*?)<\/h1>/);
        const title = h1 ? h1[1].replace(/<[^>]+>/g, '').trim() : slug(name);
        const bodyHtml = h1 ? html.slice(h1[0].length) : html;
        store.set({ id: slug(name), data: { plainHtml: bodyHtml, toc, title }, body, rendered: { ...rendered, html: collapsible(slug(name), bodyHtml) } });
      }
      logger.info(`loaded ${store.keys().length} documents from ${base}`);
    },
  };
}

export const collections = {
  docs: defineCollection({ loader: docs('../docs'), schema: z.object({}).passthrough() }),
  spec: defineCollection({ loader: docs('../spec'), schema: z.object({}).passthrough() }),
};
