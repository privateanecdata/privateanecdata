import type { APIRoute } from 'astro';
// The public pages worth indexing. The form and contact pages are deliberately left out.
const PAGES = ['/', '/data', '/docs', '/docs/privacy-protocol', '/docs/release-spec', '/docs/schema', '/legal'];
export const GET: APIRoute = ({ site, url }) => {
  const base = (site ?? url).toString().replace(/\/$/, '');
  const body = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    PAGES.map((p) => `  <url><loc>${base}${p}</loc></url>`).join('\n') + `\n</urlset>\n`;
  return new Response(body, { headers: { 'Content-Type': 'application/xml; charset=utf-8', 'Cache-Control': 'public, max-age=3600' } });
};
