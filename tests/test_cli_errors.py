"""What the CLI says when something is wrong.

The first rejection is where people give up, so an error that names a rule and
stops there is a dead end for anyone on their first artifact. These tests fix
the part of the message that tells them where to go next.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from disensor.cli import build_parser

EXAMPLES = Path(__file__).resolve().parents[1] / "spec" / "examples"


def run(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


def test_an_invalid_artifact_says_where_to_look(tmp_path, capsys):
    broken = json.loads((EXAMPLES / "example_2_diff_gate.json").read_text(encoding="utf-8"))
    broken["residue"]["items"][0]["description"] = "ninguno"  # generic marker, R2
    path = tmp_path / "a.json"
    path.write_text(json.dumps(broken), encoding="utf-8")

    assert run(["validate", str(path)]) == 1
    out = capsys.readouterr().out
    assert "[R2]" in out
    assert "disensor guide" in out
    assert "disensor prompt" in out


def test_a_valid_artifact_gets_no_lecture(capsys):
    assert run(["validate", str(EXAMPLES / "example_2_diff_gate.json")]) == 0
    out = capsys.readouterr().out
    assert "VALID" in out
    assert "What to do next" not in out


@pytest.mark.parametrize("target", ["nope.json", "."])
def test_an_unreadable_path_is_not_a_traceback(tmp_path, target, capsys):
    """Including a directory: catching only FileNotFoundError left that one raising."""
    assert run(["validate", str(tmp_path / target if target != "." else tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "cannot read" in out
    # The template advice is about a file that was read and rejected; after a
    # missing path it would be noise.
    assert "What to do next" not in out


def test_broken_json_is_not_a_traceback(tmp_path, capsys):
    path = tmp_path / "broken.json"
    path.write_text("{ not json", encoding="utf-8")
    assert run(["validate", str(path)]) == 1
    assert "not valid JSON" in capsys.readouterr().out


def test_hashing_a_missing_file_points_at_the_packaged_brief(tmp_path, capsys):
    assert run(["hash", str(tmp_path / "nope.md")]) == 1
    out = capsys.readouterr().out
    assert "cannot read" in out
    assert "disensor prompt" in out


def test_r10_says_how_to_declare_a_round_that_found_nothing(tmp_path, capsys):
    """The message has to name the way out, because there is one."""
    artifact = json.loads((EXAMPLES / "example_2_diff_gate.json").read_text(encoding="utf-8"))
    del artifact["findings"]
    path = tmp_path / "a.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")

    assert run(["validate", str(path)]) == 1
    out = capsys.readouterr().out
    assert "[R10]" in out
    assert "total_findings=0" in out


def test_the_help_footer_offers_every_public_gate(tmp_path, capsys):
    """architecture is a public gate; leaving it out of the hint hides it."""
    broken = json.loads((EXAMPLES / "example_2_diff_gate.json").read_text(encoding="utf-8"))
    del broken["findings"]
    path = tmp_path / "a.json"
    path.write_text(json.dumps(broken), encoding="utf-8")

    run(["validate", str(path)])
    out = capsys.readouterr().out
    for gate in ("plan", "diff", "architecture"):
        assert gate in out


def test_version_flag_prints_the_package_version_and_exits_zero():
    """El primer comando que un desconocido tipea despues de instalar.

    Salia con un error de uso y codigo 2: la peor primera impresion posible,
    y se la llevo justo un reproductor externo. Se ejercita python -m disensor
    (el codigo del checkout, no un ejecutable viejo del PATH) y se compara la
    salida exacta: exit 0, stdout con la version del paquete, stderr vacio.

    Comportamiento aceptado a conciencia, estandar de action="version":
    `--version` con argumentos extra imprime y sale 0 sin validar el resto, y
    `subcomando --version` sale 2, porque la bandera es del programa y no de
    los subcomandos.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    from disensor import __version__

    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(root / "src")}

    r = subprocess.run([sys.executable, "-m", "disensor", "--version"],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0
    assert r.stdout.strip() == f"disensor {__version__}"
    assert r.stderr == ""

    sin_args = subprocess.run([sys.executable, "-m", "disensor"],
                              capture_output=True, text=True, env=env)
    assert sin_args.returncode == 2


def test_the_version_literal_matches_the_packaging_metadata():
    """__version__ es un literal duplicado de [project].version, y eso se ata.

    Sin esta guarda, un release que mueva uno solo dejaria el wheel en una
    version y `disensor --version` diciendo otra, y los tests documentales
    coincidirian todos en el valor equivocado porque comparan contra
    __version__. Se lee pyproject por regex y no con tomllib porque CI corre
    3.10, que no lo trae.
    """
    import re
    from pathlib import Path

    from disensor import __version__

    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version = "([^"]+)"$', pyproject, re.M)
    assert m, "pyproject.toml no declara version"
    assert m.group(1) == __version__, (
        f"pyproject.toml dice {m.group(1)} y disensor.__version__ dice {__version__}: "
        "el wheel y el CLI anunciarian versiones distintas"
    )
