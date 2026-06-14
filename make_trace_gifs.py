#!/usr/bin/env python3
"""make_trace_gifs.py — render forensic GIFs of KitMash assembly traces.

STANDALONE. Not a gate. Not wired into run_all_gates.sh. Pillow is *only*
required to run this; it is never a ladder dependency.

    ../.venv/bin/python make_trace_gifs.py

Reads fleet.json and renders into media/:
  assembly.gif   GS-α assembling part-by-part in commit order (true geometry).
  face_weld.gif  FV-ε moment-relieving strut welding (real moment/relief).
  auction.gif    FV-δ auction firing (real challenger/incumbent/scarcity).
  collar.gif     GS-α retrofit adapter collar spawning (real strain).

The iron rule (Inv 11): every caption number is read FROM the trace. A frame
that claims an event shows the geometry that event drives. No number is
invented; if you grep a caption number it lives in fleet.json.
"""

import json
import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FLEET = os.path.join(HERE, "fleet.json")
MEDIA = os.path.join(HERE, "media")

W, H = 720, 720
BG = (18, 20, 26)
CAP_BG = (12, 13, 17)
CAP_FG = (222, 226, 234)
CAP_DIM = (140, 148, 162)
ACCENT = (127, 209, 227)   # cyan, the "live event" highlight
WARN = (232, 163, 61)      # amber, struts / repairs
CAP_LINES = 4              # caption band height in text lines
LIGHT = np.array([0.4, 0.7, 0.6])
LIGHT = LIGHT / np.linalg.norm(LIGHT)


# ---------------------------------------------------------------- fonts
def _load_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


F_BODY = _load_font(17)
F_BOLD = _load_font(18, bold=True)
F_SMALL = _load_font(14)
LINE_H = 22
CAP_H = CAP_LINES * LINE_H + 16


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def shade(rgb, factor):
    factor = max(0.30, min(1.18, factor))
    return tuple(int(max(0, min(255, c * factor))) for c in rgb)


# ---------------------------------------------------------------- camera
class Camera:
    """Fixed isometric-ish camera with optional yaw orbit. Recentred on the
    ship centroid; scaled to fit the whole ship in the render frame."""

    def __init__(self, all_verts, yaw=0.0):
        self.center = all_verts.mean(axis=0)
        self.yaw = yaw
        # pitch fixed; gives a clean 3/4 isometric read
        self.pitch = math.radians(26.0)
        # fit scale from the rotated bbox extent
        pts = self._world_to_view(all_verts)
        ext_x = pts[:, 0].max() - pts[:, 0].min()
        ext_y = pts[:, 1].max() - pts[:, 1].min()
        avail_w = W * 0.80
        avail_h = (H - CAP_H) * 0.80
        self.scale = min(avail_w / max(ext_x, 1e-6),
                         avail_h / max(ext_y, 1e-6))
        self.cx = W / 2
        self.cy = (H - CAP_H) / 2

    def _rot(self):
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
        Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
        return Rx @ Ry

    def _world_to_view(self, verts):
        v = np.asarray(verts) - self.center
        return v @ self._rot().T

    def project(self, verts):
        """world verts -> (Nx2 screen, Nx1 view-depth). Depth larger = nearer
        camera for painter sort (we paint small-depth first)."""
        vv = self._world_to_view(verts)
        sx = self.cx + vv[:, 0] * self.scale
        sy = self.cy - vv[:, 1] * self.scale
        depth = vv[:, 2]            # +z toward viewer after rotation
        return np.column_stack([sx, sy]), depth

    def view_normal_dot_light(self, world_normal):
        n = world_normal @ self._rot().T
        d = float(np.dot(n / (np.linalg.norm(n) + 1e-9), LIGHT))
        return d


# ---------------------------------------------------------------- rendering
def _face_normal(p0, p1, p2):
    n = np.cross(p1 - p0, p2 - p0)
    ln = np.linalg.norm(n)
    return n / ln if ln > 1e-9 else n


