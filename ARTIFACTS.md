# Artifact policy

KitMash carries several kinds of file. The project's whole metaphysics is "the
recipe is truth, the mesh is cached opinion" (`ARCHITECTURE.md` §7), so the
repository must be explicit about which artifacts are *authored* and which are
*regenerated*. This document declares a policy per type. It recommends; it does
not reorganize anything.

## Source-of-truth (committed, hand- or spec-authored)

These are written by a human or by a spec and are the upstream from which
everything else derives. They must be reviewed on change.

- **Engine source** — `kitmash.py`, `director.py`, `kitmash_usd.py`,
  `kitmash_houdini.py`, the test suites, the HDA builders
  (`houdini/make_*_hda.py`, `houdini/make_ship_hip.py`).
- **Native HDAs** — `houdini/*.hda` and `houdini/hda/*.hda`. These are bodies,
  but they are *gated against the Python generator* (`verify_native_hda.py`):
  the ports/grommets are the contract, byte-checked. Treat as source-of-truth,
  large-binary subtype (see below).
- **Specs and docs** — `KITMASH-HANDOFF.md`, `AGENT-LOOP-SPEC.md`,
  `ARCHITECTURE.md`, `README.md`, `houdini/NATIVE-MIGRATION.md`,
  `houdini/*.md`, `usd/USD-EXPORT.md`. These define the contract.

## Generated proof (reproducible from source by the gate ladder)

These are *outputs* — committed so a reader can inspect the current fleet
without running anything, but always regenerable. If one drifts from its
generator, the generator wins. Do not hand-edit.

- `fleet.json` ← `kitmash.py fleet.json`
- `evolved_fleet.json` ← `make_evolved_catalogue.py`
- `CATALOGUE.md` / `CATALOGUE.html` ← `make_catalogue.py`
- `EVOLVED-CATALOGUE.md` ← `make_evolved_catalogue.py`
- `kitmash-fleet.html` (the three.js viewer) ← `make_viewer.py fleet.json`
- `usd/kitmash_fleet.usda` ← `make_fleet_usd.py`
- the `*.png.cam.usda` camera sidecars ← the render scripts

Recommended policy: regenerate these in a release step (or via
`./run_all_gates.sh` plus the catalogue rung) rather than editing by hand, and
verify the byte-exact anchor (`fleet.json` md5 `80ddaccccc594b2a7cc8c7b40a129086`,
re-baselined from `e6aeccfe…` by the P3 hull weld-faces) after any engine change.

## Large binaries / LFS candidates

Heavy or binary files that bloat git history. Recommend tracking via Git LFS (or
keeping out of the main repo and shipping only in releases):

- `*.hip` — `houdini/kitmash_ship.hip` (Houdini scene, binary).
- `*.hda` — the part HDAs (binary digital assets; source-of-truth but heavy).
- `*.png` — render plates: `houdini/plates/*.png`, `houdini/kitmash_ship.png`,
  `houdini/kitmash_fleet_render.png`.

## Release-only

Heavy renders that prove a result but do not need to live in day-to-day history.
Recommend attaching to a tagged release rather than committing to `main`:

- High-resolution specimen renders / the Borges catalogue plate set.
- Any future video turntables.

---

**Rule of thumb:** if a file can be reproduced by `./run_all_gates.sh` or a
named generator, it is *generated proof* — keep it for convenience, trust the
generator over it. If it can only be produced by hand or by a heavy DCC render,
it is *source-of-truth* or a *large binary* — review it on change and consider
LFS.
