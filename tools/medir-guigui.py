#!/usr/bin/env python3
"""Cuenta las parejas a un campo del corpus de Guigui, bajo tres alcances.

Counts the one-field pairs in Guigui's corpus, under three scopes.

Correr desde la raíz del repositorio, contra un clon de afuera / run from the
repository root, against a clone kept elsewhere:

    git clone https://github.com/DSHCorrectover/ccs-conformance-vectors <clon>
    python3 tools/medir-guigui.py <clon>

Lee los `case.json` de `vectors/mustfail-v1/` del clon y aplana igual que
`medir-parejas.py`: una ruta por hoja, y dos vectores son "a un campo" cuando
difieren en exactamente una ruta. Imprime el commit del clon, y avisa si el
clon tiene archivos versionados modificados. No escribe nada.

El punto del script es que el número cambia con el alcance y el alcance no lo
fija el corpus, lo fija quien cuenta. Por eso imprime los tres y no uno.

It reads the `case.json` files under `vectors/mustfail-v1/` of the clone and
flattens them the way `medir-parejas.py` does: one path per leaf, and two
vectors are "one field apart" when they differ in exactly one path. It prints
the commit of the clone, and warns if the clone has modified tracked files.
It writes nothing.

The point of the script is that the number changes with the scope, and the
scope is not set by the corpus: it is set by whoever counts. That is why it
prints all three and not one.
"""
import glob, itertools, json, os, subprocess, sys

RAIZ = sys.argv[1] if len(sys.argv) > 1 else "."
IDENT = ("nonce", "trace_id", "tool_call_id")


# Este aplanado tiene que ser idéntico al de `medir-parejas.py` (`flat`): los
# dos conteos se comparan en la lista, y solo son comparables si un campo es
# lo mismo en los dos.
def plano(o, p=""):
    d = {}
    if isinstance(o, dict):
        for k, v in o.items():
            d.update(plano(v, f"{p}/{k}"))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            d.update(plano(v, f"{p}/{i}"))
    else:
        d[p] = o
    return d


# Compara igual que el `dif` de `medir-parejas.py`: `null` cuenta como ausente, y con la igualdad de Python.
def dif(a, b):
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


commit = subprocess.run(["git", "-C", RAIZ, "rev-parse", "--short", "HEAD"],
                        capture_output=True, text=True).stdout.strip()
tracked = subprocess.run(["git", "--no-optional-locks", "-C", RAIZ, "status", "--porcelain",
                          "--untracked-files=no"],
                         capture_output=True, text=True).stdout.strip()
print(f"corpus: {RAIZ}  commit: {commit or '(sin git)'}")
if tracked:
    print("  ARBOL MODIFICADO: el numero no tiene fuente limpia.")
print()

vs = []
for f in sorted(glob.glob(os.path.join(RAIZ, "vectors", "mustfail-v1", "*", "case.json"))):
    with open(f, encoding="utf-8") as fh:
        vs.append((os.path.basename(os.path.dirname(f)), json.load(fh)))
print(f"vectores leidos: {len(vs)}")
con = [(n, d) for n, d in vs if isinstance(d.get("tool_call"), dict)]
print(f"con tool_call: {len(con)}  sin: {[n[:3] for n, d in vs if (n, d) not in con]}\n")

for n, d in con:
    tc = d["tool_call"]
    faltan = [k for k in IDENT if k not in tc]
    if faltan:
        print(f"  aviso: {n} no trae {faltan}")

for etiqueta, sel in (
    ("solo tool_call", lambda d: d["tool_call"]),
    ("archivo entero", lambda d: d),
    ("tool_call sin campos de identidad",
     lambda d: {k: v for k, v in d["tool_call"].items() if k not in IDENT}),
):
    pares = [(a[0], b[0], dif(plano(sel(a[1])), plano(sel(b[1]))))
             for a, b in itertools.combinations(con, 2)]
    uno = [p for p in pares if len(p[2]) == 1]
    print(f"\n=== {etiqueta} ===")
    print(f"  parejas totales: {len(pares)}")
    print(f"  a exactamente un campo: {len(uno)}")
    print(f"  minimo de campos distintos entre pares: {min(len(p[2]) for p in pares)}")
    for a, b, d in uno[:10]:
        print(f"    {a[:3]}/{b[:3]}: {d}")
    c01 = [p for p in pares if p[0].startswith("C01") or p[1].startswith("C01")]
    s01 = [p for p in c01 if p[0].startswith("S01") or p[1].startswith("S01")]
    if s01:
        print(f"  C01 contra S01: {len(s01[0][2])} campos distintos -> {s01[0][2]}")
