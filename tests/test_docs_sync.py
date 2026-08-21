"""Los dos README dicen lo mismo, en lo que una maquina puede verificar.

Ninguna maquina puede decidir si dos textos en idiomas distintos significan lo
mismo. Prometer que el CI detecta divergencia semantica seria exactamente la
clase de garantia inflada que esta herramienta existe para no emitir.

Lo que si se puede verificar:

- La FORMA: cuantas secciones hay y que bloques de codigo cuelgan de cada una.
  Comparar solo la cantidad de secciones deja pasar un renombre, un reordenamiento
  o un agregar-uno-borrar-otro, que son divergencias reales.
- Los BLOQUES QUE NO SON PROSA (json, yaml): son contrato y tienen que ser
  identicos byte a byte entre los dos idiomas.
- Los COMANDOS de los bloques bash, sin sus comentarios: los comentarios son
  prosa y tienen que diferir; los comandos son lo que el lector copia y pega.

Los titulos NO se comparan entre si: estan en idiomas distintos. Por eso las
secciones se identifican por posicion, y lo que se compara es su forma.

El resto queda en la disciplina de quien edita, y conviene decirlo en voz alta
en lugar de aparentar que el test cubre mas de lo que cubre.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Los pares sujetos a sincronia. La guia entra cuando exista su version
# castellana; hasta entonces este es el unico par.
PARES = [(ROOT / "README.md", ROOT / "README.es.md")]

CERCA = re.compile(r"^```(\w*)")
TITULO = re.compile(r"^## +(.+?)\s*$")
# Heuristica, no un parser de shell: un comentario abre al principio de la linea
# o despues de un espacio. NO entiende comillas, asi que un `#` adentro de un
# string se comeria junto con lo que sigue. Es suficiente para estos documentos
# y `test_la_heuristica_del_comentario_es_segura_para_estos_documentos` verifica
# esa cota en lugar de darla por sentada.
COMENTARIO = re.compile(r"(?:^|\s)#.*$")


def _recorrer(texto: str):
    """Emite ('titulo', t) y ('bloque', lenguaje, contenido) en orden de lectura."""
    lineas = texto.splitlines()
    i = 0
    while i < len(lineas):
        m = CERCA.match(lineas[i])
        if m:
            lenguaje = m.group(1)
            cuerpo = []
            i += 1
            while i < len(lineas) and not CERCA.match(lineas[i]):
                cuerpo.append(lineas[i])
                i += 1
            i += 1  # la cerca de cierre
            yield ("bloque", lenguaje, "\n".join(cuerpo))
            continue
        t = TITULO.match(lineas[i])
        if t:
            yield ("titulo", t.group(1))
        i += 1


def forma(texto: str) -> list[tuple[str, ...]]:
    """Por seccion, en orden: los lenguajes de los bloques que contiene.

    Es lo comparable entre idiomas: los titulos difieren, la estructura no.
    """
    secciones: list[list[str]] = [[]]
    for evento in _recorrer(texto):
        if evento[0] == "titulo":
            secciones.append([])
        else:
            secciones[-1].append(evento[1])
    return [tuple(s) for s in secciones]


def bloques(texto: str, lenguaje: str) -> list[str]:
    # Sin desempaquetar en el `for`: `_recorrer` emite tuplas de dos elementos
    # para los titulos y de tres para los bloques.
    return [e[2] for e in _recorrer(texto) if e[0] == "bloque" and e[1] == lenguaje]


def comandos(texto: str) -> list[str]:
    salida = []
    for bloque in bloques(texto, "bash"):
        for linea in bloque.splitlines():
            limpia = COMENTARIO.sub("", linea).strip()
            if limpia:
                salida.append(limpia)
    return salida


def test_los_pares_tienen_la_misma_forma():
    for a, b in PARES:
        fa, fb = forma(a.read_text(encoding="utf-8")), forma(b.read_text(encoding="utf-8"))
        assert fa == fb, (
            f"{a.name} y {b.name} tienen forma distinta: uno de los dos se atraso.\n"
            f"  {a.name}: {len(fa)} secciones, bloques {fa}\n"
            f"  {b.name}: {len(fb)} secciones, bloques {fb}"
        )


def test_los_bloques_que_no_son_prosa_son_identicos():
    """json y yaml son contrato: un ejemplo de config o de workflow que diverge
    entre idiomas le da a la mitad de los lectores algo que no funciona."""
    for a, b in PARES:
        ta, tb = a.read_text(encoding="utf-8"), b.read_text(encoding="utf-8")
        for lenguaje in ("json", "yaml"):
            assert bloques(ta, lenguaje) == bloques(tb, lenguaje), (
                f"los bloques ```{lenguaje} difieren entre {a.name} y {b.name}"
            )


def test_los_pares_documentan_los_mismos_comandos():
    for a, b in PARES:
        ca, cb = comandos(a.read_text(encoding="utf-8")), comandos(b.read_text(encoding="utf-8"))
        assert ca == cb, (
            f"{a.name} y {b.name} documentan comandos distintos.\n"
            f"  solo en {a.name}: {[c for c in ca if c not in cb]}\n"
            f"  solo en {b.name}: {[c for c in cb if c not in ca]}"
        )


def test_la_heuristica_del_comentario_es_segura_para_estos_documentos():
    """El stripper no parsea comillas. Mientras ningun comando documentado lleve
    una, la heuristica no puede mutilar nada. Si algun dia hace falta un comando
    con comillas, este test falla y obliga a mejorar el stripper en vez de
    dejarlo dando verdes falsos en silencio."""
    for par in PARES:
        for ruta in par:
            for bloque in bloques(ruta.read_text(encoding="utf-8"), "bash"):
                for linea in bloque.splitlines():
                    assert '"' not in linea and "'" not in linea, (
                        f"{ruta.name}: comando con comillas, la heuristica del "
                        f"comentario ya no alcanza -> {linea!r}"
                    )


def test_la_forma_ignora_los_encabezados_adentro_de_un_fence():
    texto = "## Real\n\n```bash\n## no es un titulo\n```\n\n## Tambien real\n"
    assert forma(texto) == [(), ("bash",), ()]


def test_la_forma_distingue_un_reordenamiento():
    """La version anterior comparaba solo la cantidad de secciones y esto pasaba."""
    uno = "## A\n\n```bash\nx\n```\n\n## B\n"
    otro = "## A\n\n## B\n\n```bash\nx\n```\n"
    assert forma(uno) != forma(otro)


def test_el_extractor_de_comandos_no_corta_un_hash_pegado():
    texto = "```bash\ngit show HEAD#nope   # esto si es comentario\n```\n"
    assert comandos(texto) == ["git show HEAD#nope"]
