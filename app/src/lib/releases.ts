// Read-only access to published releases: static directories written by tools/release.py.
// The site never computes a statistic; it only shows what the pipeline wrote.
import { existsSync, readdirSync, readFileSync, realpathSync, statSync } from 'node:fs';
import { resolve, sep } from 'node:path';

export const RELEASES_DIR = resolve(process.env.PA_RELEASES_DIR ?? resolve(process.cwd(), '../releases'));

export type Release = {
  release: string;
  date: string;
  synthetic?: boolean;
  schema_version: string;
  taxonomy_sha256: string;
  release_spec: { version: string; sha256: string };
  merkle: { root: string; leaves: number; leaves_file: string; prior_root: string | null };
  counts: { committed: number; excluded: number; analyzed: number };
  tiers: Record<string, number>;
  /** Update floor (RELEASE_SPEC "Cadence"): for each unit shown in this release, the release that computed it,
   *  that release's date and the tier it was computed at. Never a count. */
  units?: Record<string, { release: string; date: string; tier: number }>;
  /** Shown units computed in an earlier release, republished unchanged from it. */
  held?: string[];
  /** Every earlier release, oldest first. */
  history?: { release: string; date: string; leaves: number }[];
  files: Record<string, string>;
  /** Directory name under RELEASES_DIR; the URL segment. Normally equals `release`. */
  dir: string;
};

const ID = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;

export function listReleases(): Release[] {
  if (!existsSync(RELEASES_DIR)) return [];
  const out: Release[] = [];
  for (const name of readdirSync(RELEASES_DIR)) {
    if (!ID.test(name)) continue;
    const p = resolve(RELEASES_DIR, name, 'release.json');
    if (!existsSync(p)) continue;
    try {
      out.push({ ...(JSON.parse(readFileSync(p, 'utf8')) as Release), dir: name });
    } catch {
      /* an unfinished directory is not a release */
    }
  }
  return out.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
}

export function getRelease(id: string): Release | null {
  if (!ID.test(id)) return null;
  const p = resolve(RELEASES_DIR, id, 'release.json');
  if (!existsSync(p)) return null;
  return { ...(JSON.parse(readFileSync(p, 'utf8')) as Release), dir: id };
}

/** Resolve a published path inside the releases directory, or null if it escapes or is absent. */
export function releaseFile(path: string): { full: string; size: number } | null {
  if (path.includes('\0') || path.split('/').some((seg) => seg === '..' || seg === '')) return null;
  const lexical = resolve(RELEASES_DIR, path);
  if (!lexical.startsWith(RELEASES_DIR + sep)) return null;
  if (!existsSync(lexical)) return null;
  // Follow symlinks and check again: a link placed inside a release must not reach outside.
  const root = realpathSync(RELEASES_DIR);
  const full = realpathSync(lexical);
  if (!full.startsWith(root + sep)) return null;
  const st = statSync(full);
  if (!st.isFile()) return null;
  return { full, size: st.size };
}

export function readTable<T = unknown>(id: string, table: string): T | null {
  const f = releaseFile(`${id}/tables/${table}.json`);
  if (!f) return null;
  return (JSON.parse(readFileSync(f.full, 'utf8')) as { data: T }).data;
}

export function witnessFiles(id: string): string[] {
  const dir = resolve(RELEASES_DIR, id, 'witness');
  if (!ID.test(id) || !existsSync(dir)) return [];
  return readdirSync(dir).filter((n) => /^[A-Za-z0-9._-]+$/.test(n)).sort();
}

/** Figure paths for one entity, in reading order (goal beside route and source, not by table number). */
const ORDER = ['T1', 'T2', 'T16', 'T3', 'T4', 'T5', 'T6', 'T8', 'T10', 'T11', 'T12'];
export function figuresFor(rel: Release, dir: string): string[] {
  const prefix = `figures/${dir}/`;
  const num = (p: string) => { const i = ORDER.indexOf(p.slice(prefix.length).match(/^T\d+/)?.[0] ?? ''); return i < 0 ? 99 : i; };
  return Object.keys(rel.files)
    .filter((p) => p.startsWith(prefix) && p.endsWith('.svg'))
    .sort((a, b) => num(a) - num(b) || (a < b ? -1 : 1));
}

// ---------------------------------------------------------------- sections for the release page

type Cell = { id: string; label: string; count: number | null; display?: string; pct?: number; ci95?: [number, number] };
type OneWay = { n: number; percent: boolean; cells: Cell[] };
type Stratum = { n: number | null; display?: string; percent?: boolean; cells?: Cell[]; label: string };
export type Section = { name: string; title: string; src?: string; oneWay?: OneWay; grid?: { columns: string[]; rows: Stratum[] } };

/** Every published table for one compound or class, in reading order, paired with its figure. */
export function sectionsFor(rel: Release, key: string, dir: string, labels: { outcome: string[]; onset: string[]; dechallenge: string[] }): Section[] {
  const id = rel.dir;
  const T = (t: string) => readTable<Record<string, any>>(id, t)?.[key];
  const fig = (name: string) => (rel.files[`figures/${dir}/${name}.svg`] ? `/releases/${id}/figures/${dir}/${name}.svg` : undefined);
  const out: Section[] = [];
  const one = (name: string, title: string, table?: OneWay) => { if (table) out.push({ name, title, src: fig(name), oneWay: table }); };
  one('T1', 'Route', T('T1'));
  one('T2', 'Source channel', T('T2'));
  one('T16', 'What people took it for', T('T16'));
  const asOf = (x: any) => (x?.as_of ? ` (as of the ${x.as_of} release)` : '');
  const t3 = T('T3'); one('T3-start_dose', 'Starting dose', t3?.start_dose); one('T3-current_dose', 'Current or final dose', t3?.current_dose);
  one('T4', 'Frequency', T('T4'));
  one('T5', 'Duration', T('T5'));
  one('T6', 'Independent purity testing', T('T6'));
  const t8 = T('T8');
  if (t8) out.push({ name: 'T8', title: 'Outcome by goal', src: fig('T8'), grid: { columns: labels.outcome, rows: t8.strata.map((s: any) => ({ ...s, label: s.label + asOf(s) })) } });
  one('T10', 'Side effects reported', T('T10'));
  const t11 = T('T11');
  for (const e of t11?.effects ?? []) {
    if (e.n === null) continue;
    out.push({ name: `T11-${e.effect}-onset`, title: `${e.label}: when it started${asOf(e)}`, src: fig(`T11-${e.effect}-onset`), grid: { columns: labels.onset, rows: [{ label: 'When it started', n: e.n, percent: e.onset.percent, cells: e.onset.cells }] } });
    out.push({ name: `T11-${e.effect}-dechallenge`, title: `${e.label}: after stopping${asOf(e)}`, src: fig(`T11-${e.effect}-dechallenge`), grid: { columns: labels.dechallenge, rows: [{ label: 'After stopping', n: e.n, percent: e.dechallenge.percent, cells: e.dechallenge.cells }] } });
  }
  const t12 = T('T12'); one('T12-status', 'Still taking, stopped, or finished', t12?.status);
  if (t12?.stop_reason?.n) one('T12-stop_reason', 'Main reason for stopping' + asOf(t12.stop_reason), t12.stop_reason);
  return out;
}
