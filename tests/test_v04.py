"""Schema v0.4: el modo degradado declarado, y la convivencia de versiones.

Dos cosas se prueban acá. Una es que la independencia declarada no sea un
string que nadie mira: si `cross_family` se pudiera escribir sobre dos
revisores de la misma familia, la degradación quedaría invisible y todo el
punto de registrarla se cae. La otra es que una declaración vieja se valide con
SUS reglas: el dispatch existe porque una forma combinada dejaba que un
artefacto pidiera prestados campos de una versión que no existía cuando se
escribió.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from disensor.rules import CURRENT, load_schema, validate_artifact

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "spec" / "examples"


def load(name: str, historico: bool = False) -> dict:
    base = EXAMPLES / "v0.3" if historico else EXAMPLES
    return json.loads((base / name).read_text(encoding="utf-8"))


@pytest.fixture()
def diff():
    return load("example_2_diff_gate.json")


def degradar(a: dict, independencia: str = "same_model_fresh_context") -> dict:
    """Deja el artefacto como una ronda degradada bien declarada."""
    gen = a["actors"]["generator"]["family"]
    r = a["actors"]["reviewers"][0]
    r["family"] = gen
    r["model"] = a["actors"]["generator"]["model"]
    r["independence"] = independencia
    r["fallback_reason"] = {"code": "no_other_family_available"}
    a["residue"] = {
        "items": [
            {
                "id": "r1",
                "class": "reviewer_correlation",
                "reviewer_ref": r["reviewer_id"],
                "requires_human_attention": True,
                "description": (
                    "El revisor comparte modelo con el generador: los errores que el modelo "
                    "base comete de forma sistematica no los cubrio esta ronda."
                ),
            }
        ]
    }
    return a


def test_the_examples_declare_the_current_version(diff):
    assert diff["schema"] == CURRENT
    assert validate_artifact(diff) == []


def test_a_degraded_round_is_declarable(diff):
    """Lo que v0.4 viene a habilitar: decir la verdad cuando no hubo otra familia.

    Hasta v0.3 esta declaracion era imposible: R4 la rechazaba, asi que quien no
    tenia un segundo modelo no podia declarar nada y la unica salida honesta
    quedaba fuera del registro.
    """
    a = degradar(copy.deepcopy(diff))
    a["metrics"]["counts"] = {
        "total_findings": 0,
        "valid": {"incorporated": 0, "debt_recorded": 0, "owner_decision": 0},
        "false_positives": {"refuted_verifiable": 0, "refuted_interpretive": 0},
        "escalated_open": 0,
    }
    a["findings"] = []
    assert validate_artifact(a) == []


def test_cross_family_with_the_same_family_is_rejected(diff):
    """La mentira mas barata: declarar independencia que las familias desmienten."""
    a = copy.deepcopy(diff)
    a["actors"]["reviewers"][0]["family"] = a["actors"]["generator"]["family"]
    errors = validate_artifact(a)
    assert any("[R4]" in e for e in errors), errors


def test_a_degraded_independence_with_a_different_family_is_rejected(diff):
    """Y la de al lado: declararse degradado teniendo de hecho otra familia."""
    a = copy.deepcopy(diff)
    a["actors"]["reviewers"][0]["independence"] = "same_model_fresh_context"
    errors = validate_artifact(a)
    assert any("[R4]" in e for e in errors), errors


def test_a_degraded_round_without_its_residue_item_is_rejected(diff):
    """Sin residuo declarado, el modo degradado seria gratis y seria el default."""
    a = degradar(copy.deepcopy(diff))
    a["residue"] = {
        "declared_absence": True,
        "declaration": "No quedo residuo alguno de esta ronda, revisada de punta a punta.",
    }
    errors = validate_artifact(a)
    assert any("[R11]" in e for e in errors), errors


def test_a_degraded_round_without_a_fallback_reason_is_rejected(diff):
    a = degradar(copy.deepcopy(diff))
    del a["actors"]["reviewers"][0]["fallback_reason"]
    errors = validate_artifact(a)
    assert any("[R4]" in e and "fallback_reason" in e for e in errors), errors


def test_level_a_does_not_admit_a_degraded_round(diff):
    """Declarable no es admisible: en el nivel de lo irreversible, bloquea."""
    a = degradar(copy.deepcopy(diff))
    a["event"]["criticality_level"] = "A"
    errors = validate_artifact(a)
    assert any("[R4]" in e and "Level A" in e for e in errors), errors


def test_unverified_hardening_needs_its_own_residue_item(diff):
    """Correlacion y endurecimiento son riesgos distintos y llevan items distintos."""
    a = copy.deepcopy(diff)
    a["actors"]["reviewers"][0]["hardening"] = "unverified"
    errors = validate_artifact(a)
    assert any("[R12]" in e for e in errors), errors

    a["residue"] = {
        "items": [
            {
                "id": "r1",
                "class": "reviewer_hardening_gap",
                "reviewer_ref": a["actors"]["reviewers"][0]["reviewer_id"],
                "requires_human_attention": True,
                "description": (
                    "El adaptador no tiene verificada la neutralizacion de las instrucciones "
                    "del proyecto: el material revisado pudo hablarle al revisor."
                ),
            }
        ]
    }
    a["findings"] = []
    a["metrics"]["counts"] = {
        "total_findings": 0,
        "valid": {"incorporated": 0, "debt_recorded": 0, "owner_decision": 0},
        "false_positives": {"refuted_verifiable": 0, "refuted_interpretive": 0},
        "escalated_open": 0,
    }
    assert validate_artifact(a) == []


def test_one_residue_item_cannot_cover_two_degraded_reviewers(diff):
    """El item nombra a su revisor: sin eso, uno solo taparia a todos."""
    a = degradar(copy.deepcopy(diff))
    otro = copy.deepcopy(a["actors"]["reviewers"][0])
    otro["reviewer_id"] = "r2"
    a["actors"]["reviewers"].append(otro)
    errors = validate_artifact(a)
    assert any("[R11]" in e and "r2" in e for e in errors), errors


# --- Convivencia de versiones -------------------------------------------------

def test_a_historical_declaration_validates_under_its_own_rules():
    """Una v0.3 vieja sigue siendo legible: la historia no se reescribe."""
    a = load("example_2_diff_gate.json", historico=True)
    assert a["schema"] == "residue/v0.3"
    assert validate_artifact(a) == []


def test_the_current_version_renamed_to_an_older_one_is_rejected(diff):
    """Cambiarle la etiqueta a una declaracion no la convierte en otra version.

    Es el caso que el dispatch existe para cerrar: con una forma combinada,
    un artefacto podia declarar la version vieja y seguir usando campos de la
    nueva, o al reves.
    """
    a = copy.deepcopy(diff)
    a["schema"] = "residue/v0.3"
    errors = validate_artifact(a)
    assert errors, "un v0.4 con etiqueta v0.3 no puede ser valido"
    assert any("independence" in e for e in errors), errors


def test_an_older_declaration_cannot_borrow_a_newer_field():
    """Y en la otra direccion: v0.3 no conoce independence."""
    a = load("example_2_diff_gate.json", historico=True)
    a["actors"]["reviewers"][0]["independence"] = "cross_family"
    errors = validate_artifact(a)
    assert errors, "v0.3 no deberia aceptar un campo de v0.4"


def test_an_unknown_version_fails_instead_of_guessing(diff):
    a = copy.deepcopy(diff)
    a["schema"] = "residue/v9.9"
    errors = validate_artifact(a)
    assert len(errors) == 1
    assert "does not know how to validate" in errors[0]


def test_each_version_has_its_own_frozen_resource():
    """Un recurso por version, y cada uno fija la suya con const."""
    for version in ("residue/v0.2", "residue/v0.3", "residue/v0.4"):
        s = load_schema(version)
        declarado = s["properties"]["schema"]
        fijado = declarado.get("const") or declarado.get("enum")
        assert version in ([fijado] if isinstance(fijado, str) else fijado), version


def test_an_item_referencing_a_missing_reviewer_is_refused(diff):
    """La clase que admite reviewer_ref es de v0.4, asi que este caso no se puede
    expresar como vector v0.3 y va aca hasta que exista la suite de su version."""
    a = degradar(copy.deepcopy(diff))
    a["residue"] = {"items": [{
        "id": "r1", "class": "reviewer_correlation", "reviewer_ref": "revisor-fantasma",
        "requires_human_attention": True,
        "description": ("El revisor comparte familia con el generador y ese solapamiento no quedo "
                        "cubierto por la ronda, con texto suficientemente concreto."),
    }]}
    errores = validate_artifact(a)
    assert any("R13" in e and "revisor-fantasma" in e for e in errores), errores


def test_r13_does_not_reach_frozen_versions(diff):
    """Una declaracion emitida bajo un identificador congelado se sigue juzgando
    con las reglas de su contrato: endurecer una regla no puede volverla invalida.

    Es lo que los dos README prometen, y R13 entro sin la guarda: corria tambien
    para v0.2 y v0.3.
    """
    from disensor.rules import applies_from

    assert applies_from("residue/v0.4", "residue/v0.4")
    assert not applies_from("residue/v0.3", "residue/v0.4")
    assert not applies_from("residue/v0.2", "residue/v0.4")

    historico = load("example_2_diff_gate.json", historico=True)
    historico["residue"]["items"][1]["id"] = historico["residue"]["items"][0]["id"]
    assert not [e for e in validate_artifact(historico) if "R13" in e]


def test_r13_reaches_the_version_that_introduced_it(diff):
    a = copy.deepcopy(diff)
    a["findings"][0]["origin"] = "revisor-que-no-esta"
    assert [e for e in validate_artifact(a) if "R13" in e]


# Las formas en que un literal de version puede aparecer en el codigo sin que
# sea una regla preguntando por una version exacta. Es una lista blanca a
# proposito: una lista de formas prohibidas siempre va una forma atras, y este
# defecto ya se colo dos veces por una forma que el patron de turno no cazaba.
FORMAS_LEGITIMAS = (
    # La clave de un mapa de versiones conocidas, anclada al principio de la
    # linea: sin el ancla, una comparacion dentro de un `if` tambien termina en
    # dos puntos y se colaba como si fuera una clave.
    r'^"residue/v[0-9.]+":',
    # El argumento `introduced` de la pregunta ordinal, que es la forma correcta.
    r'applies_from\([^)]*"residue/v[0-9.]+"\)',
    r'appliesFrom\([^)]*"residue/v[0-9.]+"\)',
    # La definicion de las constantes de vigencia, por su nombre y no por su
    # forma: cualquier constante nueva que envuelva un literal falla esta prueba
    # y obliga a agregarla aca, que es una decision visible en un diff. Con un
    # patron generico bastaba escribir SOLO = "residue/v0.4" y comparar contra
    # eso para volver a tener una regla atada a una version exacta.
    r'^CURRENT = "residue/v[0-9.]+"$',
    r'^const ESQUEMA_VIGENTE = "residue/v[0-9.]+";$',
)


def _apariciones_ilegitimas(fuentes, raiz):
    """Toda aparicion de un literal de version que no este en una forma conocida."""
    import re

    literal = re.compile(r"""["'`]residue/v[0-9]+(?:\.[0-9]+)*["'`]""")
    legitimas = [re.compile(f) for f in FORMAS_LEGITIMAS]
    fuera = []
    for p in fuentes:
        for n, linea in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            desnuda = linea.strip()
            # Un comentario o una linea de docstring no ejecuta nada.
            if desnuda.startswith(("#", "//", "*", "/*")):
                continue
            if not literal.search(desnuda):
                continue
            if any(f.search(desnuda) for f in legitimas):
                continue
            fuera.append(f"{p.relative_to(raiz).as_posix()}:{n}: {desnuda}")
    return fuera


def _fuentes(raiz):
    return [
        *sorted((raiz / "src/disensor").rglob("*.py")),
        *sorted((raiz / "plano-evidencia/src").rglob("*.ts")),
        *sorted((raiz / "plano-evidencia/scripts").rglob("*.ts")),
    ]


def test_no_literal_version_comparison_in_any_source():
    """Ninguna fuente se pregunta si un artefacto ES una version exacta.

    Una comparacion contra un literal se lee como "esta regla vale desde v0.4" y
    significa "vale SOLO en v0.4": el dia que se abra la siguiente, el artefacto
    cae al camino de las versiones anteriores, la forma nueva de la regla
    desaparece y ninguna prueba falla. La pregunta correcta es ordinal.

    Comparar contra la CONSTANTE de vigencia es otra cosa y es legitima: no
    pregunta que reglas aplican sino si algo puede EMITIRSE hoy, que es
    exactamente una igualdad (G9, y la politica de la ingesta). Por eso lo que se
    persigue es el literal y no el operador.

    Lo que esta guardia NO puede cubrir, y queda dicho: es sintactica y mira
    fuentes, asi que un literal armado en tiempo de ejecucion (concatenado,
    formateado, leido de un archivo) le pasa por al lado. Lo que si cubre, desde
    que las constantes de vigencia se listan por nombre y no por forma, es la
    constante auxiliar: agregar una obliga a tocar esta lista, y eso se ve.
    """
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1]
    fuentes = _fuentes(raiz)
    assert len(fuentes) > 10, fuentes
    fuera = _apariciones_ilegitimas(fuentes, raiz)
    assert not fuera, (
        "un literal de version fuera de las formas conocidas; si es legitimo, va a "
        "FORMAS_LEGITIMAS con su motivo:\n" + "\n".join(fuera)
    )


