# KitMash

A deterministic, provenance-traced spaceship kitbash assembler. Ports are
points; legality is dumb (~7 checks that never grow); taste lives in the
sampler and the director, never in the legality grammar. Meshes are cached
opinion — the recipe and the ledger are truth. Given a brief (faction, seed,
wants, budgets), `kitmash.py` assembles a coherent ship and emits a complete
trace: every commit, reject-with-reason, strut, adapter, auction, and hose is a
logged event you can replay (identical ship) or perturb (counterfactual
sibling). The same JSON drives a self-contained three.js viewer, a USD export
with `primvars:kitmash:*` provenance, and a Houdini rehydrator that instances
artist-grade part HDAs from the recorded decisions.

## Status

Verified against `KITMASH-HANDOFF.md`, the per-version sections, the test
gates, and `git log` (2026-06-13).

| Component | Status | Notes |
|-----------|--------|-------|
| Core assembler (`kitmash.py`) | **done** | Pure Python, numpy only, host-agnostic. Mate / spine / auction / backjump / routing-v2 / loom all implemented. Byte-exact regression anchor (md5 `e6aeccfe352bba16f288785ea23e5bc3`). |
| Houdini native HDAs | **done** | 11/11 families migrated to native SOP/VEX interiors (v0.12). The generalized gate `houdini/verify_native_hda.py` is 784/784 green across all families. The Python-SOP wrappers in `houdini/hda/` remain as fallback; consumers install native-last. |
| USD bridge (`kitmash_usd.py`) | **done** | `primvars:kitmash:*` schema, round-trip proven in both `usd-core` (license-free) and Houdini's `pxr`. `verify_usd.py` passes. |
| Agent-loop director (`director.py`) | **done** | Creative-director loop (roadmap item 6): brief authoring, tie-only hooks, `review(trace) -> next_brief`, breeding, scarcity shocks, Goodhart firewall. No per-port LLM calls. |
| Catalogue | **done** | `make_catalogue.py` (fleet) and `make_evolved_catalogue.py` (bred fleet) emit trace-grounded captions + plates (Borges catalogue, roadmap item 7). |
| Tests | **done** | `test_kitmash.py` = **9 gates**, all green. `test_director.py` = **7 gates**, all green. |

## Dependency tiers

KitMash is layered so the public CI surface needs no DCC license:

- **Pure-Python core** — `kitmash.py`, `director.py` and their tests need only
  **numpy**. Runs anywhere Python runs.
- **USD bridge** — `kitmash_usd.py` and `verify_usd.py` need **`usd-core`**
  (the `pxr` module: `pip install usd-core`). It is license-free and needs no
  Houdini install. This cleanly separates **public CI** (pure-Python + usd-core,
  runnable in any container) from **local DCC verification**.
- **Houdini gates** — the native-HDA and rehydrator gates
  (`houdini/verify_native_hda.py`, `houdini/test_headless.py`) need **`hython`**
  (a Houdini install). These are local-only and skipped in public CI.

## Roadmap

Done:

- [x] Engine-room hardening (uncommit, transactional eviction) — v0.4
- [x] Auction + conflict-directed backjumping — v0.5
- [x] Routing v2 (channels, congestion, segregation, the loom) — v0.6
- [x] Houdini port (Python SOP + 11 part HDAs + headless rehydrator), live-verified under hython — v0.7
- [x] Anchorable surface semantics (AABB volumes) — v0.8
- [x] USD export (`primvars:kitmash:*`, dual round-trip) — v0.9
- [x] Native HDA interiors, 11/11 families — v0.12
- [x] Agent-loop director (creative director, brief/hooks/review) — v0.13
- [x] Borges catalogue (plates + trace-grounded captions) — v0.11 / v0.13

Open (honestly unticked):

- [ ] **Face-level anchorable surfaces.** Today only AABB anchor *volumes*
      exist — a strut welds anywhere inside a declared box, with no
      surface-normal semantics. Face tags / surface normals are the refinement.
- [ ] **USD as referenced assets.** The current export carries a cartoon `/geo`
      Mesh; the next step is `references` / `payload` to per-family part-asset
      USDs (the USD twin of the part HDAs).
- [ ] Higher-density routing follow-ups: bipartite demand matching, negotiation
      rounds, geometric min-distance for segregated parallel runs, per-ctype
      hose styling in the viewer.

(Other deliberate cheats are catalogued in `KITMASH-HANDOFF.md` §"Current state
& known cheats".)

## Quickstart

The core needs only **numpy**; the USD gate also needs **usd-core**
(`pip install numpy usd-core`). Use any Python that has them — the examples
below use `python3`; set `PY=/path/to/python` to point the gate ladder at a
specific interpreter.

```sh
# build a fleet → JSON (the byte-exact reference fleet)
python3 kitmash.py fleet.json

# run the assembler gates (9 gates)
python3 test_kitmash.py

# run the director gates (7 gates)
python3 test_director.py

# run the whole public gate ladder (core + director + usd) with a summary
./run_all_gates.sh                 # or:  PY=.venv/bin/python ./run_all_gates.sh
```

`run_all_gates.sh` has named rungs (`check-core`, `check-director`, `check-usd`,
`check-houdini`, `catalogue`); with no argument it runs the three public rungs.
See `ARCHITECTURE.md` for the 12 invariants, `ARTIFACTS.md` for the artifact
policy, and `CROSS-BUREAU-SPLICE-STUDY.md` for a forensic study of how the
bureaus breed hybrids (the changeling cross).
