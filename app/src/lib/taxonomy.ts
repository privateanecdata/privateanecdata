// Single source of truth for every vocabulary the form offers. Nothing in the form is typed by
// the contributor; every value is one of these ids, validated on the server against this file.
import raw from '../../../spec/taxonomy.v1.json';

export type Option = { id: string; label: string };
export type Compound = {
  id: string;
  label: string;
  aliases: string[];
  class: string;
  goals: string[];
  adverseEffects: string[];
  routes: string[];
  doseBands: string[];
  frequency: string[];
  humanEvidence: string;
};
type Class = { id: string; label: string; members: string[] };
type Shared = Record<string, Option[]>;

type Taxonomy = {
  version: string;
  shared: Shared;
  compounds: Compound[];
  classes: Class[];
  goals: Option[];
  universalAdverseEffects: Option[];
  adverseEffects: Option[];
  routes: Option[];
  frequency: Option[];
};

export const tax = raw as unknown as Taxonomy;

const byId = <T extends { id: string }>(xs: T[]) => new Map(xs.map((x) => [x.id, x]));

export const compounds = byId(tax.compounds);
export const classes = tax.classes;
export const goalLabel = byId(tax.goals);
export const aeLabel = byId([...tax.universalAdverseEffects, ...tax.adverseEffects]);
export const routeLabel = byId(tax.routes);
export const freqLabel = byId(tax.frequency);
export const shared = tax.shared;

export const OTHER = 'other';

/** "Other (not listed)": counted, never broken out. Compound-scoped fields are empty. */
export const OTHER_COMPOUND: Compound = {
  id: OTHER,
  label: 'Other (not listed)',
  aliases: [],
  class: OTHER,
  goals: [],
  adverseEffects: [],
  routes: tax.routes.map((r) => r.id),
  doseBands: [],
  frequency: tax.frequency.map((f) => f.id),
  humanEvidence: 'n/a',
};

export function compound(id: string | undefined): Compound | undefined {
  if (id === OTHER) return OTHER_COMPOUND;
  return id ? compounds.get(id) : undefined;
}

/** Options for a compound-scoped field, rendered as {id,label}. */
export function compoundOptions(c: Compound, field: 'goals' | 'routes' | 'frequency'): Option[] {
  const src = field === 'goals' ? goalLabel : field === 'routes' ? routeLabel : freqLabel;
  return c[field].map((id) => ({ id, label: src.get(id)?.label ?? id }));
}

export function doseBandOptions(c: Compound): Option[] {
  return c.doseBands.map((b, i) => ({ id: `b${i}`, label: b }));
}

/** Universal effects (route-gated) followed by the compound's own. */
export function adverseEffectOptions(c: Compound, route: string | undefined): Option[] {
  const injectable = route === 'subcutaneous' || route === 'intramuscular' || route === 'intravenous';
  const nasal = route === 'intranasal';
  const uni = tax.universalAdverseEffects.filter((a) => {
    if (a.id === 'injection-site') return injectable;
    if (a.id === 'nasal-irritation') return nasal;
    return true;
  });
  const own = c.adverseEffects.map((id) => ({ id, label: aeLabel.get(id)?.label ?? id }));
  return [...uni, ...own];
}

export const compoundsByClass = classes.map((cls) => ({
  ...cls,
  compounds: cls.members.map((m) => compounds.get(m)!).filter(Boolean),
}));
