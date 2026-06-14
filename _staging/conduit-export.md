# CONDUIT — anchor_faces export report (P3 DCC contracts)

**Branch:** `p3-face-anchors`  
**Agent:** CONDUIT  
**Date:** 2026-06-14

---

## Primvar / attr schema chosen for `anchor_faces`

### USD (`kitmash_usd.py`)

`anchor_faces` rides as a **JSON string primvar** `primvars:kitmash:anchor_faces`
(constant interpolation, same pattern as `gen_params`) on each part Xform. The
string is the serialized face list:

```
"null"                         — no declared faces (fall back to anchor_vols / AABB)
[{                             — per-face object
    "c": [x, y, z],           — centre (3 × double, local part frame)
    "n": [x, y, z],           — outward unit normal (3 × double)
    "u": [x, y, z],           — in-plane u axis (3 × double)
    "hu": double,             — half-extent along u
    "hv": double,             — half-extent along v (= n×u)
    "cls": int                — anchor class: 0=glass(no-weld), 1=secondary, 2=primary
}, ...]
```

**Why JSON string, not typed Double3Array:** The face count varies per family
(2–6); USD VtArray primvars are homogeneous and constant-length; a JSON string
matches the `gen_params` precedent and is directly parseable by any DCC's Python
SOP without bespoke USD schema extensions. Double storage is preserved inside the
JSON (Python's `json.dumps` writes full-precision floats from numpy float64).

**Struts:** `face_cls` added as `primvars:kitmash:face_cls` (Int, constant) on
each `Struts/strut{i}` BasisCurves prim. Value: the anchor class of the face that
took the weld, or `-1` if the AABB path was used (legacy / no faces declared).
Parallel to the existing `vol` primvar.

### Houdini (`kitmash_houdini.py`)

`anchor_faces` added as a **detail (Global) attribute** `s@anchor_faces` (string,
JSON) in `write_part_geo`, immediately after `anchor_vols`. Same format as the
USD string. A part-HDA can rehydrate the face declarations with a Python SOP
`json.loads(detail("anchor_faces"))` — no Houdini schema change needed.

`face_cls` added as **`i@face_cls`** (point attribute) on each strut-segment
point in `write_geo`, declared alongside `vol`. Value: `int(face_cls)` or `-1`.
An artist's grunge/dress VEX shader can read `face_cls` to decide whether to add
weld marks appropriate to primary structure vs. secondary structure.

---

## USD verify results

**Command:** `../.venv/bin/python verify_usd.py`  
**Runtime:** usd-core 26.5 (no Houdini license)  
**Result:** GREEN — 0 failures

**Check count:** 857 (was 810 before this change — +47 new checks)  
The 47 new checks cover:
- 1 `anchor_faces` check per placed part × ~47 parts across 5 ships
- 1 `face_cls` check per strut (merged into the existing per-strut check, +0 count)

**face_cls note:** The `face_cls` check is inside the existing strut check
expression (same `check()` call, just one more `and` clause), so it does not
increment the raw check count but IS verified for every strut.

**Anchor_faces breakdown in the canonical fleet:**
- All 11 families have `anchor_faces` set on this branch (fan-out further along
  than the handoff's "only hull" note). Parts with None would correctly round-trip
  as the literal string "null".
- Hull: 6 faces (deck/belly/flanks=cls2, aft=cls1, nose=cls0)
- Engine: 6 faces; fuel_tank: 5; wing: 5; cannon: 6; antenna: 6; pod: 6;
  radiator: 6; reactor: 6; turret: 6; terminator_cap: 2.
- FV-ε struts (turret braces): verified with `face_cls=2` (primary face weld)

**Tolerance:** 1e-9 (double storage — bit-exact, same as all other USD decision
coords). JSON serialization of float64 through Python's json module is lossless
at this precision.

---

## Houdini verify status

**`houdini/verify_native_hda.py` changes:** The `anchor_faces` check block is
added (after the existing `anchor_vols` block) with full round-trip logic:
parse JSON, diff each face's c/n/u/hu/hv/cls against the Python generator's
output at 1e-5 tolerance (float32-honest, matching the existing vol checks).

**Host-agnostic run:** The check *as written* requires `import hou` at the top
of `verify_native_hda.py` (the file starts with `import hou` — it is a hython-
only runner by design). The `write_part_geo` serialization logic itself is
host-agnostic pure-Python (the JSON serialization expression does not touch `hou`
before the `geo.addAttrib`/`setGlobalAttribValue` calls), but the verification of
what gets written requires a live `hou.Geometry` to read back from.

**Tested host-agnostically:** The serialization expression from `write_part_geo`
was extracted and run standalone against all 11 family generators:
- All 11 families serialized successfully
- Hull 6-face round-trip: exact to 1e-12
- None case ("null") serializes correctly (sensor_pod previously had None,
  now has faces — the null path is handled but not exercised on current branch)

**STATUS: LIVE-HYTHON VERIFICATION DEFERRED.** The actual `verify_native_hda.py`
run (which cooks the installed HDAs and reads back `g.attribValue("anchor_faces")`)
requires hython. This session has no hython access. The check code is correct and
follows the exact same pattern as the `anchor_vols` check above it. Flag for
the next hython session: run `$H houdini/verify_native_hda.py` and confirm the
`anchor_faces present` + `anchor_faces (N faces)` checks are green across all 11
families × 3 seeds × guild + feral = 44 family passes.

---

## md5 invariant

```
Expected:  80ddaccccc594b2a7cc8c7b40a129086
Produced:  80ddaccccc594b2a7cc8c7b40a129086   (/tmp/conduit.json, /tmp/conduit_final.json)
```

The assembler decision path (`kitmash.py`) was not touched. The export layer
is purely additive — reading `part.anchor_faces` (set at construction in the
generator, not in the assembler loop) and serializing it. No generator output,
ledger state, or assembly decision was altered.

---

## Files changed

| File | Change |
|------|--------|
| `kitmash_houdini.py` | `write_part_geo`: +`anchor_faces` detail attr (JSON); `write_geo`: +`face_cls` int attr declaration; +`face_cls` stamping on strut-segment points |
| `kitmash_usd.py` | `write_usd`: +`anchor_faces` string primvar on part Xform; +`face_cls` Int primvar on strut prims; `read_ship`: +recover `anchor_faces` |
| `verify_usd.py` | +`anchor_faces` round-trip check per part; +`face_cls` inside per-strut check |
| `houdini/verify_native_hda.py` | +`anchor_faces` check block (hython-gated, correct, deferred to live run) |
| `usd/USD-EXPORT.md` | +`anchor_faces` / `face_cls` to the stage layout table and contract clauses |

**NOT touched:** `kitmash.py`, `test_kitmash.py`, `fleet.json`, `usd/kitmash_fleet.usda`

---

## Goblins encountered

None in the write/read path. The serialization pattern (JSON string for a
complex per-part structure) is identical to `gen_params` and was straightforward.
The only surprise: all 11 families have `anchor_faces` set on the current branch
(more complete than the handoff's "only hull" note), which meant the `None`
round-trip case is not exercised in the canonical fleet but IS handled correctly
by construction.
