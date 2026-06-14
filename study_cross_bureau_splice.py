"""study_cross_bureau_splice.py — what does a Guild×Feral hybrid actually look like?

The cross-bureau splice (director.py:splice_trace) is wired into evolve() but was
never *studied*. This instrument drives real splices and reads the resulting
traces — no claims, only diagnoses. It answers three questions:

  1. MECHANISM — what does splice_trace actually inherit from each parent?
  2. ASYMMETRY — is Guild×Feral one ship or two? (which parent is "fitter"
     decides faction/bureau/tie_policy; both donate their loudest wants.)
  3. THE LIVE INSTANCE — what does the loop itself breed, unprompted?

Run: ../.venv/bin/python study_cross_bureau_splice.py [out.json]
Emits a forensic report to stdout and (optionally) a JSON record.
"""
import json
import sys

from director import (Director, BUREAU_OBJECTIVES, _tag, _story_sig)


def forensic(rec):
    """The numbers that distinguish one ship's body from another's."""
    d = rec["diagnosis"]
    fam = dict(sorted(d["families"].items()))
    return dict(
        name=rec["name"], faction=rec["brief"]["faction"]["name"],
        bureau=rec["bureau"], tie_policy=rec["brief"]["tie_policy"],
        heavy=rec["brief"]["heavy"], span=rec["brief"]["span"],
        parts=d["parts"], mass=d["mass"], struts=d["struts"],
        strut_per_part=d["strut_per_part"], repairs=d["repairs"],
        adapters=d["adapters"], hoses=d["hoses"], ports_open=d["ports_open"],
        monoculture=d["monoculture"], families=fam,
        fueled=(sum(d["demand_unmet"].values()) == 0), legal=rec["legal"],
        fitness=rec["fitness"])


def fit_under_all(d, diag):
    """Score one diagnosis under every bureau objective — reveals which
    aesthetic the ship's BODY actually satisfies, independent of its label."""
    return {(b or "None"): d.external_fitness(diag, bureau=b)
            for b in (None,) + tuple(BUREAU_OBJECTIVES) if b != None or True}


def wants_union_table(bg, bf):
    fams = sorted(set(bg["wants"]) | set(bf["wants"]))
    rows = []
    for fam in fams:
        wg = bg["wants"].get(fam, 0.0)
        wf = bf["wants"].get(fam, 0.0)
        rows.append((fam, wg, wf, max(wg, wf),
                     "Guild" if wg >= wf else "Feral"))
    return rows


