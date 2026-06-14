"""KitMash v0.6 — Routing v2: channels, congestion, segregation, the loom
(roadmap item 2).

v0.5 -> v0.6:
  * the grommet graph becomes a CHANNEL graph: edges carry capacity
    (min of endpoint grommet conduit_size), occupancy, and native conduit
    types. Reservation is real: a hose consumes bundle diameter
    (0.025 + 0.01 x rate) from every channel it rides.
  * segregation matrix enforced at two levels: proximity edges between
    forbidden-pair grommets are never built (pruned, counted), and a net
    may only ride channels whose native types and current occupants it is
    allowed to share (fuel x high_volt: never; optical x high_volt:
    separate bundles, crossing at nodes OK; coolant: friendly with all).
  * the LOOM DISCOUNT: a channel already carrying a compatible hose costs
    0.55x for the next one, until capacity is spent. Harnesses emerge from
    economics, not authoring. Hose events log `loomed` edge counts.
  * congestion rip-up-and-reroute (EDA-style, bounded): when a net cannot
    route under capacity, find the relaxed path, evict the squatting hoses
    (rip_up events, cause=congestion), route, then reroute the victims —
    who get no second rip. demand_unmet gains cause=congestion.
  * multi-conduit fleets: gen_reactor (supplies high_volt) + gen_turret
    (demands it); FV-epsilon «Loom» exercises the machinery live.
  * REGRESSION POLICY (amended): geometric + stats + hose-path identity for
    prior ships; trace events and JSON fields may be added, never changed.

v0.5 — auction + conflict-directed backjumping (roadmap item 1).

v0.4 -> v0.5:
  * uncommit(): transactional eviction — subtree cascade, ledger/budget/port
    restoration, freed host ports requeued. The propose->validate->commit
    architecture finally pays its full dividend: placement is reversible.
  * clearance conflicts checked BOTH ways (existing volumes vs new part AND
    new part's volumes vs existing parts — the second direction was silently
    unchecked in v0.4) and resolved by AUCTION, not silent rejection:
    bid = prio x score x scarcity; incumbents add subtree entrenchment;
    the hull is unevictable. Every bid is in the trace.
  * conflict-directed backjumping: when a prio>=7 port exhausts candidates
    and the rejects share ledger blockers, evict the most recent blocker
    (bounded, once per port/blocker pair, jump count logged with the
    conflict set). Hard collisions stay dumb legality; the auction and the
    backjump are mediation, with recorded reasons. Doctrine holds.
  * struts carry their owner's uid so eviction takes its braces with it.

v0.4 — engine-room hardening after cross-model review.

v0.3 -> v0.4 (all reviewer-driven):
  * placement is transactional: propose -> validate -> commit; no haunted ledgers
  * spine is a true tree-fold: every ancestor joint re-feels the whole outboard
    subtree (incl. candidate) before commit
  * struts pay measured debt: relief model, moment_after = M*(1-relief); a
    brace that can't cover the debt -> clean reject
  * strut anchors on nearest root-side structural neighbor, not always the hull
  * budgets enforced at spend; factions may carry debt (feral 5%, guild 0%)
  * stable port_id on every port; join events name both mouths
  * generators take real seeds; gen_params is a mutation substrate, not a manifesto
  * supplies decrement; saturation is a logged, visible state
  * axial capacity awake (engine thrust flows root-ward)
  * trace events carry cause / metrics / result (ledger-shaped, still readable)
"""
import json, math, random
import numpy as np

