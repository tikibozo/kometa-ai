# Decision Consistency

## The problem (2025)

Re-running the same evaluation flipped ~50% of titles in/out of collections on
every run: run 1 added a batch of movies, run 2 decided half of them no longer
belonged, run 3 re-added them, forever.

## Root causes

1. **Permanent near-threshold re-evaluation.** Any movie whose stored
   confidence was within 0.15 of the threshold was re-sent to Claude on
   *every* run. LLM confidence outputs cluster at 0.6–0.8 — right inside that
   band with the default 0.7 threshold — so a large slice of the library lived
   permanently in a churn pool.
2. **No memory of prior decisions.** The prompt never mentioned what was
   previously decided, so each re-evaluation was an independent coin flip near
   the boundary, and every flip immediately became a Radarr tag add/remove.
3. **Unstable batch context.** Batches were built only from the movies being
   reprocessed (different every run) in library order. The model implicitly
   judges relative to batch companions, so the same movie saw different
   context each run.
4. **Hard threshold on a noisy scalar.** A 0.68-vs-0.72 wobble became a binary
   membership flip.

## The fix (four layers, defense in depth)

All in `kometa_ai/claude/processor.py` and `prompts.py`:

1. **Bounded re-evaluation** — `DecisionRecord.revisions` counts near-threshold
   re-evaluations; after `MAX_REVISIONS` (1) only a metadata change or
   `--force-refresh` triggers another look.
2. **Hysteresis (status-quo bias)** — a re-evaluation may only flip the stored
   decision if the new evaluation clears the threshold by
   `HYSTERESIS_MARGIN` (0.1) on the opposite side. Marginal wobbles keep the
   prior decision.
3. **Deterministic batching** — movies are sorted by id before batching, so
   identical inputs produce identical batches.
4. **Prior-decision anchoring** — re-evaluated movies carry
   `previous_decision` in the prompt, with instructions to treat it as the
   standing verdict unless there is a clear, articulable reason to change.
   The system prompt also instructs evaluating each movie independently of
   its batch companions.

Structured outputs (API backend) additionally force a reasoning-first response
schema, which improves decision quality and eliminates JSON parse drift.

## Measuring

`scripts/consistency_check.py` runs a collection twice from blank state
(raw model consistency — anchoring and hysteresis can't help without priors),
reports the flip rate, then runs a normal pass on top of the second run's
state and reports membership changes (should be zero).

Benchmarks on a real 4,590-movie Radarr library (claude-sonnet-5, CLI backend):

| Collection | Movies | Raw flip rate | Stability pass |
|---|---|---|---|
| Heist Movies | 60 | 0/60 (0.0%) | 2 re-evaluated, 0 changes |
| Dark Comedies (deliberately fuzzy) | 80 | 1/80 (1.2%) | 10 re-evaluated, 0 changes |

The single raw flip was Sweeney Todd (horror-musical-comedy — genuinely
ambiguous); with priors in state, anchoring + hysteresis held it stable.

Target: <2% raw flip rate, zero changes on a normal re-run. Both met.
