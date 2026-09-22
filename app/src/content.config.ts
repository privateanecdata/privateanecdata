import { defineCollection, z } from 'astro:content';
import type { Loader } from 'astro/loaders';
import { readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// The methodology documents live at the repo root so they are the same files the public
// repository shows. They link to each other as repository files (SHUTDOWN.md, ../spec/SCHEMA.md);
// on the site those are /docs/<slug>, so links are rewritten as the files are loaded. Rendered
// read-only; nothing here is editable from the site.
const slug = (name: string) => name.replace(/\.md$/, '').toLowerCase().replace(/_/g, '-');
const LINK = /\]\((?:\.\.\/(?:docs|spec)\/|\.\/)?([A-Za-z0-9_-]+)\.md(#[^)]*)?\)/g;

function docs(base: string): Loader {
  return {
    name: `docs:${base}`,
    async load({ store, renderMarkdown, logger }) {
      store.clear();
      const dir = resolve(process.cwd(), base);
      for (const name of readdirSync(dir).filter((n) => n.endsWith('.md')).sort()) {
        const body = readFileSync(resolve(dir, name), 'utf8').replace(LINK, (_, f, h) => `](/docs/${slug(f)}${h ?? ''})`);
        store.set({ id: slug(name), data: {}, body, rendered: await renderMarkdown(body) });
      }
      logger.info(`loaded ${store.keys().length} documents from ${base}`);
    },
  };
}

export const collections = {
  docs: defineCollection({ loader: docs('../docs'), schema: z.object({}).passthrough() }),
  spec: defineCollection({ loader: docs('../spec'), schema: z.object({}).passthrough() }),
};
