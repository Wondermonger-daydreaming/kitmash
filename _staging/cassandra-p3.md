# Cassandra P3 Audit — Face-Level Anchor Code
*Adversary pass on commit `7a86a70` (v0.8.1). Read-only, reproducible at `../.venv/bin/python`.*

---

## Executive Summary

The P3 face-anchor code is **mostly sound** — the six primary charges were hunted with live command-line reproduction. Zero confirmed exploitable bugs; one CONFIRMED latent NaN path in `make_face` (silent, not canon-reachable today, becomes dangerous the moment a custom family makes a typo); one CONFIRMED provenance mismatch between the handoff document and the actual implementation scope (the handoff says only the hull declares faces; the code declares them for all 11 families). Both are diagnosed below with exact file:line and reproduction steps.

---

## Sanity Check (pre-audit)

```
../.venv/bin/python kitmash.py /tmp/cass.json && md5sum /tmp/cass.json
  → 80ddaccccc594b2a7cc8c7b40a129086   MATCHES re-baseline
../.venv/bin/python test_kitmash.py   → ALL 10 GATES PASS (gate 9 + gate 10 included)
../.venv/bin/python test_director.py  → ALL 7 DIRECTOR GATES PASS
5/5 ships legal+fueled (demand_unmet=0 on every ship, independently rebuilt)
Nose: no strut endpoint with x > 3.5 on any canonical ship — confirmed
```

---

## Charge 1 — Can a cls-0 (glass) face ever leak a weld candidate?

**Code path in `propose_strut` (kitmash.py line 528–543):**
```python
wf = getattr(node, "w_anchor_faces", None)
if wf is not None:
    for fi, face in enumerate(wf):
        for anchor, fn, cls in face_candidates(face, com):  # [] for cls 0
            ...
    node = node.parent
    continue   # ← CRITICAL: skips the anchor_vols / whole-AABB path
```

The `continue` at line 543 means that once `w_anchor_faces` is not None, the legacy AABB path is **never reached**, regardless of whether `anchor_vols` is also set. `face_candidates` (line 177–188) returns `[]` for cls 0 immediately. The fallback chain cannot expose glass.

**Adversarial test — all-glass hull with `anchor_vols` also set:**
```python
hull.anchor_faces = [make_face([0,0,0],[0,0,1],5.0,5.0,cls=0)]
hull.anchor_vols  = [(np.array([-5,-5,-5]), np.array([5,5,5]))]  # huge
# w_anchor set; w_anchor_faces set; face_candidates([cls-0]) → []
result = a.propose_strut(jpos, jaxis, com, hull)
# → None
```

**VERDICT: HOLDS.** The `continue` guard is load-bearing and correct.

---

## Charge 2 — Normal/geometry degeneracy in `face_candidates` / `propose_strut`

### 2a: com exactly ON the face plane

`to = com − c`; `dot(to, n) = 0`; `ip = to`. Clipping proceeds normally, no division. First candidate (`base + pv*v`) may equal `com` (d = 0), triggering the `d < 0.15` guard at line 535, which fires before the `sdir = (anchor − com) / d` division at line 536. The two v-edge candidates are valid. **HOLDS.**

### 2b: hv = 0 (degenerate extent)

All three candidates collapse to the same point: `base + 0*v`. The d-guard fires if that point equals `com`; otherwise the single point is a valid candidate (3 identical entries, redundant but harmless). **HOLDS.**

### 2c: Zero-length normal in `make_face` — LATENT NaN

**Reproduced:**
```python
face = make_face([0,0,0], [0,0,0], 2.0, 2.0, cls=2)
# kitmash.py line 167: n = n / np.linalg.norm(n)  → n=[nan,nan,nan]
# RuntimeWarning: invalid value encountered in divide (silently swallowed)
```

`face_candidates` called on this face:
- `v = cross(nan, u) = [nan,nan,nan]`
- `ip = to − dot(to, nan)*nan` → NaN
- `pu, pv = clip(nan, ...) = nan`
- `base = c + nan*u = [nan,nan,nan]`
- All three pts = `[nan,nan,nan]`

