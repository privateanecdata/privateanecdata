// Multi-step form engine. State is carried between screens in a hidden field, not on the server.
// Every POST validates that screen's fields against the taxonomy and merges into the state; the
// final confirm re-validates everything before the single write.
import {
  compound as getCompound, compoundOptions, doseBandOptions, adverseEffectOptions, shared, OTHER,
  type Option,
} from './taxonomy';

export type EffectDetail = { onset: string; dechallenge: string };
export type State = {
  compound?: string;
  route?: string;
  goal?: string;
  source_channel?: string;
  start_dose?: string;
  current_dose?: string;
  frequency?: string;
  titration?: string;
  duration?: string;
  purity_tested?: string;
  reconstitution?: string;
  status?: string;
  stop_reason?: string;
  outcome?: string;
  adverse_effects?: string[];
  effect_detail?: Record<string, EffectDetail>;
  age_band?: string;
  sex?: string;
};

export type Errors = Record<string, string>;

// ---------------------------------------------------------------- state encoding

export function encodeState(s: State): string {
  return Buffer.from(JSON.stringify(s), 'utf8').toString('base64url');
}

export function decodeState(raw: string | null | undefined): State {
  if (!raw) return {};
  try {
    const obj = JSON.parse(Buffer.from(raw, 'base64url').toString('utf8'));
    return typeof obj === 'object' && obj ? (obj as State) : {};
  } catch {
    return {};
  }
}

// ---------------------------------------------------------------- vocab helpers

const ids = (opts: Option[]) => new Set(opts.map((o) => o.id));
const oneOf = (v: FormDataEntryValue | null, opts: Option[]): string | undefined => {
  if (typeof v !== 'string') return undefined;
  return ids(opts).has(v) ? v : undefined;
};

export const STOPPED = (status: string | undefined) => !!status && status.startsWith('stopped-');

// ---------------------------------------------------------------- steps

export type Step = {
  slug: string;
  title: string;
  next: string | null;
  /** Validate this screen's fields. Returns merged state and any errors. */
  apply: (state: State, fd: FormData) => { state: State; errors: Errors };
  /** Whether this screen applies given the state (effects detail is skipped with no effects). */
  applies?: (state: State) => boolean;
};

export const STEPS: Step[] = [
  {
    slug: '1-compound',
    title: 'What did you take?',
    next: '2-usage',
    apply(state, fd) {
      const id = fd.get('compound');
      const c = typeof id === 'string' ? getCompound(id) : undefined;
      if (!c) return { state, errors: { compound: 'Choose a compound from the list.' } };
      // Changing compound invalidates compound-scoped answers.
      const changed = state.compound !== id;
      const next: State = changed
        ? { compound: id as string }
        : { ...state, compound: id as string };
      return { state: next, errors: {} };
    },
  },
  {
    slug: '2-usage',
    title: 'How you used it',
    next: '3-course',
    apply(state, fd) {
      const errors: Errors = {};
      const c = getCompound(state.compound);
      if (!c) return { state, errors: { compound: 'Start by choosing a compound.' } };
      const route = oneOf(fd.get('route'), compoundOptions(c, 'routes'));
      const goal = oneOf(fd.get('goal'), [...compoundOptions(c, 'goals'), { id: OTHER, label: '' }]);
      const source_channel = oneOf(fd.get('source_channel'), shared.sourceChannel);
      const bands = doseBandOptions(c);
      const start_dose = oneOf(fd.get('start_dose'), bands);
      const current_dose = oneOf(fd.get('current_dose'), bands);
      const frequency = oneOf(fd.get('frequency'), [...compoundOptions(c, 'frequency'), { id: OTHER, label: '' }]);
      const titration = oneOf(fd.get('titration'), shared.titration);
      const hasGoals = c.goals.length > 0, hasBands = c.doseBands.length > 0;
      if (!route) errors.route = 'Choose how you took it.';
      if (hasGoals && !goal) errors.goal = 'Choose the main thing you were hoping it would do.';
      if (!source_channel) errors.source_channel = 'Choose where it came from.';
      if (hasBands && !start_dose) errors.start_dose = 'Choose the dose range you started at.';
      if (hasBands && !current_dose) errors.current_dose = 'Choose the dose range you ended up at.';
      if (!frequency) errors.frequency = 'Choose how often you took it.';
      if (!titration) errors.titration = 'Choose how the dose changed over time.';
      return {
        state: { ...state, route, goal, source_channel, start_dose, current_dose, frequency, titration },
        errors,
      };
    },
  },
  {
    slug: '3-course',
    title: 'Duration and handling',
    next: '4-outcome',
    apply(state, fd) {
      const errors: Errors = {};
      const duration = oneOf(fd.get('duration'), shared.duration);
      const purity_tested = oneOf(fd.get('purity_tested'), shared.purityTested);
      const reconstitution = oneOf(fd.get('reconstitution'), shared.reconstitution);
      const status = oneOf(fd.get('status'), shared.status);
      let stop_reason = oneOf(fd.get('stop_reason'), shared.stopReason);
      if (!duration) errors.duration = 'Choose how long you took it in total.';
      if (!purity_tested) errors.purity_tested = 'Choose whether you had it tested.';
      if (!reconstitution) errors.reconstitution = 'Choose how you prepared it.';
      if (!status) errors.status = 'Choose whether you are still taking it.';
      if (STOPPED(status) && !stop_reason) errors.stop_reason = 'Choose the main reason you stopped.';
      if (!STOPPED(status)) stop_reason = undefined;
      return { state: { ...state, duration, purity_tested, reconstitution, status, stop_reason }, errors };
    },
  },
  {
    slug: '4-outcome',
    title: 'What happened',
    next: '5-effects',
    apply(state, fd) {
      const errors: Errors = {};
      const c = getCompound(state.compound);
      if (!c) return { state, errors: { compound: 'Start by choosing a compound.' } };
      const outcome = oneOf(fd.get('outcome'), shared.outcome);
      if (c.goals.length > 0 && !outcome) errors.outcome = 'Choose how it went for the goal you picked.';
      const allowed = ids(adverseEffectOptions(c, state.route));
      const picked = fd.getAll('adverse_effects').filter((v): v is string => typeof v === 'string' && allowed.has(v));
      const none = fd.get('no_effects') === '1';
      const adverse_effects = none ? [] : Array.from(new Set(picked));
      if (!none && adverse_effects.length === 0) errors.adverse_effects = 'Tick any effects you noticed, or tick "none".';
      // Drop details for effects no longer selected.
      const effect_detail: Record<string, EffectDetail> = {};
      for (const id of adverse_effects) if (state.effect_detail?.[id]) effect_detail[id] = state.effect_detail[id];
      return { state: { ...state, outcome, adverse_effects, effect_detail }, errors };
    },
  },
  {
    slug: '5-effects',
    title: 'About those effects',
    next: '6-about',
    applies: (s) => (s.adverse_effects?.length ?? 0) > 0,
    apply(state, fd) {
      const errors: Errors = {};
      const effect_detail: Record<string, EffectDetail> = {};
      for (const id of state.adverse_effects ?? []) {
        const onset = oneOf(fd.get(`onset:${id}`), shared.onset);
        const dechallenge = oneOf(fd.get(`dechallenge:${id}`), shared.dechallenge);
        if (!onset) errors[`onset:${id}`] = 'Choose when it started.';
        if (!dechallenge) errors[`dechallenge:${id}`] = 'Choose what happened when you stopped.';
        if (onset && dechallenge) effect_detail[id] = { onset, dechallenge };
      }
      return { state: { ...state, effect_detail }, errors };
    },
  },
  {
    slug: '6-about',
    title: 'About you (optional)',
    next: 'review',
    apply(state, fd) {
      const age_band = oneOf(fd.get('age_band'), shared.ageBand);
      const sex = oneOf(fd.get('sex'), shared.sex);
      return { state: { ...state, age_band, sex }, errors: {} };
    },
  },
];

