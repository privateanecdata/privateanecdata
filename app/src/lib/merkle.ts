import { createHash } from 'node:crypto';

// Leaf = SHA-256(salt || canonical JSON of the stored row). The salt is per-row, secret, and
// never published, so the published root cannot be used as a membership oracle by anyone who
// can guess a row's contents.
export function leafHash(salt: Buffer, canonical: string): Buffer {
  return createHash('sha256').update(salt).update(Buffer.from(canonical, 'utf8')).digest();
}

/** Root of a Merkle tree over leaves in log order. Odd leaves are promoted (RFC 6962 style). */
export function merkleRoot(leaves: Buffer[]): Buffer {
  if (leaves.length === 0) return createHash('sha256').update('').digest();
  let level = leaves.slice();
  while (level.length > 1) {
    const next: Buffer[] = [];
    for (let i = 0; i < level.length; i += 2) {
      if (i + 1 < level.length) {
        next.push(createHash('sha256').update(Buffer.from([1])).update(level[i]).update(level[i + 1]).digest());
      } else {
        next.push(level[i]);
      }
    }
    level = next;
  }
  return level[0];
}

/** Stable key order so the same row always hashes the same. */
export function canonicalJson(obj: Record<string, unknown>): string {
  const keys = Object.keys(obj).sort();
  const out: Record<string, unknown> = {};
  for (const k of keys) out[k] = obj[k];
  return JSON.stringify(out);
}