def collect_tris(meshes, alpha_by_idx=None):
    """Flatten (mesh, face) -> tri records with world verts, color, normal.
    alpha_by_idx: optional dict mesh_index -> alpha 0..1 (for fade-in)."""
    tris = []
    for mi, m in enumerate(meshes):
        a = 1.0 if alpha_by_idx is None else alpha_by_idx.get(mi, 0.0)
        if a <= 0.0:
            continue
        V = np.array(m["v"], dtype=float)
        base = hex2rgb(m["c"])
        for f in m["f"]:
            p = V[f[:3]]
            tris.append((p, base, _face_normal(*p[:3]), a, m.get("label", "")))
    return tris


def render_geometry(cam, tris, highlight_labels=None):
    """Painter's-algorithm render of triangle records onto an RGB image."""
    img = Image.new("RGB", (W, H - CAP_H), BG)
    draw = ImageDraw.Draw(img, "RGBA")
    # sort back-to-front by centroid depth (paint far first)
    decorated = []
    for p, base, nrm, a, label in tris:
        scr, dep = cam.project(p)
        decorated.append((dep.mean(), scr, base, nrm, a, label))
    decorated.sort(key=lambda t: t[0])
    for _, scr, base, nrm, a, label in decorated:
        ndl = cam.view_normal_dot_light(nrm)
        lit = 0.62 + 0.46 * max(0.0, ndl)         # diffuse + ambient floor
        col = shade(base, lit)
        if highlight_labels and label in highlight_labels:
            col = tuple(min(255, int(c * 0.55 + h * 0.45))
                        for c, h in zip(col, ACCENT))
        poly = [(float(x), float(y)) for x, y in scr]
        fill = col + (int(255 * a),)
        edge = shade(col, 0.55) + (int(170 * a),)
        draw.polygon(poly, fill=fill, outline=edge)
    return img


def caption_band(lines):
    """Render the forensic caption band. lines = list of (text, color, font)."""
    band = Image.new("RGB", (W, CAP_H), CAP_BG)
    d = ImageDraw.Draw(band)
    d.line([(0, 0), (W, 0)], fill=(40, 44, 54), width=1)
    y = 8
    for entry in lines[:CAP_LINES]:
        text, color, font = entry
        d.text((18, y), text, fill=color, font=font)
        y += LINE_H
    return band


def compose(geo_img, lines):
    frame = Image.new("RGB", (W, H), BG)
    frame.paste(geo_img, (0, 0))
    frame.paste(caption_band(lines), (0, H - CAP_H))
    return frame


def save_gif(path, frames, fps=14, hold_last_ms=1000):
    durs = [int(1000 / fps)] * len(frames)
    durs[-1] = max(durs[-1], hold_last_ms)
    frames[0].save(
        path, save_all=True, append_images=frames[1:],
        duration=durs, loop=0, optimize=True, disposal=2,
    )
    return os.path.getsize(path)


# ---------------------------------------------------------------- data helpers
def load_fleet():
    with open(FLEET) as fh:
        return json.load(fh)


def ship_by_prefix(fleet, prefix):
    for s in fleet["ships"]:
        if s["name"].startswith(prefix):
            return s
    raise KeyError(prefix)


def label_mesh_indices(meshes):
    """label -> list of mesh indices, in mesh order."""
    out = {}
    for i, m in enumerate(meshes):
        out.setdefault(m.get("label", ""), []).append(i)
    return out


