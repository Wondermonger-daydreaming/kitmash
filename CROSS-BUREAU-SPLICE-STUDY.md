# The Changeling Cross — what a Guild×Feral hybrid actually looks like

*A forensic study of the cross-bureau splice. Every number here is read from a
real build by `study_cross_bureau_splice.py` (`../.venv/bin/python
study_cross_bureau_splice.py /tmp/splice_study.json`); none is asserted. The
splice mechanism shipped in v0.7 (`director.py:splice_trace`, wired into
`evolve()._breed`) but had never been looked at. This is the look.*

---

## The question

The v0.7 handoff left one thread "wired but unstudied": *what does a Guild×Feral
hybrid actually look like?* The bureaus each breed within their own objective by
default; once per generation `evolve()` fires **one deliberate cross-bureau
splice** of the two fittest survivors from different bureaus. Nobody had read the
child.

## The mechanism (what splice actually inherits)

`splice_trace(brief_a, brief_b, fit_a, fit_b)` is **not symmetric**. It mixes the
two parents on different axes:

| Axis | Rule | Consequence |
|------|------|-------------|
| **wants** (per family) | `max(want_a, want_b)` — "the louder taste" | the child is *over-specified*: loud on every axis **either** parent cared about |
| **faction** | the **fitter** parent's | sets the spine physics — Guild `safety_factor` 2.0 vs Feral 1.1 |
| **bureau** (scoring objective) | the **fitter** parent's | the child rejoins a real objective lineage… |
| **tie_policy** | the **fitter** parent's | diversity vs faction tie-breaks |
| **extra_gens** | **union** of both | a Service cross drags reactor/turret genes into a child that can now feed them |
| **heavy / span** | 50/50 blend | between the parents |
| **seed** | `a.seed·131 + b.seed·17 + 1` | **order-dependent** — the two directions get *different* seeds, so they walk different mate-rolls |

The load-bearing line: the child inherits the fitter parent's **scoring
objective** and **faction physics**, but its **wants come from both**. When the
two parents reward opposite things, those pull apart — and the child is born at
war with its own label.

## The parents (each scored under its own bureau)

```
Guild-Structural [High Guild]  fit=10.03   parts=10 mass=9274  struts=3 spp=0.30 repairs=2  — clean, debt-free frame
Feral-Repair     [Feral]       fit=10.40   parts=10 mass=11249 struts=6 spp=0.60 repairs=4  — over-armed, braces hard, scars by design
```

The Guild seed wants a modest cannon (1.0); the Feral seed wants 2.8 and a heavier
lever (heavy 1.7 vs 0.9). Their wants union takes the louder of each:

```
family        Guild  Feral  child=max  louder
heavy_cannon   1.00   2.80     2.80     Feral   ← the child is armed like a Feral
wing           2.00   2.20     2.20     Feral
antenna        0.90   0.30     0.90     Guild   ← …but still antennaed like a Guild
sensor_pod     0.80   0.60     0.80     Guild
engine/fuel    3.00   2.50     —        (equal)
```

## The changeling — direction decides identity

Forcing each direction (Guild fitter / Feral fitter) holds the wants constant and
swaps only what the fitter donates. The bodies invert:

| | **Guild-fitter** child | **Feral-fitter** child |
|---|---|---|
| inherits faction | High Guild (`safety` 2.0) | Feral (`safety` 1.1) |
| inherits bureau (label) | Guild-Structural | Feral-Repair |
| seed (order-dependent) | 1309 | 3133 |
| **struts** | **7** | **3** |
| **strut_per_part** | **0.70** | **0.30** |
| repairs | 4 | 2 |
| fit under **own** label | **8.83** (Guild) | **8.10** (Feral) |
| fit under **other** label | **10.23** (Feral) | **10.03** (Guild) |
| verdict | a **Feral body wearing a Guild name** | a **Guild body wearing a Feral name** |

Both children score **higher under the *opposite* bureau than under their own.**
The Guild-fitter child braces hard (Guild discipline + the loud Feral cannon force
seven struts) — and then is scored by the Guild-Structural objective, whose
`honest` term *punishes* exactly those struts (8.83). The Feral-fitter child rides
the same load on Feral tolerance with only three struts — a clean frame — and is
scored by Feral-Repair, whose `bracing`/`repair` terms *wanted* scars it didn't
grow (8.10). Each hybrid is a stranger in its own house.

The **natural** direction (real fitnesses: Guild 10.03 < Feral 10.40) makes Feral
the fitter, so `evolve()` would breed the Feral-named child — and it still shows
the tension: a Feral-faction child with 4 struts scoring **8.87 self vs 9.63**
under Guild. The body fits the wrong house by ~0.8 fitness.

