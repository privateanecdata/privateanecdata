// The submission store. One table of coarsened rows and one Merkle log. No sessions, no drafts,
// no logs. Nothing is written until the contributor confirms.
import Database from 'better-sqlite3';
import { randomBytes } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { leafHash, merkleRoot, canonicalJson } from './merkle';
import type { State } from './form';

// Resolved from the process working directory, never from the build output, so a rebuild
// cannot orphan the store. Set PA_DB_PATH in production.
const DB_PATH = process.env.PA_DB_PATH ?? resolve(process.cwd(), 'data/reports.db');

let db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (db) return db;
  mkdirSync(dirname(DB_PATH), { recursive: true });
  db = new Database(DB_PATH);
  db.pragma('journal_mode = WAL');
  db.pragma('secure_delete = ON');
  db.pragma('synchronous = FULL');
  db.exec(`
    CREATE TABLE IF NOT EXISTS reports (
      rowid            INTEGER PRIMARY KEY,           -- random 62-bit; insertion order not recoverable from the key
      received_day     TEXT    NOT NULL,              -- YYYY-MM-DD only
      schema_version   TEXT    NOT NULL,
      compound         TEXT    NOT NULL,
      route            TEXT    NOT NULL,
      goal             TEXT,
      source_channel   TEXT    NOT NULL,
      start_dose       TEXT,
      current_dose     TEXT,
      frequency        TEXT    NOT NULL,
      duration         TEXT    NOT NULL,
      purity_tested    TEXT    NOT NULL,
      status           TEXT    NOT NULL,
      stop_reason      TEXT,
      outcome          TEXT,
      adverse_effects  TEXT    NOT NULL,              -- JSON: [{id, onset, dechallenge}]
      age_band         TEXT,
      sex              TEXT,
      salt             BLOB    NOT NULL               -- per-row, secret, never published
    );
    CREATE TABLE IF NOT EXISTS merkle_leaves (
      idx   INTEGER PRIMARY KEY AUTOINCREMENT,
      leaf  BLOB NOT NULL
    );
    CREATE TABLE IF NOT EXISTS exclusions (
      leaf_idx INTEGER PRIMARY KEY,
      reason   TEXT NOT NULL,
      noted_on TEXT NOT NULL
    );
  `);
  return db;
}

function randomRowid(): bigint {
  // 62 bits: positive, below SQLite's max rowid.
  const b = randomBytes(8);
  b[0] &= 0x3f;
  return b.readBigUInt64BE();
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export type StoredRow = {
  received_day: string;
  schema_version: string;
  compound: string;
  route: string;
  goal: string | null;
  source_channel: string;
  start_dose: string | null;
  current_dose: string | null;
  frequency: string;
  duration: string;
  purity_tested: string;
  status: string;
  stop_reason: string | null;
  outcome: string | null;
  adverse_effects: string;
  age_band: string | null;
  sex: string | null;
};

export function rowFromState(s: State, schemaVersion: string): StoredRow {
  const effects = (s.adverse_effects ?? []).map((id) => ({
    id,
    onset: s.effect_detail?.[id]?.onset ?? null,
    dechallenge: s.effect_detail?.[id]?.dechallenge ?? null,
  }));
  return {
    received_day: today(),
    schema_version: schemaVersion,
    compound: s.compound!,
    route: s.route!,
    goal: s.goal ?? null,
    source_channel: s.source_channel!,
    start_dose: s.start_dose ?? null,
    current_dose: s.current_dose ?? null,
    frequency: s.frequency!,
    duration: s.duration!,
    purity_tested: s.purity_tested!,
    status: s.status!,
    stop_reason: s.stop_reason ?? null,
    outcome: s.outcome ?? null,
    adverse_effects: JSON.stringify(effects),
    age_band: s.age_band ?? null,
    sex: s.sex ?? null,
  };
}

/** The one write. Row and Merkle leaf land in a single transaction. Returns nothing the
 *  contributor could use to find the row again — by design. */
export function insertReport(row: StoredRow): void {
  const d = getDb();
  const salt = randomBytes(32);
  const leaf = leafHash(salt, canonicalJson(row as unknown as Record<string, unknown>));
  const ins = d.prepare(`
    INSERT INTO reports (rowid, received_day, schema_version, compound, route, goal, source_channel,
      start_dose, current_dose, frequency, duration, purity_tested,
      status, stop_reason, outcome, adverse_effects, age_band, sex, salt)
    VALUES (@rowid, @received_day, @schema_version, @compound, @route, @goal, @source_channel,
      @start_dose, @current_dose, @frequency, @duration, @purity_tested,
      @status, @stop_reason, @outcome, @adverse_effects, @age_band, @sex, @salt)`);
  const leafIns = d.prepare('INSERT INTO merkle_leaves (leaf) VALUES (?)');
  d.transaction(() => {
    ins.run({ ...row, rowid: randomRowid(), salt });
    leafIns.run(leaf);
  })();
}

export function reportCount(): number {
  return (getDb().prepare('SELECT COUNT(*) AS n FROM reports').get() as { n: number }).n;
}

export function currentRoot(): { root: string; leaves: number } {
  const rows = getDb().prepare('SELECT leaf FROM merkle_leaves ORDER BY idx').all() as { leaf: Buffer }[];
  return { root: merkleRoot(rows.map((r) => r.leaf)).toString('hex'), leaves: rows.length };
}
