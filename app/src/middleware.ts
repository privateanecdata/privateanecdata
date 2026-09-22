import { defineMiddleware } from 'astro:middleware';

// Zero external origins. No script-src at all: the site runs with no JavaScript.
const CSP = [
  "default-src 'none'",
  "style-src 'self'",
  "img-src 'self'",
  "form-action 'self'",
  "base-uri 'none'",
  "frame-ancestors 'none'",
].join('; ');

export const onRequest = defineMiddleware(async (ctx, next) => {
  const url = ctx.url;
  // The intake route accepts no query parameters: nothing arrives via URL that could be
  // logged upstream or carry a referral tag.
  if (url.pathname.startsWith('/contribute') && url.search) {
    return ctx.redirect(url.pathname, 302);
  }
  const res = await next();
  res.headers.set('Content-Security-Policy', CSP);
  // 'same-origin' rather than 'no-referrer': no-referrer makes browsers send Origin: null on
  // same-origin POSTs, which defeats the origin check. Nothing here is ever cross-origin.
  res.headers.set('Referrer-Policy', 'same-origin');
  res.headers.set('X-Content-Type-Options', 'nosniff');
  res.headers.set('X-Frame-Options', 'DENY');
  res.headers.set('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), interest-cohort=()');
  res.headers.set('Cross-Origin-Opener-Policy', 'same-origin');
  if (url.pathname.startsWith('/contribute') || url.pathname.startsWith('/contact')) res.headers.set('Cache-Control', 'no-store');
  else if (!res.headers.has('Cache-Control')) res.headers.set('Cache-Control', 'no-cache');
  return res;
});
