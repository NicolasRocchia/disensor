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


def test_no_literal_version_comparison_in_any_source():
    """Ninguna fuente se pregunta si un artefacto ES una version exacta.

    Una comparacion contra un literal se lee como "esta regla vale desde v0.4" y
    significa "vale SOLO en v0.4": el dia que se abra la siguiente, el artefacto
    cae al camino de las versiones anteriores, la forma nueva de la regla
    desaparece y ninguna prueba falla. La pregunta correcta es ordinal y tiene un
    solo lugar, applies_from.

    Comparar contra la CONSTANTE de vigencia es otra cosa y es legitima: no
    pregunta que reglas aplican sino si algo puede EMITIRSE hoy, que es
    exactamente una igualdad (G9, y la politica de la ingesta). Por eso la
    guardia persigue el literal y no el operador.

    Lo que esta guardia NO puede cubrir, y queda dicho: una comparacion contra
    una constante auxiliar es sintacticamente identica a la politica de emision,
    asi que alguien que introduzca `SOLO_V04 = "residue/v0.4"` y compare contra
    eso pasa por el mismo agujero. Una prueba sintactica llega hasta aca.
    """
    import re
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1]
    fuentes = [
        *sorted((raiz / "src/disensor").glob("*.py")),
        *sorted((raiz / "plano-evidencia/src").glob("*.ts")),
        *sorted((raiz / "plano-evidencia/scripts").glob("*.ts")),
    ]
    assert len(fuentes) > 10, fuentes
    lit = r"""["']residue/v[0-9]+\.[0-9]+["']"""
    patrones = [
        re.compile(rf"[=!]==?\s*{lit}"),      # x == "residue/v0.4"
        re.compile(rf"{lit}\s*[=!]==?"),      # "residue/v0.4" == x
        re.compile(rf"\bcase\s+{lit}"),       # match/case, switch
    ]
    culpables = []
    for p in fuentes:
        # Sin saltos de linea: una comparacion partida en dos lineas es la misma
        # comparacion, y era una de las formas que la version anterior de esta
        # guardia dejaba pasar.
        plano = re.sub(r"\s+", " ", p.read_text(encoding="utf-8"))
        for patron in patrones:
            for m in patron.finditer(plano):
                culpables.append(f"{p.relative_to(raiz).as_posix()}: ...{m.group(0)}...")
    assert not culpables, "comparacion contra un literal de version:\n" + "\n".join(culpables)


def test_the_guard_catches_every_form_the_defect_had():
    """La guardia se verifica contra las formas que tuvo y las que le señalaron.

    Una guardia que no se prueba contra su propio defecto es una linea que
    tranquiliza y no sostiene nada: la primera version de esta pasaba en verde
    frente a la mitad de esta lista.
    """
    import re

    lit = r"""["']residue/v[0-9]+\.[0-9]+["']"""
    patrones = [
        re.compile(rf"[=!]==?\s*{lit}"),
        re.compile(rf"{lit}\s*[=!]==?"),
        re.compile(rf"\bcase\s+{lit}"),
    ]

    def caza(texto: str) -> bool:
        plano = re.sub(r"\s+", " ", texto)
        return any(p.search(plano) for p in patrones)

    reintroducciones = [
        'if a["schema"] == "residue/v0.4":',
        "if a['schema'] == 'residue/v0.5':",
        'if (a.schema === "residue/v0.4") {',
        'if "residue/v0.5" == a["schema"]:',
        'if a["schema"] != "residue/v0.5":',
        'if (a.schema !== "residue/v0.4") {',
        'if (a["schema"]\n            == "residue/v0.4"):',
        '        case "residue/v0.4":',
    ]
    for forma in reintroducciones:
        assert caza(forma), f"la guardia no caza: {forma}"

    legitimas = [
        'if applies_from(a["schema"], "residue/v0.4"):',
        'if (appliesFrom(a.schema, "residue/v0.4")) {',
        "if not artifact.errors and declared_version != CURRENT_SCHEMA:",
        "if (artefacto.schema !== ESQUEMA_VIGENTE) {",
        'SCHEMA_FILES = {"residue/v0.4": "residue.schema.v0.4.json"}',
    ]
    for forma in legitimas:
        assert not caza(forma), f"la guardia molesta a: {forma}"


def test_version_order_does_not_depend_on_how_the_literal_was_written():
    """De este orden depende que regla alcanza a que declaracion.

    Salia de la posicion en el diccionario, o sea del orden en que alguien
    escribio las lineas: escribir la version proxima arriba en vez de abajo daba
    vuelta el sentido de todas las reglas versionadas y nada fallaba. El orden
    alfabetico tampoco sirve, porque pone v0.10 antes que v0.2.
    """
    from disensor.rules import ORDER, _version_key

    assert list(ORDER) == sorted(ORDER, key=_version_key)
    revuelto = sorted(ORDER, key=lambda v: -_version_key(v)[1])
    assert tuple(sorted(revuelto, key=_version_key)) == ORDER
    assert _version_key("residue/v0.10") > _version_key("residue/v0.9")
    assert sorted(["residue/v0.10", "residue/v0.9"]) == ["residue/v0.10", "residue/v0.9"]


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

    bloque = port[port.index("export const SCHEMA_FILES"):]
    bloque = bloque[:bloque.index("};")]
    assert dict(re.findall(r'"(residue/v[^"]+)":\s*"([^"]+)"', bloque)) == SCHEMA_FILES

    bloque = worker[worker.index("export const VALIDADORES"):]
    bloque = bloque[:bloque.index("};")]
    declaradas = dict(re.findall(r'"(residue/v[^"]+)":\s*compilarSchema\((\w+)', bloque))
    assert sorted(declaradas) == sorted(SCHEMA_FILES)
    for version, simbolo in declaradas.items():
        importado = re.search(rf'import {simbolo} from "[^"]*/([^/"]+)"', worker)
        assert importado, f"{simbolo} no se importa"
        assert importado.group(1) == SCHEMA_FILES[version], (version, importado.group(1))

    vigente = re.search(r'const ESQUEMA_VIGENTE = "([^"]+)"', worker)
    assert vigente and vigente.group(1) == CURRENT


def test_an_unhashable_schema_is_rejected_and_does_not_crash():
    """El discriminador puede ser cualquier cosa: JSON entra de afuera.

    `declared not in SCHEMA_FILES` con una lista o un objeto reventaba con
    TypeError en vez de devolver el error de schema, y ni el CLI ni el gate lo
    atrapan: un artefacto de tres bytes tumbaba el proceso.
    """
    for basura in ([1, 2], {"a": 1}, 3, None, True):
        errores = validate_artifact({"schema": basura})
        assert errores and errores[0].startswith("[schema]"), (basura, errores)
