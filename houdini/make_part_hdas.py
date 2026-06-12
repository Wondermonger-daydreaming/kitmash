"""make_part_hdas.py — generate thin-wrapper part HDAs for EVERY family.

Run:  source /opt/hfs21.0/houdini_setup
      hython houdini/make_part_hdas.py [outdir]      # default houdini/hda/

One HDA per family in kitmash_houdini.GEN_REGISTRY, named
`kitmash::part_<family>::1.0`. Interior: a single Python SOP that calls
the family's own generator and writes the result with
kitmash_houdini.write_part_geo() — body prims (group `body`), port and
grommet points in schema attribute syntax, detail gen_params. The round
trip holds BY CONSTRUCTION: the HDA runs the same code gate 7 proves.

These are day-one placeholders so the For-Each rehydrator can assemble a
whole ship in-viewport immediately. Artists replace interiors family by
family with native networks (the migration pattern is specified in
kitmash_part_tank.md — ports and grommets are load-bearing and must not
move; gate the swap with verify_tank_hda.py adapted to the family).

Parameters per HDA = the generator's ACCEPTED kwargs only (signature
minus fc): seed everywhere, plus span/hand (wing), heavy (cannon),
size (engine), scale (hull). Derived gen_params (tank h, pod r, ...)
regenerate deterministically from the seed — that determinism is exactly
what rehydrate() asserts on every test run, so the wrapper never lies.
Plus on every HDA: `faction` (menu) and `kitmash_path` (string).

(Written ahead of the install; UNTESTED until 21.0.729 lands.)
"""
import inspect, os, sys

import hou

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
OUTDIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "hda")
os.makedirs(OUTDIR, exist_ok=True)

sys.path.insert(0, PROJECT)
import kitmash_houdini as kh

SOP_CODE = '''\
node = hou.pwd(); geo = node.geometry()
import sys
p = node.evalParm("kitmash_path")
if p and p not in sys.path: sys.path.insert(0, p)
import kitmash as km, kitmash_houdini as kh
fc = (km.GUILD, km.FERAL)[node.evalParm("faction")]
kw = {{k: node.evalParm(k) for k in {keys!r}}}
kh.write_part_geo(geo, km.{gen}(fc, **kw))
'''

obj = hou.node("/obj")
built = []
for family, (gen_name, fn) in sorted(kh.GEN_REGISTRY.items()):
    sig = inspect.signature(fn)
    accepted = [(k, p.default) for k, p in sig.parameters.items()
                if k != "fc"]
    keys = [k for k, _ in accepted]

    geo = obj.createNode("geo", "build_" + family)
    py = geo.createNode("python", "generate")
    py.parm("python").set(SOP_CODE.format(keys=keys, gen=gen_name))
    out = geo.createNode("output", "OUT")
    out.setInput(0, py)
    out.setDisplayFlag(True); out.setRenderFlag(True)

    hda_path = os.path.join(OUTDIR, f"kitmash_part_{family}.hda")
    subnet = geo.collapseIntoSubnet([py, out], "part_" + family)
    asset = subnet.createDigitalAsset(
        name=f"kitmash::part_{family}::1.0",
        hda_file_name=hda_path,
        description=f"KitMash {family} (thin wrapper over {gen_name}; "
                    f"schema kitmash/0.6)",
        min_num_inputs=0, max_num_inputs=0)

    ptg = asset.type().definition().parmTemplateGroup()
    for k, dv in accepted:
        if isinstance(dv, int):
            ptg.append(hou.IntParmTemplate(k, k, 1, default_value=(dv,)))
        else:
            ptg.append(hou.FloatParmTemplate(k, k, 1,
                                             default_value=(float(dv),)))
    ptg.append(hou.MenuParmTemplate("faction", "Faction",
                                    ("guild", "feral"),
                                    ("High Guild", "Feral")))
    ptg.append(hou.StringParmTemplate("kitmash_path", "KitMash Path", 1,
                                      default_value=(PROJECT,)))
    asset.type().definition().setParmTemplateGroup(ptg)
    asset.type().definition().updateFromNode(asset)
    asset.type().definition().save(hda_path, asset)
    built.append((family, hda_path, keys))
    print(f"built kitmash::part_{family}::1.0  parms={keys}  -> {hda_path}")

print(f"\n{len(built)} part HDAs built. Rehydrator switch order "
      f"(s@generator):")
for family, _, _ in built:
    print(f"  {kh.GEN_REGISTRY[family][0]:14s} -> kitmash::part_{family}")
