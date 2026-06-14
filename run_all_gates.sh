#!/usr/bin/env bash
# run_all_gates.sh — KitMash gate ladder. One ladder, named rungs, one venv.
#
# Usage:
#   ./run_all_gates.sh                 # public CI: core + director + usd
#   ./run_all_gates.sh check-core      # byte-exact anchor + assembler gates
#   ./run_all_gates.sh check-director  # director gates
#   ./run_all_gates.sh check-usd       # usd round-trip (needs usd-core)
#   ./run_all_gates.sh check-houdini   # native HDA gate (needs hython, local-only)
#   ./run_all_gates.sh catalogue       # regenerate the Borges catalogue
#   ./run_all_gates.sh all             # every rung (houdini skipped if no hython)
#
# Pure-Python core + usd-core run anywhere; the houdini rung is local-only.

set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Python interpreter: defaults to python3, override with `PY=/path/to/python ./run_all_gates.sh`.
# Needs numpy (core/director) and usd-core (the check-usd rung).
PY="${PY:-python3}"
# P3 re-baseline (v0.8.1): old e6aeccfe352bba16f288785ea23e5bc3 -> new below.
# Hull weld-FACES replaced the whole-box anchor; strut endpoints + relief moved,
# all 5 ships unchanged in parts/mass/struts and still legal+fueled.
ANCHOR_MD5="80ddaccccc594b2a7cc8c7b40a129086"
GATE_JSON="/tmp/kitmash_gate.json"

cd "$HERE" || exit 2

rung_core() {
    echo "== check-core =================================================="
    "$PY" kitmash.py "$GATE_JSON" >/dev/null || { echo "FAIL: kitmash.py crashed"; return 1; }
    GOT="$(md5sum "$GATE_JSON" | awk '{print $1}')"
    if [ "$GOT" = "$ANCHOR_MD5" ]; then
        echo "PASS  byte-exact anchor  ($GOT)"
    else
        echo "FAIL  anchor drift: got $GOT  want $ANCHOR_MD5"
        return 1
    fi
    "$PY" test_kitmash.py || return 1
}

rung_director() {
    echo "== check-director ============================================="
    "$PY" test_director.py || return 1
}

rung_usd() {
    echo "== check-usd (needs usd-core) ================================="
    "$PY" verify_usd.py || return 1
}

rung_houdini() {
    echo "== check-houdini (needs hython — LOCAL-ONLY) =================="
    if command -v hython >/dev/null 2>&1; then
        hython houdini/verify_native_hda.py || return 1
    else
        echo "SKIP  hython not on PATH; this rung verifies native HDAs"
        echo "      against the Python generator and only runs with a"
        echo "      Houdini install. Public CI does not need it."
        return 0
    fi
}

rung_catalogue() {
    echo "== catalogue =================================================="
    "$PY" make_catalogue.py || return 1
}

summary() {
    echo
    echo "=============================================================="
    if [ "$1" -eq 0 ]; then
        echo "GATE LADDER: ALL GREEN"
    else
        echo "GATE LADDER: FAILURES ($1 rung(s) failed)"
    fi
    echo "=============================================================="
}

run_named() {
    case "$1" in
        check-core)     rung_core ;;
        check-director) rung_director ;;
        check-usd)      rung_usd ;;
        check-houdini)  rung_houdini ;;
        catalogue)      rung_catalogue ;;
        all)
            fails=0
            rung_core     || fails=$((fails+1))
            rung_director || fails=$((fails+1))
            rung_usd      || fails=$((fails+1))
            rung_houdini  || fails=$((fails+1))
            summary "$fails"
            return "$fails"
            ;;
        *)
            echo "unknown rung: $1"
            echo "rungs: check-core check-director check-usd check-houdini catalogue all"
            return 2
            ;;
    esac
}

if [ "$#" -ge 1 ]; then
    run_named "$1"
    exit $?
fi

# default: the public ladder (pure-Python + usd-core)
fails=0
rung_core     || fails=$((fails+1))
rung_director || fails=$((fails+1))
rung_usd      || fails=$((fails+1))
summary "$fails"
exit "$fails"
