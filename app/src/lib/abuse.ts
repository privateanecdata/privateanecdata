// Anti-abuse without identifiers. A honeypot field catches naive bots. A rate limiter keys on a
// hash of the client address (for IPv6, its /64 prefix) with a salt that rotates hourly and lives
// only in memory, so no address is ever written anywhere and nothing survives a restart.
import { createHash, randomBytes } from 'node:crypto';

const WINDOW_MS = 60 * 60 * 1000;
const MAX_PER_WINDOW = 10;
// The onion service hands every connection to the app from loopback, so there is no address to
// key on and one shared bucket would lock every Tor contributor out after ten submissions an
// hour. Loopback gets no per-address limit and a generous shared ceiling instead; fabricated
// volume beyond that is what the exclusion list and integrity log are for.
const LOOPBACK_MAX_PER_WINDOW = 300;
const LOOPBACK = /^(?:127\.\d+\.\d+\.\d+|::1|::ffff:127\.\d+\.\d+\.\d+)$/;

let salt = randomBytes(32);
let saltMinted = Date.now();
const buckets = new Map<string, { n: number; reset: number }>();

/**
 * The unit the limiter counts: an IPv4 address, or an IPv6 /64 — the block a residential
 * connection is handed, so a client rotating through its own IPv6 addresses (privacy
 * extensions, or on purpose) still lands in one bucket. IPv4-mapped IPv6 (`::ffff:a.b.c.d`)
 * is treated as the IPv4 address it carries. Only ever hashed, never stored.
 */
export function bucketOf(addr: string): string {
  const a = addr.replace(/%.*$/, ''); // zone id
  const v4 = /^(?:::ffff:)?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$/i.exec(a);
  if (v4) return v4[1];
  if (!a.includes(':')) return a;
  const [head, tail] = a.split('::');
  const h = head ? head.split(':') : [];
  const t = tail ? tail.split(':') : [];
  const groups = [...h, ...new Array(Math.max(0, 8 - h.length - t.length)).fill('0'), ...t];
  return groups.slice(0, 4).map((g) => g.toLowerCase().padStart(4, '0')).join(':') + '::/64';
}

function key(addr: string): string {
  if (Date.now() - saltMinted > WINDOW_MS) {
    salt = randomBytes(32);
    saltMinted = Date.now();
    buckets.clear();
  }
  return createHash('sha256').update(salt).update(addr).digest('base64url');
}

/** True if this client may submit a report. Counts the attempt. */
export function allowSubmit(addr: string | undefined): boolean {
  return allow(addr, 'r', MAX_PER_WINDOW, LOOPBACK_MAX_PER_WINDOW);
}

/** The contact page: its own bucket, tighter. */
export function allowContact(addr: string | undefined): boolean {
  return allow(addr, 'c', 5, 60);
}

function allow(addr: string | undefined, scope: string, max: number, loopbackMax: number): boolean {
  if (!addr) return true; // unknown transport: no address to key on
  const loopback = LOOPBACK.test(addr);
  const k = scope + (loopback ? 'loopback' : key(bucketOf(addr)));
  const now = Date.now();
  const b = buckets.get(k);
  if (!b || b.reset < now) {
    buckets.set(k, { n: 1, reset: now + WINDOW_MS });
    return true;
  }
  b.n += 1;
  return b.n <= (loopback ? loopbackMax : max);
}

/** The honeypot is a visually hidden text field named to attract autofill. Any value = bot. */
export const HONEYPOT_FIELD = 'website';
export function isHoneypotTripped(fd: FormData): boolean {
  const v = fd.get(HONEYPOT_FIELD);
  return typeof v === 'string' && v.trim().length > 0;
}
