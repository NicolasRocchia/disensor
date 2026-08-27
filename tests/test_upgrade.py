"""`disensor init --upgrade`: llevar el procedimiento nuevo sin pisar lo ajeno.

`init` conserva byte por byte lo que ya existe, y esa promesa está bien. Pero
significa que actualizar el paquete no cambia nada de lo que el agente lee: un
repositorio inicializado con una versión anterior se queda con su
procedimiento para siempre y nunca invoca lo nuevo. El upgrade migra solo lo
que sigue siendo idéntico a algo que una versión conocida escribió, y ante
cualquier divergencia no toca nada, porque ahí adentro puede haber una línea
que el usuario escribió.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from disensor.cli import build_parser
from disensor.guide import guide_text
from disensor.init import (
    BLOCK_VERSION,
    CLAUDE_HEADING,
    SKILL_FRONTMATTER,
    UPGRADE_CONFLICT,
)
from disensor.pin import PinError

# La seccion que escribia la version anterior, EXACTA. El reconocimiento es
# por hash del bloque entero, asi que una version abreviada no serviria: el
# test estaria probando otra cosa que la que el upgrade va a encontrar.
CLAUDE_0_7 = """## disensor: residue declaration at event close

Before closing a plan, a diff or an architecture decision, run the round and
then declare it:

1. `disensor prompt --gate <plan|diff|architecture>` prints the adversarial
   brief. Hand it, with the material under review, to a reviewer from ANOTHER
   model family (Codex, Gemini, whatever is at hand: a free tier is enough). Same family as the
   generator does not count, and rule R4 rejects the declaration if you try.
2. Verify every finding against the actual code before accepting it. The
   reviewer is decorrelated, not right.
3. `disensor new --gate <plan|diff|architecture> --level <A|B|C>` creates the
   template under `.residue/`. Its `prompt_hash` is
   `disensor prompt --gate <plan|diff|architecture> --hash`.
4. Fill it following the disensor skill (`.claude/skills/disensor/SKILL.md`;
   the same guide is available as `disensor guide`). Do not invent findings
   or states: the artifact declares what happened, not what should have
   happened.
5. Run `disensor validate` on the file until it prints VALID; the CI gate
   rejects exactly the same.
6. The artifact goes in its own commit (`docs(residue): declare event
   <short-id>`), never mixed with code.
"""


@pytest.fixture(autouse=True)
def sin_red(monkeypatch):
    def offline(version, runner=None):
        raise PinError("offline test environment.")

    monkeypatch.setattr("disensor.init.resolve_tag_commit", offline)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def correr(repo: Path, monkeypatch, *extra: str) -> int:
    monkeypatch.chdir(repo)
    args = build_parser().parse_args(["init", *extra])
    return args.func(args)


def instalacion_vieja(repo: Path) -> None:
    """Un repositorio como lo dejaba la version anterior."""
    (repo / "CLAUDE.md").write_text(
        "# Mi proyecto\n\nReglas de la casa.\n\n" + CLAUDE_0_7, encoding="utf-8"
    )
    skill = repo / ".claude" / "skills" / "disensor" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(SKILL_FRONTMATTER + guide_text(), encoding="utf-8")


def test_an_old_installation_is_migrated(repo: Path, monkeypatch, capsys):
    instalacion_vieja(repo)
    assert correr(repo, monkeypatch, "--upgrade") == 0
    claude = (repo / "CLAUDE.md").read_text(encoding="utf-8")
    assert "disensor round" in claude
    assert f"disensor:block v{BLOCK_VERSION}" in claude
    skill = (repo / ".claude" / "skills" / "disensor" / "SKILL.md").read_text(encoding="utf-8")
    assert "exit code" in skill, "la skill tiene que ser el runbook, no el formulario"
    assert "upgraded" in capsys.readouterr().out


def test_what_the_user_wrote_around_the_block_survives(repo: Path, monkeypatch):
    instalacion_vieja(repo)
    correr(repo, monkeypatch, "--upgrade")
    claude = (repo / "CLAUDE.md").read_text(encoding="utf-8")
    assert claude.startswith("# Mi proyecto"), "lo de arriba de la seccion es del usuario"
    assert "Reglas de la casa." in claude


def test_an_edited_block_is_left_alone(repo: Path, monkeypatch, capsys):
    """Ante la duda, no se toca. Adentro puede haber algo que el usuario escribió,
    y pisarlo por migrar seria exactamente lo que init promete no hacer."""
    instalacion_vieja(repo)
    ruta = repo / "CLAUDE.md"
    ruta.write_text(
        ruta.read_text(encoding="utf-8").replace(
            "2. Verify every finding", "2. OJO: aca agregamos lo nuestro. Verify every finding"
        ),
        encoding="utf-8",
    )
    antes = ruta.read_text(encoding="utf-8")
    code = correr(repo, monkeypatch, "--upgrade")
    assert code == UPGRADE_CONFLICT
    assert ruta.read_text(encoding="utf-8") == antes, "no se toca lo que no se reconoce"
    salida = capsys.readouterr().out
    assert "CONFLICT" in salida and "Nothing was touched" in salida


def test_running_it_twice_is_a_no_op(repo: Path, monkeypatch, capsys):
    instalacion_vieja(repo)
    correr(repo, monkeypatch, "--upgrade")
    despues = (repo / "CLAUDE.md").read_text(encoding="utf-8")
    capsys.readouterr()
    assert correr(repo, monkeypatch, "--upgrade") == 0
    assert (repo / "CLAUDE.md").read_text(encoding="utf-8") == despues
    assert "current" in capsys.readouterr().out


def test_show_prints_the_new_text_without_touching_anything(repo: Path, monkeypatch, capsys):
    """El conflicto tiene salida: se puede ver que iba a escribirse y resolverlo a mano."""
    instalacion_vieja(repo)
    antes = (repo / "CLAUDE.md").read_text(encoding="utf-8")
    assert correr(repo, monkeypatch, "--upgrade", "--show") == 0
    salida = capsys.readouterr().out
    assert "disensor round" in salida and "exit code" in salida
    assert (repo / "CLAUDE.md").read_text(encoding="utf-8") == antes


def test_a_repository_without_disensor_is_reported_not_created(repo: Path, monkeypatch, capsys):
    assert correr(repo, monkeypatch, "--upgrade") == 0
    assert not (repo / "CLAUDE.md").exists()
    assert "absent" in capsys.readouterr().out


def test_the_pinned_gate_is_warned_about_when_it_is_older(repo: Path, monkeypatch, capsys):
    """Un CLI que emite un esquema nuevo contra una Action vieja produce una
    declaracion que el propio CI rechaza, y la persona se entera al final."""
    wf = repo / ".github" / "workflows" / "disensor.yml"
    wf.parent.mkdir(parents=True)
    wf.write_text("jobs:\n  gate:\n    steps:\n      - uses: NicolasRocchia/disensor@v0.7.0\n",
                  encoding="utf-8")
    correr(repo, monkeypatch, "--upgrade")
    salida = capsys.readouterr().out
    assert "WARNING" in salida and "disensor pin" in salida