# ---------------------------------------------------------------- assembly.gif
def build_assembly(fleet):
    """GS-α assembling part-by-part in commit order. True geometry animation.
    Each commit reveals the next label's meshes (fade/pop in); caption quotes
    that commit's host_port / strain / mass_left. Then repairs draw the struts,
    then the hose, then a summary frame from stats."""
    ship = ship_by_prefix(fleet, "GS-α")
    meshes = ship["meshes"]
    trace = ship["trace"]
    lab_idx = label_mesh_indices(meshes)
    all_v = np.concatenate([np.array(m["v"]) for m in meshes])
    cam = Camera(all_v)

    # strut/adapter meshes are the trailing braces; reveal them with repairs
    strut_indices = lab_idx.get("strut/adapter", [])

    frames = []
    revealed = {}                       # mesh index -> alpha
    # track which label-instances we've already consumed (repeat labels e.g. cannon)
    used_by_label = {}

    def reveal_label(label):
        """Reveal the next unconsumed mesh-instance(s) for this label.
        A 'part' is a multi-mesh body; consecutive meshes sharing the label
        form one part. We consume from the front of the unconsumed run."""
        idxs = lab_idx.get(label, [])
        start = used_by_label.get(label, 0)
        # find the contiguous run of same-label meshes starting at `start`
        # (all entries for a label that belong to one commit are adjacent in
        # the source ordering; multi-instance labels like 'cannon' get split
        # into two commits of two meshes each).
        run = []
        # how many meshes per commit-instance? cannon has 4 meshes / 2 commits.
        per = max(1, len(idxs) // max(1, sum(
            1 for e in trace if e.get("ev") == "commit" and e.get("part") == label)))
        run = idxs[start:start + per]
        used_by_label[label] = start + per
        return run

    SEED = next(e for e in trace if e["ev"] == "seed")
    title = ship["name"]

    # intro frame — seed
    geo = render_geometry(cam, [])
    frames += [compose(geo, [
        (f"{title}   {ship['plate']}", CAP_FG, F_BOLD),
        (f"seed {SEED['seed']}  /  faction {SEED['faction']}", ACCENT, F_BODY),
        ("the trace IS the genome — replay it, get this ship.", CAP_DIM, F_SMALL),
        ("assembling in commit order…", CAP_DIM, F_SMALL),
    ])] * 6

    FADE = 4   # frames to fade a part in

    repair_iter = iter([e for e in trace if e["ev"] == "repair"])
    next_strut = 0

    for e in trace:
        ev = e["ev"]
        if ev == "commit":
            run = reveal_label(e["part"])
            m = e.get("metrics", {})
            hp = e.get("host_port", "—")
            strain = m.get("strain")
            mass = m.get("mass_left")
            part_id = e.get("part_id", e["part"])
            for step in range(1, FADE + 1):
                a = step / FADE
                for mi in run:
                    revealed[mi] = a
                geo = render_geometry(cam, collect_tris(meshes, revealed),
                                      highlight_labels={e["part"]} if a >= 1 else None)
                if e["part"] == "core_hull":
                    l2 = "keel laid — host for every later port", ACCENT, F_BODY
                    l3 = (f"part_id {part_id}", CAP_DIM, F_SMALL)
                else:
                    l2 = (f"commit  {e['part']}  ->  {hp}", ACCENT, F_BODY)
                    l3 = (f"strain {strain}   mass_left {mass} kg",
                          CAP_FG, F_BODY)
                lines = [
                    (f"{title}   {ship['plate']}", CAP_FG, F_BOLD),
                    l2, l3,
                    (f"part_id {part_id}" if e["part"] != "core_hull"
                     else "ev: commit", CAP_DIM, F_SMALL),
                ]
                frames.append(compose(geo, lines))
            # settle hold
            frames.append(frames[-1])

        elif ev == "repair":
            mm = e["metrics"]
            # reveal one strut mesh per repair, drawn in onto the hull
            sidx = strut_indices[next_strut] if next_strut < len(strut_indices) else None
            next_strut += 1
            for step in range(1, FADE + 1):
                a = step / FADE
                if sidx is not None:
                    revealed[sidx] = a
                geo = render_geometry(cam, collect_tris(meshes, revealed),
                                      highlight_labels={"strut/adapter"})
                lines = [
                    (f"{title}   repair — {e['cause']}", WARN, F_BOLD),
                    (f"{e['op']} @ {mm['joint']}  ->  anchor {e['anchor']}",
                     CAP_FG, F_BODY),
                    (f"moment {mm['moment_before']} -> cap {mm['cap']} "
                     f"-> {mm['moment_after']}   relief {mm['relief']}",
                     WARN, F_BODY),
                    (f"struts {mm['struts']}   result: {e['result']}",
                     CAP_DIM, F_SMALL),
                ]
                frames.append(compose(geo, lines))
            frames.append(frames[-1])

        elif ev == "adapter":
            mm = e.get("metrics", {})
            geo = render_geometry(cam, collect_tris(meshes, revealed))
            lines = [
                (f"{title}   adapter — retrofit collar", WARN, F_BOLD),
                (f"part {e['part']}   strain {mm.get('strain')}",
                 CAP_FG, F_BODY),
                (f"result: {e['result']}", ACCENT, F_BODY),
                ("a mismatched port met -> a collar was logged", CAP_DIM, F_SMALL),
            ]
            frames += [compose(geo, lines)] * 5

        elif ev == "hose":
            mm = e["metrics"]
            # draw hose polyline(s)
            geo = render_geometry(cam, collect_tris(meshes, revealed))
            draw = ImageDraw.Draw(geo, "RGBA")
            for hose in ship.get("hoses", []):
                pts = np.array(hose["pts"], dtype=float)
                scr, _ = cam.project(pts)
                draw.line([(float(x), float(y)) for x, y in scr],
                          fill=(127, 209, 227, 235), width=3, joint="curve")
            lines = [
                (f"{title}   hose — {mm.get('hops')} hops",
                 ACCENT, F_BOLD),
                (f"route {e['frm']} -> {e['to']}", CAP_FG, F_BODY),
                (f"leaps {mm.get('leaps')}   supply_left {mm.get('supply_left')}",
                 CAP_FG, F_BODY),
                ("ev: hose", CAP_DIM, F_SMALL),
            ]
            frames += [compose(geo, lines)] * 5

    # summary frame from stats
    st = ship["stats"]
    geo = render_geometry(cam, collect_tris(meshes, revealed))
    draw = ImageDraw.Draw(geo, "RGBA")
    for hose in ship.get("hoses", []):
        pts = np.array(hose["pts"], dtype=float)
        scr, _ = cam.project(pts)
        draw.line([(float(x), float(y)) for x, y in scr],
                  fill=(127, 209, 227, 235), width=3, joint="curve")
    lines = [
        (f"{title}   complete", CAP_FG, F_BOLD),
        (f"{st['parts']} parts   {st['mass']} kg   "
         f"{st['struts']} struts   {st['hoses']} hose",
         ACCENT, F_BODY),
        ("every line above named a real logged event", CAP_DIM, F_BODY),
        ("replay the trace -> this exact ship", CAP_DIM, F_SMALL),
    ]
    frames += [compose(geo, lines)] * 12
    return frames


