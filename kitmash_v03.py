"""KitMash v0.3 — host-agnostic reference implementation (vertical slice).

Ports are points. The mesh is a cached opinion; the JSON is the truth.
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

def xform(verts, R, t):
    return verts @ R.T + t

def frame(N, up):
    z = N/np.linalg.norm(N)
    x = up - z*np.dot(up,z); x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x,y,z],axis=1)          # columns = basis

# ------------------------------------------------------------------- schema
class Port:
    def __init__(s, pos, N, up, ptype, size, gender, prio=5, sym=0, cluster="",
                 tags=""):
        s.pos=np.array(pos,float); s.N=np.array(N,float); s.up=np.array(up,float)
        s.type=ptype; s.size=size; s.gender=gender; s.prio=prio
        s.sym=sym; s.cluster=cluster; s.filled=False; s.tags=tags

class Grommet:
    def __init__(s,pos,ctype,size=0.1):
        s.pos=np.array(pos,float); s.ctype=ctype; s.size=size

class Part:
    def __init__(s, family, gen_params, mass, silhouette, faction, era,
                 color, label=""):
        s.family=family; s.gen_params=gen_params; s.mass=mass
        s.silhouette=silhouette; s.faction=faction; s.era=era; s.color=color
        s.label=label or family
        s.meshes=[]            # (verts, faces, color)
        s.ports=[]; s.grommets=[]; s.gedges=[]   # local grommet graph
        s.supplies=[]; s.demands=[]              # (ctype, rate)
        s.clearances=[]                          # AABBs needing emptiness
        s.com=np.zeros(3)
    def add(s,verts,faces,color=None): s.meshes.append((verts,faces,color or s.color))
    def aabb(s):
        allv=np.vstack([m[0] for m in s.meshes])
        return allv.min(0), allv.max(0)

CAPACITY = {  # port_type: (moment N*m, axial N) — the shipwright's table
    "struct_S": (2_000, 15_000), "struct_M": (40_000, 120_000),
    "struct_L": (900_000, 2_500_000), "mount_rail": (25_000, 60_000)}
RAIL_CLUSTER_BONUS = 1.3

# --------------------------------------------------------------- generators
def gen_hull(fc, scale=1.0, seed=0):
    p = Part("core_hull", {"scale":scale,"seed":seed}, mass=4000*scale,
             silhouette=0.9, faction=fc["name"], era=fc["era"], color=fc["hull"])
    L,W,H = 7.0*scale, 2.2, 1.8
    v,f = box(L,W,H); p.add(v,f)
    v,f = cyl(0.9,0.5,1.6); R=frame([1,0,0],[0,0,1])
    p.add(xform(v,R,[L/2+0.7,0,0]),f, fc["accent"])    # nose
    up=[0,0,1]
    p.ports += [
        Port([-L/2,0,0],[-1,0,0],up,"struct_M",1.0,0,prio=9),          # aft (engine)
        Port([0, W/2,0],[0, 1,0],up,"struct_M",1.0,0,prio=8,tags="side_R"),
        Port([0,-W/2,0],[0,-1,0],up,"struct_M",1.0,0,prio=8,tags="side_L"),
        Port([ 1.8,0, H/2],[0,0, 1],[1,0,0],"struct_M",0.8,0,prio=7),  # dorsal tank
        Port([-1.5,0, H/2],[0,0, 1],[1,0,0],"struct_S",0.30,0,prio=4), # antenna
        Port([ 0.5,0,-H/2],[0,0,-1],[1,0,0],"struct_S",0.30,0,prio=3),
        Port([ 2.6,0,-H/2],[0,0,-1],[1,0,0],"struct_S",0.30,0,prio=3)]
    # spinal grommet channel, pre-authored
    g=[Grommet([x,0,H/2-0.15],"fuel") for x in (-L/2+0.3, -1.0, 1.0, 1.8, L/2-0.6)]
    p.grommets=g; p.gedges=[(i,i+1) for i in range(len(g)-1)]
    return p

def gen_tank(fc, seed=0):
    p=Part("fuel_tank",{"seed":seed},mass=900,silhouette=0.45,
           faction=fc["name"],era=fc["era"],color=fc["accent"],label="fuel tank")
    v,f=cyl(0.55,0.55,2.4); R=frame([1,0,0],[0,0,1])
    p.add(xform(v,R,[0,0,0.55]),f)
    v,f=box(0.7,0.7,0.12); p.add(xform(v,np.eye(3),[0,0,0.05]),f,fc["hull"])
    p.ports=[Port([0,0,0],[0,0,-1],[1,0,0],"struct_M",0.8,1)]
    p.grommets=[Grommet([0,0,0.1],"fuel"),Grommet([0.6,0,0.55],"fuel")]
    p.gedges=[(0,1)]; p.supplies=[("fuel",3.0)]
    return p

def gen_engine(fc, size=1.0, seed=0):
    p=Part("engine",{"size":size,"seed":seed},mass=1400*size,silhouette=0.55,
           faction=fc["name"],era=fc["era"],color=fc["dark"],label="engine")
    v,f=cyl(0.75*size,0.95*size,2.0); R=frame([1,0,0],[0,0,1])
    p.add(xform(v,R,[-1.0,0,0]),f)
    v,f=cyl(0.95*size,0.55*size,0.7)
    p.add(xform(v,R,[-2.3,0,0]),f,fc["glow"])
    p.ports=[Port([0,0,0],[1,0,0],[0,0,1],"struct_M",1.0,1)]
    p.grommets=[Grommet([-0.2,0,0.3],"fuel")]
    p.demands=[("fuel",1.2*size)]
    p.clearances=[(np.array([-6.5,-0.9,-0.9]),np.array([-2.3,0.9,0.9]))] # exhaust
    return p

def gen_wing(fc, span=3.2, hand=1, seed=0):
    p=Part("wing",{"span":span,"hand":hand,"seed":seed},mass=600*span/3.2,
           silhouette=0.7,faction=fc["name"],era=fc["era"],color=fc["hull"],
           label="wing "+("R" if hand>0 else "L"))
    v,f=box(2.0,span,0.22); p.add(xform(v,np.eye(3),[0,span/2,0]),f)
    v,f=box(2.2,0.5,0.34); p.add(xform(v,np.eye(3),[0,0.25,0]),f,fc["accent"])
    p.ports=[Port([0,0,0],[0,-1,0],[0,0,1],"struct_M",1.0,1,
                  tags="side_R" if hand>0 else "side_L")]
    y=span-0.45; up=[hand,0,0]                       # handed: keyed rails
    rails=[Port([-0.5*hand,y,0.11],[0,0,1],up,"mount_rail",0.4,0,prio=8,sym=1,cluster="railA"),
           Port([ 0.5*hand,y,0.11],[0,0,1],up,"mount_rail",0.4,0,prio=8,sym=1,cluster="railA")]
    p.ports+=rails
    p.grommets=[Grommet([0,0.2,0.12],"fuel"),Grommet([0,y-0.4,0.12],"fuel")]
    p.gedges=[(0,1)]
    return p

def gen_cannon(fc, heavy=1.0, seed=0):
    m=950*heavy
    p=Part("heavy_cannon",{"heavy":heavy,"seed":seed},mass=m,silhouette=0.5,
           faction=fc["name"],era=fc["era"],color=fc["dark"],label="cannon")
    v,f=box(1.3,0.6,0.5); p.add(xform(v,np.eye(3),[0,0,0.35]),f)
    v,f=cyl(0.12,0.10,2.6*heavy); R=frame([1,0,0],[0,0,1])
    p.add(xform(v,R,[1.6*heavy,0,0.42]),f,fc["accent"])
    up=[1,0,0]
    p.ports=[Port([-0.5,0,0.1],[0,0,-1],up,"mount_rail",0.4,1,sym=2,cluster="railA"),
             Port([ 0.5,0,0.1],[0,0,-1],up,"mount_rail",0.4,1,sym=2,cluster="railA")]
    p.com=np.array([1.2*heavy,0,0.4])
    return p

def gen_antenna(fc, seed=0):
    p=Part("antenna",{"seed":seed},mass=40,silhouette=0.25,
           faction=fc["name"],era=fc["era"],color=fc["accent"],label="antenna")
    v,f=cyl(0.05,0.02,1.9); p.add(xform(v,np.eye(3),[0,0,0.95]),f)
    v,f=box(0.3,0.3,0.1); p.add(xform(v,np.eye(3),[0,0,0.05]),f,fc["dark"])
    p.ports=[Port([0,0,0],[0,0,-1],[1,0,0],"struct_S",0.30,1)]
    return p

def gen_pod(fc, seed=0):
    p=Part("sensor_pod",{"seed":seed},mass=120,silhouette=0.3,
           faction=fc["name"],era=fc["era"],color=fc["accent"],label="sensor pod")
    v,f=cyl(0.28,0.28,0.8,seg=10); p.add(xform(v,np.eye(3),[0,0,-0.45]),f)
    p.ports=[Port([0,0,0],[0,0,1],[1,0,0],"struct_S",0.31,1)]   # 3% strain vs .30
    return p

def gen_cap(fc):
    p=Part("terminator_cap",{},mass=8,silhouette=0.02,faction=fc["name"],
            era=fc["era"],color=fc["dark"],label="blanking cap")
    v,f=cyl(0.22,0.2,0.12,seg=8); p.add(xform(v,np.eye(3),[0,0,-0.06]),f)
    p.ports=[Port([0,0,0],[0,0,-1],[1,0,0],"struct_S",0.30,1)]
    return p

GENERATORS = [gen_tank, gen_engine, gen_wing, gen_cannon, gen_antenna, gen_pod]

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
    def __init__(s, faction, seed, brief):
        s.fc=faction; s.rng=random.Random(seed); s.brief=brief
        s.trace=[{"ev":"seed","seed":seed,"faction":faction["name"]}]
        s.placed=[]; s.ledger=[]; s.clear=[]; s.struts=[]; s.hoses=[]
        s.budget=dict(brief["budgets"])

    def log(s,**kw): s.trace.append(kw)

    def place(s, part, R, t, parent=None, joint=None, strain=0.0):
        world=[]
        for v,f,c in part.meshes: world.append((xform(v,R,t),f,c))
        part.world=world; part.R, part.t = R,t
        part.wports=[(xform(pt.pos[None],R,t)[0], R@pt.N, R@pt.up, pt)
                     for pt in part.ports]
        part.wgrom=[(xform(g.pos[None],R,t)[0],g) for g in part.grommets]
        part.parent=parent; part.joint=joint; part.strain=strain
        wc=xform(part.com[None],R,t)[0] if part.com.any() else \
           np.vstack([w[0] for w in world]).mean(0)
        part.wcom=wc
        lo=np.vstack([w[0] for w in world]).min(0)-0.02
        hi=np.vstack([w[0] for w in world]).max(0)+0.02
        s.ledger.append((lo,hi,part))
        for clo,chi in part.clearances:
            corners=np.array([[a,b,c] for a in (clo[0],chi[0])
                              for b in (clo[1],chi[1]) for c in (clo[2],chi[2])])
            wc8=xform(corners,R,t)
            s.clear.append((wc8.min(0),wc8.max(0),part))
        s.placed.append(part)
        s.budget["mass"]-=part.mass; s.budget["silhouette"]-=part.silhouette
        s.budget["parts"]-=1

    def collides(s, verts, ignore):
        lo,hi=verts.min(0)-0.02, verts.max(0)+0.02
        for l,h,p in s.ledger:
            if p is ignore: continue
            if np.all(lo<h) and np.all(l<hi): return p
        for l,h,p in s.clear:
            if p is ignore: continue
            if np.all(lo<h) and np.all(l<hi): return p
        return None

    def mate_xform(s, part, plug_ports, sock):
        """Closed-form rigid alignment, single port or rail cluster."""
        if len(plug_ports)==1:
            pp=plug_ports[0]; spos,sN,sup,sp=sock[0]
            roll=sup
            if sp.sym>=1:                          # symmetry-snap the roll
                step=2*math.pi/max(sp.sym,1)
                Bp=frame(pp.N,pp.up)
                # choose target up = sup rotated to nearest legal multiple — for
                # the slice, snapping to sup itself satisfies n-fold exactly.
            Bs=frame(-sN, roll)
            Bp=frame(pp.N, pp.up)
            R=Bs@Bp.T
            t=spos-R@pp.pos
            return R,t,0.0
        # dual-rail cluster: midpoint frame, roll keyed to up vectors
        p0,p1=plug_ports
        best=None
        for (q0,N0,u0,_),(q1,N1,u1,_) in (((sock[0]),(sock[1])),((sock[1]),(sock[0]))):
            zP=(p0.N+p1.N); zP/=np.linalg.norm(zP)
            xP=(p1.pos-p0.pos); xP/=np.linalg.norm(xP)
            BP=np.stack([xP,np.cross(zP,xP),zP],axis=1)
            zS=-(N0+N1); zS/=np.linalg.norm(zS)
            xS=(q1-q0); xS/=np.linalg.norm(xS)
            BS=np.stack([xS,np.cross(zS,xS),zS],axis=1)
            R=BS@BP.T
            mid_p=(p0.pos+p1.pos)/2; mid_s=(q0+q1)/2
            t=mid_s-R@mid_p
            res=max(np.linalg.norm(R@p0.pos+t-q0),np.linalg.norm(R@p1.pos+t-q1))
            key=float(np.dot(R@p0.up,u0))            # up keying: must agree
            if key>0.5 and (best is None or res<best[2]): best=(R,t,res)
        if best is None: return np.eye(3),np.zeros(3),9e9   # no keyed fit
        return best

    # ---- the spine: tree moment fold ------------------------------------
    def spine_ok(s, part, joint_pos, port_type, axis, cluster=False):
        g=9.81*s.brief["design_g"]; sf=s.fc["safety_factor"]
        cap=CAPACITY[port_type][0]
        if cluster: cap*=2*RAIL_CLUSTER_BONUS      # rails sum, triangulation pays
        r=part.wcom-joint_pos
        ax=axis/np.linalg.norm(axis)
        lever=np.linalg.norm(r-ax*np.dot(r,ax))     # perpendicular component only
        M=part.mass*g*lever
        return M<=cap/sf, M, cap/sf

    def spawn_strut(s, part, joint_pos):
        hull=s.placed[0]
        lo,hi=hull.world[0][0].min(0),hull.world[0][0].max(0)
        anchor=np.clip(part.wcom,lo,hi)
        a,b=part.wcom,anchor
        d=b-a; L=np.linalg.norm(d)
        if L<0.1: return False
        v,f=cyl(0.06,0.06,L,seg=6)
        z=d/L; up=np.array([0,0,1.0])
        if abs(np.dot(z,up))>0.95: up=np.array([1.0,0,0])
        R=frame(z,up)
        s.struts.append((xform(v,R,(a+b)/2),f,s.fc["dark"]))
        s.log(ev="strut", part=part.label, reason="moment over cap",
              anchor=[round(float(x),2) for x in anchor])
        return True

    # ---- main loop: propose -> reserve -> validate -> commit ------------
    def run(s):
        hull=gen_hull(s.fc, seed=s.rng.randint(0,9999))
        s.place(hull, np.eye(3), np.zeros(3))
        s.log(ev="commit", part="core_hull")
        openq=[(wp,hull) for wp in hull.wports]
        openq.sort(key=lambda e:-e[0][3].prio)
        i=0
        while i<len(openq):
            (spos,sN,sup,sp),host=openq[i]; i+=1
            if sp.filled: continue
            if s.budget["parts"]<=0 or s.budget["mass"]<=0:
                s.log(ev="budget_exhausted"); break
            cands=[]
            for gen in GENERATORS:
                part=gen(s.fc, **s.brief.get("overrides",{}).get(gen.__name__,{}),
                         seed=s.rng.randint(0,9999)) if False else gen(s.fc)
                # gather plug ports / clusters
                clusters={}
                for pt in part.ports:
                    if pt.gender!=1: continue
                    clusters.setdefault(pt.cluster or id(pt),[]).append(pt)
                for key,plugs in clusters.items():
                    if plugs[0].type!=sp.type: continue
                    if plugs[0].tags and sp.tags and plugs[0].tags!=sp.tags:
                        continue                      # handed part, wrong side
                    strain=abs(plugs[0].size-sp.size)/max(plugs[0].size,sp.size)
                    if strain>0.15: continue
                    if len(plugs)==2:
                        # need a matching socket cluster on host: fingerprint
                        mates=[w for w in host.wports
                               if w[3].cluster==sp.cluster and w[3].type==sp.type
                               and not w[3].filled]
                        if len(mates)!=2: continue
                        d_p=np.linalg.norm(plugs[1].pos-plugs[0].pos)
                        d_s=np.linalg.norm(mates[1][0]-mates[0][0])
                        if abs(d_p-d_s)>0.02: continue   # cluster fingerprint
                        cands.append((part,plugs,mates,strain))
                    elif len(plugs)==1 and not sp.cluster:
                        cands.append((part,plugs,[(spos,sN,sup,sp)],strain))
            if not cands:
                if s.fc["caps_unused"] and sp.type=="struct_S":
                    cap=gen_cap(s.fc)
                    R,t,_=s.mate_xform(cap,[cap.ports[0]],[(spos,sN,sup,sp)])
                    s.place(cap,R,t,host,spos); sp.filled=True
                    s.log(ev="terminate", port=sp.type, part="cap")
                else:
                    s.log(ev="port_open", port=sp.type,
                          note="left open" if not s.fc["caps_unused"] else "no cand")
                continue
            # ---- score the legal -----------------------------------------
            def score(c):
                part,_,_,strain=c
                n=sum(1 for q in s.placed if q.family==part.family)
                v = s.brief["wants"].get(part.family,0.0)/(1+1.5*n)
                if abs(spos[1])>0.3:                      # lateral port: prefer
                    mir=np.array([spos[0],-spos[1],spos[2]])   # the mirror twin
                    for q in s.placed:
                        if q.joint is not None and np.linalg.norm(q.joint-mir)<0.2 \
                           and q.family==part.family:
                            v+=2.5; break
                v += part.silhouette * max(s.budget["silhouette"],0)*0.5
                v += s.fc["strain_taste"]*strain
                v += s.rng.uniform(0,s.fc["blasphemy"])
                return v
            cands.sort(key=score, reverse=True)
            committed=False
            for part,plugs,mates,strain in cands:
                R,t,res=s.mate_xform(part,plugs,mates)
                if res>0.02:
                    s.log(ev="reject",part=part.label,reason=f"cluster residual {res:.3f}")
                    continue
                wv=np.vstack([xform(v,R,t) for v,_,_ in part.meshes])
                hit=s.collides(wv,host)
                if hit:
                    s.log(ev="reject",part=part.label,reason=f"ledger: {hit.label}")
                    continue
                jpos=np.mean([m[0] for m in mates],axis=0)
                s.place(part,R,t,host,jpos,strain)
                ok,M,cap=s.spine_ok(part,jpos,sp.type,sN,cluster=len(plugs)==2)
                if not ok:
                    s.log(ev="spine_fail",part=part.label,
                          moment=int(M),cap=int(cap))
                    if not s.spawn_strut(part,jpos):
                        s.log(ev="reject",part=part.label,reason="no strut anchor")
                        continue
                for m in mates: m[3].filled=True
                for pl in plugs: pl.filled=True
                if strain>0.001:
                    s.log(ev="adapter",part=part.label,strain=round(strain,3))
                    v,f=cyl(sp.size*0.55,sp.size*0.55,0.1,seg=8)
                    Bs=frame(sN,sup)
                    s.struts.append((xform(v,Bs,jpos+sN*0.02),f,s.fc["accent"]))
                s.log(ev="commit",part=part.label,strain=round(strain,3),
                      mass_left=int(s.budget["mass"]))
                for wp in part.wports:
                    if not wp[3].filled: openq.append((wp,part))
                openq[i:]=sorted(openq[i:],key=lambda e:-e[0][3].prio)
                committed=True; break
            if not committed:
                s.log(ev="port_open",port=sp.type,note="all candidates rejected")
        s.route()
        return s

    # ---- plumbing: demand match + A* over grommets ----------------------
    def route(s):
        nodes=[]; owner=[]
        for p in s.placed:
            for wpos,g in p.wgrom:
                nodes.append((wpos,g.ctype)); owner.append(p)
        # edges
        E={i:[] for i in range(len(nodes))}
        idx=0; offs={}
        for p in s.placed:
            offs[id(p)]=idx; idx+=len(p.wgrom)
        for p in s.placed:
            o=offs[id(p)]
            for a,b in p.gedges:
                d=np.linalg.norm(nodes[o+a][0]-nodes[o+b][0])
                E[o+a].append((o+b,0.2*d,"internal")); E[o+b].append((o+a,0.2*d,"internal"))
        for i in range(len(nodes)):
            for j in range(i+1,len(nodes)):
                if owner[i] is owner[j]: continue
                if nodes[i][1]!=nodes[j][1]: continue
                d=np.linalg.norm(nodes[i][0]-nodes[j][0])
                if d>4.5: continue
                blocked=any(seg_hits_aabb(nodes[i][0],nodes[j][0],lo,hi)
                            for lo,hi,_ in s.clear)
                if blocked:
                    s.log(ev="route_block",reason="exhaust clearance",
                          gap=round(float(d),2)); continue
                kind="leap" if d>1.2 else "jump"
                cost=(4.0 if kind=="leap" else 1.0)*d
                E[i].append((j,cost,kind)); E[j].append((i,cost,kind))
        # demand matching (greedy by distance)
        sups=[(i,p) for p in s.placed for k,(wpos,g) in enumerate(p.wgrom)
              for i in [offs[id(p)]+k] if any(c=="fuel" for c,_ in p.supplies)]
        dems=[(i,p) for p in s.placed for k,(wpos,g) in enumerate(p.wgrom)
              for i in [offs[id(p)]+k] if any(c=="fuel" for c,_ in p.demands)]
        for di,dp in dems:
            if not sups: s.log(ev="demand_unmet",part=dp.label); continue
            si,sp_=min(sups,key=lambda e:np.linalg.norm(nodes[e[0]][0]-nodes[di][0]))
            path=s.astar(nodes,E,si,di)
            if not path:
                s.log(ev="demand_unmet",part=dp.label,reason="no route"); continue
            pts=[nodes[k][0] for k in path]
            kinds=[next(k for j,c,k in E[a] if j==b) for a,b in zip(path,path[1:])]
            s.hoses.append({"pts":[list(map(float,p)) for p in pts],
                            "kinds":kinds,"ctype":"fuel"})
            s.log(ev="hose",frm=sp_.label,to=dp.label,
                  hops=len(path)-1,leaps=kinds.count("leap"))
        return

    def astar(s,nodes,E,a,b):
        import heapq
        goal=nodes[b][0]
        pq=[(0,0,a,[a])]; seen={}
        while pq:
            f,g,u,path=heapq.heappop(pq)
            if u==b: return path
            if u in seen and seen[u]<=g: continue
            seen[u]=g
            for v,c,_ in E[u]:
                h=np.linalg.norm(nodes[v][0]-goal)
                heapq.heappush(pq,(g+c+h,g+c,v,path+[v]))
        return None

# ----------------------------------------------------------------- factions
GUILD=dict(name="High Guild", era=812, hull="#d8d2c4", accent="#b08d3f",
           dark="#3a4150", glow="#7fd1e3", safety_factor=2.0, blasphemy=0.1,
           strain_taste=-3.0, caps_unused=True, hose="shroud")
FERAL=dict(name="Feral", era=977, hull="#7d6a58", accent="#b4502e",
           dark="#46413a", glow="#e8a33d", safety_factor=1.1, blasphemy=0.9,
           strain_taste=+1.5, caps_unused=False, hose="catenary")

def build(faction, seed, wants, heavy=1.0, span=3.2, parent=None, mutation=None):
    global GENERATORS
    GENERATORS=[gen_tank, gen_engine,
                lambda fc,**k: gen_wing(fc,span=span,hand=1),
                lambda fc,**k: gen_wing(fc,span=span,hand=-1),
                lambda fc,**k: gen_cannon(fc,heavy=heavy),
                gen_antenna, gen_pod]
    brief=dict(design_g=2.5, wants=wants,
               budgets=dict(mass=11000, silhouette=3.2, parts=14))
    a=Assembler(faction,seed,brief).run()
    a.lineage=dict(parent=parent,mutation=mutation,
                   gen_params=dict(seed=seed,heavy=heavy,span=span))
    return a

def export(ships, path):
    out={"ships":[]}
    for name,a,offset,plate in ships:
        meshes=[]
        for p in a.placed:
            for v,f,c in p.world:
                meshes.append({"v":(v+offset).round(3).tolist(),
                               "f":[list(t) for t in f],"c":c,"label":p.label})
        for v,f,c in a.struts:
            meshes.append({"v":(v+offset).round(3).tolist(),
                           "f":[list(t) for t in f],"c":c,"label":"strut/adapter"})
        hoses=[]
        for h in a.hoses:
            hoses.append({"pts":[[round(x+o,3) for x,o in zip(p,offset)]
                                  for p in h["pts"]],
                          "kinds":h["kinds"],"style":a.fc["hose"]})
        out["ships"].append({"name":name,"plate":plate,
            "faction":a.fc["name"],"era":a.fc["era"],
            "meshes":meshes,"hoses":hoses,
            "trace":a.trace,"lineage":a.lineage,
            "stats":dict(parts=len(a.placed),
                         mass=int(sum(p.mass for p in a.placed)),
                         struts=len(a.struts),hoses=len(a.hoses))})
    json.dump(out,open(path,"w"))
    return out

if __name__=="__main__":
    wants_g={"engine":3.0,"fuel_tank":2.5,"wing":2.0,"heavy_cannon":1.4,
             "antenna":0.8,"sensor_pod":0.6}
    wants_f={"engine":3.0,"fuel_tank":2.5,"wing":2.0,"heavy_cannon":2.2,
             "sensor_pod":1.0,"antenna":0.4}
    A=build(GUILD,seed=7,wants=wants_g,heavy=1.0,span=3.0)
    B=build(GUILD,seed=7,wants=wants_g,heavy=1.7,span=3.9,
            parent="GS-α", mutation="heavy 1.0→1.7, span 3.0→3.9")
    C=build(FERAL,seed=23,wants=wants_f,heavy=1.4,span=3.4)
    data=export([("GS-α  «Lawful Mean»",A,np.array([0,-7.5,0]),"Plate XLVII"),
                 ("GS-β  «Heavier Daughter»",B,np.array([0,0,0]),"Plate XLVIII"),
                 ("FV-γ  «Tape Holds»",C,np.array([0,7.5,0]),"Plate XLIX")],
                "/home/claude/kitmash/fleet.json")
    for sh in data["ships"]:
        print(sh["name"],sh["stats"])
        for ev in sh["trace"]:
            if ev["ev"] in ("strut","spine_fail","adapter","hose","demand_unmet",
                            "route_block","port_open","terminate"):
                print("   ",ev)
