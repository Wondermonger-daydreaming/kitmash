# KitMash

**A port-based procedural kitbash assembler.** A format plus an algorithm
family for generating endless, coherent, *provenance-rich* assemblies —
spaceships in the reference slice, but the schema is kingdom-agnostic.

> **Thesis:** infinite generation is easy; infinite *provenance* is the art.
> The mesh is a cached opinion; the JSON is the truth.

![KitMash fleet viewer](https://img.shields.io/badge/deps-numpy_only-blue)
![tests](https://img.shields.io/badge/gates-6%2F6_passing-brightgreen)

## What it does

`kitmash.py` (~800 lines, numpy only, host-agnostic) grows assemblies by
mating typed, gendered, size-banded **ports** under a transactional
`propose → reserve → validate → commit` loop. Failures are never silent —
they become *form*, with a recorded reason:

| Failure | Mediation |
|---|---|
| Size strain | gasket / adapter collar |
| Bending moment over joint capacity | strut (relief measured by brace geometry) |
| Two parts want the same emptiness | **auction** — bid = prio × score × scarcity |
| Every candidate dies on the same blocker | **conflict-directed backjump** (bounded, traced) |
| Channel out of capacity, no alternative | **rip-up-and-reroute** — the squatter is evicted and reroutes |
| Fuel and high-voltage in one channel | never — the segregation matrix prunes it at graph build |
| Unmet fuel demand | a cold, scavenged engine — not an error |
| Unfilled port | blanking cap (guild) or left open, taped (feral) |

Hoses route over a **channel graph** with real capacity reservation, and a
channel already carrying a compatible hose costs 0.55× for the next one —
the **loom discount**: harnesses emerge from economics, not authoring.

Every decision appends to an `assembly_trace`. Replay the trace and you get
the identical ship; perturb it and you get a counterfactual sibling.
Factions are parameter cultures: the High Guild builds with safety factor
2.0 and zero debt tolerance; the Feral fleet flies at 1.1 with 5% overdraft
and visible tape.

## Quickstart

```bash
pip install numpy
python3 kitmash.py fleet.json        # generate the five-ship fleet
python3 make_viewer.py fleet.json    # rebuild the self-contained viewer
python3 test_kitmash.py              # run the six verification gates
```

Then open `kitmash-fleet.html` — drag to orbit, click a plate, and watch
the trace ticker replay every commit, strut, auction, and rejection that
shaped the hull.

## The fleet

| Ship | Faction | Story told by the trace |
|---|---|---|
| GS-α «Lawful Mean» | High Guild | the baseline: 3 struts, one adapter collar |
| GS-β «Heavier Daughter» | High Guild | α's mutant child — heavier cannons starve her sensors at 99.7% of mass budget |
| FV-γ «Tape Holds» | Feral | safety factor 1.1, debt tolerated, ports left open |
| FV-δ «Cold Shoulder» | Feral | carries a clearance-hogging radiator that loses four auctions, honestly |
| FV-ε «Loom» | Feral | electrified: a reactor feeds two turrets; the second feed rides the first one's channel because the loom made it cheapest, and neither may touch the fuel trunk |

## Doctrine (the part that matters)

1. **Legality stays dumb; taste lives in the sampler.** ~7 legality checks,
   ever. "Ships look wrong" bugs are fixed by reweighting the scorer.
2. **Mediate failures visibly, don't reject silently.**
3. **Trace everything.** The trace is the assembly's genome.
4. **Propose → reserve → validate → commit.** Geometry is never instanced
   before the reservation ledger clears — which is what makes placement
   *reversible* (auctions can evict; backjumps can undo).
5. **The artist pre-authors knowledge where knowledge lives.** Routing
   graphs live inside parts; the router only stitches the gaps.

The full schema (ports, grommets, capacity tables, segregation matrix),
algorithms (cluster fingerprints, symmetry-snapped mating, tree-fold spine
solver, A* hose routing), hard-won lessons, and roadmap live in
[KITMASH-HANDOFF.md](KITMASH-HANDOFF.md) — the project's living ledger.

## Roadmap

- [x] v0.4 — engine-room hardening (transactional placement, true tree-fold
      spine, measured strut relief) — driven by convergent cross-model review
- [x] v0.5 — clearance auctions + conflict-directed backjumping
- [x] v0.6 — Routing v2: channel capacity reservation, congestion rip-up,
      segregation enforcement, the loom discount
- [ ] Anchorable-surface semantics for struts
- [ ] USD export (`kitmash:` namespaced primvars)
- [ ] Houdini HDA generators — the original host, arriving late, by design
- [ ] Agent loop — brief author / tie-break hooks / trace review
- [ ] The Borges catalogue

## Provenance

Designed conversationally and built across sessions in June 2026 — a
human–AI collaboration in which the human stress-tests each design by
finding the places it quietly lies about being finished, and external AI
reviewers supplied convergent critiques (that's how the v0.4 spine fix
happened). The development history, including two diary entries from the
build days, lives in the authors' lab archive.

## License

MIT — see [LICENSE](LICENSE).
