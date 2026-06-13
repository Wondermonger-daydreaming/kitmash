#!/usr/bin/env python3
"""
make_catalogue.py — the Borges catalogue.

Reads fleet.json and writes CATALOGUE.html + CATALOGUE.md: one museum plate
per ship, each with a render (from houdini/plates/, if present) and a placard
grown from the ship's own assembly trace.

The discipline (item 7, from the handoff): *every quantitative claim in a
caption describes a real logged event.* Nothing is invented. A sentence about
a spawned strut is emitted ONLY when the trace holds a `repair` event, and its
numbers (the moment before, the cap, the relief) are read straight from that
event's metrics. To make the grounding checkable, the script prints an audit:
for each ship, how many trace events the prose consumed, and which it left on
the floor.

License-free: pure stdlib, runs on the lab venv. The slow, Houdini-bound half
(the plate renders) is render_plates.py; this just consumes the PNGs.

    .venv/bin/python make_catalogue.py
"""
import html
import json
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
FLEET = os.path.join(HERE, "fleet.json")
PLATES_DIR = os.path.join(HERE, "houdini", "plates")

EPIGRAPH = (
    "Each plate records a craft that was never drawn, only decided — a "
    "sequence of commitments, overloads, and repairs, logged by the assembler "
    "as they happened. Nothing in these captions is invented. Every moment, "
    "every strain, every spawned strut is read back from the machine’s own "
    "ledger."
)

# ship-prim slug for the matching render in houdini/plates/
PRIM_SLUG = {
    "Plate XLVII": "GS_alpha", "Plate XLVIII": "GS_beta",
    "Plate XLIX": "FV_gamma", "Plate L": "FV_delta", "Plate LI": "FV_epsilon",
}


def epithet(name):
    """Pull the «...» epithet out of a ship name; '' if none."""
    m = re.search(r"«(.+?)»", name)
    return m.group(1) if m else ""


def art(part):
    """'a'/'an' for a part word."""
    return "an" if part[:1].lower() in "aeiou" else "a"


def placard(ship):
    """Grow the prose placard from the ship's trace. Returns (sentences,
    consumed_event_indices)."""
    tr = ship.get("trace", [])
    sents = []
    used = set()

    # 1. provenance, from the seed event
    seed_i = next((i for i, e in enumerate(tr) if e.get("ev") == "seed"), None)
    if seed_i is not None:
        e = tr[seed_i]
        used.add(seed_i)
        sents.append(
            "Struck from seed %s in the %s yards, in the %sᵗʰ era."
            % (e["seed"], e.get("faction", ship["faction"]), ship.get("era", "?")))

    # 2. the spine, from the first commit
    commits = [(i, e) for i, e in enumerate(tr) if e.get("ev") == "commit"]
    if commits:
        i0, e0 = commits[0]
        used.add(i0)
        sents.append("Its spine is %s %s." % (art(e0["part"]), e0["part"]))

    # 3. lineage, only if a real parent is logged
    lin = ship.get("lineage") or {}
    if lin.get("parent"):
        mut = lin.get("mutation")
        sents.append("Bred from %s%s." % (
            lin["parent"], " by %s" % mut if mut else ""))

    # 4. repairs — spawned struts under moment overload. Group by the metric
    #    signature (same overload, same relief) so identical struts read as
    #    "twice", and so two joints sharing one overload read as one sentence.
    reps = [(i, e) for i, e in enumerate(tr)
            if e.get("ev") == "repair" and e.get("op") == "spawn_strut"]
    if reps:
        for i, _ in reps:
            used.add(i)
        groups = []  # [(sig, [joints], event)] in first-seen order
        index = {}
        for _, e in reps:
            m = e["metrics"]
            sig = (m.get("moment_before"), m.get("cap"),
                   m.get("moment_after"), m.get("relief"))
            if sig not in index:
                index[sig] = len(groups)
                groups.append([sig, [], e])
            groups[index[sig]][1].append(m.get("joint"))

        first = True
        for sig, joints, e in groups:
            m = e["metrics"]
            target = e.get("target", "the part")
            mb, cap = _num(m["moment_before"]), _num(m["cap"])
            ma, rel = _num(m["moment_after"]), round(m["relief"] * 100)
            distinct = list(dict.fromkeys(joints))
            n = len(joints)
            jtxt = " and ".join("the %s" % j for j in distinct)
            again = "" if first else " again"
            if n == 1:
                sents.append(
                    "When the %s loaded the %s joint%s, its moment rose to %s "
                    "against a cap of %s; a strut was spawned, and the load "
                    "fell to %s — %s."
                    % (target, distinct[0], again, mb, cap, ma, _pct(rel)))
            else:
                sents.append(
                    "%s the %s overran its cap at %s joint%s (%s against %s); "
                    "each time a strut answered, settling the load to %s — "
                    "%s."
                    % (_times(n).capitalize(), target, jtxt,
                       "s" if len(distinct) > 1 else "", mb, cap, ma, _pct(rel)))
            first = False

    # 5. adapters — a collar spawned to seat a strained part
    for i, e in enumerate(tr):
        if e.get("ev") == "adapter" and e.get("result") == "collar_spawned":
            used.add(i)
            strain = e.get("metrics", {}).get("strain")
            sents.append(
                "The %s refused a clean seat (strain %.3f); a collar was "
                "spawned to seat it." % (e.get("part", "part"), strain))

    # 6. fuel routing, from the hose event
    for i, e in enumerate(tr):
        if e.get("ev") == "hose":
            used.add(i)
            m = e.get("metrics", {})
            leaps = m.get("leaps", 0)
            hops = m.get("hops", 0)
            extra = (" across %d leap%s" % (leaps, "s" if leaps != 1 else "")) \
                if leaps else ""
            sents.append("Fuel runs from the %s to the %s in %d hop%s%s."
                         % (e.get("frm"), e.get("to"), hops,
                            "" if hops == 1 else "s", extra))

    # 7. the closing tally, from stats (descriptive, not from trace indices)
    s = ship.get("stats", {})
    sents.append(
        "In the end: %d parts, %s units of mass, %d spawned strut%s, %d hose run%s."
        % (s.get("parts", 0), _num(s.get("mass", 0)),
           s.get("struts", 0), "" if s.get("struts") == 1 else "s",
           s.get("hoses", 0), "" if s.get("hoses") == 1 else "s"))

    return sents, used