# ---------------------------------------------------------------- mesh utils
def box(sx, sy, sz):
    x, y, z = sx/2, sy/2, sz/2
    v = [(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    f = [(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),(2,3,7),(2,7,6),
         (1,2,6),(1,6,5),(0,4,7),(0,7,3)]
    return np.array(v,float), f

def cyl(r0, r1, h, seg=14):
    v, f = [], []
    for i in range(seg):
        a = 2*math.pi*i/seg
        v.append((r0*math.cos(a), r0*math.sin(a), -h/2))
        v.append((r1*math.cos(a), r1*math.sin(a),  h/2))
    n = seg*2
    for i in range(seg):
        a,b,c,d = 2*i,2*i+1,(2*i+2)%n,(2*i+3)%n
        f += [(a,c,b),(b,c,d)]
    v += [(0,0,-h/2),(0,0,h/2)]; bo, to = n, n+1
    for i in range(seg):
        f += [(bo,(2*i+2)%n,2*i),(to,2*i+1,(2*i+3)%n)]
    return np.array(v,float), f

def xform(verts, R, t): return verts @ R.T + t

def frame(N, up):
    z = N/np.linalg.norm(N)
    x = up - z*np.dot(up,z); x /= np.linalg.norm(x)
    return np.stack([x, np.cross(z,x), z], axis=1)

# ------------------------------------------------------------------- schema
class Port:
    def __init__(s, pos, N, up, ptype, size, gender, prio=5, sym=0,
                 cluster="", tags=""):
        s.pos=np.array(pos,float); s.N=np.array(N,float); s.up=np.array(up,float)
        s.type=ptype; s.size=size; s.gender=gender; s.prio=prio
        s.sym=sym; s.cluster=cluster; s.tags=tags
        s.filled=False; s.pid=""          # assigned by Part.finalize

class Grommet:
    def __init__(s,pos,ctype,size=0.1):
        s.pos=np.array(pos,float); s.ctype=ctype; s.size=size

class Part:
    _n=0
    def __init__(s, family, gen_params, mass, silhouette, faction, era,
                 color, label=""):
        Part._n+=1; s.uid=f"{family}#{Part._n}"
        s.family=family; s.gen_params=gen_params; s.mass=mass
        s.silhouette=silhouette; s.faction=faction; s.era=era; s.color=color
        s.label=label or family
        s.meshes=[]; s.ports=[]; s.grommets=[]; s.gedges=[]
        s.supplies=[]; s.demands=[]; s.clearances=[]
        s.anchor_vols=None   # local AABBs where struts may weld;
                             # None = whole part anchorable (legacy)
        s.anchor_faces=None  # P3: face-level anchor patches (refines vols).
                             # list of make_face() dicts; None = fall back to
                             # anchor_vols. A face carries an outward NORMAL and
                             # an anchor_class (0 glass/no-weld, 1 secondary,
                             # 2 primary load-bearing) — struts weld to a SURFACE
                             # with orientation, not anywhere inside a box.
        s.com=np.zeros(3)
        # tree bookkeeping (set on commit)
        s.parent=None; s.children=[]
        s.jpos=None; s.jaxis=None; s.jcap=None
        s.sub_mass=0.0; s.sub_mc=np.zeros(3)   # subtree mass / mass*com sum
    def add(s,verts,faces,color=None): s.meshes.append((verts,faces,color or s.color))
    def finalize(s):
        counts={}
        for pt in s.ports:
            k=pt.type; counts[k]=counts.get(k,0)+1
            pt.pid=f"{s.uid}/{k}_{counts[k]}"
        return s

CAPACITY = {"struct_S":(2_000,15_000), "struct_M":(40_000,120_000),
            "struct_L":(900_000,2_500_000), "mount_rail":(25_000,60_000)}
RAIL_CLUSTER_BONUS = 1.3

# Segregation matrix (library-level, versioned with the schema).
# Listed pairs may NOT share a channel; everything else is friendly.
# "forbidden" also prunes proximity edges at graph build (never adjacent);
# "separate" allows crossing at nodes but not co-bundling on an edge.
# The 20cm parallel-run minimum for fuel x high_volt is cartooned as
# no-share (geometric min-distance between distinct channels: not built).
SEGREGATION = {frozenset(("fuel","high_volt")): "forbidden",
               frozenset(("optical","high_volt")): "separate"}

def seg_share_ok(a, b):
    return a==b or frozenset((a,b)) not in SEGREGATION

def joint_cap(ptype, cluster):
    m,a = CAPACITY[ptype]
    if cluster: m*=2*RAIL_CLUSTER_BONUS; a*=2
    return m,a

# P3 — face-level anchor patches. A face is a planar rectangular weld surface
# in part-LOCAL space: centre c, outward unit normal n, an in-plane axis u
# (v = n×u derived), half-extents hu/hv, and an anchor_class. The normal lets
# the relief model reward a strut that pulls NORMAL-ON (tension/compression into
# the surface) over one that SHEARS along it; the class lets a part forbid welds
# to glass (cls 0) and prefer primary structure (cls 2) over secondary (cls 1).
ANCHOR_CLASS_RELIEF = {2: 1.0, 1: 0.65}   # cls 0 yields NO candidate (no-weld)

def make_face(c, n, hu, hv, cls=2, u=None):
    # Fail loudly at AUTHORING. A degenerate normal would otherwise normalize to
    # NaN, and a NaN candidate WINS a brace (best-is-None seeds it, and no later
    # candidate beats NaN under `>`), poisoning the strut with NaN coords. With
    # 11 families declaring faces by hand, a typo'd normal must crash, not creep.
    # (Cassandra P3 C2c.)
    n=np.asarray(n,float); nn=np.linalg.norm(n)
    if nn<1e-9: raise ValueError(f"make_face: degenerate normal {n}")
    n=n/nn
    if u is None:
        a=np.array([1.0,0,0]) if abs(n[0])<0.9 else np.array([0,1.0,0])
        u=a-np.dot(a,n)*n
    else:
        u=np.asarray(u,float); u=u-np.dot(u,n)*n
    uu=np.linalg.norm(u)
    if uu<1e-9: raise ValueError(f"make_face: in-plane axis u parallel to n {n}")
    u=u/uu
    if cls not in (0,1,2): raise ValueError(f"make_face: bad anchor_class {cls}")
    return dict(c=np.asarray(c,float),n=n,u=u,
                hu=float(hu),hv=float(hv),cls=int(cls))

def face_candidates(face, com):
    """Nearest point ON the patch plus its two v-edge points (triangulation
    still pays). Returns [(anchor_point, normal, cls), ...]; empty for cls 0."""
    if face["cls"]==0: return []
    c,n,u,hu,hv=face["c"],face["n"],face["u"],face["hu"],face["hv"]
    v=np.cross(n,u)
    to=com-c; ip=to-np.dot(to,n)*n
    pu=float(np.clip(np.dot(ip,u),-hu,hu))
    pv=float(np.clip(np.dot(ip,v),-hv,hv))
    base=c+pu*u
    pts=[base+pv*v, base+(-hv)*v, base+hv*v]   # nearest, then both v-edges
    return [(p,n,face["cls"]) for p in pts]

def xform_face(face, R, t):
    """Local face -> world. Centre takes R and t; the normal and in-plane axis
    are directions (R only); R is a pure rotation so the extents survive."""
    return dict(c=xform(face["c"][None],R,t)[0],
                n=R@face["n"], u=R@face["u"],
                hu=face["hu"], hv=face["hv"], cls=face["cls"])

# --------------------------------------------------------------- generators
def gen_hull(fc, seed=0, scale=1.0):
    rng=random.Random(seed)
    p=Part("core_hull",{"scale":scale,"seed":seed},mass=4000*scale,
           silhouette=0.9,faction=fc["name"],era=fc["era"],color=fc["hull"])
    L,W,H=7.0*scale,2.2,1.8
    v,f=box(L,W,H); p.add(v,f)
    v,f=cyl(0.9,0.5,1.6); p.add(xform(v,frame([1,0,0],[0,0,1]),[L/2+0.7,0,0]),
                                f,fc["accent"])
    up=[0,0,1]
    p.ports+=[
        Port([-L/2,0,0],[-1,0,0],up,"struct_M",1.0,0,prio=9),
        Port([0, W/2,0],[0, 1,0],up,"struct_M",1.0,0,prio=8,tags="side_R"),
        Port([0,-W/2,0],[0,-1,0],up,"struct_M",1.0,0,prio=8,tags="side_L"),
        Port([ 1.8,0, H/2],[0,0, 1],[1,0,0],"struct_M",0.8,0,prio=9),  # fuel first
        Port([-1.5,0, H/2],[0,0, 1],[1,0,0],"struct_S",0.30,0,prio=4),
        Port([ 0.5,0,-H/2],[0,0,-1],[1,0,0],"struct_S",0.30,0,prio=3),
        Port([ 2.6,0,-H/2],[0,0,-1],[1,0,0],"struct_S",0.30,0,prio=3)]
    g=[Grommet([x,0,H/2-0.15],"fuel") for x in (-L/2+0.3,-1.0,1.0,1.8,L/2-0.6)]
    p.grommets=g; p.gedges=[(i,i+1) for i in range(len(g)-1)]
    # P3 — the hull is the universal strut anchor; declare its weldable
    # SURFACES. Deck/belly/flanks are primary structure (cls 2); the +x nose
    # cone is aerodynamic glass (cls 0 — a strut may never weld to it). Before
    # P3 a brace could land anywhere in the whole box, nose included.
    p.anchor_faces=[
        make_face([0,0, H/2],[0,0, 1],L/2,W/2,2,u=[1,0,0]),   # top deck
        make_face([0,0,-H/2],[0,0,-1],L/2,W/2,2,u=[1,0,0]),   # belly
        make_face([0, W/2,0],[0, 1,0],L/2,H/2,2,u=[1,0,0]),   # flank R
        make_face([0,-W/2,0],[0,-1,0],L/2,H/2,2,u=[1,0,0]),   # flank L
        make_face([-L/2,0,0],[-1,0,0],W/2,H/2,1,u=[0,1,0]),   # aft bulkhead (secondary)
        make_face([L/2+1.4,0,0],[1,0,0],0.5,0.5,0,u=[0,1,0])] # nose cone: GLASS
    return p.finalize()

def gen_tank(fc, seed=0):
    rng=random.Random(seed); h=2.4*rng.uniform(0.9,1.1)
    p=Part("fuel_tank",{"seed":seed,"h":h},mass=900*h/2.4,
           silhouette=0.45,faction=fc["name"],era=fc["era"],
           color=fc["accent"],label="fuel tank")
    v,f=cyl(0.55,0.55,h); p.add(xform(v,frame([1,0,0],[0,0,1]),[0,0,0.55]),f)
    v,f=box(0.7,0.7,0.12); p.add(xform(v,np.eye(3),[0,0,0.05]),f,fc["hull"])
    p.ports=[Port([0,0,0],[0,0,-1],[1,0,0],"struct_M",0.8,1)]
    p.grommets=[Grommet([0,0,0.1],"fuel"),Grommet([0.6,0,0.55],"fuel")]
    p.gedges=[(0,1)]; p.supplies=[["fuel",3.0]]
    # P3 — anchorable surfaces. The base flange (box 0.7×0.7×0.12 centred at
    # [0,0,0.05]) is primary structure: struts weld to its top face, four sides.
    # The cylindrical tank body is a pressure vessel — not a weld surface.
    p.anchor_faces=[
        make_face([0,0,0.11],[0,0, 1],0.35,0.35,2,u=[1,0,0]),  # flange top cls-2
        make_face([0.35,0,0.05],[1,0,0],0.06,0.35,2,u=[0,1,0]),# flange +x side cls-2
        make_face([-0.35,0,0.05],[-1,0,0],0.06,0.35,2,u=[0,1,0]),# flange -x side cls-2
        make_face([0,0.35,0.05],[0,1,0],0.35,0.06,2,u=[1,0,0]),# flange +y side cls-2
        make_face([0,-0.35,0.05],[0,-1,0],0.35,0.06,2,u=[1,0,0])]# flange -y side cls-2
    return p.finalize()

def gen_engine(fc, seed=0, size=1.0):
    p=Part("engine",{"size":size,"seed":seed},mass=1400*size,silhouette=0.55,
           faction=fc["name"],era=fc["era"],color=fc["dark"],label="engine")
    R=frame([1,0,0],[0,0,1])
    v,f=cyl(0.75*size,0.95*size,2.0); p.add(xform(v,R,[-1.0,0,0]),f)
    v,f=cyl(0.95*size,0.55*size,0.7); p.add(xform(v,R,[-2.3,0,0]),f,fc["glow"])
    p.ports=[Port([0,0,0],[1,0,0],[0,0,1],"struct_M",1.0,1)]
    p.grommets=[Grommet([-0.2,0,0.3],"fuel")]
    p.demands=[["fuel",1.2*size]]
    p.thrust_axial=True
    p.clearances=[(np.array([-6.5,-0.9,-0.9]),np.array([-2.3,0.9,0.9]))]
    # P3 — anchorable surfaces. The casing (x∈[-2.0, 0.0]) is primary structure;
    # its four barrel-sides are cls-2 weld faces. The forward mating flange at x=0
    # is cls-2. The glow nozzle (x∈[-3.0,-2.0]; the -x cone of fc["glow"] colour)
    # is GLASS — cls-0, never weldable. anchor_vols kept for legacy consumers.
    s=0.95*size   # casing radius (max radius of main cone)
    p.anchor_vols=[(np.array([-2.0,-s,-s]),np.array([0.0,s,s]))]
    p.anchor_faces=[
        make_face([-1.0, s,0],[ 0, 1,0],1.0,s,2,u=[1,0,0]),  # casing +y barrel cls-2
        make_face([-1.0,-s,0],[ 0,-1,0],1.0,s,2,u=[1,0,0]),  # casing -y barrel cls-2
        make_face([-1.0,0, s],[ 0,0, 1],1.0,s,2,u=[1,0,0]),  # casing +z barrel cls-2
        make_face([-1.0,0,-s],[ 0,0,-1],1.0,s,2,u=[1,0,0]),  # casing -z barrel cls-2
        make_face([0.0, 0,0],[1,0,0],s,s,2,u=[0,1,0]),        # fwd flange cls-2
        make_face([-3.0,0,0],[-1,0,0],0.55*size,0.55*size,0,  # glow nozzle: GLASS
                  u=[0,1,0])]
    return p.finalize()

def gen_wing(fc, seed=0, span=3.2, hand=1):
    p=Part("wing",{"span":span,"hand":hand,"seed":seed},mass=600*span/3.2,
           silhouette=0.7,faction=fc["name"],era=fc["era"],color=fc["hull"],
           label="wing "+("R" if hand>0 else "L"))
    v,f=box(2.0,span,0.22); p.add(xform(v,np.eye(3),[0,span/2,0]),f)
    v,f=box(2.2,0.5,0.34); p.add(xform(v,np.eye(3),[0,0.25,0]),f,fc["accent"])
    p.ports=[Port([0,0,0],[0,-1,0],[0,0,1],"struct_M",1.0,1,
                  tags="side_R" if hand>0 else "side_L")]
    y=span-0.45; up=[hand,0,0]
    p.ports+=[Port([-0.5*hand,y,0.11],[0,0,1],up,"mount_rail",0.4,0,
                   prio=8,sym=1,cluster="railA"),
              Port([ 0.5*hand,y,0.11],[0,0,1],up,"mount_rail",0.4,0,
                   prio=8,sym=1,cluster="railA")]
    p.grommets=[Grommet([0,0.2,0.12],"fuel"),Grommet([0,y-0.4,0.12],"fuel")]
    p.gedges=[(0,1)]
    # P3 — anchorable surfaces. The root spar (box 2.2×0.5×0.34, centred at
    # [0, 0.25, 0]) is primary load-bearing structure — top/bottom faces cls-2;
    # +x/-x chord faces cls-1 (secondary). The wing panel proper (2.0×span×0.22)
    # is a thin aerofoil shell — cls-0, never weld to the panel skin.
    # Handedness matters for which chord face faces outboard vs inboard, but the
    # root-spar faces are symmetric about the port-axis (y=0), so no hand flip.
    p.anchor_faces=[
        make_face([0,0.25, 0.17],[0,0, 1],1.1,0.25,2,u=[1,0,0]), # root top cls-2
        make_face([0,0.25,-0.17],[0,0,-1],1.1,0.25,2,u=[1,0,0]), # root belly cls-2
        make_face([ 1.1,0.25,0],[ 1,0,0],0.17,0.25,1,u=[0,1,0]),# root +x chord cls-1
        make_face([-1.1,0.25,0],[-1,0,0],0.17,0.25,1,u=[0,1,0]),# root -x chord cls-1
        make_face([0,0.5+span/4,0.11],[0,0,1],1.0,span/4,0,      # wing panel: GLASS
                  u=[1,0,0])]
    return p.finalize()

def gen_cannon(fc, seed=0, heavy=1.0):
    p=Part("heavy_cannon",{"heavy":heavy,"seed":seed},mass=950*heavy,
           silhouette=0.5,faction=fc["name"],era=fc["era"],color=fc["dark"],
           label="cannon")
    v,f=box(1.3,0.6,0.5); p.add(xform(v,np.eye(3),[0,0,0.35]),f)
    v,f=cyl(0.12,0.10,2.6*heavy)
    p.add(xform(v,frame([1,0,0],[0,0,1]),[1.6*heavy,0,0.42]),f,fc["accent"])
    up=[1,0,0]
    p.ports=[Port([-0.5,0,0.1],[0,0,-1],up,"mount_rail",0.4,1,sym=1,cluster="railA"),
             Port([ 0.5,0,0.1],[0,0,-1],up,"mount_rail",0.4,1,sym=1,cluster="railA")]
    p.com=np.array([1.2*heavy,0,0.4])
    # P3 — anchorable surfaces. The mount block (box 1.3×0.6×0.5 at [0,0,0.35],
    # so x∈[-0.65,0.65], y∈[-0.3,0.3], z∈[0.1,0.6]) is primary structure;
    # its four sides and top are cls-2. The barrel is a gun tube — GLASS cls-0.
    p.anchor_faces=[
        make_face([0,0,0.6],[0,0, 1],0.65,0.3,2,u=[1,0,0]),     # block top cls-2
        make_face([0.65,0,0.35],[1,0,0],0.25,0.3,2,u=[0,1,0]),  # block +x side cls-2
        make_face([-0.65,0,0.35],[-1,0,0],0.25,0.3,2,u=[0,1,0]),# block -x side cls-2
        make_face([0,0.3,0.35],[0,1,0],0.65,0.25,1,u=[1,0,0]),  # block +y face cls-1
        make_face([0,-0.3,0.35],[0,-1,0],0.65,0.25,1,u=[1,0,0]),# block -y face cls-1
        make_face([1.6*heavy,0,0.42],[1,0,0],0.12,0.12,0,        # barrel tip: GLASS
                  u=[0,1,0])]
    return p.finalize()

def gen_antenna(fc, seed=0):
    rng=random.Random(seed); h=1.9*rng.uniform(0.85,1.2)
    p=Part("antenna",{"seed":seed,"h":h},mass=40,silhouette=0.25,
           faction=fc["name"],era=fc["era"],color=fc["accent"],label="antenna")
    v,f=cyl(0.05,0.02,h); p.add(xform(v,np.eye(3),[0,0,h/2]),f)
    v,f=box(0.3,0.3,0.1); p.add(xform(v,np.eye(3),[0,0,0.05]),f,fc["dark"])
    p.ports=[Port([0,0,0],[0,0,-1],[1,0,0],"struct_S",0.30,1)]
    # P3 — anchorable surfaces. Base box (0.3×0.3×0.1 at [0,0,0.05],
    # so x∈[-0.15,0.15], y∈[-0.15,0.15], z∈[0.0,0.1]) is primary structure:
    # top face cls-2, four sides cls-2. The mast is a whip — cls-0, no weld.
    p.anchor_vols=[(np.array([-0.15,-0.15,0.0]),np.array([0.15,0.15,0.1]))]
    p.anchor_faces=[
        make_face([0,0,0.1],[0,0,1],0.15,0.15,2,u=[1,0,0]),      # base top cls-2
        make_face([ 0.15,0,0.05],[ 1,0,0],0.05,0.15,2,u=[0,1,0]),# base +x cls-2
        make_face([-0.15,0,0.05],[-1,0,0],0.05,0.15,2,u=[0,1,0]),# base -x cls-2
        make_face([0, 0.15,0.05],[0, 1,0],0.15,0.05,2,u=[1,0,0]),# base +y cls-2
        make_face([0,-0.15,0.05],[0,-1,0],0.15,0.05,2,u=[1,0,0]),# base -y cls-2
        make_face([0,0,h/2],[0,0,1],0.03,0.03,0,u=[1,0,0])]      # mast tip: GLASS
    return p.finalize()

def gen_pod(fc, seed=0):
    rng=random.Random(seed); r=rng.uniform(0.30,0.345)   # strain substrate
    p=Part("sensor_pod",{"seed":seed,"r":r},mass=120,silhouette=0.3,
           faction=fc["name"],era=fc["era"],color=fc["accent"],label="sensor pod")
    v,f=cyl(r-0.02,r-0.02,0.8,seg=10); p.add(xform(v,np.eye(3),[0,0,-0.45]),f)
    p.ports=[Port([0,0,0],[0,0,1],[1,0,0],"struct_S",r,1)]
    # P3 — anchorable surfaces. The sensor pod is a cylindrical pressure vessel;
    # the mounting flange at z=0 (top) is the primary structural weld point cls-2.
    # Four cardinal side faces at the pod's widest radius are cls-1 secondary.
    # The bottom dome (z≈-0.85) is instrument glass — cls-0, never weldable.
    rw=r-0.02   # actual cylinder radius
    p.anchor_faces=[
        make_face([0,0,0],[0,0,1],rw,rw,2,u=[1,0,0]),           # mounting flange cls-2
        make_face([ rw,0,-0.45],[ 1,0,0],0.02,0.45,1,u=[0,1,0]),# +x barrel cls-1
        make_face([-rw,0,-0.45],[-1,0,0],0.02,0.45,1,u=[0,1,0]),# -x barrel cls-1
        make_face([0, rw,-0.45],[0, 1,0],rw,0.45,1,u=[1,0,0]),  # +y barrel cls-1
        make_face([0,-rw,-0.45],[0,-1,0],rw,0.45,1,u=[1,0,0]),  # -y barrel cls-1
        make_face([0,0,-0.85],[0,0,-1],rw,rw,0,u=[1,0,0])]      # bottom dome: GLASS
    return p.finalize()

def gen_radiator(fc, seed=0):
    """Drop radiator: hangs below a struct_S port, and its radiating faces
    demand a wide emptiness — a clearance hog, built to start auctions."""
    rng=random.Random(seed); w=rng.uniform(1.6,2.0)
    p=Part("radiator",{"seed":seed,"w":w},mass=260,silhouette=0.5,
           faction=fc["name"],era=fc["era"],color=fc["glow"],label="radiator")
    v,f=box(0.16,w,1.4); p.add(xform(v,np.eye(3),[0,0,-0.82]),f)
    v,f=box(0.3,0.3,0.24); p.add(xform(v,np.eye(3),[0,0,-0.12]),f,fc["dark"])
    p.ports=[Port([0,0,0],[0,0,1],[1,0,0],"struct_S",0.30,1)]
    p.clearances=[(np.array([-2.2,-w/2-0.5,-2.4]),
                   np.array([ 2.2, w/2+0.5,-0.25]))]
    # P3 — anchorable surfaces. The mounting block (0.3×0.3×0.24 at [0,0,-0.12],
    # so x∈[-0.15,0.15], y∈[-0.15,0.15], z∈[-0.24,0.0]) is primary structure.
    # The radiating panel (0.16×w×1.4) IS the glass — cls-0. anchor_vols kept
    # for legacy consumers that do not read anchor_faces.
    p.anchor_vols=[(np.array([-0.15,-0.15,-0.24]),
                    np.array([ 0.15, 0.15, 0.0]))]
    p.anchor_faces=[
        make_face([0,0,0],[0,0,1],0.15,0.15,2,u=[1,0,0]),         # block top cls-2
        make_face([ 0.15,0,-0.12],[ 1,0,0],0.12,0.15,2,u=[0,1,0]),# block +x cls-2
        make_face([-0.15,0,-0.12],[-1,0,0],0.12,0.15,2,u=[0,1,0]),# block -x cls-2
        make_face([0, 0.15,-0.12],[0, 1,0],0.15,0.12,1,u=[1,0,0]),# block +y cls-1
        make_face([0,-0.15,-0.12],[0,-1,0],0.15,0.12,1,u=[1,0,0]),# block -y cls-1
        make_face([0,0,-0.82],[0,0,-1],0.08,w/2,0,u=[1,0,0])]     # panel face: GLASS
    return p.finalize()

def gen_reactor(fc, seed=0):
    """Auxiliary reactor pod: supplies high_volt. First grommet is the
    supply tap (routing taps wgrom[0])."""
    rng=random.Random(seed); h=rng.uniform(0.85,1.0)
    p=Part("reactor",{"seed":seed,"h":h},mass=420,silhouette=0.35,
           faction=fc["name"],era=fc["era"],color=fc["glow"],label="reactor")
    v,f=cyl(0.34,0.30,h,seg=10); p.add(xform(v,np.eye(3),[0,0,-h/2-0.07]),f)
    v,f=box(0.5,0.5,0.14); p.add(xform(v,np.eye(3),[0,0,-0.07]),f,fc["dark"])
    p.ports=[Port([0,0,0],[0,0,1],[1,0,0],"struct_S",0.30,1)]
    p.grommets=[Grommet([0,0,-0.18],"high_volt",0.12),
                Grommet([0.36,0,-h-0.05],"high_volt",0.12)]
    p.gedges=[(0,1)]
    p.supplies=[["high_volt",4.0]]
    # P3 — anchorable surfaces. The base plate (0.5×0.5×0.14 at [0,0,-0.07],
    # so x∈[-0.25,0.25], y∈[-0.25,0.25], z∈[-0.14,0.0]) is primary structure.
    # The reactor cylinder is a pressurised vessel — cls-1 (secondary weld only).
    # No cls-0 glass on this part; the reactor is a forged pod, not an optic.
    p.anchor_faces=[
        make_face([0,0,0],[0,0,1],0.25,0.25,2,u=[1,0,0]),          # top plate cls-2
        make_face([ 0.25,0,-0.07],[ 1,0,0],0.07,0.25,2,u=[0,1,0]),# plate +x cls-2
        make_face([-0.25,0,-0.07],[-1,0,0],0.07,0.25,2,u=[0,1,0]),# plate -x cls-2
        make_face([0, 0.25,-0.07],[0, 1,0],0.25,0.07,2,u=[1,0,0]),# plate +y cls-2
        make_face([0,-0.25,-0.07],[0,-1,0],0.25,0.07,2,u=[1,0,0]),# plate -y cls-2
        make_face([0.30,0,-h/2-0.07],[1,0,0],0.04,h/2,1,           # cylinder +x cls-1
                  u=[0,1,0])]
    return p.finalize()

def gen_turret(fc, seed=0):
    """Point-defense turret: demands high_volt. Mounts any struct_S."""
    rng=random.Random(seed); barrel=rng.uniform(0.7,0.9)
    p=Part("turret",{"seed":seed,"barrel":barrel},mass=170,
           silhouette=0.3,faction=fc["name"],era=fc["era"],color=fc["dark"],
           label="turret")
    v,f=box(0.5,0.5,0.3); p.add(xform(v,np.eye(3),[0,0,0.2]),f)
    v,f=cyl(0.06,0.05,barrel)
    p.add(xform(v,frame([1,0,0.35],[0,0,1]),[barrel/2+0.2,0,0.42]),f,
          fc["accent"])
    p.ports=[Port([0,0,0],[0,0,-1],[1,0,0],"struct_S",0.30,1)]
    p.grommets=[Grommet([0,0,0.12],"high_volt",0.1)]
    p.demands=[["high_volt",1.8]]
    # P3 — anchorable surfaces. The turret base box (0.5×0.5×0.3 at [0,0,0.2],
    # so x∈[-0.25,0.25], y∈[-0.25,0.25], z∈[0.05,0.35]) is primary structure.
    # The barrel is a gun tube — GLASS cls-0 (barrel axis is roughly +x+z tilted,
    # but the face declaration covers its muzzle tip as a no-weld zone).
    p.anchor_faces=[
        make_face([0,0,0.35],[0,0,1],0.25,0.25,2,u=[1,0,0]),       # box top cls-2
        make_face([ 0.25,0,0.2],[ 1,0,0],0.15,0.25,2,u=[0,1,0]),  # box +x cls-2
        make_face([-0.25,0,0.2],[-1,0,0],0.15,0.25,2,u=[0,1,0]),  # box -x cls-2
        make_face([0, 0.25,0.2],[0, 1,0],0.25,0.15,1,u=[1,0,0]),  # box +y cls-1
        make_face([0,-0.25,0.2],[0,-1,0],0.25,0.15,1,u=[1,0,0]),  # box -y cls-1
        make_face([barrel+0.2,0,0.42],[1,0,0],0.06,0.06,0,         # barrel tip: GLASS
                  u=[0,1,0])]
    return p.finalize()

def gen_cap(fc, seed=0):
    p=Part("terminator_cap",{},mass=8,silhouette=0.02,faction=fc["name"],
           era=fc["era"],color=fc["dark"],label="blanking cap")
    v,f=cyl(0.22,0.2,0.12,seg=8); p.add(xform(v,np.eye(3),[0,0,-0.06]),f)
    p.ports=[Port([0,0,0],[0,0,-1],[1,0,0],"struct_S",0.30,1)]
    # P3 — anchorable surfaces. A blanking cap is a sheet-metal disc; the only
    # honest weld surface is the mounting ring face at z=0 (cls-2 primary).
    # The domed underside at z=-0.12 is a pressed shell — cls-0, no weld.
    p.anchor_faces=[
        make_face([0,0,0],[0,0,1],0.22,0.22,2,u=[1,0,0]),  # mounting ring cls-2
        make_face([0,0,-0.12],[0,0,-1],0.20,0.20,0,         # dome underside: GLASS
                  u=[1,0,0])]
    return p.finalize()

# ---------------------------------------------------------------- assembler
def seg_hits_aabb(p0,p1,lo,hi):
    d=p1-p0; tmin,tmax=0.0,1.0
    for i in range(3):
        if abs(d[i])<1e-9:
            if p0[i]<lo[i] or p0[i]>hi[i]: return False
        else:
            t1,t2=(lo[i]-p0[i])/d[i],(hi[i]-p0[i])/d[i]
            if t1>t2: t1,t2=t2,t1
            tmin,tmax=max(tmin,t1),min(tmax,t2)
            if tmin>tmax: return False
    return True

class Assembler:
    def __init__(s, faction, seed, brief, generators, director=None):
        s.fc=faction; s.rng=random.Random(seed); s.brief=brief
        s.generators=generators
        s.director=director          # None => byte-identical legacy path
        s.trace=[{"ev":"seed","seed":seed,"faction":faction["name"]}]
        s.placed=[]; s.ledger=[]; s.clear=[]; s.struts=[]; s.hoses=[]
        s.strut_segs=[]   # decision records (endpoints), parallel to struts
        s.budget=dict(brief["budgets"]); s.mass_cap0=brief["budgets"]["mass"]
        s.requeue=[]; s.backjumps_left=4; s.bj_tried=set()
        s.tried_clusters=set(); s.ripups_left=4

    def log(s,**kw): s.trace.append(kw)

    # -- pure proposal: computes everything, mutates nothing ----------------
    def make_proposal(s, part, R, t, host, mates, plugs, strain):
        world=[(xform(v,R,t),f,c) for v,f,c in part.meshes]
        allv=np.vstack([w[0] for w in world])
        wcom=xform(part.com[None],R,t)[0] if part.com.any() else allv.mean(0)
        jpos=np.mean([m[0] for m in mates],axis=0)
        jaxis=mates[0][1]/np.linalg.norm(mates[0][1])
        clears=[]
        for clo,chi in part.clearances:
            c8=xform(np.array([[a,b,cc] for a in (clo[0],chi[0])
                     for b in (clo[1],chi[1]) for cc in (clo[2],chi[2])]),R,t)
            clears.append((c8.min(0),c8.max(0)))
        return dict(part=part,R=R,t=t,world=world,
                    lo=allv.min(0)-0.02,hi=allv.max(0)+0.02,wcom=wcom,
                    jpos=jpos,jaxis=jaxis,jtype=mates[0][3].type,
                    jcluster=len(plugs)==2,host=host,mates=mates,plugs=plugs,
                    strain=strain,clears=clears)

    def collides(s, prop, ignore=()):
        """Hard part-vs-part AABB overlap. Dumb legality — stays dumb."""
        for lo,hi,p in s.ledger:
            if p is prop["host"] or p in ignore: continue
            if np.all(prop["lo"]<hi) and np.all(lo<prop["hi"]): return p
        return None

    def clearance_conflicts(s, prop):
        """Soft-occupancy conflicts, BOTH directions: existing clearance
        volumes vs the new part's AABB, and the new part's own clearance
        volumes vs existing part AABBs (the direction v0.4 never checked).
        These are auctionable, not hard rejects."""
        out=[]
        for lo,hi,p in s.clear:
            if p is prop["host"]: continue
            if np.all(prop["lo"]<hi) and np.all(lo<prop["hi"]): out.append(p)
        for clo,chi in prop["clears"]:
            for lo,hi,p in s.ledger:
                if p is prop["host"]: continue
                if np.all(clo<hi) and np.all(lo<chi): out.append(p)
        seen=set(); uniq=[]
        for p in out:
            if id(p) not in seen: seen.add(id(p)); uniq.append(p)
        return uniq

    def open_ports(s, ptype):
        return sum(1 for p in s.placed for w in p.wports
                   if w[3].type==ptype and not w[3].filled)

    def subtree(s, part):
        out=[part]
        for ch in part.children: out+=s.subtree(ch)
        return out

    def auction(s, prop, sc, sp, conf):
        """Clearance-conflict auction. bid = prio x score x scarcity.
        Scarcity = 1/(1+open ports of that type): a part with nowhere else
        to go bids high. Incumbents multiply by subtree size — eviction
        cost is entrenchment. The hull never sells."""
        scar=1.0/(1+s.open_ports(sp.type))
        ch=sp.prio*max(sc,0.1)*scar
        inc=0.0; det=[]
        for p in conf:
            if p.parent is None:
                return False, dict(challenger=round(ch,2),incumbent="hull",
                                   reason="hull_unevictable")
            n=len(s.subtree(p))
            pscar=1.0/(1+s.open_ports(p.jtype))
            b=p._prio*max(p._bid_score,0.1)*pscar*n
            inc+=b; det.append(dict(part=p.label,prio=p._prio,
                                    score=round(p._bid_score,2),
                                    subtree=n,bid=round(b,2)))
        return ch>inc, dict(challenger=round(ch,2),incumbent=round(inc,2),
                            scarcity=round(scar,3),rivals=det)

    def uncommit(s, part, cause):
        """Transactional eviction: subtree cascade, root-ward mass
        un-propagation, ledger/clearance/strut removal, budget refund,
        host ports freed and requeued. The exact inverse of commit."""
        part.evicted=True
        for ch in list(part.children): s.uncommit(ch,"cascade_"+cause)
        host=part.parent
        node=host
        while node is not None:
            node.sub_mass-=part.mass; node.sub_mc-=part.mass*part.wcom
            node=node.parent
        host.children.remove(part)
        s.budget["mass"]+=part.mass; s.budget["silhouette"]+=part.silhouette
        s.budget["parts"]+=1
        s.ledger=[e for e in s.ledger if e[2] is not part]
        s.clear=[e for e in s.clear if e[2] is not part]
        s.struts=[st for st in s.struts if st[3]!=part.uid]
        s.strut_segs=[st for st in s.strut_segs if st["owner"]!=part.uid]
        for m in part._mates:
            m[3].filled=False
            if m[3].cluster: s.tried_clusters.discard((id(host),m[3].cluster))
            s.requeue.append((m,host))
        s.placed.remove(part)
        part.parent=None
        s.log(ev="evict",part=part.label,part_id=part.uid,cause=cause,
              result="removed")

    # -- the TRUE tree-fold: every root-side joint re-feels the subtree -----
    def chain_checks(s, prop):
        """Yield (label, jpos, jaxis, jtype, jcluster, outboard_mass,
        outboard_com, root_side_part) for candidate joint + every ancestor."""
        cm, cc = prop["part"].mass, prop["wcom"]
        yield (prop["part"].label, prop["jpos"], prop["jaxis"], prop["jtype"],
               prop["jcluster"], cm, cc, prop["host"])
        node=prop["host"]
        while node.parent is not None:
            m  = node.sub_mass + cm
            com= (node.sub_mc + cm*cc)/m
            yield (node.label, node.jpos, node.jaxis, node.jtype,
                   node.jcluster, m, com, node.parent)
            node=node.parent

    def moment_at(s, jpos, jaxis, mass, com):
        g=9.81*s.brief["design_g"]
        r=com-jpos; lever=np.linalg.norm(r-jaxis*np.dot(r,jaxis))
        return mass*g*lever

    def propose_strut(s, jpos, jaxis, com, root_side):
        """Brace from outboard com to a root-side neighbor. Anchor candidates
        include DIAGONALS (top/bottom edges) because triangulation pays:
        relief = 0.35 + 0.5*sin(angle strut vs member axis). Returns the
        highest-relief brace.

        Anchorable surface semantics (roadmap 3): if the neighbor declares
        anchor_vols, candidates clip to those volumes ONLY — no welding to
        glass. No declaration = whole-AABB anchorable (legacy). This
        restricts the repair-proposal space; it is mediation, not a new
        legality check."""
        best=None; viable=[]
        node=root_side
        def consider(cand):
            nonlocal best
            if s.director is not None: viable.append(cand)
            if best is None or cand["relief"]>best["relief"]+1e-9 or \
               (abs(cand["relief"]-best["relief"])<1e-9 and cand["L"]<best["L"]):
                best=cand
        while node is not None:
            wf=getattr(node,"w_anchor_faces",None)
            if wf is not None:
                # P3 face path — weld to a declared SURFACE. Relief gains a
                # normal-alignment term (pull-normal-on beats shear) and an
                # anchor_class strength factor; cls-0 faces yield no candidate.
                for fi,face in enumerate(wf):
                    for anchor,fn,cls in face_candidates(face,com):
                        d=np.linalg.norm(anchor-com)
                        # NaN comparisons are False, so a NaN d would slip the
                        # <0.15 guard and a NaN-relief brace would win (Cassandra
                        # P3 C2c). make_face blocks the source; this is the net.
                        if not (d>=0.15): continue
                        sdir=(anchor-com)/d
                        geom=0.35+0.5*np.linalg.norm(np.cross(sdir,jaxis))
                        align=0.6+0.4*abs(float(np.dot(sdir,fn)))  # [0.6,1.0]
                        relief=geom*align*ANCHOR_CLASS_RELIEF[cls]
                        consider(dict(a=com,b=anchor,relief=float(relief),
                                      anchor_part=node.label,L=float(d),
                                      vol=fi,face_cls=cls))
                node=node.parent
                continue
            # legacy AABB path — BYTE-IDENTICAL to v0.8 for non-face parts
            if getattr(node,"w_anchor",None) is not None:
                vols=list(enumerate(node.w_anchor))
            else:
                allv=np.vstack([w[0] for w in node.world])
                vols=[(-1,(allv.min(0),allv.max(0)))]
            for vi,(lo,hi) in vols:
                straight=np.clip(com,lo,hi)
                diag_lo=np.array([np.clip(com[0],lo[0],hi[0]),
                                  np.clip(com[1],lo[1],hi[1]),lo[2]])
                diag_hi=np.array([np.clip(com[0],lo[0],hi[0]),
                                  np.clip(com[1],lo[1],hi[1]),hi[2]])
                for anchor in (straight,diag_lo,diag_hi):
                    d=np.linalg.norm(anchor-com)
                    if d<0.15: continue
                    sdir=(anchor-com)/d
                    relief=0.35+0.5*np.linalg.norm(np.cross(sdir,jaxis))
                    consider(dict(a=com,b=anchor,relief=float(relief),
                                  anchor_part=node.label,L=float(d),vol=vi))
            node=node.parent
        # on_repair_choice (3b): PROMOTED — director-gated, rng-free,
        # reorder-only. The legacy `best`-accumulator above remains the
        # byte-identical path and stays authoritative when director is None
        # OR when on_repair_choice returns None. When a director IS attached,
        # ≥2 braces are viable, AND its repair policy is active (flag ON), it
        # may hand back a permutation; we then commit the brace at the HEAD of
        # that permutation INSTEAD of the legacy argmin. Byte-identity on the
        # canonical fleet is preserved by the director itself: rank_braces uses
        # the SAME (-relief, L) key the accumulator does, so the director only
        # returns a non-None permutation when its head genuinely differs from
        # the legacy committed brace (never on canonical input) — otherwise it
        # returns None and the accumulator's `best` rides through untouched.
        if s.director is not None and len(viable)>=2:
            pick=s.director.on_repair_choice(
                viable,s._repair_context(jpos,jaxis))
            if pick is not None:
                viable=[viable[i] for i in pick]
                best=viable[0]
                s.log(ev="repair_choice",anchor=best["anchor_part"],
                      among=len(pick),relief=round(best["relief"],3))
        return best

    def validate(s, prop, ignore=()):
        """Transactional gate: collision + full spine fold + repairs. Returns
        (ok, repairs, events). NOTHING is mutated here. `ignore` carries
        auction-won rivals whose space is already promised to this part."""
        ev=[]
        hit=s.collides(prop,ignore)
        if hit:
            prop["_blocker"]=hit
            return False,[],[dict(ev="reject",part=prop["part"].label,
                                  cause="ledger",blocker=hit.label)]
        repairs=[]
        for (lbl,jpos,jaxis,jtype,jclus,m,com,rootside) in s.chain_checks(prop):
            cap,acap=joint_cap(jtype,jclus)
            sf=s.fc["safety_factor"]; cap/=sf; acap/=sf
            M=s.moment_at(jpos,jaxis,m,com)
            if M<=cap: continue
            # up to two composed braces per joint (jury strut + lift strut)
            jreps=[]; M2=M
            for k in range(2):
                rep=s.propose_strut(jpos,jaxis,com,rootside)
                if not rep: break
                M2*= (1-rep["relief"])
                jreps.append(rep)
                if M2<=cap: break
            metrics=dict(joint=lbl,moment_before=int(M),cap=int(cap),
                         struts=len(jreps),
                         relief=float(round(1-M2/M,2)) if jreps else 0.0,
                         moment_after=int(M2))
            if jreps and M2<=cap:
                repairs+=jreps
                ev.append(dict(ev="repair",cause="moment_over_cap",
                               op="spawn_strut",target=prop["part"].label,
                               anchor=jreps[0]["anchor_part"],metrics=metrics,
                               result="accepted"))
            else:
                ev.append(dict(ev="reject",part=prop["part"].label,
                               cause="moment_over_cap",metrics=metrics,
                               result="strut_insufficient" if jreps
                                      else "no_anchor"))
                return False,[],ev
        # axial: engine thrust flows root-ward
        if getattr(prop["part"],"thrust_axial",False):
            thrust=prop["part"].mass*9.81*s.brief["design_g"]
            node=prop["host"]; jtype=prop["jtype"]; jclus=prop["jcluster"]
            _,acap=joint_cap(jtype,jclus); acap/=s.fc["safety_factor"]
            if thrust>acap:
                return False,[],[dict(ev="reject",part=prop["part"].label,
                    cause="axial_over_cap",
                    metrics=dict(thrust=int(thrust),cap=int(acap)))]
        # budget at spend — with debt culture
        over=prop["part"].mass-s.budget["mass"]
        if over>0:
            if over<=s.fc["debt"]*s.mass_cap0:
                ev.append(dict(ev="debt",part=prop["part"].label,
                               cause="mass_overdraft",kg=int(over),
                               result="tolerated"))
            else:
                return False,[],[dict(ev="reject",part=prop["part"].label,
                                      cause="mass_budget",kg_over=int(over))]
        return True,repairs,ev

    def commit(s, prop, repairs, events):
        part=prop["part"]
        part.world=prop["world"]; part.R,part.t=prop["R"],prop["t"]
        part.wcom=prop["wcom"]
        part.wports=[(xform(pt.pos[None],prop["R"],prop["t"])[0],
                      prop["R"]@pt.N,prop["R"]@pt.up,pt) for pt in part.ports]
        part.wgrom=[(xform(g.pos[None],prop["R"],prop["t"])[0],g)
                    for g in part.grommets]
        part.w_anchor=None
        if part.anchor_vols is not None:    # 8 corners — Lesson 3
            part.w_anchor=[]
            for lo,hi in part.anchor_vols:
                c8=xform(np.array([[a,b,cc] for a in (lo[0],hi[0])
                         for b in (lo[1],hi[1]) for cc in (lo[2],hi[2])]),
                         prop["R"],prop["t"])
                part.w_anchor.append((c8.min(0),c8.max(0)))
        part.w_anchor_faces=None            # P3: faces -> world (preferred path)
        if part.anchor_faces is not None:
            part.w_anchor_faces=[xform_face(fa,prop["R"],prop["t"])
                                 for fa in part.anchor_faces]
        part.parent=prop["host"]; part.jpos=prop["jpos"]
        part.jaxis=prop["jaxis"]; part.jtype=prop["jtype"]
        part.jcluster=prop["jcluster"]
        part._mates=prop["mates"]
        part._prio=prop["mates"][0][3].prio
        part._bid_score=prop.get("score",0.0)
        prop["host"].children.append(part)
        node=part                       # propagate subtree mass root-ward
        while node is not None:
            node.sub_mass+=part.mass; node.sub_mc+=part.mass*part.wcom
            node=node.parent
        s.ledger.append((prop["lo"],prop["hi"],part))
        for lo,hi in prop["clears"]: s.clear.append((lo,hi,part))
        s.placed.append(part)
        s.budget["mass"]-=part.mass; s.budget["silhouette"]-=part.silhouette
        s.budget["parts"]-=1
        for rep in repairs:
            a,b=rep["a"],rep["b"]; d=b-a; L=np.linalg.norm(d); z=d/L
            up=np.array([0,0,1.0]) if abs(z[2])<0.95 else np.array([1.0,0,0])
            v,f=cyl(0.06,0.06,L,seg=6)
            s.struts.append((xform(v,frame(z,up),(a+b)/2),f,s.fc["dark"],
                             part.uid))
            s.strut_segs.append(dict(kind="strut",
                a=[float(x) for x in a],b=[float(x) for x in b],
                owner=part.uid,relief=round(float(rep["relief"]),3),
                anchor=rep["anchor_part"],vol=rep.get("vol",-1),
                face_cls=rep.get("face_cls")))   # P3: which class took the weld
        for m in prop["mates"]: m[3].filled=True
        for pl in prop["plugs"]: pl.filled=True
        if prop["strain"]>0.001:
            spos,sN,sup,sp=prop["mates"][0]
            v,f=cyl(sp.size*0.55,sp.size*0.55,0.1,seg=8)
            s.struts.append((xform(v,frame(sN,sup),prop["jpos"]+sN*0.02),
                             f,s.fc["accent"],part.uid))
            s.strut_segs.append(dict(kind="collar",
                pos=[float(x) for x in prop["jpos"]+sN*0.02],
                axis=[float(x) for x in sN],up=[float(x) for x in sup],
                r=float(sp.size*0.55),owner=part.uid,
                strain=round(float(prop["strain"]),3)))
            events.append(dict(ev="adapter",part=part.label,
                               metrics=dict(strain=round(prop["strain"],3)),
                               result="collar_spawned"))
        for e in events: s.log(**e)
        s.log(ev="commit",part=part.label,part_id=part.uid,
              host_port=prop["mates"][0][3].pid,
              part_port=prop["plugs"][0].pid,
              metrics=dict(strain=round(prop["strain"],3),
                           mass_left=int(s.budget["mass"])))

    def _tie_context(s, sp, host):
        """Read-only context handed to director.on_tie. No mutable internals
        leak: families is a fresh Counter, budget is a shallow copy."""
        from collections import Counter
        return dict(port_type=sp.type, port_prio=sp.prio,
                    placed_families=Counter(p.family for p in s.placed),
                    budget=dict(s.budget), faction=s.fc["name"])

    def _repair_context(s, jpos, jaxis):
        """Read-only context for director.on_repair_choice (3b). No mutable
        internals leak: positions are fresh copies."""
        return dict(jpos=[float(x) for x in jpos],
                    jaxis=[float(x) for x in jaxis],
                    faction=s.fc["name"])

    def run(s, hull_gen=gen_hull):
        hull=hull_gen(s.fc,seed=s.rng.randint(0,99999))
        hull.world=[(v,f,c) for v,f,c in hull.meshes]
        hull.wports=[(pt.pos.copy(),pt.N.copy(),pt.up.copy(),pt)
                     for pt in hull.ports]
        hull.wgrom=[(g.pos.copy(),g) for g in hull.grommets]
        hull.wcom=np.zeros(3); hull.R=np.eye(3); hull.t=np.zeros(3)
        hull.w_anchor=None if hull.anchor_vols is None else \
            [(np.array(lo,float),np.array(hi,float))
             for lo,hi in hull.anchor_vols]
        hull.w_anchor_faces=None if hull.anchor_faces is None else \
            [xform_face(fa,np.eye(3),np.zeros(3)) for fa in hull.anchor_faces]
        allv=np.vstack([w[0] for w in hull.world])
        s.ledger.append((allv.min(0)-0.02,allv.max(0)+0.02,hull))
        s.placed.append(hull)
        s.budget["mass"]-=hull.mass; s.budget["silhouette"]-=hull.silhouette
        s.budget["parts"]-=1
        s.log(ev="commit",part="core_hull",part_id=hull.uid)
        openq=[(wp,hull) for wp in hull.wports]
        openq.sort(key=lambda e:-e[0][3].prio)
        i=0
        while i<len(openq):
            (spos,sN,sup,sp),host=openq[i]; i+=1
            if sp.filled or getattr(host,"evicted",False): continue
            if sp.cluster:
                ck=(id(host),sp.cluster)
                if ck in s.tried_clusters: continue
                s.tried_clusters.add(ck)
            if s.budget["parts"]<=0:
                s.log(ev="budget_exhausted",which="parts"); break
            cands=[]
            for gen in s.generators:
                part=gen(s.fc,seed=s.rng.randint(0,999999))
                clusters={}
                for pt in part.ports:
                    if pt.gender!=1: continue
                    clusters.setdefault(pt.cluster or pt.pid,[]).append(pt)
                for key,plugs in clusters.items():
                    if plugs[0].type!=sp.type: continue
                    if plugs[0].tags and sp.tags and plugs[0].tags!=sp.tags:
                        continue
                    strain=abs(plugs[0].size-sp.size)/max(plugs[0].size,sp.size)
                    if strain>0.15: continue
                    if len(plugs)==2:
                        mates=[w for w in host.wports
                               if w[3].cluster==sp.cluster and
                                  w[3].type==sp.type and not w[3].filled]
                        if len(mates)!=2: continue
                        d_p=np.linalg.norm(plugs[1].pos-plugs[0].pos)
                        d_s=np.linalg.norm(mates[1][0]-mates[0][0])
                        if abs(d_p-d_s)>0.02: continue
                        cands.append((part,plugs,mates,strain))
                    elif len(plugs)==1 and not sp.cluster:
                        cands.append((part,plugs,[(spos,sN,sup,sp)],strain))
            if not cands:
                if s.fc["caps_unused"] and sp.type=="struct_S":
                    cap=gen_cap(s.fc)
                    R,t,_=s.mate(cap,[cap.ports[0]],[(spos,sN,sup,sp)])
                    prop=s.make_proposal(cap,R,t,host,[(spos,sN,sup,sp)],
                                         [cap.ports[0]],0.0)
                    ok,reps,ev=s.validate(prop)
                    if ok:
                        s.commit(prop,reps,ev)
                        s.log(ev="terminate",port=sp.pid,result="capped")
                else:
                    s.log(ev="port_open",port=sp.pid,
                          result="left_open" if not s.fc["caps_unused"]
                                 else "no_candidate")
                continue
            def score(c):
                part,_,_,strain=c
                n=sum(1 for q in s.placed if q.family==part.family)
                v=s.brief["wants"].get(part.family,0.0)/(1+1.5*n)
                if abs(spos[1])>0.3:
                    mir=np.array([spos[0],-spos[1],spos[2]])
                    for q in s.placed:
                        if q.jpos is not None and \
                           np.linalg.norm(q.jpos-mir)<0.2 and \
                           q.family==part.family: v+=2.5; break
                v+=part.silhouette*max(s.budget["silhouette"],0)*0.5
                v+=s.fc["strain_taste"]*strain
                v+=s.rng.uniform(0,s.fc["blasphemy"])
                return v
            # one score() call per candidate, in list order — preserves the
            # rng stream exactly as the old sort(key=score) did
            scored=sorted(((score(c),c) for c in cands),key=lambda e:-e[0])
            # on_tie (3a): director-gated, genuine-tie-only, rng-free,
            # reorder-only. No effect when director is None.
            if s.director is not None and len(scored)>=2:
                s0=scored[0][0]; s1=scored[1][0]
                if s0-s1<s.director.tie_eps:          # genuine tie ONLY
                    ranked=[c for _,c in scored]        # candidate tuples
                    new_order=s.director.on_tie(ranked,s._tie_context(sp,host))
                    if new_order is not None:
                        scored=[(scored[i][0],scored[i][1]) for i in new_order]
                        s.log(ev="tie_break",port=sp.pid,
                              among=[c[0].label for c in ranked],
                              chose=ranked[new_order[0]][0].label)
            blockers=[]; placed_one=False
            for sc,(part,plugs,mates,strain) in scored:
                R,t,res=s.mate(part,plugs,mates)
                if res>0.02:
                    s.log(ev="reject",part=part.label,cause="cluster_residual",
                          metrics=dict(residual=round(float(res),4)))
                    continue
                prop=s.make_proposal(part,R,t,host,mates,plugs,strain)
                prop["score"]=sc
                conf=s.clearance_conflicts(prop)
                if conf:
                    won,bids=s.auction(prop,sc,sp,conf)
                    s.log(ev="auction",part=part.label,port=sp.pid,
                          rivals=[p.label for p in conf],metrics=bids,
                          result="challenger_wins" if won
                                 else "incumbent_holds")
                    if not won: continue
                ok,reps,ev=s.validate(prop,ignore=conf)
                if not ok:
                    for e in ev: s.log(**e)
                    if prop.get("_blocker") is not None:
                        blockers.append(prop["_blocker"])
                    continue
                for p in sorted(conf,key=lambda p:-s.placed.index(p)):
                    if p in s.placed: s.uncommit(p,"auction_evict")
                s.commit(prop,reps,ev)
                for wp in part.wports:
                    if not wp[3].filled: openq.append((wp,part))
                placed_one=True
                break
            # conflict-directed backjump: every candidate died on the same
            # committed geometry — evict the most recent blocker and retry
            if not placed_one and blockers and s.backjumps_left>0 \
               and sp.prio>=7:
                live=[p for p in set(blockers) if p in s.placed
                      and p.parent is not None
                      and (sp.pid,p.uid) not in s.bj_tried]
                if live:
                    target=max(live,key=lambda p:s.placed.index(p))
                    s.bj_tried.add((sp.pid,target.uid))
                    s.backjumps_left-=1
                    s.log(ev="backjump",port=sp.pid,
                          conflict_set=sorted(set(p.uid for p in blockers)),
                          evicted=target.uid,jumps_left=s.backjumps_left)
                    s.uncommit(target,"backjump")
                    if sp.cluster:
                        s.tried_clusters.discard((id(host),sp.cluster))
                    i-=1                      # retry this port
            if s.requeue:                     # freed host ports re-enter
                openq+=[(w,h) for w,h in s.requeue
                        if not getattr(h,"evicted",False) and not w[3].filled]
                s.requeue=[]
            openq[i:]=sorted(openq[i:],key=lambda e:-e[0][3].prio)
        s.route()
        return s

    def mate(s, part, plug_ports, sock):
        if len(plug_ports)==1:
            pp=plug_ports[0]; spos,sN,sup,sp=sock[0]
            R=frame(-sN,sup)@frame(pp.N,pp.up).T
            return R, spos-R@pp.pos, 0.0
        p0,p1=plug_ports; best=None
        for (q0,N0,u0,_),(q1,N1,u1,_) in ((sock[0],sock[1]),(sock[1],sock[0])):
            zP=(p0.N+p1.N); zP/=np.linalg.norm(zP)
            xP=(p1.pos-p0.pos); xP/=np.linalg.norm(xP)
            BP=np.stack([xP,np.cross(zP,xP),zP],axis=1)
            zS=-(N0+N1); zS/=np.linalg.norm(zS)
            xS=(q1-q0); xS/=np.linalg.norm(xS)
            BS=np.stack([xS,np.cross(zS,xS),zS],axis=1)
            R=BS@BP.T
            t=(q0+q1)/2-R@(p0.pos+p1.pos)/2
            res=max(np.linalg.norm(R@p0.pos+t-q0),np.linalg.norm(R@p1.pos+t-q1))
            if float(np.dot(R@p0.up,u0))>0.5 and (best is None or res<best[2]):
                best=(R,t,res)
        return best if best else (np.eye(3),np.zeros(3),9e9)

    # ------------------------------------------- routing v2: channel graph
    LOOM_DISCOUNT = 0.55

    def build_channels(s):
        """Channel graph: nodes are grommets; edges are channels with real
        capacity (min endpoint conduit_size), occupancy, and native types.
        Proximity edges between segregation-incompatible grommet types are
        never built (pruned, counted)."""
        nodes=[]; offs={}
        for p in s.placed:
            offs[id(p)]=len(nodes)
            for wpos,g in p.wgrom: nodes.append((wpos,g.ctype,p,g))
        edges=[]; adj={i:[] for i in range(len(nodes))}
        def add(a,b,base,kind):
            edges.append(dict(a=a,b=b,base=base,kind=kind,
                              cap=min(nodes[a][3].size,nodes[b][3].size),
                              used=0.0,occ=[]))
            adj[a].append(len(edges)-1); adj[b].append(len(edges)-1)
        for p in s.placed:
            o=offs[id(p)]
            for a,b in p.gedges:
                d=np.linalg.norm(nodes[o+a][0]-nodes[o+b][0])
                add(o+a,o+b,0.2*d,"internal")
        pruned=dict(seg_pruned=0,clear_pruned=0)
        for i in range(len(nodes)):
            for j in range(i+1,len(nodes)):
                if nodes[i][2] is nodes[j][2]: continue
                d=np.linalg.norm(nodes[i][0]-nodes[j][0])
                if d>4.5: continue
                if not seg_share_ok(nodes[i][1],nodes[j][1]):
                    pruned["seg_pruned"]+=1; continue
                if any(seg_hits_aabb(nodes[i][0],nodes[j][0],lo,hi)
                       for lo,hi,_ in s.clear):
                    pruned["clear_pruned"]+=1; continue
                kind="leap" if d>1.2 else "jump"
                add(i,j,(4.0 if kind=="leap" else 1.0)*d,kind)
        return nodes,edges,adj,offs,pruned

    def astar2(s,nodes,edges,adj,a,b,ctype,dia,cap_check=True):
        """A* over channels. Admission: remaining capacity (unless relaxed),
        native-type share rules, occupant share rules. Cost: base x loom
        discount when a compatible hose already rides the channel."""
        import heapq
        goal=nodes[b][0]; pq=[(0.0,0.0,a,())]; best={}
        while pq:
            f,g,u,path=heapq.heappop(pq)
            if u==b: return list(path)
            if u in best and best[u]<=g: continue
            best[u]=g
            for eid in adj[u]:
                e=edges[eid]
                if cap_check and e["used"]+dia>e["cap"]+1e-9: continue
                if not (seg_share_ok(ctype,nodes[e["a"]][1]) and
                        seg_share_ok(ctype,nodes[e["b"]][1])): continue
                if not all(seg_share_ok(ctype,oc) for oc,_,_ in e["occ"]):
                    continue
                v=e["b"] if e["a"]==u else e["a"]
                c=e["base"]*(s.LOOM_DISCOUNT
                             if any(oc==ctype for oc,_,_ in e["occ"]) else 1.0)
                heapq.heappush(pq,(g+c+np.linalg.norm(nodes[v][0]-goal),
                                   g+c,v,path+(eid,)))
        return None

    def release_net(s,net,edges):
        for eid in net["path"]:
            e=edges[eid]
            e["occ"]=[o for o in e["occ"] if o[2] is not net]
            e["used"]-=net["dia"]
        s.hoses.remove(net["hose"])
        net["path"]=None; net["hose"]=None

    def commit_net(s,net,path,nodes,edges,si,src,supply_left):
        loom=0; u=si; seq=[si]; kinds=[]
        for eid in path:
            e=edges[eid]
            if any(oc==net["ctype"] for oc,_,_ in e["occ"]): loom+=1
            e["used"]+=net["dia"]; e["occ"].append((net["ctype"],net["dia"],net))
            kinds.append(e["kind"])
            u=e["b"] if e["a"]==u else e["a"]; seq.append(u)
        hose={"pts":[list(map(float,nodes[x][0])) for x in seq],
              "kinds":kinds,"ctype":net["ctype"],"dia":net["dia"]}
        net["path"]=list(path); net["hose"]=hose; s.hoses.append(hose)
        m=dict(hops=len(path),leaps=kinds.count("leap"),
               supply_left=round(supply_left,1))
        if loom: m["loomed"]=loom
        if net["ripped"]: m["rerouted"]=True
        s.log(ev="hose",frm=src.label,to=net["part"].label,metrics=m)

    def try_ripup(s,nodes,edges,adj,si,net):
        """Congestion negotiation, EDA-style: find the relaxed path, evict
        the squatters on its over-subscribed channels (bounded, logged),
        return the victims for rerouting. Victims get no second rip."""
        if s.ripups_left<=0: return None
        relaxed=s.astar2(nodes,edges,adj,si,net["di"],net["ctype"],
                         net["dia"],cap_check=False)
        if relaxed is None: return None
        victims=[]
        for eid in relaxed:
            e=edges[eid]
            if e["used"]+net["dia"]>e["cap"]+1e-9:
                for _,_,vn in e["occ"]:
                    if vn not in victims: victims.append(vn)
        if not victims or len(victims)>s.ripups_left: return None
        for vn in victims:
            s.ripups_left-=1; vn["ripped"]=True
            s.release_net(vn,edges)
            s.log(ev="rip_up",victim=vn["part"].label,
                  instigator=net["part"].label,cause="congestion",
                  metrics=dict(rips_left=s.ripups_left))
        return victims

    def route(s):
        nodes,edges,adj,offs,pruned=s.build_channels()
        ctypes=sorted({ct for _,ct,_,_ in nodes})
        if len(ctypes)>1:
            s.log(ev="channel_graph",metrics=dict(nodes=len(nodes),
                  edges=len(edges),conduits=ctypes,**pruned))
        pool={}                                   # supply decrement
        for p in s.placed:
            for c,r in p.supplies: pool[(id(p),c)]=[p,c,r]
        nets=[]; seen=set()
        for p in s.placed:
            for c,rate in p.demands:
                if (p.uid,c) in seen: continue
                taps=[offs[id(p)]+k for k,(w,g) in enumerate(p.wgrom)
                      if g.ctype==c]
                if not taps: continue
                seen.add((p.uid,c))
                nets.append(dict(di=taps[0],part=p,ctype=c,rate=rate,
                                 dia=round(0.025+0.01*rate,3),
                                 ripped=False,path=None,hose=None,src=None))
        queue=list(nets)
        while queue:
            net=queue.pop(0)
            if net["src"] is None:
                live=[(k,v) for k,v in pool.items()
                      if v[1]==net["ctype"] and v[2]>=net["rate"]]
                if not live:
                    s.log(ev="demand_unmet",part=net["part"].label,
                          cause="supply_saturated")
                    continue
                k,(sp_,_,_)=min(live,key=lambda e:np.linalg.norm(
                    e[1][0].wgrom[0][0]-nodes[net["di"]][0]))
                net["src"]=sp_; net["pkey"]=k
            si=offs[id(net["src"])]
            path=s.astar2(nodes,edges,adj,si,net["di"],net["ctype"],
                          net["dia"])
            if path is None and not net["ripped"]:
                victims=s.try_ripup(nodes,edges,adj,si,net)
                if victims:
                    path=s.astar2(nodes,edges,adj,si,net["di"],
                                  net["ctype"],net["dia"])
                    queue+=victims            # they reroute after me
            if path is None:
                relaxed=s.astar2(nodes,edges,adj,si,net["di"],net["ctype"],
                                 net["dia"],cap_check=False)
                cause="congestion" if relaxed else "no_route"
                if net["ripped"]:
                    pool[net["pkey"]][2]+=net["rate"]   # refund the supply
                s.log(ev="demand_unmet",part=net["part"].label,cause=cause)
                continue
            if not net["ripped"]:
                pool[net["pkey"]][2]-=net["rate"]
            s.commit_net(net,path,nodes,edges,si,net["src"],
                         pool[net["pkey"]][2])

# ----------------------------------------------------------------- factions
GUILD=dict(name="High Guild",era=812,hull="#d8d2c4",accent="#b08d3f",
           dark="#3a4150",glow="#7fd1e3",safety_factor=2.0,blasphemy=0.1,
           strain_taste=-3.0,caps_unused=True,hose="shroud",debt=0.0)
FERAL=dict(name="Feral",era=977,hull="#7d6a58",accent="#b4502e",
           dark="#46413a",glow="#e8a33d",safety_factor=1.1,blasphemy=0.9,
           strain_taste=+1.5,caps_unused=False,hose="catenary",debt=0.05)

def build(faction,seed,wants,heavy=1.0,span=3.2,parent=None,mutation=None,
          extra_gens=(),director=None):
    gens=[gen_tank,gen_engine,
          lambda fc,seed=0: gen_wing(fc,seed,span=span,hand=1),
          lambda fc,seed=0: gen_wing(fc,seed,span=span,hand=-1),
          lambda fc,seed=0: gen_cannon(fc,seed,heavy=heavy),
          gen_antenna,gen_pod]+list(extra_gens)
    brief=dict(design_g=2.5,wants=wants,
               budgets=dict(mass=11000,silhouette=3.2,parts=14))
    a=Assembler(faction,seed,brief,gens,director=director).run()
    a.lineage=dict(parent=parent,mutation=mutation,
                   gen_params=dict(seed=seed,heavy=heavy,span=span))
    return a

def export(ships,path):
    out={"schema":"kitmash/0.6","ships":[]}
    for name,a,offset,plate in ships:
        meshes=[]
        for p in a.placed:
            for v,f,c in p.world:
                meshes.append({"v":(v+offset).round(3).tolist(),
                               "f":[list(t) for t in f],"c":c,"label":p.label})
        for v,f,c,_ in a.struts:
            meshes.append({"v":(v+offset).round(3).tolist(),
                           "f":[list(t) for t in f],"c":c,"label":"strut/adapter"})
        hoses=[{"pts":[[round(x+o,3) for x,o in zip(pt,offset)]
                       for pt in h["pts"]],
                "kinds":h["kinds"],"style":a.fc["hose"],
                "ctype":h.get("ctype","fuel"),"dia":h.get("dia",0.037)}
               for h in a.hoses]
        out["ships"].append({"name":name,"plate":plate,
            "offset":[float(x) for x in offset],
            "faction":a.fc["name"],"era":a.fc["era"],
            "meshes":meshes,"hoses":hoses,"trace":a.trace,"lineage":a.lineage,
            "stats":dict(parts=len(a.placed),
                         mass=int(sum(p.mass for p in a.placed)),
                         struts=len(a.struts),hoses=len(a.hoses))})
    json.dump(out,open(path,"w"))
    return out

if __name__=="__main__":
    import os, sys
    outdir=os.path.dirname(os.path.abspath(
        sys.argv[1] if len(sys.argv)>1 else "./fleet.json"))
    os.makedirs(outdir,exist_ok=True)
    dest=sys.argv[1] if len(sys.argv)>1 else "./fleet.json"
    wants_g={"engine":3.0,"fuel_tank":2.5,"wing":2.0,"heavy_cannon":1.4,
             "antenna":0.8,"sensor_pod":0.6}
    wants_f={"engine":3.0,"fuel_tank":2.5,"wing":2.0,"heavy_cannon":2.2,
             "sensor_pod":1.0,"antenna":0.4}
    # FV-δ: a feral hull that wants radiators — the clearance hog exists to
    # exercise auctions and backjumps. α/β/γ remain untouched regression
    # anchors (same seeds, same rng stream, same gens).
    wants_d={"engine":3.0,"fuel_tank":2.5,"wing":2.0,"heavy_cannon":1.8,
             "radiator":2.4,"sensor_pod":1.2,"antenna":0.8}
    A=build(GUILD,7,wants_g,heavy=1.0,span=3.0)
    B=build(GUILD,7,wants_g,heavy=1.7,span=3.9,
            parent="GS-α",mutation="heavy 1.0→1.7, span 3.0→3.9")
    C=build(FERAL,23,wants_f,heavy=1.4,span=3.4)
    D=build(FERAL,41,wants_d,heavy=1.2,span=3.2,extra_gens=[gen_radiator],
            parent="FV-γ",mutation="+radiator gene, wants reshuffled")
    # FV-ε: electrified feral — reactor supplies high_volt, turrets demand
    # it. Exercises routing v2: channel capacities, segregation pruning
    # (the high-volt nets may not ride the fuel trunk), the loom discount.
    wants_e={"engine":3.0,"fuel_tank":2.5,"wing":1.6,"heavy_cannon":0.9,
             "turret":2.6,"reactor":2.3,"sensor_pod":0.4,"antenna":0.3}
    E=build(FERAL,101,wants_e,heavy=1.0,span=3.0,
            extra_gens=[gen_reactor,gen_turret],
            parent="FV-γ",mutation="+reactor/turret genes, electrified")
    data=export([("GS-α  «Lawful Mean»",A,np.array([0,-7.5,0]),"Plate XLVII"),
                 ("GS-β  «Heavier Daughter»",B,np.array([0,0,0]),"Plate XLVIII"),
                 ("FV-γ  «Tape Holds»",C,np.array([0,7.5,0]),"Plate XLIX"),
                 ("FV-δ  «Cold Shoulder»",D,np.array([0,15,0]),"Plate L"),
                 ("FV-ε  «Loom»",E,np.array([0,22.5,0]),"Plate LI")],dest)
    for sh in data["ships"]:
        print(sh["name"],sh["stats"])
        for ev in sh["trace"]:
            if ev["ev"] in ("repair","reject","adapter","debt","hose",
                            "demand_unmet","port_open","spine_fail",
                            "auction","evict","backjump","channel_graph",
                            "rip_up"):
                print("   ",{k:v for k,v in ev.items() if k!="part_id"})