In `propose_strut` (line 535): `d = nan < 0.15` evaluates **False** in Python (NaN comparisons), so the `d < 0.15` guard **does not fire**. Execution continues:
- `sdir = (nan − com) / nan = [nan,nan,nan]`
- `geom = 0.35 + 0.5*norm(cross(nan,jaxis)) = nan`
- `relief = nan`

`consider()` evaluates `best is None → True`, so `best = cand` (the NaN candidate). Subsequent valid candidates cannot beat NaN: `nan > nan+1e-9 → False`, so **the NaN dict is returned as the winning brace**.

```python
# Result: {'a':com, 'b':[nan,nan,nan], 'relief':nan, 'vol':0, 'face_cls':2}
```

`validate()` then computes `M2 *= (1 − nan) = nan`, `nan <= cap → False`, and the repair is logged as `strut_insufficient` — but **`commit()` may still be called with NaN anchor coordinates** if the code path allows it (depends on the calling context). The strut geometry would contain NaN vertices.

**Is this canon-reachable?** No. Every canonical generator uses axis-aligned unit normals; `make_face([0,0,0],[0,0,0],…)` would require an explicit authoring error. But the schema has no runtime guard: the next family author who mis-types a face normal will silently poison the brace.

**Location:** `kitmash.py` line 167 (`make_face`), lines 535–539 (`face_candidates`/`propose_strut`).

**VERDICT: CONFIRMED LATENT.** Not live in the 11 canonical generators; becomes a live defect the moment a custom family or a per-family fan-out author supplies a zero or near-zero normal. Suggested fix: add `assert np.linalg.norm(n) > 1e-6, f"make_face: degenerate normal {n}"` at kitmash.py line 167 before the division.

### 2d–2e: d = 0 guard ordering, point face

`d < 0.15` (line 535) fires **before** `sdir = (anchor − com) / d` (line 536). Division is safe. A point face (hu = hv = 0) gives three identical candidates; all filtered if d < 0.15, otherwise valid. **HOLDS.**

---

## Charge 3 — Byte-identity for non-face parts

**Finding:** The handoff v0.8.1 states *"Only the hull declares faces"* as the delivered scope and lists the other 10 families as DEFERRED. The code refutes this: **all 11 non-hull families now declare `anchor_faces`**.

```
gen_engine:  6 faces (casing ×4 cls-2, fwd flange cls-2, glow nozzle cls-0)
gen_tank:    5 faces (flange top + 4 sides, all cls-2)
gen_wing:    5 faces (root spar top/belly cls-2, chord ×2 cls-1, wing panel cls-0)
gen_cannon:  6 faces (block ×2 cls-2, ×2 cls-1, barrel tip cls-0)
gen_antenna: 6 faces (base top+4sides cls-2, mast tip cls-0)
gen_pod:     6 faces (flange cls-2, 4×barrel cls-1, dome cls-0)
gen_radiator:6 faces (block ×3 cls-2, ×2 cls-1, panel face cls-0)
gen_reactor: 6 faces (plate ×5 cls-2, cylinder cls-1)
gen_turret:  6 faces (box ×3 cls-2, ×2 cls-1, barrel tip cls-0)
gen_cap:     2 faces (mounting ring cls-2, dome cls-0)
```

Gate 10 (`test_family_face_coverage`) already asserts `>= 8 / 10 families have faces` and passes with 10/10. The gate is live and correct; the handoff is not.

**Consequence for byte-identity claim:** Since every canonical generator now has `anchor_faces`, the AABB path (`anchor_vols` or whole-AABB fallback) is **dead code for all canonical generator families**. `propose_strut` takes the face path for every node in every canonical ship. The re-baseline (e6aeccfe → 80ddaccc) correctly captures all shifted weld points. The AABB path remains reachable for custom/future parts with `anchor_faces = None` and behaves correctly (verified).

**VERDICT: WEAK (provenance gap, not functional bug).** The code is *more complete* than documented. The re-baseline is correct. The DEFERRED list in the handoff should be cleared for family face coverage and updated for DCC contract (Houdini/USD export) which genuinely remains unbuilt.

---

## Charge 4 — Goodhart edge: duplicate/overlapping cls-2 faces

