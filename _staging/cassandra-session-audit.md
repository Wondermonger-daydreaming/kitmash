# CASSANDRA — session audit (KEYSTONE + PHOTON)

**Date:** 2026-06-14
**Auditor:** Cassandra (read-only adversary)
**Verdict:** **CLEARED TO COMMIT.** No blocking findings. Both bodies of work
reproduce at the command line under my own hands. Three flip-failures
independently reproduced; 914/0/exit-0 in both runtimes; anchor unmoved; every
GIF caption number forensic.

---

## Sacred anchor — CONFIRMED

```
../.venv/bin/python kitmash.py /tmp/cass.json && md5sum /tmp/cass.json
-> 80ddaccccc594b2a7cc8c7b40a129086   /tmp/cass.json
```
Re-run a second time on /tmp/cass2.json → same hash. The contract holds.

---

## Charge-by-charge

| Charge | Verdict | Evidence |
|--------|---------|----------|
| C1 cook test SELECTs not DECORATEs | **HOLDS** | All 3 halves reproduced RED by my own throwaway harness (below). Half (c) genuinely rehydrates the per-instance body. |
| C2 references compose, body not empty | **HOLDS** | Fresh open of committed `usd/kitmash_fleet.usda`: 47/47 part `/geo` resolve through `./assets/` arcs with real points, 0 empty, Flatten OK. 0 inline geo Mesh in fleet. |
| C3 counts honest (914, +57) | **HOLDS** | 914 ok / 0 FAIL / exit 0 in **both** runtimes. 47 ref-resolves + 10 cook-split = +57; 857+57=914. Arithmetic re-derived. |
| C4 collateral / anchor | **HOLDS** | No forbidden file in diff; `git diff --check` clean; anchor `80ddacc…` unmoved. |
| C5 round-trip still exact | **HOLDS** | 47 anchor_faces + 47 gp:* typed checks fire & pass (none None-skipped); full decision layer round-trips. |
| C6 captions forensic (Inv 11) | **HOLDS** | Every caption number read off rendered frames (via `Image.seek`) exists in `fleet.json`. No hardcoded numeric literals in caption code. |
| C7 Pillow not a gate dep | **HOLDS** | No gate file imports PIL; `run_all_gates.sh` has 0 Pillow/make_trace_gifs refs; `./run_all_gates.sh all` → ALL GREEN, exit 0. |
| C8 assembly.gif animates part-by-part | **HOLDS** | Geometry-ink grows 0→96,657 across 47 frames (sampled 0,68769,81524,94404,95676,96903,96657). Other 3 GIFs static-ish per the receipt's honest admission. |

---

## C1 — the crux, reproduced by hand

Throwaway harness against a fresh in-memory stage (GS-α part0 = core_hull):

```
BASELINE half(b): geo resolves? True  proto err: 9.54e-08   (<=1e-4 PASS)
BASELINE half(c): world err: 0.0                            (<=1e-4 PASS)
FLIP(a) ClearReferences()      -> geo points: None          -> RED
FLIP(b) corrupt proto +0.5     -> half(b) err = 0.5  > 1e-4 -> RED
FLIP(c) wrong +90deg z rot     -> half(c) world err = 5.487 > 1e-4 -> RED
```

**Adversarial probe of half (c) — does it test the truth or the prototype?**
I checked all 47 parts: is `rehydrate(rec)` body identical to the canonical
prototype (which would make (c) prototype-vs-itself)?

```
total parts: 47
per-instance body == prototype (would-be-tautology): 16
per-instance body DIFFERS from prototype (half(c) genuinely tests truth): 31
  e.g. heavy_cannon#98 diff 2.03, wing#82 diff 0.70, fuel_tank#9 diff 0.16
```

For 31/47 parts the truth body genuinely diverges from the asset body, so half
(c) (`verify_usd.py:174` calls `kh.rehydrate(rec)`, NOT `geo_pts`) composes the
TRUTH and compares to assembler world — not a tautology. The 16 coincident parts
are legitimately at canonical params; (c) still asserts truth re-renders and the
flip (wrong orient → RED) proves it can fail. **Half (c) selects.**

`verify_usd.py:148-190` — (a) line 156, (b) line 187, (c) line 189.

---

## C2 — references compose

```
part Xforms: 47   resolved-with-points: 47   empty: 0
Flatten() succeeded: True
families referenced: antenna core_hull engine fuel_tank heavy_cannon
                     radiator reactor sensor_pod turret wing  (10, all have asset files)
terminator_cap referenced? False    asset on disk? False
```
terminator_cap genuinely unplaced in canonical fleet (`fleet_families` → 10
families, terminator_cap absent) → correct omission. The 21 inline `point3f[]
points` arrays in the fleet file are all on `BasisCurves` (struts/hoses), not
part bodies — legitimate. Zero `def Mesh "geo"` inline in the fleet.

---

## C6/C8 — PHOTON GIFs

Caption numbers read from rendered frames and grepped in fleet.json (all True):
`2.39, 4.22, 0.5, 2045, 1818, 29545, 20000, 12622, 0.57, 0.109, 9464, 3635,
struct_M_3, wing#26, core_hull#1`.

- auction f12: "challenger antenna 2.39 vs incumbent radiator 4.22 / scarcity 0.5
  / prio 3 bid 4.22" — matches FV-δ auction trace.
- face_weld f15: "moment 2045 over cap 1818" — matches FV-ε repair.
- assembly f20: "commit wing L -> core_hull#1/struct_M_3 / strain 0.0 mass_left
  3635 / part_id wing#26"; f46 summary "10 parts 9464 kg 3 struts 1 hose".

assembly.gif ink grows 0→96,657 (true part-by-part build). The other three are
captioned highlight sequences exactly as the receipt admits — that admission is
the whole truth.

Caption code (`make_trace_gifs.py:263-377, 409-448`) interpolates ONLY trace
fields (`mm['moment_before']`, `SEED['seed']`, `st['parts']`, …); no hardcoded
caption numerals.

---

## Soft spots noted (non-blocking, already disclosed by receipts)
- usdview renders every instance at canonical size (variation lives in primvars,
  doctrine-correct; KEYSTONE soft-spot #1).
- `usd/assets/` is fleet-sufficient, not registry-complete (no "every family has
  an asset" gate; terminator_cap has no asset — correct for now). KEYSTONE #3.
- PHOTON: 3 of 4 GIFs are highlight sequences, anchor-face polygon not rendered.
  Disclosed honestly.

**Headline: no body found. Both work bodies reproduce; cleared to commit.**
