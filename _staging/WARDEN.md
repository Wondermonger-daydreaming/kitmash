# WARDEN — anchor_faces silent-skip ended

**Scope:** edited ONLY `houdini/verify_native_hda.py`. No other file touched.
The body: `verify_native_hda.py:188-217` guarded the anchor_faces check with
`if g.findGlobalAttrib("anchor_faces") is not None:`. Native baked part HDAs
never write the attr, so the block was silently skipped on all 11 families ×
4 passes (44 cooks) — green that never asserted. The gate decorated instead
of selected (v0.7-lesson-4 failure).

---

## Diff summary (file:line)

### Task 1 — replace silent-skip block with a LOUD always-run assertion
- **Removed:** `houdini/verify_native_hda.py:188-217` — the
  `if g.findGlobalAttrib("anchor_faces") is not None:` guarded block
  (anchor_faces present / null / per-face round-trip), which never executed.
- **Added (same location):** an unconditional `check(...)` codifying the
  doctrine (ARCHITECTURE.md inv 7 & 8): the native body HDA must carry NO
  baked anchor_faces; provenance rides the rehydrator + USD primvars.

  ```python
  check(f"{tag} native carries no baked anchor_faces (rides rehydrator+USD)",
        g.findGlobalAttrib("anchor_faces") is None,
        "native HDA baked anchor_faces — violates ARCHITECTURE.md inv 7&8; ...")
  ```
  Same `check(name, ok, detail)` call style and `tag` interpolation as the
  rest of the file. The 3rd arg (failure detail) only prints on FAIL, per
  `check()`'s own contract. If a future native HDA ever bakes anchor_faces,
  this FAILS loudly and forces a doctrine decision — the skip can never recur.

### Task 2 — one-line comment on the anchor_vols stub-vs-None match (behaviour unchanged)
- **`houdini/verify_native_hda.py`**, the `if g.findGlobalAttrib("anchor_vols")
  is not None:` block (~line 185): added a comment noting the pass is a
  STUB-vs-None coincidence — canonical parts have `anchor_vols=None` and the
  HDA's static `setdetailattrib(0,"anchor_vols","null")` stub deserialises to
  None — NOT a live volume round-trip. The `check(...)` call itself is
  unchanged (out of scope).

### Task 3 — printed pointer line (once per run) in main()
- **`houdini/verify_native_hda.py`**, in `main()` just before the final
  `NATIVE ROUND TRIP PROVEN` print: added one `print(...)` stating where
  faces ARE proven:
  ```
  anchor_faces/face_cls proven on the USD rung (verify_usd.py, 47 primvars)
  and the rehydrator rung (test_headless gate5).
  ```

---

## Traces

### New assertion ACTUALLY RAN (the whole point)
```
$ grep -c "native carries no baked anchor_faces" /tmp/warden_hython.log
44
```
44 >= 11 (11 families × 3 GUILD seeds + 1 FERAL pass = 44). First lines:
```
16:  ok   antenna[seed=0,H] native carries no baked anchor_faces (rides rehydrator+USD)
32:  ok   antenna[seed=7,H] native carries no baked anchor_faces (rides rehydrator+USD)
48:  ok   antenna[seed=41,H] native carries no baked anchor_faces (rides rehydrator+USD)
```
FAIL count in log: `grep -c "FAIL" /tmp/warden_hython.log` → `0`.

### hython tail (exit 0, ends PROVEN, pointer line present)
```
  ok   wing[seed=0,F] anchor_vols
  ok   wing[seed=0,F] native carries no baked anchor_faces (rides rehydrator+USD)
  ok   wing[seed=0,F] body group non-empty
  ok   wing[seed=0,F] body bbox

anchor_faces/face_cls proven on the USD rung (verify_usd.py, 47 primvars) and the rehydrator rung (test_headless gate5).
NATIVE ROUND TRIP PROVEN for: antenna, core_hull, engine, fuel_tank, heavy_cannon, radiator, reactor, sensor_pod, terminator_cap, turret, wing
```
Command: `hython houdini/verify_native_hda.py` → `EXIT=0`.

### Fleet anchor md5 unchanged
```
$ ../.venv/bin/python kitmash.py /tmp/warden.json && md5sum /tmp/warden.json
80ddaccccc594b2a7cc8c7b40a129086  /tmp/warden.json
```
Matches canonical `80ddaccccc594b2a7cc8c7b40a129086`. fleet.json untouched.

---

## What I did NOT do
- Did NOT edit any file other than `houdini/verify_native_hda.py`.
- Did NOT change the anchor_vols `check(...)` behaviour — comment only.
- Did NOT touch fleet.json (md5 verified unchanged).
- Did NOT edit CLAUDE.md or MEMORY.md.
- Did NOT commit anything (no `git add`/`git commit`).
- Did NOT modify the part-HDA generators (`houdini/make_*_hda.py`), the
  rehydrator (`kitmash_houdini.py`), the USD path (`verify_usd.py`), or any
  other rung of the ladder — the doctrine deliberately keeps anchor provenance
  off the static native body HDA, so no generator change was warranted.