# ---------------------------------------------------------------- face_weld.gif
def build_face_weld(fleet):
    """FV-ε: a moment-relieving strut welding to a declared face. Full geometry
    shown; the strut draws in; the two repair events' real numbers caption."""
    ship = ship_by_prefix(fleet, "FV-ε")
    meshes = ship["meshes"]
    lab_idx = label_mesh_indices(meshes)
    all_v = np.concatenate([np.array(m["v"]) for m in meshes])
    repairs = [e for e in ship["trace"] if e["ev"] == "repair"]
    strut_indices = lab_idx.get("strut/adapter", [])

    frames = []
    n_orbit = 26
    title = ship["name"]
    # base alpha: everything but struts fully shown
    base_alpha = {i: 1.0 for i in range(len(meshes))
                  if meshes[i].get("label") != "strut/adapter"}

    # intro: ship without struts, slow orbit, naming the over-cap condition
    rp = repairs[0]
    mm = rp["metrics"]
    for k in range(n_orbit):
        yaw = math.radians(360.0 * k / n_orbit) * 0.35 - 0.35
        cam = Camera(all_v, yaw=yaw)
        geo = render_geometry(cam, collect_tris(meshes, dict(base_alpha)),
                              highlight_labels={"turret"})
        lines = [
            (f"{title}   face-level weld", CAP_FG, F_BOLD),
            (f"repair — {rp['cause']}  @ joint {mm['joint']}", WARN, F_BODY),
            (f"moment {mm['moment_before']} over cap {mm['cap']}", WARN, F_BODY),
            ("struts weld to declared faces, not generic hull", CAP_DIM, F_SMALL),
        ]
        frames.append(compose(geo, lines))

    # weld each strut in, one per repair event
    cam = Camera(all_v, yaw=-0.05)
    alpha = dict(base_alpha)
    FADE = 6
    for ri, rp in enumerate(repairs):
        mm = rp["metrics"]
        sidx = strut_indices[ri] if ri < len(strut_indices) else None
        for step in range(1, FADE + 1):
            a = step / FADE
            if sidx is not None:
                alpha[sidx] = a
            geo = render_geometry(cam, collect_tris(meshes, alpha),
                                  highlight_labels={"strut/adapter"})
            lines = [
                (f"{title}   strut {ri + 1} -> face on {mm['joint']}",
                 WARN, F_BOLD),
                (f"{rp['op']}  anchor {rp['anchor']}", CAP_FG, F_BODY),
                (f"moment {mm['moment_before']} -> cap {mm['cap']} "
                 f"-> {mm['moment_after']}", ACCENT, F_BODY),
                (f"relief {mm['relief']}   result: {rp['result']}",
                 CAP_FG, F_BODY),
            ]
            frames.append(compose(geo, lines))
        frames.append(frames[-1])

    # final summary hold
    geo = render_geometry(cam, collect_tris(meshes, alpha))
    lines = [
        (f"{title}   relieved", CAP_FG, F_BOLD),
        (f"2 struts   each moment {repairs[0]['metrics']['moment_before']}"
         f" -> {repairs[0]['metrics']['moment_after']}", ACCENT, F_BODY),
        (f"relief {repairs[0]['metrics']['relief']} per weld", CAP_FG, F_BODY),
        ("the moment math is in the ledger, not the artist's eye", CAP_DIM, F_SMALL),
    ]
    frames += [compose(geo, lines)] * 12
    return frames