def _num(n):
    return "{:,}".format(int(n))


def _times(n):
    return {1: "once", 2: "twice", 3: "three times", 4: "four times"}.get(
        n, "%d times" % n)


def _pct(n):
    """'an 85% relief' / 'a 61% relief' — article by spoken first sound."""
    article = "an" if (n == 8 or n == 11 or n == 18 or 80 <= n <= 89) else "a"
    return "%s %d%% relief" % (article, n)


# ---------------------------------------------------------------- renderers

def render_md(fleet):
    out = ["# KITMASH PLATES",
           "",
           "*A registry of ships assembled by a machine that kept its reasons.*",
           "",
           "> " + EPIGRAPH,
           "",
           "*after Borges, who catalogued the animals that belong to the Emperor.*",
           "", "---", ""]
    for ship in fleet["ships"]:
        plate = ship["plate"]
        ep = epithet(ship["name"])
        slug = PRIM_SLUG.get(plate)
        img = "houdini/plates/%s.png" % slug if slug else None
        out.append("## %s — %s" % (plate.upper(), html.unescape(ship["name"])))
        out.append("")
        out.append("*%s · era %s%s*" % (
            ship["faction"], ship.get("era", "?"),
            " · “%s”" % ep if ep else ""))
        out.append("")
        if img and os.path.exists(os.path.join(HERE, img)):
            out.append("![%s](%s)" % (plate, img))
            out.append("")
        sents, _ = placard(ship)
        out.append(" ".join(sents))
        out.append("")
        out.append("---")
        out.append("")
    return "\n".join(out)