def test_the_guard_catches_every_form_the_defect_had(tmp_path):
    """La guardia se verifica contra las formas que tuvo y las que le señalaron.

    Una guardia que no se prueba contra su propio defecto es una linea que
    tranquiliza y no sostiene nada: la primera version pasaba en verde ante la
    mitad de esta lista y la segunda ante un tercio.
    """
    reintroducciones = [
        'if a["schema"] == "residue/v0.4":',
        "if a['schema'] == 'residue/v0.5':",
        'if (a.schema === "residue/v0.4") {',
        'if "residue/v0.5" == a["schema"]:',
        'if a["schema"] != "residue/v0.5":',
        'if (a.schema !== "residue/v0.4") {',
        '        case "residue/v0.4":',
        'if a["schema"] in {"residue/v0.4"}:',
        'if a["schema"] == ("residue/v0.4"):',
        'if (["residue/v0.4"].includes(a.schema)) {',
        "if (a.schema === `residue/v0.4`) {",
        'if a["schema"] == "residue/v0.4.0":',
        # La constante auxiliar, que era el limite declarado de la version
        # anterior de esta guardia: al listar las de vigencia por nombre en vez
        # de por forma, una constante nueva ya no entra sin que se vea.
        'SOLO_V04 = "residue/v0.4"',
        'SOLO = "residue/v0.4"',
        'const SOLO = "residue/v0.4";',
    ]
    legitimas = [
        'if applies_from(a["schema"], "residue/v0.4"):',
        'if (appliesFrom(a.schema, "residue/v0.4")) {',
        "if not artifact.errors and declared_version != CURRENT_SCHEMA:",
        "if (artefacto.schema !== ESQUEMA_VIGENTE) {",
        '    "residue/v0.4": "residue.schema.v0.4.json",',
        'CURRENT = "residue/v0.4"',
        'const ESQUEMA_VIGENTE = "residue/v0.4";',
        '# El comentario puede nombrar "residue/v0.4" sin que sea una regla.',
    ]

    def caza(texto: str) -> bool:
        f = tmp_path / "fuente.py"
        f.write_text(texto, encoding="utf-8")
        return bool(_apariciones_ilegitimas([f], tmp_path))

    for forma in reintroducciones:
        assert caza(forma), f"la guardia no caza: {forma}"
    for forma in legitimas:
        assert not caza(forma), f"la guardia molesta a: {forma}"