export const stepBySlug = new Map(STEPS.map((s) => [s.slug, s]));

/** The next applicable step after `slug`, skipping steps whose `applies` returns false. */
export function nextStep(slug: string, state: State): string {
  let cur = stepBySlug.get(slug)?.next ?? 'review';
  while (cur !== 'review') {
    const s = stepBySlug.get(cur)!;
    if (!s.applies || s.applies(state)) return cur;
    cur = s.next ?? 'review';
  }
  return 'review';
}

/** The earliest step whose fields are missing — used to bounce users who skip ahead. */
export function firstIncomplete(state: State): string | null {
  const c = getCompound(state.compound);
  if (!c) return '1-compound';
  const needGoal = c.goals.length > 0, needBands = c.doseBands.length > 0;
  if (!state.route || (needGoal && !state.goal) || !state.source_channel || (needBands && (!state.start_dose || !state.current_dose)) || !state.frequency || !state.titration) return '2-usage';
  if (!state.duration || !state.purity_tested || !state.reconstitution || !state.status || (STOPPED(state.status) && !state.stop_reason)) return '3-course';
  if ((needGoal && !state.outcome) || !Array.isArray(state.adverse_effects)) return '4-outcome';
  for (const id of state.adverse_effects) if (!state.effect_detail?.[id]) return '5-effects';
  return null;
}

/** Full re-validation before the write. Returns null if valid, else the offending step. */
export function validateComplete(state: State): string | null {
  const missing = firstIncomplete(state);
  if (missing) return missing;
  const c = getCompound(state.compound)!;
  if (!ids(compoundOptions(c, 'routes')).has(state.route!)) return '2-usage';
  if (c.goals.length > 0 && state.goal !== OTHER && !ids(compoundOptions(c, 'goals')).has(state.goal!)) return '2-usage';
  if (c.doseBands.length > 0) {
    const bands = ids(doseBandOptions(c));
    if (!bands.has(state.start_dose!) || !bands.has(state.current_dose!)) return '2-usage';
  }
  if (state.frequency !== OTHER && !ids(compoundOptions(c, 'frequency')).has(state.frequency!)) return '2-usage';
  if (c.goals.length > 0 && !ids(shared.outcome).has(state.outcome!)) return '4-outcome';
  const allowed = ids(adverseEffectOptions(c, state.route));
  for (const id of state.adverse_effects!) if (!allowed.has(id)) return '4-outcome';
  return null;
}
