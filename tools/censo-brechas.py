#!/usr/bin/env python3
"""Censo de gap_reason en el corpus, y a donde iria cada `other` con los valores de v0.5.

Correr desde la raiz del repositorio:

    python3 tools/censo-brechas.py [commit]

Por defecto mide HEAD. Lee las declaraciones de los objetos git de ese commit,
no del arbol de trabajo: el numero es el del commit aunque haya cambios sin
commitear, y el script igual los nombra para que nadie los confunda con lo
medido. No escribe nada, bytecode incluido.

La pregunta es la del #51 contra los valores que prometen el #52 y el #53: si
los nuevos valores de gap_reason vacian el balde `other` o si `other` sigue
siendo la puerta grande. Cada `other` se clasifica aplicando la definicion
literal de cada issue:

- #52, unobservable_before_release: lo que no se puede observar hasta que la
  release exista ("el wheel que se va a publicar, la Action en el tag, la
  pagina de PyPI, el workflow de release que corre recien con el tag"), con el
  criterio estricto del issue: solo se puede observar cuando la release ocurra.
- #53, reviewer_confinement como valor de gap_reason: el confinamiento del
  revisor se mantuvo y le impidio correr algo (el caso 0085276e). Un
  confinamiento que se violo (8cc6f0c1) no es este valor: el issue lo separa.

La clasificacion es juicio, asi que vive aca como dato y no como heuristica:
cada entrada cita el fragmento de la descripcion que la justifica, y el script
verifica que ese fragmento este literalmente en la descripcion. Un caso dudoso
va como dudoso. Un item con mas de un motivo se clasifica por el principal y
lleva los otros anotados: las cuentas por familia no son exclusivas. Un `other`
nuevo que no este en la tabla sale como sin clasificar y el script termina con
codigo 1: la tabla no se queda vieja en silencio.
"""
import json
import os
import sys
from collections import Counter

# "No escribe nada" incluye el bytecode de los modulos que importa desde src.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.getcwd(), "src"))
from disensor import gitctx  # noqa: E402

UBR = "unobservable_before_release"
RC = "reviewer_confinement"
CATEGORIAS = {UBR, RC, "dudoso: " + UBR, "dudoso: " + RC, "ninguno"}

# Las familias de los que no van a ningun valor nuevo: lo que un vocabulario
# revisable podria nombrar, o lo que no es una brecha de ejecucion. Las tres de
# 8c01d56d siguen la lectura publica del mensaje 0002 de la lista de la W3C.
NO_ES_BRECHA = "no es brecha de ejecucion"
HERRAMIENTA = "limite de herramienta o de cobertura"
PLAN = "compuerta plan: nada que ejecutar todavia"
OPT_IN = "pruebas opt-in con costo"
EXTERNA = "fuente externa no consultada"
VIOLACION = "violacion de confinamiento"
DESPUES = "observable despues de la declaracion"
FAMILIAS = {NO_ES_BRECHA, HERRAMIENTA, PLAN, OPT_IN, EXTERNA, VIOLACION, DESPUES}