def main():
    d = Director()

    # -- the two parents: each bureau's gen-0 seed, built and reviewed --------
    bg = d._bureau_seed("Guild-Structural")
    bf = d._bureau_seed("Feral-Repair")
    pg = d._build_and_review(bg, 0, 0)
    pf = d._build_and_review(bf, 0, 1)
    fg, ff = pg["fitness"], pf["fitness"]

    print("=" * 72)
    print("PARENTS (each scored under its OWN bureau objective)")
    print("=" * 72)
    for p in (pg, pf):
        f = forensic(p)
        print(f"\n{f['bureau']:18s} [{f['faction']}]  fit={f['fitness']}")
        print(f"  parts={f['parts']} mass={f['mass']} struts={f['struts']} "
              f"spp={f['strut_per_part']} repairs={f['repairs']} "
              f"adapters={f['adapters']} open={f['ports_open']}")
        print(f"  families={f['families']}")
        print(f"  fueled={f['fueled']} legal={f['legal']} "
              f"heavy={f['heavy']} span={f['span']} tie={f['tie_policy']}")

    # -- the splice mechanism, made explicit ---------------------------------
    print("\n" + "=" * 72)
    print("WANTS UNION (splice takes max per family — 'the louder taste')")
    print("=" * 72)
    print(f"  {'family':14s} {'Guild':>7s} {'Feral':>7s} {'child=max':>10s}  louder")
    for fam, wg, wf, mx, who in wants_union_table(bg, bf):
        print(f"  {fam:14s} {wg:7.2f} {wf:7.2f} {mx:10.2f}  {who}")

    # -- the two directions: who is fitter decides identity ------------------
    # natural direction uses the REAL fitnesses; both forced directions show
    # the asymmetry the mechanism guarantees.
    natural = "Guild" if fg >= ff else "Feral"
    print("\n" + "=" * 72)
    print(f"DIRECTION — raw fitnesses: Guild={fg}  Feral={ff}  → "
          f"natural fitter = {natural}")
    print("=" * 72)

    # Guild-fitter child: splice with Guild's fitness forced higher
    child_G = d.splice_trace(bg, bf, fit_a=10.0, fit_b=1.0)   # bg is fitter
    # Feral-fitter child: splice with Feral's fitness forced higher
    child_F = d.splice_trace(bf, bg, fit_a=10.0, fit_b=1.0)   # bf is fitter

    rG = d._build_and_review(child_G, 1, 0)
    rF = d._build_and_review(child_F, 1, 1)

    records = {"parents": {}, "children": {}, "live": {}}
    records["parents"]["Guild-Structural"] = forensic(pg)
    records["parents"]["Feral-Repair"] = forensic(pf)

    for tag, child_brief, rec in (("GUILD-fitter", child_G, rG),
                                  ("FERAL-fitter", child_F, rF)):
        f = forensic(rec)
        print(f"\n--- {tag} hybrid ---------------------------------------")
        print(f"  inherits: faction={f['faction']}  bureau={f['bureau']}  "
              f"tie={f['tie_policy']}  heavy={f['heavy']} span={f['span']}")
        print(f"  seed={child_brief['seed']}  genes={[g.__name__ for g in child_brief['extra_gens']]}")
        print(f"  mutation: {child_brief['mutation']}")
        print(f"  BODY: parts={f['parts']} mass={f['mass']} struts={f['struts']} "
              f"spp={f['strut_per_part']} repairs={f['repairs']} "
              f"adapters={f['adapters']} open={f['ports_open']}")
        print(f"  families={f['families']}  monoculture={f['monoculture']}")
        print(f"  fueled={f['fueled']} legal={f['legal']}")
        scored = fit_under_all(d, rec["diagnosis"])
        print(f"  fitness under each bureau objective:")
        for b, v in scored.items():
            mark = "  <- its label" if b == f["bureau"] else ""
            print(f"      {b:18s} {v:8.4f}{mark}")
        rec_out = forensic(rec)
        rec_out["seed"] = child_brief["seed"]
        rec_out["genes"] = [g.__name__ for g in child_brief["extra_gens"]]
        rec_out["mutation"] = child_brief["mutation"]
        rec_out["fitness_under_each_bureau"] = scored
        records["children"][tag] = rec_out

    # -- the live loop: extract a cross-bureau child evolve() bred itself -----
    print("\n" + "=" * 72)
    print("LIVE INSTANCE — a cross-bureau child the loop bred unprompted")
    print("=" * 72)
    lin = d.evolve(generations=2, population=4, seed=0)
    found = []
    for gr in lin["generations"]:
        for r in gr["ships"]:
            mut = (r["brief"].get("mutation") or "")
            if "cross-bureau" in mut:
                found.append((gr["gen"], r))
    if not found:
        print("  (no cross-bureau child surfaced into a built ship this run;")
        print("   the splice is appended to next_briefs and may be trimmed by")
        print("   round-robin padding before it is built — see _breed.)")
    for gen, r in found:
        f = forensic(r)
        print(f"\n  gen{gen} {f['name']}  parents={r['parents']}")
        print(f"  {f['brief'] if False else ''}mutation: {r['brief']['mutation']}")
        print(f"  faction={f['faction']} bureau={f['bureau']}  parts={f['parts']} "
              f"struts={f['struts']} spp={f['strut_per_part']} repairs={f['repairs']}")
        print(f"  families={f['families']} fueled={f['fueled']} legal={f['legal']} "
              f"fit={f['fitness']}")
        records["live"].setdefault("children", []).append(
            dict(gen=gen, **forensic(r), parents=r["parents"],
                 mutation=r["brief"]["mutation"]))

    # -- generality: every cross-pair, NATURAL direction (real fitnesses) -----
    print("\n" + "=" * 72)
    print("ALL CROSS-PAIRS (natural direction) — is the changeling general?")
    print("=" * 72)
    print("  'self' = child fitness under its INHERITED label; 'other' = under")
    print("  the weaker parent's label. self<other ⇒ body fits the wrong house.")
    bnames = list(BUREAU_OBJECTIVES)
    bnames = [b for b in bnames if b is not None]
    seeds = {b: d._bureau_seed(b) for b in bnames}
    builts = {b: d._build_and_review(seeds[b], 0, i)
              for i, b in enumerate(bnames)}
    print(f"\n  {'cross':34s} {'faction':11s} {'struts':>6s} {'spp':>5s} "
          f"{'rep':>3s} {'hose':>4s} {'self':>7s} {'other':>7s}  tension")
    matrix = []
    for i in range(len(bnames)):
        for j in range(i + 1, len(bnames)):
            ba, bb = bnames[i], bnames[j]
            pa, pb = builts[ba], builts[bb]
            child = d.splice_trace(pa["brief"], pb["brief"],
                                   pa["fitness"], pb["fitness"])
            rc = d._build_and_review(child, 1, 99)
            inherited = rc["bureau"]
            other = bb if inherited == ba else ba
            self_fit = d.external_fitness(rc["diagnosis"], bureau=inherited)
            other_fit = d.external_fitness(rc["diagnosis"], bureau=other)
            dd = rc["diagnosis"]
            tension = "BODY≠LABEL" if other_fit > self_fit + 1e-9 else "aligned"
            label = f"{ba.split('-')[0]}×{bb.split('-')[0]}→{inherited.split('-')[0]}"
            print(f"  {label:34s} {rc['brief']['faction']['name']:11s} "
                  f"{dd['struts']:6d} {dd['strut_per_part']:5.2f} "
                  f"{dd['repairs']:3d} {dd['hoses']:4d} "
                  f"{self_fit:7.3f} {other_fit:7.3f}  {tension}")
            matrix.append(dict(
                cross="%s×%s" % (ba, bb), inherits=inherited,
                faction=rc["brief"]["faction"]["name"],
                struts=dd["struts"], strut_per_part=dd["strut_per_part"],
                repairs=dd["repairs"], hoses=dd["hoses"],
                families=dict(sorted(dd["families"].items())),
                fueled=(sum(dd["demand_unmet"].values()) == 0),
                legal=rc["legal"], self_fit=self_fit, other_fit=other_fit,
                tension=tension))
    records["cross_pair_matrix"] = matrix

    if len(sys.argv) > 1:
        with open(sys.argv[1], "w") as fh:
            json.dump(records, fh, indent=2, default=str)
        print(f"\n[wrote {sys.argv[1]}]")


if __name__ == "__main__":
    main()
