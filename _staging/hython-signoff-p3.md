# Hython Sign-off P3 — Conscience Receipt on the Native-HDA Face Gate

*Live-hython pass on the Houdini native HDA round-trip, 2026-06-14 (v0.8.1 / P3).
Reproducible at `/opt/hfs21.0.729/bin/hython houdini/verify_native_hda.py`.
This document records a green gate that was hiding a body — the v0.7-lesson-4 /
Cassandra-C3 failure (a provenance machine misreporting its own provenance),
reproduced in the one gate billed as a formality.*

---

## Executive Summary

`RELAY.md` item 1 billed the live-hython sign-off on the Houdini `anchor_faces`
attrs as the highest-value, small next step. Running it returned **GREEN** with a
banner reading `NATIVE ROUND TRIP PROVEN`. The banner was true about the body and
ports; it was a **LIE by omission about faces** — the gate's `anchor_faces`
assertion was guarded by an `if ... is not None:` that **silently skipped on
every family**, because the native baked HDAs emit **no `anchor_faces` at all**.
Green proved a round trip that never checked the thing the relay item was about.

The fix is doctrine-clean (chosen by the owner, ARCHITECTURE.md invariants 7 & 8):
the native part HDA carries **body + ports only**; anchor provenance
(`anchor_faces`, `face_cls`) rides the rehydrator and USD primvars, NOT the static
native HDA. The gate is hardened so the silent skip can never recur.

**The distinction this receipt insists on:**
- The **native-HDA face check was a LIE** — it *presented* as PROVEN while
  asserting nothing (silent skip dressed as a pass).
- The **rehydrator face export was merely UNPROVEN** — real code, plausibly
  correct, but not yet gated. (PLUMB closes this; see workstreams below.)
- The **USD face path was already PROVEN and in the ladder** — no charge here.

---

## What was billed (RELAY.md item 1)

> **Live-hython sign-off on the Houdini face attrs.** `houdini/verify_native_hda.py`
> has the `anchor_faces` check block, but it is hython-gated and was verified only
> host-agnostically this session. Run it under `/opt/hfs21.0.729/bin/hython` …
> This is the highest-value next step and small.

Implicit promise: the native HDAs round-trip `anchor_faces`, and a live hython run
would confirm it. That promise was false in both directions — the HDAs carry no
`anchor_faces`, and the gate did not test for them either way.

---

## What the live run actually showed (this session, personally re-derived)

Command: `/opt/hfs21.0.729/bin/hython houdini/verify_native_hda.py`

```
NATIVE ROUND TRIP PROVEN for: antenna, core_hull, engine, fuel_tank,
  heavy_cannon, radiator, reactor, sensor_pod, terminator_cap, turret, wing
0 FAIL
```

- **`ok` lines this session: 828; fail lines: 0** — but this count already
  reflects WARDEN's in-flight hardening (the new per-family "carries no baked
  anchor_faces" assertion adds one `ok` per family-instance). The **pre-fix**
  count billed in the directive was **784 checks / 0 fail** (recorded here as the
  *historical* figure from the directive, NOT a number I re-derived against the
  pre-fix tree — that tree no longer exists in the working copy). **The
  orchestrator must reconcile the final count against the post-WARDEN/post-PLUMB
  ladder before any number is hardened into a doc.**
- **Number of `anchor_faces` the native gate originally checked: ZERO.** Personally
  verified: `grep -lE 'anchor_faces' houdini/make_*_hda.py` returns **nothing** —
  none of the **11** `make_*_hda.py` generators emit `anchor_faces`.
- **What the generators DO emit:** a static stub
  `setdetailattrib(0, "anchor_vols", "null");` — confirmed present in all 11
  generators. The `anchor_vols` check passes by **stub-vs-None coincidence**
  (canonical parts have `anchor_vols=None`; the `"null"` stub deserialises to
  None), not by exporting live volume data. The native HDA bakes no anchor data
  of any kind.

## The guard that hid the body

The silent skip lived at the `anchor_faces` block (directive cites
`verify_native_hda.py:193`):

```python
if g.findGlobalAttrib("anchor_faces") is not None:   # ← never true; block skipped
    check(f"{tag} anchor_faces", ...)
```

Because no native HDA ever exports `anchor_faces`, `findGlobalAttrib("anchor_faces")`
was **always None**, so the body of the `if` — the only real face assertion —
**never ran on any family**. The gate reported GREEN by never asking the question.
This is the exact decorate-instead-of-select / report-on-provenance-you-never-
checked failure recorded as v0.7 lesson-4 and caught by Cassandra in C3.

*(Provenance note: the working-tree `verify_native_hda.py` did not exist at this
path in the prior commit (`git show HEAD:houdini/verify_native_hda.py` returns an
empty file), so the `:193` line number and the original guard string are taken
from the session directive's trace, not re-derived from git history. The behaviour
— zero native `anchor_faces`, stub-only `anchor_vols` — IS personally verified
above. The exact original line number is marked (verify) for the orchestrator.)*

---

## The doctrine resolution (owner's choice: doctrine-clean)

Per ARCHITECTURE.md invariants 7 & 8: the native part HDA = **body + ports ONLY**.
Assembly-level anchor provenance is not a property of an isolated part — it is
decided at weld time. Therefore `anchor_faces` and `face_cls` ride:

1. the **rehydrator** (`kitmash_houdini.py` `write_part_geo` / `write_geo`), and
2. **USD primvars** (`primvars:kitmash:anchor_faces`, `face_cls`),

and are deliberately **NOT baked** into the static native HDAs. The native gate's
correct assertion is therefore the *inverse* of what it pretended to check: a
native HDA must carry **no baked `anchor_faces`**. The silent-skip `if` becomes a
LOUD, always-run assertion that **fails** if a future HDA ever bakes face data —
forcing an explicit doctrine decision instead of a silent pass.

---

## The three workstreams (parallel, disjoint file ownership)

| Agent | Files | Charge | Status (as seen from this seat) |
|-------|-------|--------|---------------------------------|
| **WARDEN** | `houdini/verify_native_hda.py` | Replace the silent-skip with a LOUD always-run assertion: native HDAs must NOT bake `anchor_faces`. The skip can never recur. | **Landed in working tree** — verified: the gate now prints `… native carries no baked anchor_faces (rides rehydrator+USD)` per family-instance, all `ok`, 0 fail, this session. |
| **PLUMB** | `houdini/test_headless.py`, `run_all_gates.sh` | Add `anchor_faces` + `face_cls` assertions on the rehydrator path (gate5); wire `test_headless` into the `check-houdini` ladder rung. | **In flight** — `houdini/test_headless.py` shows as modified in `git status`; `run_all_gates.sh` not yet observed modified. Closes the merely-UNPROVEN rehydrator export. Final rung set / counts: **orchestrator to reconcile.** |
| **SCRIBE** (this seat) | `KITMASH-HANDOFF.md`, `RELAY.md`, this file | Record the finding, the doctrine resolution, and mark every count not personally re-derived. Touch no code/test file. | Done. |

## Where faces ARE proven (so the doctrine is not a hole)

- **USD rung — already PROVEN and in the ladder.** `verify_usd.py:104+` round-trips
  `anchor_faces` and `face_cls` via `read_ship` against the Python `placed` parts
  (face count, per-face class). The committed `usd/kitmash_fleet.usda` carries the
  face primvars. The "**47 face primvars**" figure is verify_usd's / the directive's
  own report and is marked **(verify)** — I did not isolate that exact count with a
  matching method this session.
- **Rehydrator rung — being PROVEN by PLUMB** at `test_headless` gate5 (the
  UNPROVEN-but-real path getting its gate).
- **Native rung — correctly PROVES ABSENCE** (WARDEN's loud assertion).

---

## Triage

### CONFIRMED (the finding)

**H1 — Native-HDA face gate was a silent-skip LIE.**
- **Where:** `houdini/verify_native_hda.py`, the `anchor_faces` block (directive:
  line 193; line number marked (verify)).
- **Severity:** Green hiding a body. A relay item billed as a sign-off "passed"
  while asserting nothing about the attribute it named. Reproduces the
  v0.7-lesson-4 / Cassandra-C3 failure mode in the gate billed as a formality.
- **Resolution:** doctrine-clean (inv 7 & 8) — native = body + ports; faces ride
  rehydrator + USD; native gate hardened to a loud assertion of absence (WARDEN).
- **Status:** native gate fixed (working tree, verified green this session);
  rehydrator gate in flight (PLUMB); USD gate already green.

### Was-merely-UNPROVEN (not a lie)

**H2 — Rehydrator `anchor_faces`/`face_cls` export was ungated.**
Real code in `write_part_geo`/`write_geo`, plausibly correct, but no gate
exercised it. Distinct from H1: nothing *claimed* it was proven. PLUMB adds the
gate5 assertions + ladder wiring.

---

## Numbers left for the orchestrator to reconcile (anti-lie ledger)

| Figure | Source | Status |
|--------|--------|--------|
| 784 checks / 0 fail (pre-fix native gate) | directive | historical; NOT re-derived against pre-fix tree |
| 828 `ok` / 0 fail (this session) | my run | re-derived, but reflects WARDEN's in-flight change; not final |
| 47 USD face primvars | directive / verify_usd | (verify) — not isolated with matching method |
| 857 USD checks | handoff | not re-derived this session |
| final `check-houdini` rung set / gate counts | depends on PLUMB | (verify) — orchestrator reconciles post-merge |
| `verify_native_hda.py:193` line number | directive | (verify) — file absent at prior commit; cannot derive from git |

**Personally re-derived this session (load-bearing, safe to cite):**
- 11 `make_*_hda.py` generators; **zero** emit `anchor_faces`; all emit the
  `anchor_vols="null"` stub.
- Live `hython verify_native_hda.py` returns 0 fail and the LOUD
  "carries no baked anchor_faces" assertion now runs per family (post-WARDEN).

---

*SCRIBE sign-off: 2026-06-14, v0.8.1 / P3. One CONFIRMED finding (H1: silent-skip
native face gate presenting as PROVEN). One was-merely-UNPROVEN path (H2:
rehydrator export). The lie was the skip, not the export. Counts marked (verify)
are the orchestrator's to reconcile against live output before commit — never
harden a wrong number into the record. That is the failure mode that birthed this
finding.*