## Is the changeling general? The cross-pair matrix

Across all six unordered bureau pairs (natural direction, real fitnesses), the
`BODY≠LABEL` tension — child scores higher under the *loser's* objective than its
own inherited one — appears in **2 of 6** crosses:

```
cross                         faction      struts  spp  rep  hose   self    other   tension
Guild×Feral   → Feral         Feral           4   0.40   2    1    8.867   9.634   BODY≠LABEL
Guild×Service → Service       Feral           2   0.20   2    3   11.901  10.434   aligned
Guild×Austerity → Austerity   High Guild      2   0.22   2    1   11.600  10.212   aligned
Feral×Service → Service       Feral           3   0.30   3    2   11.501   8.101   aligned
Feral×Austerity → Austerity   High Guild      6   0.67   4    1   11.600   9.568   aligned
Service×Austerity → Service   Feral           2   0.20   1    2   11.968  12.546   BODY≠LABEL
```

The tension is **not** universal — and *where* it appears is legible: the two
changeling crosses (Guild×Feral, Service×Austerity) are precisely the pairs whose
objectives are most **opposed** in what they reward (honest-frame vs visible-scar;
intricate-service vs punish-repetition). When the parents' objectives are
compatible — a Guild and a Service bureau both like a legal, well-fed ship —
the hybrid's body aligns with its inherited label and there is no war.

*(Honesty caveat: the Austerity column scores with **no sibling context**, so its
`antirepeat` term defaults to 1.0 — an upper ceiling it would not hold inside a
real generation with siblings to collide against. The `self<other` **direction**
holds regardless of that magnitude; don't read Austerity's absolute 12.5 as a
loop-realistic number.)*

## The live win — what the loop bred unprompted

In a real `evolve(generations=2, population=4)` run, the loop's own once-per-gen
cross-bureau splice produced **Service-Network × Austerity → Service** (child
`G1-02-Feral`, parents `Feral/101×High/53`):

```
faction=Feral  bureau=Service-Network   parts=10  struts=2  spp=0.20  repairs=1
families = {engine, fuel_tank, heavy_cannon×2, reactor, sensor_pod, turret, wing×2}
fueled=True  legal=True   fitness = 11.97   ← the fittest ship in the run
```

It carries the **reactor + turret** service genes (unioned in from the Service
parent) *and* the broad family spread Austerity's wide taste seeds — a richly
plumbed, broadly armed frame that **neither parent bureau would have bred alone.**
Hybridization here didn't confuse the lineage; it founded a fitter school. (And
per the matrix, this very cross is a changeling — it would score 12.55 under
Austerity, even above its 11.97 Service label. The loop crowned a stranger and was
right to.)

## What this means

1. **A cross-bureau splice is a face-graft, not a blend.** The child wears the
   fitter parent's name and physics but carries both parents' loudest wants. In
   opposed crosses it is a genuinely *new* body — one the inherited bureau would
   never have produced — injected into that bureau's lineage.
2. **The changeling is the anti-monoculture mechanism working.** The whole point
   of v0.7 was to stop the loop from breeding one High-Guild jawline forever. A
   hybrid scored *against* its own objective is a body the objective didn't ask
   for — exactly the kind of stranger that breaks an attractor. Selection then
   keeps it (if it scores well despite the mismatch, like the live Service child)
   or culls it. Either way the lineage *tried on another house's face.*
3. **Direction matters and is legible.** Because identity follows the fitter
   parent, the same two bureaus yield two different ships depending on which
   lineage is ahead that generation. A Guild×Feral cross in a Guild-leading run is
   a scarred ship apologizing for its struts; in a Feral-leading run it's a clean
   ship that forgot to bleed. Read the fitter parent to predict the child.
4. **The wants-union trends hybrids loud.** Taking `max` per family means every
   cross is over-specified relative to either parent — louder on every axis anyone
   cared about. Over enough generations that is a pressure toward maximalist
   ships; a future study should watch whether splice chains inflate part counts
   into the budget ceiling.

## Reproduce

```sh
../.venv/bin/python study_cross_bureau_splice.py /tmp/splice_study.json
```

Deterministic, rng-free, no network. The JSON record carries every parent, both
forced-direction children, the live-loop instance, and the full cross-pair matrix.

*The bureaus do not merely score the same ships differently; crossed, they breed
ships that score themselves wrong — and that wrongness is the point. A house that
only ever bred its own jawline would never know it had one.*