def render_html(fleet):
    css = """
    body{background:#f4efe3;color:#2b2620;font-family:'Iowan Old Style',
      'Palatino Linotype',Palatino,Georgia,serif;line-height:1.5;
      max-width:760px;margin:0 auto;padding:48px 24px}
    h1{font-size:2.2rem;letter-spacing:.08em;margin:0 0 .2em;font-weight:600}
    .sub{font-style:italic;color:#6b6155;margin-bottom:1.6em}
    .epigraph{border-left:3px solid #c9bda3;padding:.4em 1.2em;margin:1.6em 0;
      color:#534a3d;font-size:.98rem}
    .after{font-style:italic;color:#8a8071;font-size:.9rem;margin-bottom:2.4em}
    .plate{border-top:1px solid #d8cdb6;padding:2.2em 0}
    .pnum{font-variant:small-caps;letter-spacing:.12em;color:#9a7b3f;
      font-size:.95rem}
    .pname{font-size:1.5rem;margin:.1em 0 .15em}
    .meta{font-style:italic;color:#6b6155;margin-bottom:1em;font-size:.95rem}
    .plate img{width:100%;border:1px solid #d8cdb6;background:#fff;
      border-radius:2px;margin:.4em 0 1em}
    .placard{font-size:1.05rem}
    footer{margin-top:3em;color:#8a8071;font-style:italic;font-size:.85rem;
      border-top:1px solid #d8cdb6;padding-top:1.2em}
    """
    parts = ["<!doctype html><html><head><meta charset='utf-8'>",
             "<title>KitMash Plates</title><style>%s</style></head><body>" % css,
             "<h1>KitMash Plates</h1>",
             "<div class='sub'>A registry of ships assembled by a machine "
             "that kept its reasons.</div>",
             "<div class='epigraph'>%s</div>" % html.escape(EPIGRAPH),
             "<div class='after'>after Borges, who catalogued the animals "
             "that belong to the Emperor.</div>"]
    for ship in fleet["ships"]:
        plate = ship["plate"]
        ep = epithet(ship["name"])
        slug = PRIM_SLUG.get(plate)
        img = "houdini/plates/%s.png" % slug if slug else None
        sents, _ = placard(ship)
        parts.append("<div class='plate'>")
        parts.append("<div class='pnum'>%s</div>" % html.escape(plate))
        parts.append("<div class='pname'>%s</div>"
                     % html.escape(html.unescape(ship["name"])))
        parts.append("<div class='meta'>%s &middot; era %s%s</div>" % (
            html.escape(ship["faction"]), ship.get("era", "?"),
            " &middot; &ldquo;%s&rdquo;" % html.escape(ep) if ep else ""))
        if img and os.path.exists(os.path.join(HERE, img)):
            parts.append("<img src='%s' alt='%s'>" % (img, html.escape(plate)))
        parts.append("<div class='placard'>%s</div>"
                     % html.escape(" ".join(sents)))
        parts.append("</div>")
    parts.append("<footer>Every claim above is read back from the assembler’s "
                 "ledger (fleet.json). No event was invented; "
                 "see make_catalogue.py for the archaeology.</footer>")
    parts.append("</body></html>")
    return "\n".join(parts)


def audit(fleet):
    print("=== caption archaeology audit ===")
    print("(every numeric claim must trace to a logged event; "
          "unused events are fine, invented ones are not)")
    for ship in fleet["ships"]:
        tr = ship.get("trace", [])
        sents, used = placard(ship)
        kinds = Counter(e.get("ev") for e in tr)
        unused = [tr[i].get("ev") for i in range(len(tr)) if i not in used]
        # commits beyond the spine are intentionally summarised in the tally,
        # not narrated one by one — report them so the gap is visible, not hidden
        print("  %-12s %-22s %2d sentences | %2d/%2d trace events consumed"
              % (ship["plate"], epithet(ship["name"]),
                 len(sents), len(used), len(tr)))
        narrated_commits = 1 if kinds.get("commit") else 0
        if kinds.get("commit", 0) > narrated_commits:
            print("       (%d further 'commit' events folded into the part tally, "
                  "not narrated)" % (kinds["commit"] - narrated_commits))


def main():
    fleet = json.load(open(FLEET))
    audit(fleet)
    md = render_md(fleet)
    htmlpage = render_html(fleet)
    with open(os.path.join(HERE, "CATALOGUE.md"), "w") as f:
        f.write(md)
    with open(os.path.join(HERE, "CATALOGUE.html"), "w") as f:
        f.write(htmlpage)
    print("\nwrote CATALOGUE.md and CATALOGUE.html (%d plates)"
          % len(fleet["ships"]))


if __name__ == "__main__":
    main()