**Formula:** `relief = geom * align * ANCHOR_CLASS_RELIEF[cls]`
- `geom ∈ [0.35, 0.85]` (function of strut angle vs member axis)
- `align ∈ [0.6, 1.0]` (function of strut angle vs face normal)
- `ANCHOR_CLASS_RELIEF[2] = 1.0`

**Max single brace:** `0.85 * 1.0 * 1.0 = 0.85` (strut perpendicular to member axis AND normal-on to face).

**Max composed (2 braces):** `1 − (1 − 0.85)² = 0.9775`.

**Duplicate faces:** `face_candidates` returns 3 candidates per face. N identical faces yield 3N candidates, all geometrically identical → same relief. `consider()` evaluates each and keeps the best; duplicates cannot raise the ceiling.

**Reproduced with 100 identical cls-2 faces:**
```python
hull.anchor_faces = [make_face([0,2,0],[0,1,0],3.5,0.9,cls=2)] * 100
result = a.propose_strut(jpos, jaxis, com, hull)
# → relief = 0.85 (exactly the formula maximum)
```

**VERDICT: HOLDS.** Relief is bounded at 0.85 per brace by the formula; 0.9775 composed. Duplicate faces buy nothing.

---

## Charge 5 — The re-baseline

Independent verification:

| Check | Result |
|-------|--------|
| `md5sum /tmp/cass.json` | `80ddaccccc594b2a7cc8c7b40a129086` ✓ |
| 5/5 ships legal+fueled | demand_unmet=0 on all ✓ |
| `test_kitmash.py` | 10/10 PASS ✓ |
| `test_director.py` | 7/7 PASS ✓ |
| Nose unweldable | No strut endpoint with x > 3.5 on any ship ✓ |
| Hull nose face | cls=0, centre=[4.9,0,0] ✓ |

GS-α struts anchor at `vol=2` (flank R) and `vol=3` (flank L) with `face_cls=2`. All canonical strut records show `anchor=core_hull`, consistent with the hull being the tree root and always the nearest root-side node.

**VERDICT: HOLDS.**

---

## Charge 6 — Provenance: does `face_cls` always match the face that actually took the weld?

`consider()` (kitmash.py lines 521–524):
```python
def consider(cand):
    nonlocal best
    if best is None or cand["relief"] > best["relief"] + 1e-9 or \
       (abs(cand["relief"] - best["relief"]) < 1e-9 and cand["L"] < best["L"]):
        best = cand
```

`best` is assigned the **entire candidate dict**, including `face_cls` and `vol`. There is no field-by-field copy; `face_cls` in `best` is exactly from the winning candidate. The only way it could be wrong is if the dict were mutated after `consider()`, which does not happen.

**Adversarial test — two cls-2 faces at different positions:**
```python
hull.anchor_faces = [
    make_face([0,2,0],[0,1,0],3.5,0.9,cls=2),   # face 0
    make_face([0,0,0.5],[0,0,1],3.5,0.9,cls=2), # face 1
]
result = a.propose_strut(jpos, jaxis, com, hull)
# Manual computation confirms winning face_cls == result['face_cls']
```

**Tie-breaker path (gate 9 sub-test C):** two co-located faces `[TOP(1), TOP(2)]` — identical geometry, different cls. `ANCHOR_CLASS_RELIEF[2] / ANCHOR_CLASS_RELIEF[1] = 1.538` makes cls-2 always win. `stc['vol'] == 1` (index of cls-2 face), `stc['face_cls'] == 2`. Correct.

**Multi-level path:** hull (all-glass) → wing (cls-2 spar faces). `propose_strut` traverses wing first, sets best from wing's cls-2 face. Hull contributes zero candidates (cls-0). `face_cls = 2`, `anchor_part = 'wing R'`. Correct.

**VERDICT: HOLDS.** `face_cls` faithfully records the winning face in all tested configurations.

---

## Supplementary Finding — Missing u-edge triangulation candidates

`face_candidates` returns 3 candidates: nearest point + two v-edge points (`base ± hv*v`). The u-edge points (`base ± hu*u`) are not included. In general, u-edge candidates have:
- Same `geom` when strut direction is horizontal and jaxis is also horizontal
- Lower `align` than the nearest point (which is optimal for normal-on)

