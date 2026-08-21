"""Los dos README dicen lo mismo, en lo que una maquina puede verificar.

Ninguna maquina puede decidir si dos textos en idiomas distintos significan lo
mismo. Prometer que el CI detecta divergencia semantica seria exactamente la
clase de garantia inflada que esta herramienta existe para no emitir.

Lo que si se puede verificar:

- La FORMA: cuantas secciones hay y que bloques de codigo cuelgan de cada una,
  en orden. Detecta que se agregue o se borre una seccion, y que un bloque de
  codigo cambie de seccion o de lenguaje.

  NO detecta un renombre ni un reordenamiento entre secciones de la misma
  forma, y no puede: los titulos estan en idiomas distintos, asi que un titulo
  renombrado es indistinguible de uno traducido. La mayoria de las secciones de
  estos documentos no tienen bloques, o sea que su forma es () y son
  intercambiables para este chequeo. Es un limite del metodo, no un bug: entre
  idiomas no hay nada mas que comparar sin traducir, y traducir seria adivinar.
- Los BLOQUES QUE NO SON PROSA (json, yaml): son contrato y tienen que ser
  identicos entre los dos idiomas, despues de normalizar el fin de linea. No es
  byte a byte: CRLF y LF equivalentes pasan, y no se comparan los delimitadores
  del fence.
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
# o despues de un espacio. NO entiende comillas ni heredocs, asi que un `#` que
# no sea comentario se come junto con lo que sigue. Es suficiente para estos
# documentos; el alcance real de la guarda esta explicado en
# `test_la_heuristica_del_comentario_es_segura_para_estos_documentos`.
COMENTARIO = re.compile(r"(?:^|\s)#.*$")


def _recorrer(texto: str):
    """Emite ('titulo', t) y ('bloque', lenguaje, contenido) en orden de lectura.

    Reconoce solo el fence de tres backticks en columna cero, que es el unico
    que usan estos documentos. NO maneja fences de cuatro backticks conteniendo
    uno de tres, ni `~~~`, ni fences indentados, y un fence sin cerrar se come
    el resto del archivo sin avisar. Es un lector de estos README, no un parser
    de Markdown; si algun dia hacen falta esas formas, hay que reemplazarlo por
    uno de verdad en lugar de estirar este.
    """
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

    Es lo comparable entre idiomas: los titulos difieren, la estructura no. Con
    el costo de que dos secciones sin bloques son indistinguibles entre si, y
    la mayoria de estos documentos lo son. Ver el limite en el docstring del
    modulo.
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
    entre idiomas le da a la mitad de los lectores algo que no funciona.

    Compara el contenido despues de normalizar el fin de linea, no los bytes
    crudos."""
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
    """El stripper no parsea shell: corta desde el primer # precedido por espacio.

    Esta guarda prohibe comillas, que es el caso mas comun de un # que no es
    comentario. NO cubre todos: un heredoc sin comillas cuyo cuerpo lleve un #
    tambien se mutila, y esta guarda lo dejaria pasar. Y es mas estricta de lo
    necesario en la otra direccion: rechaza un comando con comillas aunque no
    tenga ningun #.

    Se acepta por lo que cuesta la alternativa, que es parsear shell. Cuando
    algun documento necesite un comando que esta guarda rechace, el test falla
    y obliga a decidir en vez de dejar la heuristica dando verdes en silencio."""
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


def test_la_forma_distingue_que_un_bloque_cambie_de_seccion():
    """La version anterior comparaba solo la cantidad de secciones y esto pasaba.

    Ojo con el alcance: distingue que un BLOQUE se mueva, no que se reordenen
    dos secciones sin bloques. Ver el limite explicado arriba."""
    uno = "## A\n\n```bash\nx\n```\n\n## B\n"
    otro = "## A\n\n## B\n\n```bash\nx\n```\n"
    assert forma(uno) != forma(otro)


def test_el_extractor_de_comandos_no_corta_un_hash_pegado():
    texto = "```bash\ngit show HEAD#nope   # esto si es comentario\n```\n"
    assert comandos(texto) == ["git show HEAD#nope"]
