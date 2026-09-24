"""El comentario del gate nombra todo lo que el esquema deja declarar.

El render tiene su propia tabla de nombres por clase, y el esquema no la
actualiza solo. v0.4 sumó `reviewer_correlation` y `reviewer_hardening_gap`,
R11 y R12 los exigen cuando un revisor declara independencia degradada o
`hardening: unverified`, y la tabla siguió con tres entradas: la declaración
validaba y el gate moría con KeyError al armar el comentario, también con
`--no-comment`, porque el cuerpo se renderiza antes de decidir si se publica
(#56). Ninguna declaración del repo llevaba esas clases y ningún test las
pasaba por el render, así que el modo degradado que v0.4 volvió declarable
rompía el gate la primera vez que alguien lo declaraba de verdad.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from disensor.render import CLASS_NAME, md_code, md_literal, render_comment
from disensor.rules import load_schema, validate_artifact

EXAMPLE = Path(__file__).resolve().parents[1] / "spec" / "examples" / "example_2_diff_gate.json"


def degradar(a: dict) -> dict:
    """Una ronda degradada bien declarada: el revisor es el mismo modelo que el
    generador y corrió sin endurecimiento verificado, con el ítem que cada
    regla exige para cada cosa."""
    gen = a["actors"]["generator"]
    r = a["actors"]["reviewers"][0]
    r["family"] = gen["family"]
    r["model"] = gen["model"]
    r["independence"] = "same_model_fresh_context"
    r["fallback_reason"] = {"code": "no_other_family_available"}
    r["hardening"] = "unverified"
    a["residue"]["items"] += [
        {
            "id": "r4",
            "class": "reviewer_correlation",
            "reviewer_ref": r["reviewer_id"],
            "requires_human_attention": True,
            "description": (
                "El revisor comparte modelo con el generador: los errores que ese modelo "
                "comete de forma sistemática no los cubrió esta ronda."
            ),
        },
        {
            "id": "r5",
            "class": "reviewer_hardening_gap",
            "reviewer_ref": r["reviewer_id"],
            "requires_human_attention": True,
            "description": (
                "El adaptador no tiene verificada la neutralización de las instrucciones "
                "del proyecto: el material revisado pudo hablarle al revisor."
            ),
        },
    ]
    return a


@pytest.fixture()
def degradada() -> dict:
    a = degradar(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    errores = validate_artifact(a)
    assert errores == [], f"la declaración degradada tiene que validar: el bug es del render, no de las reglas: {errores}"
    return a


def test_render_names_every_class_the_schema_admits():
    """La tabla del render y el enum del esquema no se separan en silencio."""
    clases = load_schema()["$defs"]["residue_item"]["properties"]["class"]["enum"]
    assert set(CLASS_NAME) == set(clases)


@pytest.mark.parametrize("profile", ["full", "minimized"])
def test_the_comment_names_the_degraded_reviewer_in_both_profiles(degradada, profile):
    """El ítem dice de qué revisor habla también cuando el perfil omite la descripción."""
    degradada["profile"] = profile
    if profile == "minimized":
        for item in degradada["residue"]["items"]:
            item.pop("description", None)
    body = render_comment([degradada], {}, [])
    rid = degradada["actors"]["reviewers"][0]["reviewer_id"]
    for klass in ("reviewer_correlation", "reviewer_hardening_gap"):
        linea = next(line for line in body.splitlines() if CLASS_NAME[klass] in line)
        assert f"(reviewer {rid})" in linea, linea
        assert "requires human attention" in linea, linea


@pytest.mark.parametrize("profile", ["full", "minimized"])
def test_a_finding_ref_does_not_hide_the_reviewer(degradada, profile):
    """Hallazgo de la ronda del PR #57: el esquema admite `finding_ref` y
    `reviewer_ref` en el mismo ítem, y el primero tapaba al segundo."""
    for item in degradada["residue"]["items"]:
        if item["class"] in ("reviewer_correlation", "reviewer_hardening_gap"):
            item["finding_ref"] = "h1"
    assert validate_artifact(degradada) == [], "las dos referencias juntas son válidas: el bug era del render"
    degradada["profile"] = profile
    if profile == "minimized":
        for item in degradada["residue"]["items"]:
            item.pop("description", None)
    body = render_comment([degradada], {}, [])
    rid = degradada["actors"]["reviewers"][0]["reviewer_id"]
    for klass in ("reviewer_correlation", "reviewer_hardening_gap"):
        linea = next(line for line in body.splitlines() if CLASS_NAME[klass] in line)
        assert f"(finding h1, reviewer {rid})" in linea, linea


# --- El texto de la declaracion se ve como se escribio (#85) ------------------------
#
# Lo que GitHub hace con cada caso se midio con su API de markdown, en modo gfm:
# el emoji y la formula no respetan la barra, y adentro de una URL suelta la barra
# queda a la vista. Estas pruebas no llaman a GitHub: leen el markdown que sale con
# las reglas que ese subconjunto usa, y exigen que no quede ninguna marca activa.

BARRA = chr(92)
PUNTUACION = "!\"#$%&'()*+,-./:;<=>?@[" + BARRA + "]^_`{|}~"
ENTIDADES = {"&amp;": "&", "&lt;": "<", "&gt;": ">"}


def piezas(md: str):
    """El markdown del render en piezas: (tipo, lo que se ve)."""
    i = 0
    while i < len(md):
        if md[i] == BARRA and i + 1 < len(md) and md[i + 1] in PUNTUACION:
            yield "escape", md[i + 1]
            i += 2
            continue
        if md[i] == "`":
            cerca = re.match(r"`+", md[i:]).group()
            cierre = None
            # GitHub no reconoce una cerca de mas de 80 comillas (medido).
            if len(cerca) <= 80:
                cierre = re.compile(r"(?<!`)" + cerca + r"(?!`)").search(md, i + len(cerca))
            if cierre:
                # El codigo va entero, con sus comillas: la prueba compara contra
                # el texto declarado, que las tiene.
                yield "codigo", md[i:cierre.end()]
                i = cierre.end()
                continue
            yield "crudo", cerca
            i += len(cerca)
            continue
        entidad = next((e for e in ENTIDADES if md.startswith(e, i)), None)
        if entidad:
            yield "entidad", ENTIDADES[entidad]
            i += len(entidad)
            continue
        span = re.match(r"<span>(.)</span>", md[i:])
        if span:
            yield "span", span.group(1)
            i += span.end()
            continue
        if md.startswith("<br>", i):
            yield "salto", "\n"
            i += 4
            continue
        yield "crudo", md[i]
        i += 1


def lo_que_se_ve(md: str) -> str:
    return "".join(visto for _, visto in piezas(md))


def marcas_activas(md: str) -> list[str]:
    """Lo que GitHub interpretaria en el texto crudo que quedo fuera del codigo.

    Las piezas que no son crudas (escapes, entidades, spans, codigo) cuentan como
    un espacio: cortan lo que las rodea.
    """
    crudo = "".join(visto if tipo == "crudo" else " " for tipo, visto in piezas(md))
    halladas = [c for c in "*~`<>&$" if c in crudo]
    for patron in (r"\]\(", r"://", r"(?i)www\.", r":[A-Za-z0-9_+-]+:", BARRA * 2 + "$"):
        halladas += [m.group() for m in re.finditer(patron, crudo)]
    # Un bloque se abre por lo que la linea tiene al principio, escapes incluidos.
    if re.match(r" {0,3}([-+#]|[0-9]+[.)])", md):
        halladas.append("inicio de bloque")
    for i, c in enumerate(crudo):
        antes, despues = crudo[i - 1:i], crudo[i + 1:i + 2]
        if c == "_" and not (antes.isalnum() and despues.isalnum()):
            halladas.append("_ fuera de una palabra")
    return halladas


CASOS = {
    "los cuatro del issue": "__x__ y *x* y [t](u) y <!-- x -->",
    "la ruta de a2dae540": "tools/__pycache__/censo-brechas.cpython-314.pyc",
    "comentario html": "antes <!-- esto no se ve --> despues",
    "codigo y comilla suelta": "`codigo_con <!-- -->` y _guion_ y una ` suelta",
    "cercas dobles": "``doble ` adentro`` y `` `bordes` ``",
    "urls": "https://ejemplo.invalid/a_b?c=1&d=2 y www.ejemplo.invalid y HTTPS://X.INVALID/Y_Z",
    "emoji, formula y tachado": ":white_check_mark: y $" + BARRA + "phantom{oculto}$ y ~~t~~",
    "saltos y encabezado": "uno\ndos\r\n## tres\r- cuatro",
    "encabezado al principio": "## titulo",
    "lista al principio": "1) uno y 2. dos",
    "barras": "C:" + BARRA + "Users" + BARRA + "x y a" + BARRA + "*b y fin" + BARRA,
    "entidades y html": "a & b &amp; c <b>x</b> y &lt;",
    "corchetes sin enlace": "[G6] y [x] y snake_case_largo",
    "cerca de 80 comillas": "`" * 80 + " <!-- x --> *y* " + "`" * 80,
    "cerca de 81 comillas": "`" * 81 + " <!-- x --> *y* " + "`" * 81,
}


@pytest.mark.parametrize("caso", list(CASOS))
def test_declaration_text_is_shown_as_written(caso):
    texto = CASOS[caso]
    md = md_literal(texto)
    assert lo_que_se_ve(md) == re.sub(r"\r\n|\r", "\n", texto)
    assert marcas_activas(md) == [], md
    assert "\n" not in md and "\r" not in md, "un salto real deja que el texto arme su propio bloque"


def test_what_github_does_not_read_as_markup_is_left_alone():
    """El mismo markdown sale por el log del CI: lo que no se interpreta no se escapa."""
    for texto in ("[G6] el gate", "reviewer_correlation", "C:" + BARRA + "Users" + BARRA + "x",
                  "issue #18 y 3 + 2"):
        assert md_literal(texto) == texto


def test_md_code_falls_back_to_text_past_the_longest_fence_github_reads():
    texto = "a" + "`" * 80 + "<!-- x -->"
    md = md_code(texto)
    assert lo_que_se_ve(md) == texto
    assert marcas_activas(md) == [], md


def test_md_code_cannot_be_closed_by_its_own_backticks():
    for texto in (".residue/x.json", "a`b", "`x", "x``y`", " a "):
        md = md_code(texto)
        [(tipo, visto)] = list(piezas(md))
        assert tipo == "codigo"
        contenido = visto.strip("`")
        if contenido.startswith(" ") and contenido.endswith(" ") and contenido.strip():
            contenido = contenido[1:-1]
        assert contenido == texto, md


@pytest.fixture()
def con_casos() -> dict:
    """Una declaracion valida con el texto de los casos en los campos que se muestran."""
    a = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    items = a["residue"]["items"]
    items[0]["description"] = CASOS["los cuatro del issue"]
    items[0]["evidence"] = {"link": "https://ejemplo.invalid/a_(b) c?d=1&e=2"}
    a["actors"]["generator"]["model"] = "modelo *raro* <!--"
    a["actors"]["reviewers"][0]["model"] = "[revisor](https://ejemplo.invalid) -->"
    assert validate_artifact(a) == []
    return a


def test_the_comment_shows_the_declaration_as_written(con_casos):
    body = render_comment([con_casos], {}, [])
    assert body.count("<!--") == 1, "solo el marcador del propio gate"
    assert md_literal(CASOS["los cuatro del issue"]) in body
    assert "Generator modelo \\*raro\\* &lt;!--" in body
    assert "reviewer [revisor\\](https\\://ejemplo.invalid) --&gt;" in body


def test_the_evidence_link_shows_its_destination():
    """`[evidence](u)` decia "evidence" y llevaba a cualquier lado; un `)` o un
    espacio en `u` cortaban el enlace."""
    from disensor.render import _evidence_link

    link = "https://ejemplo.invalid/a_(b) c?d=1&e=2"
    md = _evidence_link(link)
    texto, destino = re.fullmatch(r"\[(.*)\]\(<(.*)>\)", md).groups()
    assert lo_que_se_ve(texto) == link
    assert destino == link.replace("&", "&amp;")
    assert _evidence_link("javascript:alert(1)") == "javascript:alert(1)", "solo http(s) es enlace"
    assert _evidence_link("src/x.cs#L41") == "src/x.cs#L41"


def test_error_lines_escape_what_they_quote_from_the_declaration():
    """Los mensajes citan valores de la declaracion, y el nombre del archivo lo elige
    quien lo agrega: un `<!--` ahi escondia las lineas que siguieran."""
    body = render_comment([], {".residue/a`b<!--.json": ["[R2] generic marker: '<!-- x'"]},
                          ["[G7] `x` y -->"])
    # El nombre del archivo va entero adentro del codigo, donde se muestra literal.
    assert "- ``.residue/a`b<!--.json``: [R2] generic marker: '&lt;!-- x'" in body
    assert "- [G7] `x` y --&gt;" in body
    assert "'<!-- x'" not in body and "y -->" not in body


def test_the_gate_comment_and_the_job_summary_show_it_as_written(tmp_path, monkeypatch, capsys):
    """El criterio del issue, de punta a punta: el gate arma un solo cuerpo que va al
    comentario del PR y al resumen del job."""
    import subprocess

    from disensor import gate

    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args) -> str:
        return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                              cwd=repo, check=True, capture_output=True, text=True).stdout.strip()

    git("init", "-q", "-b", "main")
    (repo / "disensor.config.json").write_text(
        json.dumps({"criticality_level": "B", "level_A_enabled": False}), encoding="utf-8")
    (repo / "README.md").write_text("x", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "codigo")
    a = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    a["event"]["head_commit"] = git("rev-parse", "HEAD")
    a["event"]["base_commit"] = base
    a["residue"]["items"][0]["description"] = CASOS["los cuatro del issue"]
    # El aviso de confinamiento sin verificar cita el reviewer_id, que es texto libre.
    revisor = a["actors"]["reviewers"][0]
    revisor["reviewer_id"] = "r<!--1"
    revisor["confinement"]["verified"] = False
    for hallazgo in a["findings"]:
        hallazgo["origin"] = "r<!--1"
    assert validate_artifact(a) == []
    (repo / ".residue").mkdir()
    (repo / ".residue" / f"{a['event']['event_id']}.json").write_text(
        json.dumps(a, ensure_ascii=False), encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "declaracion")
    head = git("rev-parse", "HEAD")

    comentarios = []
    monkeypatch.setattr(gate, "post_comment", lambda body: comentarios.append(body) or "capturado")
    resumen = tmp_path / "resumen.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(resumen))
    assert gate.run_gate(".residue", "disensor.config.json", base, head, repo,
                         post=True, report=False) == 0
    esperado = md_literal(CASOS["los cuatro del issue"])
    [comentario] = comentarios
    for cuerpo in (comentario, resumen.read_text(encoding="utf-8")):
        assert esperado in cuerpo
        assert "confinement of reviewer r&lt;!--1 without post-run verification" in cuerpo
        assert cuerpo.count("<!--") == 1, "solo el marcador del propio gate"