def test_ordinality_does_not_go_through_a_derived_order():
    """La ordinalidad compara claves; no busca posiciones en un orden.

    Salia de la posicion en el diccionario, o sea del orden en que alguien
    escribio las lineas, y la primera prueba que escribi para eso pasaba igual
    con la derivacion regresada: el diccionario ya estaba escrito en orden, asi
    que ordenarlo o no daba lo mismo y la prueba no distinguia. Mientras exista
    un orden derivado hay un lugar donde equivocarse, asi que no hay: se comparan
    las claves numericas, y esta prueba mira que el codigo lo haga.
    """
    import re
    from pathlib import Path

    from disensor.rules import ORDER, _version_key

    assert _version_key("residue/v0.10") > _version_key("residue/v0.9")
    assert sorted(["residue/v0.10", "residue/v0.9"]) == ["residue/v0.10", "residue/v0.9"]
    assert list(ORDER) == sorted(ORDER, key=_version_key)

    raiz = Path(__file__).resolve().parents[1]
    for fuente, funcion in (("src/disensor/rules.py", "def applies_from"),
                            ("plano-evidencia/src/validar.ts", "export function appliesFrom")):
        texto = (raiz / fuente).read_text(encoding="utf-8")
        cuerpo = texto[texto.index(funcion):]
        cuerpo = cuerpo[:cuerpo.index("\n\n\n")] if "\n\n\n" in cuerpo else cuerpo
        # Nombrar ORDER para armar un mensaje es inocuo; buscar una POSICION en
        # el es la forma que tenia el defecto.
        assert not re.search(r"\bORDER\.(index|indexOf)\b", cuerpo), (
            f"{fuente}: la ordinalidad volvio a pasar por un orden derivado, que "
            "es un lugar donde equivocarse sin que nada falle"
        )
        assert "ersionKey" in cuerpo or "_version_key" in cuerpo, fuente


