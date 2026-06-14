# CASSANDRA — Hython-Rung Hardening Sign-off (post-P3, v0.8.1)

**Mandate:** read-only adversary. Reproduce every claim at the CLI; trust nothing.
**Verdict scope:** the silent-skip-killing session (WARDEN / PLUMB / orchestrator / SCRIBE).
**Host:** `/opt/hfs21.0.729/bin/hython`, `../.venv/bin/python` (numpy + usd-core).

---

## Headline

**No blocking findings. The gates SELECT; they do not decorate.** Every count in the
handoff docs re-derived live and matched. The two silent-skips are genuinely closed:
the anchor_faces block is now a loud always-run assertion, and the `run_all_gates.sh`
houdini rung actually executes (`using /opt/hfs21.0.729/bin/hython`) instead of
`command -v`-skipping. Fleet anchor md5 holds; collateral is clean. One **WEAK**
(cosmetic, pre-existing) doc contradiction noted below — not a regression, not a blocker.

---

## C1 — Do the hardened gates SELECT, not decorate?  **HOLDS**

### WARDEN (verify_native_hda.py:204-208)
Prior behavior (git diff HEAD) confirmed: the whole anchor_faces block was wrapped in
`if g.findGlobalAttrib("anchor_faces") is not None:` with the comment
`LIVE-HYTHON VERIFICATION: deferred`. Native HDAs bake no anchor_faces, so the guard
was always False → **the block never executed on any family**. Claim 1 TRUE.

The replacement is an unconditional `check(...)` asserting
`g.findGlobalAttrib("anchor_faces") is None`. Adversarial reasoning: if a future native
HDA *did* bake anchor_faces, `findGlobalAttrib` returns a non-None attrib → predicate
False → `check` appends to `FAIL` → `main()` prints `NATIVE ROUND TRIP FAILED` and
`sys.exit(1)`. This is a real selection, inverted-sense: it fails loudly on the exact
condition it claims to forbid. The doctrine (ARCHITECTURE.md inv 7&8: native = body+ports;
faces ride rehydrator+USD) is internally consistent and the USD/rehydrator rungs that DO
prove faces are cited in `main()`'s success print.

Live run: `ok wing[seed=0,F] native carries no baked anchor_faces (rides rehydrator+USD)`
appears — the assertion **runs**, it is not skipped.

### PLUMB (test_headless.py gate5b_face_export)
Two teeth, both verified to be capable of failing on a wrong expected value:
- **face_cls path:** `assert int(got) == exp_fc` per strut endpoint point, where
  `exp_fc` comes from the strut record. A mismatched face_cls fails per-point.
  Crucially `assert saw_real_face` (≥1 strut with `face_cls >= 0`) — if faces stopped
  selecting (all -1), this fails. Proves SELECT, not mere existence.
- **anchor_faces path:** builds `km.gen_hull(GUILD)` (verified live: 6 faces),
  `write_part_geo`, parses the JSON, asserts field-by-field (`c/n/u` at 1e-5, `hu/hv`
  at 1e-5, `cls` int-exact). A wrong expected value on any field fails.