Reproduction shows u-edge relief ≤ nearest-point relief in all axis-aligned cases tested. The nearest point dominates because it maximizes `|dot(sdir, face_normal)|` for a straight-above approach.

**VERDICT: DEFERRED.** The nearest point is the geometrically dominant candidate in the typical strut configuration. u-edge candidates could theoretically yield higher geom in edge cases where jaxis aligns with v, but the effect is second-order and not observable on the canonical fleet. Document as optimization opportunity, not correctness defect.

---

## TRIAGE

### CONFIRMED (must fix before family fan-out)

**C2c — Silent NaN from zero-length face normal**
- **Where:** `kitmash.py` line 167 (`make_face`); affects `face_candidates` → `propose_strut` NaN result
- **Severity:** Silent data corruption. A custom or fan-out family with a typo in the normal vector silently produces a NaN-relief brace record with `b=[nan,nan,nan]`. No exception raised; the NaN candidate wins whenever it's evaluated first (because `best is None → best = cand`).
- **Fix:** `assert np.linalg.norm(n_raw) > 1e-6` before the division in `make_face`, and/or `if any(np.isnan(relief_or_d)): continue` in `face_candidates`.
- **Status:** NOT canon-reachable (all 11 canonical generators use explicit axis-aligned normals). Becomes live the moment the per-family fan-out adds a new generator.

### CONFIRMED (provenance)

**C3 — Handoff document misrepresents P3 scope**
- **Where:** `KITMASH-HANDOFF.md` v0.8.1 section, DEFERRED item 1
- **Text says:** *"Only the hull declares faces. The other 10 families still use AABB anchor_vols."*
- **Code says:** All 11 non-hull families already declare `anchor_faces` (verified by gate 10, which passes 10/10, and by direct inspection of every generator).
- **Impact:** The DEFERRED items in the handoff will mislead the next instance into re-implementing already-done work. Specifically, the *per-family face-author (10 families)* sub-task in the fan-out roadmap is **already complete in the code**; only the DCC export (Houdini/USD `write_part_geo`/`write_usd` plumbing for `anchor_faces`) remains genuinely unbuilt.
- **Fix:** Update KITMASH-HANDOFF.md v0.8.1 DEFERRED section to reflect that family face coverage is complete (gate 10 passes), and revise remaining deferred work to: (1) DCC export plumbing, (2) Cassandra sign-off (now satisfied by this audit).

### DEFERRED

**D1 — NaN swallowed by AABB path too (Charge 2c extended)**
The NaN issue is specific to the face path but the same `consider()` logic handles the AABB path. If a future custom generator returns NaN world coords from a corrupted AABB, the same stale-best problem exists. Not canon-reachable. Deferred to a general input-validation hardening pass.

**D2 — Missing u-edge triangulation candidates (supplementary)**
`face_candidates` omits `base ± hu*u` candidates. In degenerate jaxis alignment, u-edge candidates could yield higher geom. Dominant case (nearest point) is always in the candidate set. Deferred as optimization; would require adding 2 more candidates per face and may not change any canonical weld.

**D3 — AABB path dead code for canonical generators**
All 11 canonical generators now declare `anchor_faces`, making the AABB fallback path (`anchor_vols`/whole-AABB) unreachable in normal operation. The path remains correct for custom parts with `anchor_faces = None`. Not a bug; flag for clarity: the path is no longer exercised by any gate on the canonical fleet.

---

## What Was Not Hunted

- DCC export (`write_part_geo`, `write_usd`) does not yet export `anchor_faces`. This is the genuine remaining DEFERRED item (handoff item 2). Not hunted here because Cassandra is read-only and the Houdini/USD tests are not in scope for a pure-Python audit.
- The `face_cls` provenance field on the USD `primvars:kitmash:strut:face_cls` path (if any) — the extractor side was not audited against the USD export.

---

*CASSANDRA sign-off: commit `7a86a70`, branch `p3-face-anchors`, audit date 2026-06-14.*
*Two CONFIRMED findings: one latent NaN in `make_face` (zero-normal guard missing), one provenance mismatch (handoff DEFERRED list overstates what remains). Zero live exploits on the canonical fleet.*