def test_the_evidence_plane_knows_the_same_versions_as_the_reference():
    """Abrir una version nueva sin llevar el port y la ingesta es una falla.

    Son cuatro lugares que tienen que moverse juntos: SCHEMA_FILES de la
    referencia, el del port, los recursos que el Worker importa uno por uno
    porque no tiene filesystem, y la version que la ingesta acepta emitir. Nada
    los ataba: el port se quedo dos versiones atras y lo que lo delato fue que
    la ingesta rechazaba el cien por ciento de lo que el CLI emite.
    """
    import re
    from pathlib import Path

    from disensor.rules import CURRENT, SCHEMA_FILES

    raiz = Path(__file__).resolve().parents[1]
    port = (raiz / "plano-evidencia/src/validar.ts").read_text(encoding="utf-8")
    worker = (raiz / "plano-evidencia/src/index.ts").read_text(encoding="utf-8")

    def mapa(texto, declaracion, valor):
        """El bloque de un mapa a nivel de modulo, hasta su cierre en columna cero.

        Cortar en el primer `};` alcanzaba para el mapa actual y dejaba pasar
        cualquier cosa escrita despues; el cierre de una declaracion de modulo
        esta al principio de la linea.
        """
        assert texto.count(declaracion) == 1, declaracion
        bloque = texto[texto.index(declaracion):]
        fin = re.search(r"^\};", bloque, re.M)
        assert fin, declaracion
        return dict(re.findall(valor, bloque[:fin.start()]))

    assert mapa(port, "export const SCHEMA_FILES", r'"(residue/v[^"]+)":\s*"([^"]+)"') == SCHEMA_FILES

    declaradas = mapa(worker, "export const VALIDADORES",
                      r'"(residue/v[^"]+)":\s*compilarSchema\((\w+)')
    assert sorted(declaradas) == sorted(SCHEMA_FILES)
    for version, simbolo in declaradas.items():
        # El path entero, no el nombre final: dos archivos distintos pueden
        # llamarse igual en directorios distintos.
        importado = re.search(rf'^import {simbolo} from "([^"]+)";$', worker, re.M)
        assert importado, f"{simbolo} no se importa"
        assert importado.group(1) == f"../../spec/{SCHEMA_FILES[version]}", (
            version, importado.group(1))

    vigente = re.findall(r'^const ESQUEMA_VIGENTE = "([^"]+)";$', worker, re.M)
    assert vigente == [CURRENT], vigente


