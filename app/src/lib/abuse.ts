// Anti-abuse without identifiers. A honeypot field catches naive bots. A rate limiter keys on a
// hash of the client address with a salt that rotates hourly and lives only in memory, so no
// address is ever written anywhere and nothing survives a restart.
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

function key(addr: string): string {
  if (Date.now() - saltMinted > WINDOW_MS) {
    salt = randomBytes(32);
    saltMinted = Date.now();
    buckets.clear();
  }
  return createHash('sha256').update(salt).update(addr).digest('base64url');
}

/** True if this client may submit. Counts the attempt. */
export function allowSubmit(addr: string | undefined): boolean {
  if (!addr) return true; // unknown transport: no address to key on
  const loopback = LOOPBACK.test(addr);
  const k = loopback ? 'loopback' : key(addr);
  const now = Date.now();
  const b = buckets.get(k);
  if (!b || b.reset < now) {
    buckets.set(k, { n: 1, reset: now + WINDOW_MS });
    return true;
  }
  b.n += 1;
  return b.n <= (loopback ? LOOPBACK_MAX_PER_WINDOW : MAX_PER_WINDOW);
}

/** The honeypot is a visually hidden text field named to attract autofill. Any value = bot. */
export const HONEYPOT_FIELD = 'website';
export function isHoneypotTripped(fd: FormData): boolean {
  const v = fd.get(HONEYPOT_FIELD);
  return typeof v === 'string' && v.trim().length > 0;
}
