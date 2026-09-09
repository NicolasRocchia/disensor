"""Cada regla del registro tiene un vector MUST-FAIL, o una exencion probada.

El conteo de ceros por regla lo propuso Kenne Ives en la lista
public-agent-conformance@w3.org: para cada regla, contar cuantos vectores
MUST-FAIL la nombran, y tratar un cero como bandera (mensajes 2026Sep/0010 del
5 de septiembre de 2026 y 2026Sep/0014 del 8). Una regla en cero es una regla
que un verificador puede no implementar sin que ningun vector lo note, porque
la comparacion exacta de reglas disparadas no tiene nada que comparar.

Corrido sobre el corpus da dos ceros, R3 y R8. Para esas dos el cero no
significa que falte el vector: significa que el vector no puede existir. El
esquema de cada version prohibe exactamente la condicion que la regla prueba
(`abbreviated_path.used` tiene que ser false cuando hay casos protegidos
tocados; `requires_human_attention` tiene que ser true en una refutacion
interpretativa), y `validate_artifact` no evalua las reglas cuando la forma
falla. Un artefacto que dispare R3 o R8 es invalido por esquema antes de llegar
a la capa de reglas. Los dos escenarios ya tienen vector, registrado como
["schema"] (2026Sep/0016, del 9 de septiembre).

Por eso la exencion no se declara, se PRUEBA. `spec/rule_coverage.json` dice
solo cuales estan exentas; la prueba la escribe cada implementacion por su
lado. Para cada regla exenta y cada version, este test parte de un vector
MUST-PASS de la suite de esa version, que valida limpio contra su propio
esquema, le aplica el escenario, y exige tres cosas: que el esquema lo rechace
en el campo bajo prueba y EN NINGUN OTRO LADO, que la regla dispare cuando se
saltea el esquema, y que el vector del escenario siga diciendo lo mismo.

Que no haya rechazo fuera del campo es la parte que importa. La primera version
de este test relabeleaba un artefacto v0.4 como v0.2, que lo rechazaba por un
campo ajeno que v0.2 no conoce, y con eso alcanzaba para dar por probada la
exencion: el control quedaba verde por el motivo equivocado en dos de las tres
versiones, y el comentario que lo justificaba la volvia invisible. Con la base
limpia contra su propio esquema, todo error viene del escenario, y se exige que
todos caigan en la ruta que la exencion nombra o en un ancestro suyo. Una misma
violacion puede salir como mas de un error cuando el validador tambien informa
el condicional que la envuelve; eso es la misma violacion subiendo, no ruido.

Si una version afloja el esquema, el rechazo deja de venir del campo bajo
prueba y el test falla: ahi si hace falta el vector. Si alguien borra la regla,
falla la otra mitad. Una exencion que nada verifica es exactamente la clase de
afirmacion sin chequear que esta herramienta existe para cazar.

Limites del mecanismo, dichos en voz alta:

- El registro sale de la fuente de ESTA implementacion. Que el port emita las
  mismas etiquetas lo verifica
  `test_the_port_and_the_reference_emit_the_same_rule_registry`, y el port
  prueba sus propias exenciones en `plano-evidencia/scripts/conformidad.ts`.
- El conteo va sobre las suites juntas, no por suite. Por suite hay ceros
  legitimos: R11, R12 y R13 se introdujeron en v0.4 y no alcanzan a una
  declaracion v0.2 o v0.3 (`applies_from`), y el generador se niega a escribir
  sobre una suite historica. Contar por suite pediria vectores que no se
  pueden agregar.
- Que R3 y R8 sean inalcanzables es un dato, no una conclusion. Si corresponde
  borrarlas o aflojar el esquema en la version siguiente es una decision
  aparte, y este archivo no la toma.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from disensor.rules import SCHEMA_FILES, load_schema, rule_errors, schema_errors

ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "spec" / "vectors"
COBERTURA = json.loads((ROOT / "spec" / "rule_coverage.json").read_text(encoding="utf-8"))
EXENTAS = COBERTURA["exempt"]

# Lo que cada escenario sabe pedirle a su base. Una clave que este archivo no
# entienda es un error y no un requisito ignorado: un typo en el dato
# compartido aflojaria la eleccion de la base sin que nada lo diga.
NECESIDADES = {"residue_item_class"}


def _registro() -> list[str]:
    """Las etiquetas de regla que rules.py puede emitir, leidas de la fuente."""
    fuente = (ROOT / "src" / "disensor" / "rules.py").read_text(encoding="utf-8")
    entrecomilladas = set(re.findall(r'"(R\d+)"', fuente))
    sueltas = set(re.findall(r"\bR\d+\b", fuente))
    assert sueltas <= entrecomilladas, (
        f"rules.py nombra {sorted(sueltas - entrecomilladas)} fuera de un literal entre "
        "comillas dobles. El barrido del registro solo ve los literales, asi que una "
        "regla escrita de otra forma queda fuera del censo y nadie pide su vector."
    )
    return sorted(entrecomilladas, key=lambda r: int(r[1:]))


def _ruta(error: str) -> str:
    """La ruta de la instancia dentro de un error de esquema, sin la barra inicial.

    El port informa un JSON Pointer y esta implementacion una ruta unida por
    barras. Se normaliza para que el dato compartido diga una sola cosa.
    """
    return error.split("]", 1)[1].split(":", 1)[0].strip().removeprefix("/")


def _dentro(ruta: str, objetivo: str) -> bool:
    """La ruta es el objetivo o un ancestro suyo.

    Una misma violacion puede salir como mas de un error cuando el validador
    tambien informa el condicional que la envuelve. Eso es la misma violacion
    subiendo, no ruido: el ruido cae en otra rama del artefacto.
    """
    return objetivo == ruta or objetivo.startswith(ruta + "/")


def _vectores(suite: Path):
    for archivo in sorted(suite.glob("*.json")):
        if archivo.name == "index.json":
            continue
        yield archivo.stem, json.loads(archivo.read_text(encoding="utf-8"))


def _cuenta_mustfail() -> dict[str, int]:
    """Cuantos vectores MUST-FAIL nombran cada etiqueta, en las suites juntas."""
    cuenta: dict[str, int] = {}
    for suite in sorted(p for p in VECTORS.iterdir() if p.is_dir()):
        for _, vector in _vectores(suite):
            if vector["expected"]["valid"]:
                continue
            for etiqueta in set(vector["expected"]["rules"]):
                cuenta[etiqueta] = cuenta.get(etiqueta, 0) + 1
    return cuenta


def _cumple(artefacto: dict, necesita: dict) -> bool:
    desconocidas = set(necesita) - NECESIDADES
    assert not desconocidas, (
        f"spec/rule_coverage.json pide {sorted(desconocidas)} y este test no sabe que "
        "es. Implementarlo o corregir el dato: ignorarlo elegiria una base que no "
        "sirve para el escenario."
    )
    clase = necesita.get("residue_item_class")
    if clase is not None:
        items = artefacto.get("residue", {}).get("items", [])
        if not any(i.get("class") == clase for i in items):
            return False
    return True


def _base(suite: str, necesita: dict) -> tuple[str, dict]:
    """El primer MUST-PASS de la suite, en orden de archivo, que sirve de base.

    De la propia suite y no del ejemplo vigente: un artefacto de otra version
    lo rechaza el esquema por campos ajenos al escenario, y entonces el rechazo
    no dice nada sobre la exencion.
    """
    for nombre, vector in _vectores(VECTORS / suite):
        if vector["expected"]["valid"] and _cumple(vector["artifact"], necesita):
            return nombre, vector["artifact"]
    raise LookupError(
        f"la suite {suite} no tiene ningun vector MUST-PASS que cumpla {necesita}, "
        "asi que la exencion no se puede probar en esa version"
    )


def _escenario_r3(a: dict) -> dict:
    a["event"]["abbreviated_path"] = {
        "used": True,
        "justification": "cambio trivial de una linea en un helper",
        "protected_cases_touched": ["data_migration"],
    }
    return a


def _escenario_r8(a: dict) -> dict:
    for item in a["residue"]["items"]:
        if item["class"] == "principal_refutation":
            item["refutation_type"] = "interpretive"
            item["requires_human_attention"] = False
            return a
    raise LookupError("la base no tiene el item que el escenario necesita")


ESCENARIOS = {"R3": _escenario_r3, "R8": _escenario_r8}


def test_cada_regla_tiene_un_vector_mustfail_o_una_exencion():
    """El censo. Un cero sin exencion es una regla que nadie esta obligado a implementar."""
    registro = _registro()
    cuenta = _cuenta_mustfail()
    exentas = {e["rule"]: e["reason"] for e in EXENTAS}

    inesperadas = [r for r in registro if cuenta.get(r, 0) == 0 and r not in exentas]
    assert not inesperadas, (
        f"reglas sin ningun vector MUST-FAIL que las nombre: {', '.join(inesperadas)}. "
        "Un verificador puede no implementarlas y pasar la suite entera. Escribir el "
        "vector, o agregarlas a spec/rule_coverage.json con la prueba de que el vector "
        "no puede existir."
    )

    obsoletas = [r for r in exentas if cuenta.get(r, 0) > 0]
    assert not obsoletas, (
        "estas reglas estan exentas y ya tienen vector MUST-FAIL: "
        + "; ".join(f"{r} ({cuenta[r]} vectores), exenta porque {exentas[r]}" for r in obsoletas)
        + ". Sacarlas de spec/rule_coverage.json: la exencion sobrevivio al motivo que "
        "la justificaba."
    )

    fantasmas = [r for r in exentas if r not in registro]
    assert not fantasmas, (
        f"spec/rule_coverage.json exime {', '.join(fantasmas)}, que esta implementacion "
        "ya no emite. Una exencion de una regla que no existe deja el censo hablando de "
        "otro contrato."
    )

    assert set(ESCENARIOS) == set(exentas), (
        f"las exentas del dato compartido son {sorted(exentas)} y los escenarios de este "
        f"test son {sorted(ESCENARIOS)}. Una exenta sin escenario queda declarada y no "
        "probada, que es justo lo que este archivo no admite."
    )


def test_the_port_and_the_reference_emit_the_same_rule_registry():
    """El censo mide el registro de esta implementacion; el del port no lo miraba nadie.

    Si el port pierde o renombra una regla que hoy no tiene cobertura negativa,
    ningun vector lo dice, porque no hay ninguno que la nombre, y los dos censos
    pasarian a hablar de registros distintos. Es el mismo agujero que el runner
    ya cerro para las versiones con su linea NO COVERAGE.
    """
    fuente = (ROOT / "plano-evidencia" / "src" / "validar.ts").read_text(encoding="utf-8")
    entrecomilladas = set(re.findall(r'"(R\d+)"', fuente))
    sueltas = set(re.findall(r"\bR\d+\b", fuente))
    assert sueltas <= entrecomilladas, (
        f"validar.ts nombra {sorted(sueltas - entrecomilladas)} fuera de un literal entre "
        "comillas dobles, asi que el censo del port no la ve."
    )
    del_port = sorted(entrecomilladas, key=lambda r: int(r[1:]))
    assert del_port == _registro(), (
        f"la referencia emite {_registro()} y el port {del_port}. Dos implementaciones que "
        "dicen seguir el mismo contrato tienen registros distintos, y la que perdio una "
        "regla sin cobertura negativa pasa la suite igual."
    )


@pytest.mark.parametrize("version", sorted(SCHEMA_FILES), ids=lambda v: v.split("/")[1])
@pytest.mark.parametrize("exenta", EXENTAS, ids=lambda e: e["rule"])
def test_una_regla_exenta_es_inalcanzable_y_no_esta_muerta(exenta, version):
    """La exencion se prueba en las dos direcciones, en cada version, cada vez que corre el CI."""
    regla = exenta["rule"]
    suite = version.split("/")[1]
    esquema = load_schema(version)

    nombre, base = _base(suite, exenta["base_needs"])
    assert not schema_errors(base, esquema), (
        f"{regla} en {version}: la base {nombre} no valida limpia contra su propio "
        "esquema, asi que un rechazo posterior podria venir de ella y no del escenario."
    )

    artefacto = ESCENARIOS[regla](copy.deepcopy(base))
    errores = schema_errors(artefacto, esquema)
    rutas = [_ruta(e) for e in errores]
    objetivo = [r for r in rutas if re.search(exenta["schema_path"], r)]
    assert objetivo, (
        f"{regla} en {version}: el escenario sobre {nombre} no da ningun error de esquema "
        f"en {exenta['schema_path']!r}; da {rutas}. La exencion dice que {exenta['reason']}. "
        "Si no da ninguno, el esquema dejo de prohibirlo y hay que escribir el vector "
        "MUST-FAIL; si da otro, rechaza por otra cosa y no prueba nada."
    )
    ajenas = [r for r in rutas if not any(_dentro(r, o) for o in objetivo)]
    assert not ajenas, (
        f"{regla} en {version}: el escenario sobre {nombre} tambien es rechazado en {ajenas}, "
        f"fuera de {exenta['schema_path']!r}. Con la base limpia, todo error tiene que venir "
        "del escenario: un rechazo que llega por otro lado deja el control verde por el "
        "motivo equivocado."
    )

    disparo = [e for e in rule_errors(artefacto) if e.startswith(f"[{regla}]")]
    assert disparo, (
        f"{regla} en {version}: salteado el esquema, la regla no dispara en su propio "
        "escenario. Quedo sin efecto y ningun vector lo iba a decir, porque su cobertura "
        f"negativa esta exenta porque {exenta['reason']}."
    )

    # El vector del escenario existe en las suites que lo tienen. v0.2 se
    # escribio a mano y no lo trae; el generador solo escribe la suite vigente.
    archivo = VECTORS / suite / f"{exenta['vector']}.json"
    if archivo.exists():
        vector = json.loads(archivo.read_text(encoding="utf-8"))
        assert vector["expected"] == {"valid": False, "rules": ["schema"]}, (
            f"{regla} en {version}: el vector {exenta['vector']} cambio de veredicto o de "
            f"etiquetas ({vector['expected']}). Si ahora dispara la regla, la exencion "
            "termino y hay que sacarla de spec/rule_coverage.json."
        )