def test_a_frozen_version_is_never_dropped():
    """Ningun recurso congelado sale del mapa de versiones conocidas.

    La ingesta valida antes de buscar el recibo, asi que un artefacto ya atestado
    solo puede devolver su recibo mientras su version siga siendo validable. Eso
    convierte "las versiones congeladas se leen para siempre" en una invariante
    de la que depende la idempotencia, y una invariante de la que algo depende
    tiene que estar sostenida por algo mas que la costumbre.
    """
    import re
    from pathlib import Path

    from disensor.rules import SCHEMA_FILES

    raiz = Path(__file__).resolve().parents[1]
    congelados = sorted(p.name for p in (raiz / "spec").glob("residue.schema.v*.json"))
    assert congelados, "no hay recursos congelados"
    assert sorted(SCHEMA_FILES.values()) == congelados, (
        "hay un schema congelado que el mapa de versiones no conoce, o al reves; "
        "sacar una version del mapa rompe la idempotencia de todo lo ya atestado "
        "bajo ella"
    )
    for version, archivo in SCHEMA_FILES.items():
        assert archivo == f"residue.schema.{version.split('/')[1]}.json", (version, archivo)
        # Y cada recurso se declara a si mismo: el discriminador que el archivo
        # exige es la version bajo la que esta archivado.
        texto = (raiz / "spec" / archivo).read_text(encoding="utf-8")
        declara = re.search(r'"schema":\s*\{[^}]*"const":\s*"([^"]+)"', texto)
        assert declara and declara.group(1) == version, (archivo, declara)