# ---------------------------------------------------------------- auction.gif
def build_auction(fleet):
    """FV-δ: auctions firing over the assembled ship. Captioned highlight
    sequence; every bid number from the trace's auction events."""
    ship = ship_by_prefix(fleet, "FV-δ")
    meshes = ship["meshes"]
    all_v = np.concatenate([np.array(m["v"]) for m in meshes])
    auctions = [e for e in ship["trace"] if e["ev"] == "auction"]

    frames = []
    title = ship["name"]
    full = {i: 1.0 for i in range(len(meshes))}

    # intro
    cam = Camera(all_v, yaw=-0.2)
    geo = render_geometry(cam, collect_tris(meshes, full))
    frames += [compose(geo, [
        (f"{title}   port auctions", CAP_FG, F_BOLD),
        (f"{len(auctions)} contested ports — challenger vs incumbent",
         ACCENT, F_BODY),
        ("a port is scarce; bids are logged; the loser is named", CAP_DIM, F_BODY),
        ("ev: auction", CAP_DIM, F_SMALL),
    ])] * 6

    for ai, e in enumerate(auctions):
        mm = e["metrics"]
        riv = mm.get("rivals", [{}])[0]
        # slow drift so the still frames aren't dead
        for k in range(8):
            yaw = -0.2 + 0.012 * k
            cam = Camera(all_v, yaw=yaw)
            geo = render_geometry(cam, collect_tris(meshes, full),
                                  highlight_labels={e["part"], riv.get("part", "")})
            lines = [
                (f"{title}   auction {ai + 1}/{len(auctions)} — port "
                 f"{e['port'].split('/')[-1]}", WARN, F_BOLD),
                (f"challenger {e['part']} {mm['challenger']}  vs  "
                 f"incumbent {riv.get('part','?')} {mm['incumbent']}",
                 CAP_FG, F_BODY),
                (f"scarcity {mm['scarcity']}   incumbent prio "
                 f"{riv.get('prio','?')} bid {riv.get('bid','?')}",
                 ACCENT, F_BODY),
                (f"result: {e['result']}", WARN, F_BODY),
            ]
            frames.append(compose(geo, lines))
        frames.append(frames[-1])

    # summary
    holds = sum(1 for e in auctions if e["result"] == "incumbent_holds")
    geo = render_geometry(cam, collect_tris(meshes, full))
    frames += [compose(geo, [
        (f"{title}   auctions settled", CAP_FG, F_BOLD),
        (f"{holds}/{len(auctions)} incumbent_holds", ACCENT, F_BODY),
        ("cold shoulder: the held ports never changed hands", CAP_DIM, F_BODY),
        ("every bid above is in the trace", CAP_DIM, F_SMALL),
    ])] * 12
    return frames


