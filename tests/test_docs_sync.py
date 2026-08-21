"""Los dos README dicen lo mismo, en lo que una maquina puede verificar.

Ninguna maquina puede decidir si dos textos en idiomas distintos significan lo
mismo. Prometer que el CI detecta divergencia semantica seria exactamente la
clase de garantia inflada que esta herramienta existe para no emitir.

Lo que si se puede verificar es la estructura y los comandos. Si el ingles gana
una seccion y el castellano no, o si un comando difiere entre los dos, uno de
los dos se atraso: es barato de cazar y caro de notar a mano. El resto queda en
la disciplina de quien edita, y conviene decirlo en voz alta en lugar de
aparentar que el test cubre mas de lo que cubre.

Los comentarios en linea de los bloques de comando SI tienen que diferir: son
prosa y se traducen. Por eso se comparan los comandos sin ellos.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Los pares sujetos a sincronia. La guia entra cuando exista su version
# castellana; hasta entonces este es el unico par.
PARES = [(ROOT / "README.md", ROOT / "README.es.md")]

CERCA = re.compile(r"^```")
TITULO = re.compile(r"^## +(.+?)\s*$")
# Un comentario abre al principio de la linea o despues de un espacio. Cortar en
# cualquier `#` romperia un comando que lo lleve adentro.
COMENTARIO = re.compile(r"(?:^|\s)#.*$")


def secciones(texto: str) -> list[str]:
    """Los titulos de nivel 2, en orden, ignorando los que caen en un fence.

    Un `##` adentro de un bloque de codigo no es un encabezado. Sin el estado
    del fence, un ejemplo con un comentario `## algo` inventaria una seccion
    que no existe y el test fallaria por su propio error.
    """
    fuera = True
    salida = []
    for linea in texto.splitlines():
        if CERCA.match(linea):
            fuera = not fuera
            continue
        if not fuera:
            continue
        m = TITULO.match(linea)
        if m:
            salida.append(m.group(1))
    return salida


def comandos(texto: str) -> list[str]:
    """Los comandos de los bloques ```bash, sin comentarios ni lineas vacias."""
    dentro = False
    salida = []
    for linea in texto.splitlines():
        if CERCA.match(linea):
            dentro = linea.strip() == "```bash"
            continue
        if not dentro:
            continue
        limpia = COMENTARIO.sub("", linea).strip()
        if limpia:
            salida.append(limpia)
    return salida


def test_los_pares_tienen_la_misma_estructura_de_secciones():
    for a, b in PARES:
        sa, sb = secciones(a.read_text(encoding="utf-8")), secciones(b.read_text(encoding="utf-8"))
        assert len(sa) == len(sb), (
            f"{a.name} tiene {len(sa)} secciones y {b.name} tiene {len(sb)}: "
            f"uno de los dos se atraso.\n  {a.name}: {sa}\n  {b.name}: {sb}"
        )


def test_los_pares_documentan_los_mismos_comandos():
    """Los comandos son el contrato; los comentarios que los rodean, no.

    Un comando que aparece en un idioma y no en el otro es documentacion que
    diverge en lo unico que el lector va a copiar y pegar.
    """
    for a, b in PARES:
        ca, cb = comandos(a.read_text(encoding="utf-8")), comandos(b.read_text(encoding="utf-8"))
        assert ca == cb, (
            f"{a.name} y {b.name} documentan comandos distintos.\n"
            f"  solo en {a.name}: {[c for c in ca if c not in cb]}\n"
            f"  solo en {b.name}: {[c for c in cb if c not in ca]}"
        )


def test_el_extractor_de_secciones_ignora_los_fences():
    """El propio extractor se prueba: si contara adentro de un fence, los dos
    documentos podrian coincidir por un error simetrico y el test pasaria."""
    texto = "## Real\n\n```bash\n## no es un titulo\n```\n\n## Tambien real\n"
    assert secciones(texto) == ["Real", "Tambien real"]


def test_el_extractor_de_comandos_no_corta_un_hash_pegado():
    """`#` pegado a un token es parte del comando; con un espacio antes, es un
    comentario. Cortar en cualquier `#` mutilaria el primero."""
    texto = "```bash\ngit show HEAD#nope   # esto si es comentario\n```\n"
    assert comandos(texto) == ["git show HEAD#nope"]
