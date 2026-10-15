"""El modo degradado de un solo asistente, de punta a punta y sin costo (#79).

`same_model_fresh_context` es la entrada para quien tiene un solo asistente:
el mismo modelo, con contexto limpio, revisa lo que genero. Hasta ahora existia
por piezas que no encajaban: `reviewer add --yes` prometia un consentimiento
que no registraba, el consentimiento dado desde un subdirectorio no servia en
un repositorio sin remoto, `--generator-model` no estaba documentado, y las
recetas `claude` y `gemini` declaraban un modelo que no ponian en el argv, asi
que la declaracion afirmaba mas independencia de la que hubo. En el corpus no
habia una sola declaracion en este modo: el camino no se habia recorrido nunca.

Esta prueba lo recorre entero con los comandos del CLI, como lo haria una
persona: registrar, consentir, `round`, `new --round` y `validate`. El revisor
es un programa de mentira que escribe un informe valido: argv real, sin red,
sin costo. Lo unico que la prueba hace a mano es lo que una persona hace a
mano, llenar los textos que la plantilla deja marcados.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from disensor import reviewers
from disensor.cli import build_parser

GENERADOR = "claude-opus-5-5"

INFORME = """# Findings

No findings: the reviewer read the range and found nothing to object to.
"""

# Un revisor propio, registrado con --command: recibe el paquete por stdin y
# escribe el informe donde el runner le dice, el unico argumento.
REVISOR_PROPIO = f"""import sys
from pathlib import Path
paquete = sys.stdin.buffer.read().decode("utf-8")
assert "disensor" in paquete.lower(), "el paquete no llego"
Path(sys.argv[1]).write_text({INFORME!r}, encoding="utf-8")
"""


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.strip()


@pytest.fixture(autouse=True)
def registro_aislado(tmp_path: Path, monkeypatch) -> Path:
    """El registro real del dueño no se toca: ni sus revisores ni sus consentimientos."""
    monkeypatch.setattr(reviewers, "REGISTRY_DIR", tmp_path / ".disensor")
    monkeypatch.setattr(reviewers, "REGISTRY", tmp_path / ".disensor" / "reviewers.json")
    return tmp_path / ".disensor" / "reviewers.json"


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """Un repositorio SIN remoto, con un subdirectorio versionado y una rama de trabajo.

    Sin remoto a proposito: ahi la identidad del repositorio es su ruta, y es
    donde el consentimiento dado desde un subdirectorio dejaba de servir.
    """
    d = tmp_path / "repo"
    (d / "sub").mkdir(parents=True)
    git(d, "init", "-q", "-b", "main")
    (d / "disensor.config.json").write_text('{"criticality_level": "B"}', encoding="utf-8")
    (d / "a.py").write_text("x = 1\n", encoding="utf-8")
    (d / "sub" / "b.py").write_text("y = 1\n", encoding="utf-8")
    git(d, "add", "-A")
    git(d, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    git(d, "checkout", "-q", "-b", "trabajo")
    (d / "a.py").write_text("x = 2\n", encoding="utf-8")
    git(d, "add", "-A")
    git(d, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "cambio")
    return d


def cli(*argv: str) -> int:
    args = build_parser().parse_args(list(argv))
    return args.func(args)


def llenar(declaracion: dict) -> dict:
    """Lo que la persona escribe: los textos que la plantilla deja marcados.

    Nada mas. Si la plantilla dejara otro marcador sin llenar, `validate` lo
    rechazaria y la prueba fallaria ahi, que es lo que tiene que pasar.
    """
    for item in declaracion.get("residue", {}).get("items", []):
        if item["class"] == "reviewer_correlation":
            item["description"] = (
                "The reviewer was the generator's own model with a fresh context: the errors "
                "that model makes consistently were not covered by this round."
            )
        elif item["class"] == "reviewer_hardening_gap":
            item["description"] = (
                "The adapter's hardening is not verified: the reviewed range could have "
                "addressed the reviewer before the brief. The range was read by the owner."
            )
    return declaracion


def ronda_degradada(repo: Path, tmp_path: Path, monkeypatch, capsys, reviewer_id: str) -> tuple[dict, str]:
    """consent desde el subdirectorio, round desde la raiz, new --round, validate."""
    monkeypatch.setattr(reviewers, "_terminal", lambda stream: False)
    monkeypatch.chdir(repo / "sub")
    assert cli("reviewer", "consent", reviewer_id) == 0
    capsys.readouterr()

    monkeypatch.chdir(repo)
    resultado = tmp_path / "afuera" / "resultado.json"
    resultado.parent.mkdir()
    codigo = cli(
        "round", "--gate", "diff", "--generator-family", "anthropic",
        "--generator-model", GENERADOR, "--base", "main", "--head", "HEAD",
        "--result", str(resultado), "--report", str(tmp_path / "afuera" / "informe.md"),
    )
    err = capsys.readouterr().err
    assert codigo == 0, err
    assert "DEGRADED MODE" in err
    # El consentimiento que destrabo la ronda se muestra, y este no se dio
    # desde una terminal (#84).
    assert "without an interactive terminal" in err

    assert cli("new", "--gate", "diff", "--level", "B", "--round", str(resultado)) == 0
    capsys.readouterr()
    [archivo] = (repo / ".residue").iterdir()
    declaracion = llenar(json.loads(archivo.read_text(encoding="utf-8")))
    archivo.write_bytes((json.dumps(declaracion, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    assert cli("validate", str(archivo)) == 0, capsys.readouterr().out
    assert "VALID" in capsys.readouterr().out
    return declaracion, err


def test_a_single_assistant_declares_the_degraded_mode_end_to_end(repo, tmp_path, monkeypatch, capsys):
    """Un revisor propio, del mismo modelo que el generador, de punta a punta."""
    script = tmp_path / "revisor.py"
    script.write_text(REVISOR_PROPIO, encoding="utf-8")
    assert cli(
        "reviewer", "add", "mismo", "--family", "anthropic", "--model", GENERADOR,
        "--egress", "cloud", "--stdin", "pack", "--yes",
        "--command", sys.executable, str(script), "{report}",
    ) == 0
    # Registrar no autoriza mandar nada: el registro no tiene consentimientos.
    assert not json.loads(reviewers.REGISTRY.read_text(encoding="utf-8")).get("consents")
    capsys.readouterr()

    declaracion, _ = ronda_degradada(repo, tmp_path, monkeypatch, capsys, "mismo")
    revisor = declaracion["actors"]["reviewers"][0]
    assert declaracion["actors"]["generator"] == {"family": "anthropic", "model": GENERADOR}
    assert revisor["family"] == "anthropic" and revisor["model"] == GENERADOR
    assert revisor["independence"] == "same_model_fresh_context"
    assert revisor["fallback_reason"]["code"]
    clases = sorted(i["class"] for i in declaracion["residue"]["items"])
    assert clases == ["reviewer_correlation", "reviewer_hardening_gap"]
    consentimiento = declaracion["extensions"]["dev.disensor.round"]["consent"]
    assert consentimiento["recorded"] is True
    assert consentimiento["stdin_terminal"] is False and consentimiento["stdout_terminal"] is False


CLAUDE_FALSO = """#!{python}
import json, sys
from pathlib import Path
Path({volcado!r}).write_text(json.dumps(sys.argv[1:]), encoding="utf-8")
print({informe!r})
"""


@pytest.mark.skipif(
    os.name == "nt",
    reason=(
        "la receta pasa el paquete como argumento, y en Windows un `claude` de mentira "
        "tendria que ser un .cmd que corta el argumento en el primer salto de linea; "
        "el CI corre en Linux"
    ),
)
def test_the_claude_recipe_with_the_generators_model_is_same_model_fresh_context(
    repo, tmp_path, monkeypatch, capsys,
):
    """El criterio de cierre de #79, con la receta del catalogo: registrada con el
    modelo del generador, la ronda se declara `same_model_fresh_context`, y lo
    declarado es lo que corre, porque el argv lleva `--model` con ese valor.

    Antes la receta declaraba el literal `claude-code`, que no es un modelo, y
    la ronda salia `same_family_distinct_model` aunque el CLI corriera el mismo
    modelo que genero.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    volcado = tmp_path / "argv.json"
    falso = bin_dir / "claude"
    falso.write_text(
        CLAUDE_FALSO.format(python=sys.executable, volcado=str(volcado), informe=INFORME),
        encoding="utf-8",
    )
    falso.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    assert cli("reviewer", "add", "claude", "--model", GENERADOR, "--yes") == 0
    capsys.readouterr()

    declaracion, _ = ronda_degradada(repo, tmp_path, monkeypatch, capsys, "claude")
    revisor = declaracion["actors"]["reviewers"][0]
    assert revisor["model"] == GENERADOR
    assert revisor["independence"] == "same_model_fresh_context"
    argv = json.loads(volcado.read_text(encoding="utf-8"))
    assert argv[argv.index("--model") + 1] == GENERADOR
    assert "--safe-mode" in argv
    assert "{model}" not in argv