# ---------------------------------------------------------------- collar.gif
def build_collar(fleet):
    """GS-α: a retrofit adapter collar spawning. Captioned over geometry; the
    strain and result come from the adapter event; the collar mesh (a
    strut/adapter brace) draws in."""
    ship = ship_by_prefix(fleet, "GS-α")
    meshes = ship["meshes"]
    lab_idx = label_mesh_indices(meshes)
    all_v = np.concatenate([np.array(m["v"]) for m in meshes])
    adapter = next(e for e in ship["trace"] if e["ev"] == "adapter")
    mm = adapter.get("metrics", {})
    # the adapter collar is the b08d3f-colored strut/adapter brace
    strut_indices = lab_idx.get("strut/adapter", [])
    collar_idx = strut_indices[-1] if strut_indices else None

    frames = []
    title = ship["name"]
    base = {i: 1.0 for i in range(len(meshes)) if i != collar_idx}

    # intro: full ship minus the collar, slow orbit
    for k in range(14):
        yaw = -0.25 + 0.02 * k
        cam = Camera(all_v, yaw=yaw)
        geo = render_geometry(cam, collect_tris(meshes, dict(base)))
        frames.append(compose(geo, [
            (f"{title}   retrofit collar", CAP_FG, F_BOLD),
            (f"part {adapter['part']} arrived on a mismatched port",
             ACCENT, F_BODY),
            (f"strain {mm.get('strain')} — within tolerance, so adapt",
             CAP_FG, F_BODY),
            ("ev: adapter", CAP_DIM, F_SMALL),
        ]))

    # spawn the collar in
    cam = Camera(all_v, yaw=0.03)
    FADE = 8
    alpha = dict(base)
    for step in range(1, FADE + 1):
        a = step / FADE
        if collar_idx is not None:
            alpha[collar_idx] = a
        geo = render_geometry(cam, collect_tris(meshes, alpha),
                              highlight_labels={"strut/adapter"})
        frames.append(compose(geo, [
            (f"{title}   collar spawning", WARN, F_BOLD),
            (f"part {adapter['part']}   strain {mm.get('strain')}",
             CAP_FG, F_BODY),
            (f"result: {adapter['result']}", ACCENT, F_BODY),
            ("the collar is a logged decision, not a fudge", CAP_DIM, F_SMALL),
        ]))

    geo = render_geometry(cam, collect_tris(meshes, alpha))
    frames += [compose(geo, [
        (f"{title}   {adapter['result']}", CAP_FG, F_BOLD),
        (f"strain {mm.get('strain')} -> collar logged", ACCENT, F_BODY),
        ("replay the trace -> the same collar reappears", CAP_DIM, F_BODY),
        ("ev: adapter / result: collar_spawned", CAP_DIM, F_SMALL),
    ])] * 12
    return frames


# ---------------------------------------------------------------- main
def main():
    os.makedirs(MEDIA, exist_ok=True)
    fleet = load_fleet()

    jobs = [
        ("assembly.gif", build_assembly, dict(fps=14)),
        ("face_weld.gif", build_face_weld, dict(fps=14)),
        ("auction.gif", build_auction, dict(fps=14)),
        ("collar.gif", build_collar, dict(fps=14)),
    ]
    for fname, builder, kw in jobs:
        frames = builder(fleet)
        path = os.path.join(MEDIA, fname)
        size = save_gif(path, frames, **kw)
        print(f"  {fname:14s}  {len(frames):3d} frames  "
              f"{size/1024:7.1f} KB  -> {path}")


if __name__ == "__main__":
    main()