- **None case (b'):** clears the field and asserts `json.loads(none_str) is None`.

Source line references in the docstrings checked against the codebase:
`kitmash_houdini.py:424-425` (face_cls setAttribValue) ✓; `:283-284` (anchor_faces
json.dumps None branch) ✓. Accurate.

---

## C2 — Counts honest?  **HOLDS** (one WEAK doc note)

Every figure in claim 5 re-derived live (no trust):

| Figure (doc claim) | Live re-derivation | Match |
|---|---|---|
| verify_usd 857 checks | `grep -cE '^  (ok\|FAIL) '` on `verify_usd.py` → **857**, 0 FAIL, exit 0 | ✓ |
| verify_usd 47 face primvars | `grep -ci face` → **47** | ✓ |
| verify_native_hda 828 checks | hython run → **828**, 0 FAIL, exit 0 | ✓ |
| verify_native_hda 44 face-absence | `grep -c 'native carries no baked anchor_faces'` → **44** (11 fam × 4 calls: 3 GUILD seeds + 1 FERAL) | ✓ |
| test_headless 9/9 | hython → `9/9 gates passed`, exit 0, gate5b present | ✓ |
| test_kitmash 11 gates | `grep -c '^PASS '` → **11** | ✓ |
| test_director 7 gates | `grep -c '^PASS '` → **7** | ✓ |

**test_kitmash unmodified this session:** `git diff --stat HEAD -- test_kitmash.py` is
EMPTY. So "11 gates" is the true live count and "docs previously said 10" is a genuine
*pre-existing undercount* — not a change SCRIBE made to inflate. Claim 5 honest.

**WEAK (cosmetic, pre-existing — NOT a blocker):** `KITMASH-HANDOFF.md:662` still reads
`test_kitmash.py now 10 gates` (verified NOT in this session's diff → stale line SCRIBE
left untouched). RELAY.md and the new HANDOFF additions correctly say 11, so the doc now
internally contradicts itself (662 says 10; 705-region implies 11). Provenance is clean
(no lie was introduced); the stale figure simply wasn't swept. Recommend a one-word fix
in a follow-up, but it does not gate the commit.

---

## C3 — Portability not broken.  **HOLDS**

`run_all_gates.sh` rung_houdini now:
```
HYTHON="$(command -v hython 2>/dev/null || ls /opt/hfs*/bin/hython 2>/dev/null | sort -V | tail -1)"
if [ -n "$HYTHON" ] && [ -x "$HYTHON" ]; then ... else SKIP; return 0; fi
```
Simulated a Houdini-less host (forced both branches to miss):
`HYTHON=[]` → `[ -n "" ]` False → SKIP branch → `return 0`. **Public CI does not break.**
The `-x` guard additionally protects against a matched-but-non-executable path. Sound.

---

## C4 — Anchor + no collateral.  **HOLDS**

- `../.venv/bin/python kitmash.py /tmp/cass2.json` → exit 0;
  `md5sum` = **`80ddaccccc594b2a7cc8c7b40a129086`** — matches canonical fleet anchor.
- `git diff --stat HEAD` shows EXACTLY: `KITMASH-HANDOFF.md`, `RELAY.md`,
  `houdini/test_headless.py`, `houdini/verify_native_hda.py`, `run_all_gates.sh`.
  No other tracked file modified. New untracked: `_staging/PLUMB.md`, `_staging/WARDEN.md`,
  `_staging/hython-signoff-p3.md` (+ this file). No collateral.
- `git diff --check HEAD` → exit 0; **no conflict markers**.

---

## C5 — Full ladder green WITH hython rungs executing.  **HOLDS**

`./run_all_gates.sh all` → **exit 0**, final banner `GATE LADDER: ALL GREEN`.
check-houdini rung evidence in the log (proving it RAN, not SKIPped):
- L896 `using /opt/hfs21.0.729/bin/hython`
- L1749 `NATIVE ROUND TRIP PROVEN for: antenna, core_hull, engine, ... wing`
- L1764 `9/9 gates passed`

Zero `SKIP` lines in the run. The decorate-instead-of-select bug the session set out
to kill is verifiably dead in this host's run.

---

## Triage

| Charge | Verdict |
|---|---|
| C1 gates select not decorate | **HOLDS** |
| C2 counts honest | **HOLDS** (+ WEAK stale doc line, pre-existing) |
| C3 portability | **HOLDS** |
| C4 anchor + no collateral | **HOLDS** |
| C5 full ladder green w/ hython | **HOLDS** |

**CONFIRMED BLOCKING FINDINGS: none.** Cleared to commit. Optional follow-up: sweep the
pre-existing stale `KITMASH-HANDOFF.md:662` "10 gates" → "11 gates" for internal
consistency.

— CASSANDRA
