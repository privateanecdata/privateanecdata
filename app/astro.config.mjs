import { defineConfig } from 'astro/config';
import node from '@astrojs/node';

// Server-rendered so the form can POST without JavaScript. Standalone Node server, bound to
// loopback; Caddy (access logging off) sits in front and terminates TLS.
export default defineConfig({
  site: `https://${process.env.PA_HOST ?? 'privateanecdata.org'}`,
  output: 'server',
  adapter: node({ mode: 'standalone', bodySizeLimit: 65536 }),
  server: { host: '127.0.0.1', port: 4321 },
  // PA_HOST is read HERE, at build time (npm run build:prod refuses to run without it).
  security: {
    checkOrigin: true,
    // The public hostname. Required for Astro to trust X-Forwarded-For from Caddy.
    allowedDomains: process.env.PA_HOST ? [{ hostname: process.env.PA_HOST, protocol: 'https' }] : [],
  },
  // External stylesheet so the CSP can be style-src 'self' with no 'unsafe-inline'.
  build: { inlineStylesheets: 'never' },
  // Shiki emits inline style attributes on code blocks, which the CSP (style-src 'self') blocks.
  markdown: { syntaxHighlight: false },
  devToolbar: { enabled: false },
});