# (evento, item) -> (categoria, familia si es "ninguno", motivo principal,
#                    fragmento textual que lo justifica, otros motivos)
CLASIFICACION = {
    ("51dcaca3", "r1"): ("ninguno", EXTERNA, "arxiv bloqueado por el proxy de egreso",
                         "arxiv esta bloqueado por el proxy de egress de este entorno", ()),
    ("d0545d00", "r1"): (UBR, None, "el workflow de release corre recien con la publicacion",
                         "la primera corrida real es la publicacion de 0.6.0, posterior a este merge", ()),
    ("62bcf207", "r1"): ("ninguno", EXTERNA,
                         "la version ya estaba publicada: lo que falto fue verificar por red",
                         "sea el de la version publicada", ()),
    ("8cc6f0c1", "r1"): ("ninguno", VIOLACION, "el confinamiento se violo; el #53 lo separa del valor",
                         "ninguna clase del esquema describe una violacion de confinamiento", ()),
    ("e81a7dd8", "r1"): ("ninguno", NO_ES_BRECHA, "un dato falso en otras declaraciones (#66)",
                         "afirman que las reviso gpt-5-codex", ()),
    ("0085276e", "r1"): (RC, None, "el confinamiento se mantuvo e impidio correr la suite",
                         "su confinamiento le permite exactamente una escritura fuera del repositorio", ()),
    ("130672cb", "r1"): (UBR, None, "la pagina de PyPI se ve recien con la publicacion",
                         "este commit no esta publicado", ()),
    ("8c01d56d", "r2"): ("ninguno", NO_ES_BRECHA, "equivalencia establecida por lectura comparada (0002)",
                         "varias ramas de esa regla no tienen vector que las ejercite", ()),
    ("8c01d56d", "r3"): ("ninguno", NO_ES_BRECHA, "limite conocido de una guardia que si corrio (0002)",
                         "La guardia contra la comparacion literal es sintactica", ()),
    ("8c01d56d", "r4"): ("ninguno", NO_ES_BRECHA, "la ronda la corto el arbitro por costo (0002)",
                         "la ronda se corta aca por decision del arbitro humano", ()),
    ("e522dac1", "r1"): ("dudoso: " + UBR, None,
                         "el wheel a publicar se ve despues del tag, pero construirlo antes no era imposible",
                         "el wheel y el sdist que se van a publicar no se miraron", ()),
    ("048b92cd", "r1"): ("ninguno", PLAN, "la correccion todavia no tiene que ejecutar",
                         "queda verificada recien cuando esas fases corran", ()),
    ("fbff4775", "r1"): (UBR, None, "la disponibilidad de lo publicado se establece despues del tag",
                         "solo puede establecerse despues del tag", ()),
    ("6b969ccb", "r1"): (RC, None, "el confinamiento se mantuvo e impidio correr la suite",
                         "la consigna prohíbe crear archivos",
                         ("publicacion del comentario sin comprobar", "sin segunda pasada")),
    ("6b969ccb", "r2"): ("ninguno", NO_ES_BRECHA, "endurecimiento archivado aca porque el render abortaba (#56)",
                         "no conoce esa clase y aborta", ()),
    ("7547847a", "r2"): ("dudoso: " + RC, None,
                         "el revisor no ejecuto nada y el item no dice por que; su vecino r3 dice interfaz web",
                         "El revisor no ejecutó nada", ("sin segunda pasada",)),
    ("7547847a", "r3"): ("ninguno", NO_ES_BRECHA, "consigna no empaquetada, sin prompt_hash",
                         "La ronda no fue la empaquetada", ("endurecimiento sin verificar (#56)",)),
    ("125b2816", "r3"): ("ninguno", HERRAMIENTA, "ventana de captura de la herramienta del revisor",
                         "la ventana de captura de la herramienta del revisor", ()),
    ("bb2b3c73", "r1"): ("ninguno", HERRAMIENTA, "no hay navegador en la suite",
                         "no hay navegador en la suite", ()),
    ("bb2b3c73", "r2"): ("ninguno", DESPUES, "otras plataformas corren en el CI del PR",
                         "corren en el CI del PR, después de esta declaración y no antes",
                         ("pruebas opt-in con costo",)),
    ("df0da106", "r1"): ("ninguno", PLAN, "las piezas todavia no existian",
                         "las piezas no existían al momento de la ronda", ()),
    ("c544bf19", "r1"): ("ninguno", OPT_IN, "smoke tests de endurecimiento",
                         "que son opt-in con costo", ()),
    ("10ef1bac", "r2"): ("ninguno", OPT_IN, "smoke tests de endurecimiento",
                         "opt-in con costo (DISENSOR_SMOKE=1)",
                         ("prueba de plataforma que corre en el CI", "salteadas que no son brechas")),
}

# La tabla se valida antes de medir nada: una categoria o una familia mal
# escrita tiene que fallar aca y no quedar fuera de las cuentas en silencio.
for _clave, (_cat, _fam, _motivo, _frag, _otros) in CLASIFICACION.items():
    if _cat not in CATEGORIAS:
        sys.exit(f"{_clave}: categoria desconocida {_cat!r}")
    if (_cat == "ninguno") != (_fam is not None) or (_fam is not None and _fam not in FAMILIAS):
        sys.exit(f"{_clave}: la familia {_fam!r} no corresponde a la categoria {_cat!r}")


def git(args, texto=True, sin_fallar=False):
    r = gitctx.run_git(args, os.getcwd(), text=texto)
    if r.returncode != 0 and not sin_fallar:
        sys.exit(f"git {' '.join(args)}: {(r.stderr or '').strip() if texto else 'fallo'}")
    return r


rev = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
commit = git(["rev-parse", f"{rev}^{{commit}}"]).stdout.strip()
tracked = git(["status", "--porcelain", "--untracked-files=no"]).stdout.strip()
residuo_suelto = [l[3:] for l in git(["status", "--porcelain", "--", ".residue"]).stdout.splitlines()
                  if l.startswith("?? ")]

print(f"commit medido: {commit[:7]}")
if tracked:
    print("  hay cambios tracked sin commitear; no entran: se mide el commit")
if residuo_suelto:
    print(f"  declaraciones sin commitear en .residue/ ({len(residuo_suelto)}), no contadas:")
    for f in residuo_suelto:
        print(f"    {f}")


def declaraciones_en(rev):
    rutas = [p for p in git(["ls-tree", "-r", "-z", "--name-only", rev, "--", ".residue"]).stdout.split("\0")
             if p.endswith(".json")]
    return {p: json.loads(git(["show", f"{rev}:{p}"], texto=False).stdout.decode("utf-8")) for p in rutas}


declaraciones = list(declaraciones_en(commit).values())

