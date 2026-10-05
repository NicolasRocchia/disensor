#!/usr/bin/env python3
"""Las dos mediciones de parejas de vectores citadas en la lista del W3C: el
42 y el 0, y el 0 y el 132.

The two vector-pair measurements cited on public-agent-conformance@w3.org:
the 42 and the 0, and the 0 and the 132.

Correr desde la raíz del repositorio / run from the repository root:

    python3 tools/medir-parejas.py [commit]

Por defecto mide HEAD. Lee `spec/vectors/{v0.2,v0.3,v0.4}/*.json` de los
objetos de git de ese commit, no del árbol de trabajo: el número es el del
commit aunque haya cambios sin commitear. Imprime el commit, para que el
número viaje con su fuente. No escribe nada.

No corre el checker: compara lo que los vectores declaran en `expected`.

1) Parejas MUST-PASS / MUST-FAIL de una misma suite cuyos artefactos difieren
   en exactamente un campo, y cuántas de esas dejan la lista de reglas sin
   moverse.
2) Parejas MUST-FAIL / MUST-FAIL de una misma suite con distinta lista de
   reglas, a uno y a dos campos. El número citado es el total.

Qué es un campo. El artefacto se aplana: un campo es una hoja, es decir una
ruta a un valor escalar. Dos vectores están a N campos cuando hay N rutas cuyo
valor difiere entre los dos, o que están en uno solo. Una lista o un objeto
vacío no deja hoja, así que `[]` contra ausente cuenta 0 campos. Una hoja con
valor `null` cuenta igual que una ausente, así que `null` contra ausente
también cuenta 0. Los valores se comparan con la igualdad de Python, que no
distingue `true` de `1` ni `1` de `1.0`. Los números dependen de esta
definición.

By default it measures HEAD. It reads `spec/vectors/{v0.2,v0.3,v0.4}/*.json`
from the git objects of that commit, not from the working tree: the number is
the commit's even with uncommitted changes. It prints the commit, so the
number travels with its source. It writes nothing.

It does not run the checker: it compares what the vectors declare in
`expected`.

1) MUST-PASS / MUST-FAIL pairs within a suite whose artifacts differ in
   exactly one field, and how many of those leave the rule list unmoved.
2) MUST-FAIL / MUST-FAIL pairs within a suite with different rule lists, one
   field and two fields apart. The cited number is the total.

What a field is. The artifact is flattened: a field is a leaf, that is, a path
to a scalar value. Two vectors are N fields apart when N paths hold different
values in the two, or exist in only one. An empty list or object leaves no
leaf, so `[]` against absent counts as 0 fields. A leaf holding `null` counts
the same as an absent one, so `null` against absent also counts as 0. Values
are compared with Python equality, which does not tell `true` from `1` or `1`
from `1.0`. The numbers depend on this definition.
"""
import itertools
import json
import subprocess
import sys

SUITES = ('v0.2', 'v0.3', 'v0.4')

def git(*args):
    r = subprocess.run(['git', '--no-optional-locks', *args], capture_output=True)
    if r.returncode != 0:
        sys.exit(f"git {' '.join(args)}: {r.stderr.decode('utf-8', 'replace').strip()}")
    return r.stdout.decode('utf-8')

def flat(o, p=''):
    d = {}
    if isinstance(o, dict):
        for k, v in o.items(): d.update(flat(v, f'{p}/{k}'))
    elif isinstance(o, list):
        for i, v in enumerate(o): d.update(flat(v, f'{p}/{i}'))
    else:
        d[p] = o
    return d

def cargar(suite):
    vs = []
    rutas = git('ls-tree', '--full-tree', '-z', '--name-only', commit, '--', f'spec/vectors/{suite}/')
    for f in sorted(rutas.split('\0')):
        nombre = f.rsplit('/', 1)[-1]
        if not nombre.endswith('.json') or nombre == 'index.json': continue
        d = json.loads(git('show', f'{commit}:{f}'))
        vs.append((nombre[:-5], d.get('expected') or {}, flat(d.get('artifact') or {})))
    return vs

def dif(a, b):
    return [k for k in set(a) | set(b) if a.get(k) != b.get(k)]

rev = sys.argv[1] if len(sys.argv) > 1 else 'HEAD'
commit = git('rev-parse', '--verify', f'{rev}^{{commit}}').strip()
print(f'commit: {commit[:7]}')
if git('status', '--porcelain', '--untracked-files=no', '--', ':/spec/vectors').strip():
    print('  hay cambios sin commitear en spec/vectors; no entran: se mide el commit')
print()

vectores = {suite: cargar(suite) for suite in SUITES}

print('1) parejas MUST-PASS / MUST-FAIL a UN campo, y si mueven solo el veredicto')
tot = solo = 0
for suite in SUITES:
    vs = vectores[suite]
    mp = [v for v in vs if v[1].get('valid')]
    mf = [v for v in vs if not v[1].get('valid')]
    n = 0
    for a in mp:
        for b in mf:
            if len(dif(a[2], b[2])) == 1:
                n += 1; tot += 1
                if (a[1].get('rules') or []) == (b[1].get('rules') or []): solo += 1
    print(f'   {suite}: {n}')
print(f'   total: {tot} | de esos, con la lista de reglas sin moverse: {solo}\n')

print('2) parejas MUST-FAIL / MUST-FAIL con distinta lista de reglas')
for campos in (1, 2):
    print(f'   a {campos} campo(s):')
    tot = 0
    for suite in SUITES:
        mf = [v for v in vectores[suite] if not v[1].get('valid')]
        c = sum(1 for a, b in itertools.combinations(mf, 2)
                if len(dif(a[2], b[2])) == campos
                and (a[1].get('rules') or []) != (b[1].get('rules') or []))
        tot += c
        print(f'      {suite}: {c}')
    print(f'      total: {tot}')
