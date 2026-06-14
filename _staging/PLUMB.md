# PLUMB — welding the rehydrator face-export joint shut

**Scope:** trace P3 face data through the headless rehydrator until a gate fails when it breaks. The rehydrator EXPORTED `face_cls` (per-strut-point) and `anchor_faces` (per-part detail) but NO ladder rung asserted either, and `test_headless.py` was not wired into `run_all_gates.sh` at all. Both leaks now welded.

Touched ONLY the two authorized files: `houdini/test_headless.py`, `run_all_gates.sh`.

---

## 1. Diffs

### `houdini/test_headless.py`

**(a) New gate `gate5b_face_export(a)` inserted before `gate6_attribute_spotcheck` (test_headless.py:~142).** +83 lines. Two welds:

- **face_cls on strut points** (mirrors `kitmash_houdini.py:424-425`): for each strut prim written by `write_geo`, for BOTH endpoint points, assert `int(point.attribValue("face_cls")) == int(st.get("face_cls"))` (default -1 when None). Plus a *selection* assertion: `assert saw_real_face` — at least one canonical strut must have `face_cls >= 0`, proving faces actually SELECT (took welds), not merely that the attr exists.
- **anchor_faces detail attr** (mirrors `verify_usd.py:104-122`): build `km.gen_hull(km.GUILD)` (6 declared faces incl. nose GLASS cls-0), `write_part_geo(pgeo, part)`, `json.loads(pgeo.attribValue("anchor_faces"))`, assert field-by-field vs `part.anchor_faces`: c/n/u via `assert_close(..., 1e-5)`; hu/hv `abs <= 1e-5`; cls exact `int==int`.
- **None case** (drives `kitmash_houdini.py:283-284`'s `None if part.anchor_faces is None else ...`): no canonical generator yields None (all 11 families declare faces — surveyed), so clear `faceless.anchor_faces = None` on a fresh hull, write it, assert `json.loads(...) is None`.

**(b) Wiring into `main()` (test_headless.py:~222):**
```
     gate("5 write_geo",            lambda: gate5_write_geo(a))
+    gate("5b face export",         lambda: gate5b_face_export(a))
     gate("6 attribute spot-check", lambda: gate6_attribute_spotcheck(a))
```

**(c) Docstring gate-list updated** (test_headless.py:~16) to document gate 5b. (Comment only.)

### `run_all_gates.sh` (rung_houdini, line ~53)
```
     if command -v hython >/dev/null 2>&1; then
         hython houdini/verify_native_hda.py || return 1
+        hython houdini/test_headless.py || return 1
     else
```
Added AFTER `verify_native_hda.py`, under the same `command -v hython` gate, using the file's bare-`hython` convention. No restructuring of the public/lab divergence.

---

## 2. Trace — new assertions running GREEN

`/opt/hfs21.0.729/bin/hython houdini/test_headless.py`:
```
kitmash headless test suite  (seed=42)
──────────────────────────────────────────
  ✓  1 hython environment
  ✓  2 kitmash imports
     reference assembly: 10 parts, 3 struts, 1 hoses
  ✓  3 pure-Python bridge
  ✓  4 rehydrate round-trip
  ✓  5 write_geo
  ✓  5b face export          ← NEW
  ✓  6 attribute spot-check
  ✓  7 provenance detail
  ✓  8 multi-faction
──────────────────────────────────────────
  9/9 gates passed
```
Reference assembly's 3 struts both carry `face_cls=2` (verified: `saw_real_face` is True — faces select). Hull exports 6 anchor_faces, all round-trip field-by-field.

---

## 3. Proof the assertions SELECT (would-fail reasoning, verified in /tmp scratch, NOT committed)

**face_cls weld.** Scratch copy with `assert int(got) == exp_fc` mutated to `== exp_fc + 1`:
```
  ✗  5b face export
       strut heavy_cannon#34 face_cls 2 != 2
```
The strut's real face_cls is 2; comparing against 2+1=3 fails. Proof the assertion binds the *actual* exported value, not a tautology. (If the assertion were vacuous it would still pass under the wrong expectation.)

**anchor_faces.cls weld.** Scratch copy with `int(gf["cls"]) == int(pf["cls"])` mutated to `== 99`:
```
  ✗  5b face export
       face.cls 2 != 2
```
The hull's first face is cls-2; comparing against 99 fails. Proof the detail-attr round-trip is real.

Both scratch files removed (`/tmp/scratch_th.py`, `/tmp/scratch_af.py`); no break left in the committed tree.

---

## 4. check-houdini rung — test_headless wired in

`PATH="/opt/hfs21.0.729/bin:$PATH" ./run_all_gates.sh check-houdini` (hython is NOT on PATH by default, so it had to be prepended to exercise the rung rather than hit SKIP):
```
... NATIVE ROUND TRIP PROVEN for: antenna, core_hull, engine, fuel_tank,
    heavy_cannon, radiator, reactor, sensor_pod, terminator_cap, turret, wing

kitmash headless test suite  (seed=42)
──────────────────────────────────────────
  ✓  1 hython environment
  ... ✓  5b face export ...
  9/9 gates passed
  All gates passed — hython integration confirmed.
```
Both `verify_native_hda.py` and `test_headless.py` now run in the rung, both green. The rehydrator face export is no longer unproven.

---

## 5. Anchor md5 — UNCHANGED

```
../.venv/bin/python kitmash.py /tmp/plumb.json && md5sum /tmp/plumb.json
→ 80ddaccccc594b2a7cc8c7b40a129086  /tmp/plumb.json
```
Matches canonical exactly. fleet.json untouched. All 5 ships unchanged.

---

## 6. What I did NOT do

- **Did NOT touch fleet.json, kitmash.py, kitmash_houdini.py, verify_usd.py, or verify_native_hda.py.** My only edits: `houdini/test_headless.py` (+83) and `run_all_gates.sh` (+1). `git diff --stat` confirms.
- **Did NOT commit** (per instructions).
- **NOTE / out-of-scope observation (NOT my work):** `git status` shows `houdini/verify_native_hda.py` modified and a `_staging/WARDEN.md` present — these belong to a concurrent sibling agent (WARDEN), not PLUMB. Repo was "(clean)" at PLUMB's session start; I never opened verify_native_hda.py for editing. Flagging so the orchestrator does not attribute those changes to this task. I left them alone.
- **No pre-existing breakage** found in test_headless.py under hython — gates 1-8 were already green before my addition; gate 5b joined them cleanly. Nothing to report there.