clases = Counter()
razones = Counter()
otros = []
for a in declaraciones:
    for item in a.get("residue", {}).get("items", []):
        clases[item["class"]] += 1
        if item["class"] == "execution_gap":
            razones[item.get("gap_reason", "(sin gap_reason)")] += 1
            if item.get("gap_reason") == "other":
                otros.append((a["event"]["event_id"][:8], item, a["event"]["created_at"]))
otros.sort(key=lambda x: x[2])
otros = [(e, i) for e, i, _ in otros]

print(f"\ndeclaraciones: {len(declaraciones)}")
print(f"items de residuo: {sum(clases.values())}  {dict(clases)}")
print(f"execution_gap por gap_reason: {dict(razones)}")

largos = [len(i.get("description") or "") for _, i in otros]
con_texto = sum(1 for n in largos if n)
sin_atencion = sum(1 for _, i in otros if not i.get("requires_human_attention"))
print(f"\nother: {len(otros)}  con descripcion: {con_texto}", end="")
if largos:
    print(f"  largo: {min(largos)} a {max(largos)} caracteres", end="")
print(f"  requires_human_attention en false: {sin_atencion}")

print("\nclasificacion de cada other (definicion literal del #52 y del #53):")
categorias = Counter()
familias = Counter()
mixtos = 0
problemas = []
for evento, item in otros:
    clave = (evento, item["id"])
    texto = item.get("description") or ""
    atencion = "atencion" if item.get("requires_human_attention") else "sin atencion"
    if clave not in CLASIFICACION:
        problemas.append(f"{evento} {item['id']}: sin clasificar")
        categorias["sin clasificar"] += 1
        print(f"  {evento} {item['id']} [{atencion}] SIN CLASIFICAR")
        continue
    categoria, familia, motivo, fragmento, otros_motivos = CLASIFICACION[clave]
    if fragmento not in texto:
        problemas.append(f"{evento} {item['id']}: el fragmento citado no esta en la descripcion")
    categorias[categoria] += 1
    if familia:
        familias[familia] += 1
    etiqueta = f"{categoria} ({familia})" if familia else categoria
    print(f"  {evento} {item['id']} [{atencion}] {etiqueta}: {motivo}")
    if otros_motivos:
        mixtos += 1
        print(f"      tambien: {'; '.join(otros_motivos)}")
    print(f"      \"{fragmento}\"")

# Medir un commit viejo deja afuera declaraciones que todavia no existian, y eso
# no es un error. Que una declaracion que ya estaba en ese commit falte, o que
# le falte el item, si: el registro es de solo agregar. Para saberlo se busca en
# HEAD el archivo del evento y el commit que lo agrego.
presentes = {(e, i["id"]) for e, i in otros}
medidos = {a["event"]["event_id"][:8] for a in declaraciones}
en_head = declaraciones_en("HEAD") if commit != git(["rev-parse", "HEAD^{commit}"]).stdout.strip() else {}
posteriores = []
for clave in sorted(set(CLASIFICACION) - presentes):
    evento, item_id = clave
    if evento in medidos:
        problemas.append(f"{evento} {item_id}: la declaracion esta en el commit medido y el item no")
        continue
    rutas = [p for p, a in en_head.items() if a["event"]["event_id"].startswith(evento)]
    if not rutas:
        problemas.append(f"{evento} {item_id}: la declaracion no esta ni en el commit medido ni en HEAD")
        continue
    agregado = git(["log", "--diff-filter=A", "--format=%H", "HEAD", "--", rutas[0]]).stdout.split()
    anterior = agregado and git(["merge-base", "--is-ancestor", agregado[-1], commit],
                                sin_fallar=True).returncode == 0
    if anterior:
        problemas.append(f"{evento} {item_id}: la declaracion ya estaba en el commit medido y falta")
    else:
        posteriores.append(f"{evento} {item_id}")
if posteriores:
    print(f"\nen la tabla y posteriores al commit medido ({len(posteriores)}): {', '.join(posteriores)}")

seguros = categorias[UBR] + categorias[RC]
dudosos = categorias["dudoso: " + UBR] + categorias["dudoso: " + RC]
print(f"\npor categoria: {dict(categorias)}")
print(f"con los valores del #52 y el #53, en other quedarian entre {len(otros) - seguros - dudosos} "
      f"(los dudosos reclasificados) y {len(otros) - seguros} (los dudosos en other), de {len(otros)}")
print(f"los que no van a ningun valor nuevo, por familia ({sum(familias.values())}):")
for familia, n in familias.most_common():
    print(f"  {n}  {familia}")
print(f"items con mas de un motivo: {mixtos} (se cuentan por el principal)")
print(f"con requires_human_attention obligatorio para other, cambiarian {sin_atencion} de {len(otros)}")

if problemas:
    print("\nLA TABLA NO COINCIDE CON EL CORPUS:")
    for p in problemas:
        print(f"  {p}")
    sys.exit(1)
