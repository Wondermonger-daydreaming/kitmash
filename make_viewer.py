"""make_viewer.py — splice a fleet JSON into the self-contained viewer.

The viewer html is its own template: the DATA constant lives on a single
line, and the camera-target line is patched (idempotently) to read each
ship's exported offset instead of a hardcoded 3-ship array.

Usage: python3 make_viewer.py fleet.json [out.html] [template.html]
"""
import json, re, sys

OLD_TARGET = "target.y=[-7.5,0,7.5][i]*0.55;"
NEW_TARGET = "target.y=(sh.offset?sh.offset[1]:0)*0.55;"

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "fleet.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "kitmash-fleet.html"
    tpl = sys.argv[3] if len(sys.argv) > 3 else "kitmash-fleet.html"
    data = json.load(open(src))
    html = open(tpl).read()
    payload = "const DATA = " + json.dumps(data) + ";"
    html, n = re.subn(r"^const DATA = .*$", lambda m: payload,
                      html, count=1, flags=re.M)
    assert n == 1, "DATA line not found in template"
    html = html.replace(OLD_TARGET, NEW_TARGET)  # idempotent
    assert NEW_TARGET in html, "camera-target line not found/patched"
    open(out, "w").write(html)
    print(f"{out}: {len(data['ships'])} ships, {len(html)} bytes")

if __name__ == "__main__":
    main()
