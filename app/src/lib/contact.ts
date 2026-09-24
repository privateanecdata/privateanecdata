// The contact page's storage and forwarding. Separate database file from the reports store, so a
// message can never sit next to a report. Messages are the one place on the site where a person
// types free text; they are stored for at most 30 days (deploy/prune-contact.sh) and read on the
// server (DigitalOcean blocks outgoing mail, so PA_CONTACT_TO is left empty in production; the
// forwarding below is kept for a host that allows it). The
// address is never rendered anywhere.
import Database from 'better-sqlite3';
import { randomBytes } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import { createConnection } from 'node:net';
import { dirname, resolve } from 'node:path';

const DB_PATH = process.env.PA_CONTACT_DB_PATH ?? resolve(process.cwd(), 'data/contact.db');
// Forwarding talks plain SMTP to a mail relay on loopback (postfix as a null client), so the
// hardened service needs no set-gid helper and no write access outside its data directory.
const SMTP = process.env.PA_SMTP ?? '127.0.0.1:25';
export const MAX_MESSAGE = 2000;
export const MAX_EMAIL = 200;

let db: Database.Database | null = null;
function getDb(): Database.Database {
  if (db) return db;
  mkdirSync(dirname(DB_PATH), { recursive: true });
  db = new Database(DB_PATH);
  db.pragma('journal_mode = WAL');
  db.pragma('secure_delete = ON');
  db.exec(`
    CREATE TABLE IF NOT EXISTS messages (
      id           TEXT PRIMARY KEY,   -- random; no ordering information
      received_day TEXT NOT NULL,      -- YYYY-MM-DD only
      reply_to     TEXT,               -- optional, as typed by the sender
      body         TEXT NOT NULL,
      forwarded    INTEGER NOT NULL DEFAULT 0
    );
  `);
  return db;
}

export type Contact = { body: string; replyTo: string | null };

export function validate(fd: FormData): { ok: true; value: Contact } | { ok: false; error: string } {
  const body = String(fd.get('message') ?? '').replace(/\r\n/g, '\n').trim();
  const email = String(fd.get('email') ?? '').trim();
  if (!body) return { ok: false, error: 'Write a message first.' };
  if (body.length > MAX_MESSAGE) return { ok: false, error: `Please keep it under ${MAX_MESSAGE} characters.` };
  if (email && (email.length > MAX_EMAIL || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))) {
    return { ok: false, error: 'That email address does not look right. Leave it blank if you do not want a reply.' };
  }
  return { ok: true, value: { body, replyTo: email || null } };
}

/** Store the message, then try to forward it. Storage is the durable copy; forwarding is best effort. */
export function receive(c: Contact): void {
  const d = getDb();
  const id = randomBytes(16).toString('hex');
  d.prepare('INSERT INTO messages (id, received_day, reply_to, body) VALUES (?, ?, ?, ?)')
    .run(id, new Date().toISOString().slice(0, 10), c.replyTo, c.body);
  const to = process.env.PA_CONTACT_TO;
  if (!to) return;
  const from = process.env.PA_CONTACT_FROM ?? 'no-reply@localhost';
  const clean = (s: string) => s.replace(/[\r\n]/g, ' ');
  const headers = [
    `To: ${clean(to)}`,
    `From: Private Anecdata contact form <${clean(from)}>`,
    `Subject: [Private Anecdata] message${c.replyTo ? ' (reply requested)' : ''}`,
    c.replyTo ? `Reply-To: ${clean(c.replyTo)}` : null,
    'MIME-Version: 1.0',
    'Content-Type: text/plain; charset=utf-8',
  ].filter(Boolean).join('\r\n');
  // Dot-stuff the body per RFC 5321 so a line beginning "." cannot end the message early.
  const body = c.body.replace(/\r?\n/g, '\r\n').replace(/^\./gm, '..');
  smtpSend(from, to, `${headers}\r\n\r\n${body}\r\n`)
    .then(() => d.prepare('UPDATE messages SET forwarded = 1 WHERE id = ?').run(id))
    .catch((err: Error) => { console.error(`contact: forward failed (${err.message}); message kept in the store`); });
}

/** Minimal SMTP client for a trusted relay on loopback: no auth, no TLS, one message. */
function smtpSend(from: string, to: string, data: string): Promise<void> {
  const [host, port] = SMTP.split(':');
  return new Promise((resolveP, reject) => {
    const sock = createConnection({ host, port: Number(port ?? 25) });
    const steps = [`EHLO localhost`, `MAIL FROM:<${from}>`, `RCPT TO:<${to}>`, `DATA`, `${data}.`, `QUIT`];
    let i = -1;
    let buf = '';
    const fail = (m: string) => { sock.destroy(); reject(new Error(m)); };
    sock.setTimeout(15000, () => fail('timeout'));
    sock.on('error', (e) => reject(e));
    sock.on('data', (chunk) => {
      buf += chunk.toString();
      // A complete reply ends with "<code><space>"; multi-line replies use "<code>-".
      const lines = buf.split('\r\n');
      const last = lines.length >= 2 ? lines[lines.length - 2] : '';
      if (!/^\d{3} /.test(last)) return;
      buf = '';
      const code = Number(last.slice(0, 3));
      if (i === -1 ? code !== 220 : i === 3 ? code !== 354 : code >= 400) return fail(`smtp ${code} at step ${i}`);
      i += 1;
      if (i >= steps.length) { sock.end(); resolveP(); return; }
      sock.write(steps[i] + '\r\n');
    });
  });
}
