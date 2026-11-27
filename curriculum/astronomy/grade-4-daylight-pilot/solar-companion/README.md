# Grade 4 solar ephemeris companion

**Draft proposal, unregistered, not ready for teaching.** Prepared for review on
26 November 2026 against SchoolOps main
`2aa3eb3a7934a564755823c0fb604ff1bb3b3cfd`, which contains PR #67. This is a
companion to the [synthetic daylight pilot](../README.md). Its original records,
tasks, keys, lessons and entry checks remain unchanged. No curriculum/resource
registration, timetable, approval, new canonical identifier or learner result is
created by this increment.

## What the increment adds

Actual NASA/JPL Horizons solar position outputs for two public reference points
on 21 June and 21 December 2026 replace invention **only inside this companion**.
The original synthetic packet remains available for controlled exercises. These
new position outputs are calculated ephemerides, not observations. The packet
author derives sunrise/set labels from a standard horizon criterion and rounds
bearings to the existing 15-degree scale. The [source and method record](sources.md)
separates source values, calculations, assumptions and unresolved review.

| Existing local outcome | Companion evidence | Mathematical work |
| --- | --- | --- |
| D1: daylight interval arithmetic | C2, C3, C4 | Read 24-hour times, split at noon, regroup minutes, distinguish duration from clock reading |
| D2: seasonal comparison and missing data | C3, C4, C5, C6 | Compare same-site intervals on one scale; identify the limits of an incomplete copy |
| D3: horizon-bearing representation | C7, C8, C10 | Nearest 15-degree mark, strip positions, explicit clockwise turns and north wrap |
| D4: bounded interpretation of samples | C1, C9, C10, C11, C12 | Classify calculation/observation/assumption; preserve unknowns and limit claims about unsampled times and causes |

C1-C12 and P1-P3 are local authoring labels, not stable curriculum identifiers.
Astronomy is the primary art; arithmetic and geometry do real work. Grammar names
the quantities and source types, logic checks comparisons and missing evidence,
and rhetoric requires a checkable report. Music is excluded.

## Materials and accessible routes

- [Learner records](records.md): event ledger, source-decimal bearing tables,
  15-degree values and clearly labeled omissions. No teacher-key link.
- [Learner tasks](learner.md): twelve exposed practice/reference tasks. No
  teacher-key link and no claim that a publicly exposed form is secure assessment.
- [Teacher key](teacher.md): complete answers, outcome-specific evidence,
  alternative response modes, feedback and a controlled parallel-form plan.
- [Teaching sequence](lessons.md): four proposed 25-minute episodes, prior E1-E4
  checks and additional taught checks for rounding, clocks and source types.
- [Source custody and methods](sources.md): exact public inputs, technical
  conventions, source references, rights, verification limits and reproduction.
- [Verification record](verification.md): executed checks and remaining review.

Plain text/Markdown is authoritative for accessible reading. A print edition is
an additional format; do not assume an untagged PDF provides full screen-reader
access. Read prompts and tables aloud, allow oral or dictated reasoning, use
large print and tactile direction markers, and accept labeled tables in place of
precise drawing. Keep the same arithmetic/evidence criterion. Do not time reading
or fine-motor work, or supply the answer as an accommodation. The agreed support
for an eventual assessment still needs owner review.

## Safety and privacy

**No direct Sun viewing, with the eyes or through any optical instrument.** This
is an indoor paper/text exercise. There is no outdoor observation, learner-location
collection, geolocation, telescope, camera, binocular or live Sun-finding task.
Greenwich and Sydney are public calculation references. Their model coordinates
and heights do not represent a learner, household or real observing setup.

## Reproduction

From the repository root, using only Python's standard library:

```sh
python tools/solar_ephemeris.py verify
python -m unittest discover -s tests -p 'test_solar_ephemeris.py' -v
python -m unittest discover -s ci -p 'test_*.py' -v
```

The verifier checks original response bytes and receipts, target/body/coordinate/
calendar/clock conventions, complete minute series, midpoint event rounding and
all committed derived artifacts. It does not contact a service.

To regenerate into a separate review directory:

```sh
python tools/solar_ephemeris.py build --output /tmp/solar-companion-rebuild
```

To request fresh provider responses, explicitly choose a new directory:

```sh
python tools/solar_ephemeris.py fetch --output /tmp/solar-companion-new-source-review
```

Acquisition is sequential, identifies the application/contact, bounds retries,
checks the API signature, and never overwrites or admits the frozen source
snapshot. API failures stop the refresh; no synthetic fallback is allowed. A
fresh response may differ because the provider header, Earth-orientation input
or service version changes. Review such changes before replacing any receipt.
No live provider request is embedded in the learner materials.

## Proposed review decision

Review the actual source/method choices, decimal-rounding scaffolds, fixed clocks,
scientific wording, task-key pairs, accessibility equivalents and proposed time
budget. Decide whether the companion is useful for D1-D4 and what fresh parallel
form and evidence thresholds would be needed. This packet provides no independent
learner evidence and does not complete an assessment approval or observation
outcome. Scientific/pedagogical sign-off, any real observation protocol, adopted
teaching time, source/resource admission and eventual course registration remain
owner decisions under the [curriculum model](../../../../docs/curriculum-model.md).
The initial 26 November review package was prepared without publication. On
27 November 2026 the user authorized opening a PR against main and merging after
applicable checks. Repository inclusion does not grant teaching approval or
complete the owner decisions above; the companion remains draft and unregistered.
