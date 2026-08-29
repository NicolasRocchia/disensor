"""La decisión de si un rango exige declaración, compartida por el gate y por round.

Antes de esta función el disparador de una ronda y el enforcement de CI eran
dos implementaciones de la misma pregunta, y divergían justo donde importa: la
política se lee de la punta del destino y no del working tree, el rango es
merge-base y no base, la evidencia no cuenta como código, `gate.required=false`
saltea toda la cobertura, y G7 exige una compuerta común y no que alguna ruta
pida algo. Estos tests fijan esa clasificación y, sobre todo, que el gate
siga estando de acuerdo con ella: dos respuestas distintas a la misma pregunta
serían peores que no tener la función.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from disensor.gate import (
    GateFailure,
    classify_requirement,
    resolve_context,
    review_requirement,
    run_gate,
)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.strip()


def commit(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """Un repositorio con una rama main y una rama de trabajo, como un PR real."""
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "disensor.config.json").write_text(
        json.dumps({"criticality_level": "B", "level_A_enabled": False}), encoding="utf-8"
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "nota.md").write_text("hola\n", encoding="utf-8")
    commit(tmp_path, "base")
    git(tmp_path, "checkout", "-q", "-b", "trabajo")
    return tmp_path


def requirement_of(repo: Path):
    _, req = review_requirement(".residue", "disensor.config.json", "main", "HEAD", repo)
    return req


def set_policy(repo: Path, gate: dict) -> None:
    """Escribe la política EN MAIN, que es de donde el gate la lee."""
    actual = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    git(repo, "checkout", "-q", "main")
    cfg = json.loads((repo / "disensor.config.json").read_text(encoding="utf-8"))
    cfg["gate"] = gate
    (repo / "disensor.config.json").write_text(json.dumps(cfg), encoding="utf-8")
    commit(repo, "politica")
    git(repo, "checkout", "-q", actual)
    git(repo, "merge", "-q", "main", "-m", "traer politica")


def test_code_change_demands_a_round(repo: Path):
    (repo / "src" / "app.py").write_text("x = 2\n", encoding="utf-8")
    commit(repo, "cambio")
    req = requirement_of(repo)
    assert req.status == "required"
    assert req.code == "scope_demands"
    assert req.accepted_gates == ("diff",)
    assert "src/app.py" in req.demanding


def test_an_exempt_path_demands_nothing(repo: Path):
    set_policy(repo, {"scope": [{"paths": ["docs/**"], "accepts": []},
                                {"paths": ["**"], "accepts": ["diff"]}]})
    (repo / "docs" / "nota.md").write_text("otra cosa\n", encoding="utf-8")
    commit(repo, "solo docs")
    req = requirement_of(repo)
    assert req.status == "not_required"
    assert req.code == "all_exempt"


def test_the_floor_demands_even_when_the_scope_exempts_everything(repo: Path):
    """El piso no es relajable por scope: la configuración se revisa siempre."""
    set_policy(repo, {"scope": [{"paths": ["**"], "accepts": []}]})
    cfg = json.loads((repo / "disensor.config.json").read_text(encoding="utf-8"))
    cfg["criticality_level"] = "C"
    (repo / "disensor.config.json").write_text(json.dumps(cfg), encoding="utf-8")
    commit(repo, "toca la config")
    req = requirement_of(repo)
    assert req.status == "required"
    assert "disensor.config.json" in req.demanding


def test_required_false_demands_nothing_not_even_the_floor(repo: Path):
    """El interruptor maestro apaga la cobertura entera, piso incluido.

    Es el comportamiento real del gate ([gate.py] required), y la clasificación
    tiene que decir lo mismo: si `round` corriera una ronda acá, gastaría una
    corrida en algo que el gate no va a pedir.
    """
    set_policy(repo, {"required": False})
    (repo / "src" / "app.py").write_text("x = 3\n", encoding="utf-8")
    commit(repo, "cambio con el gate apagado")
    req = requirement_of(repo)
    assert req.status == "not_required"
    assert req.code == "gate_not_required"


def test_paths_without_a_common_gate_block_instead_of_demanding(repo: Path):
    """G7: si no hay compuerta común, ninguna ronda puede cubrir el PR entero."""
    set_policy(repo, {"scope": [{"paths": ["src/**"], "accepts": ["diff"]},
                                {"paths": ["docs/**"], "accepts": ["plan"]},
                                {"paths": ["**"], "accepts": ["diff"]}]})
    (repo / "src" / "app.py").write_text("x = 4\n", encoding="utf-8")
    (repo / "docs" / "nota.md").write_text("cambia\n", encoding="utf-8")
    commit(repo, "dos mundos")
    req = requirement_of(repo)
    assert req.status == "blocked"
    assert req.code == "no_common_gate"


def test_a_custom_config_path_is_honoured(repo: Path):
    """El gate acepta --config; una clasificación que lo ignore mira otra política."""
    git(repo, "checkout", "-q", "main")
    (repo / "politica.json").write_text(
        json.dumps({"criticality_level": "B", "gate": {"required": False}}), encoding="utf-8"
    )
    commit(repo, "config alternativa")
    git(repo, "checkout", "-q", "trabajo")
    git(repo, "merge", "-q", "main", "-m", "traer")
    (repo / "src" / "app.py").write_text("x = 5\n", encoding="utf-8")
    commit(repo, "cambio")
    _, req = review_requirement(".residue", "politica.json", "main", "HEAD", repo)
    assert req.status == "not_required"
    assert req.code == "gate_not_required"


def test_without_a_range_it_fails_closed(repo: Path, monkeypatch):
    """Sin rango no hay decisión posible, y "no hace falta ronda" sería un bypass."""
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    with pytest.raises(GateFailure, match="range is missing"):
        review_requirement(".residue", "disensor.config.json", None, None, repo)


def test_evidence_mutations_are_not_part_of_the_requirement(repo: Path):
    """Modificar una declaración vieja es un defecto del PR, no una ronda pendiente.

    Mezclar las dos cosas haría que `round` dijera "no corras" cuando lo que
    hay que hacer es corregir el PR, y que el gate dejara de reportar el resto
    de los problemas al primer error.
    """
    # La evidencia tiene que existir en el merge-base para que tocarla sea una
    # mutacion y no un alta: se crea en main, antes de que la rama la modifique.
    git(repo, "checkout", "-q", "main")
    residue = repo / ".residue"
    residue.mkdir()
    (residue / "vieja.json").write_text('{"schema": "residue/v0.3"}', encoding="utf-8")
    commit(repo, "evidencia previa")
    git(repo, "checkout", "-q", "trabajo")
    git(repo, "merge", "-q", "main", "-m", "traer evidencia")
    (residue / "vieja.json").write_text('{"schema": "residue/v0.3", "tocada": true}', encoding="utf-8")
    (repo / "src" / "app.py").write_text("x = 6\n", encoding="utf-8")
    commit(repo, "toca evidencia y codigo")

    ctx = resolve_context(".residue", "disensor.config.json", "main", "HEAD", repo)
    req = classify_requirement(ctx)
    assert ctx.mutations, "la mutacion tiene que estar en el contexto"
    assert req.status == "required", "y la ronda sigue siendo necesaria por el codigo"


@pytest.mark.parametrize(
    "policy, cambios, espera_ronda",
    [
        ({}, {"src/app.py": "a = 1\n"}, True),
        ({"required": False}, {"src/app.py": "a = 2\n"}, False),
        ({"scope": [{"paths": ["docs/**"], "accepts": []},
                    {"paths": ["**"], "accepts": ["diff"]}]}, {"docs/nota.md": "b\n"}, False),
    ],
)
def test_the_gate_agrees_with_the_classification(repo: Path, capsys, policy, cambios, espera_ronda):
    """La prueba que justifica el refactor: el gate no puede opinar distinto.

    Si la clasificación dice que hace falta una ronda, un PR sin declaración
    tiene que fallar; si dice que no, tiene que pasar. Cualquier divergencia
    acá significa que el disparador y el enforcement volvieron a ser dos
    decisiones distintas, que es exactamente lo que esta función existe para
    impedir.
    """
    if policy:
        set_policy(repo, policy)
    for ruta, contenido in cambios.items():
        (repo / ruta).write_text(contenido, encoding="utf-8")
    commit(repo, "cambio")

    req = requirement_of(repo)
    assert (req.status == "required") is espera_ronda

    base = git(repo, "rev-parse", "main")
    head = git(repo, "rev-parse", "HEAD")
    code = run_gate(".residue", "disensor.config.json", base, head, repo, post=False)
    capsys.readouterr()
    assert (code != 0) is espera_ronda, (
        "el gate y la clasificacion tienen que responder lo mismo sobre la necesidad de ronda"
    )


def test_level_a_without_coverage_is_blocked_not_exempt(repo: Path):
    """El gate rechaza esa politica, asi que el preflight no puede decir que no
    hace falta ronda: son las dos caras de la misma decision, y que difieran es
    lo que esta funcion existe para impedir."""
    set_policy(repo, {"required": False})
    actual = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    git(repo, "checkout", "-q", "main")
    cfg = json.loads((repo / "disensor.config.json").read_text(encoding="utf-8"))
    cfg["criticality_level"] = "A"
    cfg["level_A_enabled"] = True
    (repo / "disensor.config.json").write_text(json.dumps(cfg), encoding="utf-8")
    commit(repo, "nivel A sin cobertura")
    git(repo, "checkout", "-q", actual)
    (repo / "src" / "app.py").write_text("x = 4\n", encoding="utf-8")
    commit(repo, "cambio bajo esa politica")
    req = requirement_of(repo)
    assert req.status == "blocked"
    assert req.code == "level_a_without_coverage"