def test_an_unhashable_schema_is_rejected_and_does_not_crash():
    """El discriminador puede ser cualquier cosa: JSON entra de afuera.

    `declared not in SCHEMA_FILES` con una lista o un objeto reventaba con
    TypeError en vez de devolver el error de schema, y ni el CLI ni el gate lo
    atrapan: un artefacto de tres bytes tumbaba el proceso.
    """
    for basura in ([1, 2], {"a": 1}, 3, None, True):
        errores = validate_artifact({"schema": basura})
        assert errores and errores[0].startswith("[schema]"), (basura, errores)


def test_shared_vectors_of_identifier_form_and_ordinality():
    """La forma del identificador y la ordinalidad se verifican con vectores.

    Es como se verifica todo el resto del contrato, y era justo lo que estas dos
    cosas no tenian: la equivalencia entre las dos implementaciones se habia
    establecido leyendo las dos, y ahi fue donde los parsers se separaron sin que
    nada lo dijera. El port leia `residue/v0.` como (0, 0) y `residue/v0.1e1`
    como (0, 10); esta implementacion los rechaza.
    """
    import json
    from pathlib import Path

    from disensor.rules import _version_key, applies_from

    raiz = Path(__file__).resolve().parents[1]
    casos = json.loads((raiz / "spec/version_ordinality.json").read_text(encoding="utf-8"))

    for c in casos["form"]:
        try:
            _version_key(c["id"])
            acepta = True
        except ValueError:
            acepta = False
        assert acepta == c["valid"], (c, acepta)

    for c in casos["ordinality"]:
        if c.get("raises"):
            with pytest.raises(ValueError):
                applies_from(c["declared"], c["introduced"])
        else:
            assert applies_from(c["declared"], c["introduced"]) == c["applies"], c


def test_every_vector_suite_declares_its_own_contents():
    """Cada suite dice que version es y que vectores tiene, en el mismo formato.

    El indice es lo que el generador lee para negarse a escribir encima de una
    suite de otra version. Una suite con el indice en otra forma no lo protege, y
    la primera que escribi a mano tenia el conteo donde va la lista.
    """
    import json
    from pathlib import Path

    from disensor.rules import SCHEMA_FILES

    raiz = Path(__file__).resolve().parents[1]
    suites = sorted(p for p in (raiz / "spec/vectors").iterdir() if p.is_dir())
    assert {p.name for p in suites} == {v.split("/")[1] for v in SCHEMA_FILES}, [p.name for p in suites]

    for suite in suites:
        indice = json.loads((suite / "index.json").read_text(encoding="utf-8"))
        nombres = sorted(p.stem for p in suite.glob("*.json") if p.name != "index.json")
        assert indice["schema"] == f"residue/{suite.name}", (suite.name, indice["schema"])
        assert sorted(indice["vectors"]) == nombres, suite.name
        assert nombres, suite.name
        for nombre in nombres:
            vector = json.loads((suite / f"{nombre}.json").read_text(encoding="utf-8"))
            assert vector["name"] == nombre, (suite.name, nombre)
            assert vector["artifact"]["schema"] == indice["schema"], (suite.name, nombre)
