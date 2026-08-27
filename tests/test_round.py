"""El runner de la ronda, con revisores falsos que reproducen los casos malos.

El caso que da nombre a este archivo es el primero: un informe compartido entre
los intentos de la cadena se atribuye al revisor equivocado. Lo encontró la
propia ronda de esta versión, y es exactamente la clase de defecto que la
herramienta existe para hacer imposible, porque la evidencia terminaba firmada
por alguien que no la escribió.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from disensor import round as ronda
from disensor.round import CHAIN_EXHAUSTED, OK, chain_for, independence_of, run_reviewer


def revisor_falso(tmp_path: Path, nombre: str, cuerpo: str) -> list[str]:
    """Un adaptador de mentira, escrito en Python: argv real, sin red, sin costo."""
    script = tmp_path / f"{nombre}.py"
    script.write_text(cuerpo, encoding="utf-8")
    return [sys.executable, str(script), "{report}"]


ESCRIBE_Y_FALLA = """import sys
from pathlib import Path
Path(sys.argv[1]).write_text("informe del que despues fallo", encoding="utf-8")
sys.exit(1)
"""

SALE_BIEN_SIN_ESCRIBIR = """import sys
sys.exit(0)
"""

ESCRIBE_Y_SALE_BIEN = """import sys
from pathlib import Path
Path(sys.argv[1]).write_text("informe legitimo", encoding="utf-8")
sys.exit(0)
"""


def entrada(nombre: str, familia: str, command: list[str], **extra) -> dict:
    base = {
        "id": nombre,
        "family": familia,
        "model": nombre,
        "command": command,
        "executable": command[0],
        "hardening": "unverified",
    }
    base.update(extra)
    return base


# --- La atribución del informe -------------------------------------------------

def test_a_failed_reviewers_report_is_not_attributed_to_the_next_one(tmp_path: Path):
    """El hallazgo de la ronda de la 0.9.0, fijado.

    A escribe su informe y sale con error; B sale bien sin escribir nada. Con un
    archivo compartido, el runner veia el texto de A, decia que B habia andado,
    y hasheaba lo de A firmandolo con la familia de B. Un informe de la misma
    familia podia terminar figurando como una revision cross-family.
    """
    a = entrada("a", "openai", revisor_falso(tmp_path, "a", ESCRIBE_Y_FALLA))
    b = entrada("b", "google", revisor_falso(tmp_path, "b", SALE_BIEN_SIN_ESCRIBIR))

    informe_a = tmp_path / "report-1-a.md"
    informe_b = tmp_path / "report-2-b.md"
    assert run_reviewer(a, "paquete", informe_a, 60)["outcome"] == "failed"
    assert informe_a.exists(), "A escribio, y su archivo queda para el registro"

    resultado_b = run_reviewer(b, "paquete", informe_b, 60)
    assert resultado_b["outcome"] == "no_report", (
        "B no escribio nada: no puede heredar el informe de A"
    )


def test_exit_zero_without_a_report_is_a_failure(tmp_path: Path):
    e = entrada("x", "openai", revisor_falso(tmp_path, "x", SALE_BIEN_SIN_ESCRIBIR))
    assert run_reviewer(e, "p", tmp_path / "no-existe.md", 60)["outcome"] == "no_report"


def test_a_reviewer_that_writes_and_exits_zero_is_ok(tmp_path: Path):
    e = entrada("x", "openai", revisor_falso(tmp_path, "x", ESCRIBE_Y_SALE_BIEN))
    destino = tmp_path / "informe.md"
    assert run_reviewer(e, "p", destino, 60)["outcome"] == "ok"
    assert destino.read_text(encoding="utf-8") == "informe legitimo"


def test_an_empty_report_is_a_failure(tmp_path: Path):
    vacio = """import sys
from pathlib import Path
Path(sys.argv[1]).write_text("", encoding="utf-8")
sys.exit(0)
"""
    e = entrada("x", "openai", revisor_falso(tmp_path, "x", vacio))
    assert run_reviewer(e, "p", tmp_path / "i.md", 60)["outcome"] == "empty_report"


def test_a_missing_executable_is_reported_not_crashed(tmp_path: Path):
    e = entrada("x", "openai", ["no-existe-este-binario"])
    e["executable"] = None
    assert run_reviewer(e, "p", tmp_path / "i.md", 60)["outcome"] == "not_found"


def test_a_changed_executable_is_refused(tmp_path: Path):
    """El binario que corre tiene que ser el que el dueño aprobo."""
    e = entrada("x", "openai", revisor_falso(tmp_path, "x", ESCRIBE_Y_SALE_BIEN))
    e["executable_hash"] = "sha256:" + "0" * 64
    assert run_reviewer(e, "p", tmp_path / "i.md", 60)["outcome"] == "executable_changed"


def test_the_package_travels_as_utf8_bytes(tmp_path: Path):
    """text=True codifica en la pagina local y el revisor recibe basura.

    Ya paso contra un CLI real: contesto que la entrada no era UTF-8 valido y la
    corrida parecia un fallo del revisor.
    """
    eco = """import sys
from pathlib import Path
Path(sys.argv[1]).write_bytes(sys.stdin.buffer.read())
sys.exit(0)
"""
    e = entrada("x", "openai", revisor_falso(tmp_path, "x", eco), stdin="pack")
    destino = tmp_path / "i.md"
    run_reviewer(e, "consigna con acentos: revisión adversarial", destino, 60)
    assert destino.read_bytes().decode("utf-8") == "consigna con acentos: revisión adversarial"


# --- La cadena -----------------------------------------------------------------

def test_the_chain_puts_independence_first_then_hardening():
    """Agotar lo mejor antes de degradar: si no, el modo degradado se vuelve el
    camino por defecto y el registro mostraria una degradacion que nunca hizo falta."""
    # El endurecimiento se deriva del catalogo, asi que el unico que puede
    # salir verified es una entrada que coincide con una receta catalogada.
    from disensor.reviewers import CATALOG
    registro = {"reviewers": [
        entrada("propio", "anthropic", ["x"], model="claude-opus-5"),
        entrada("otro-sin-verificar", "openai", ["x"]),
        entrada("codex", "google", list(CATALOG["codex"]["command"])),
    ]}
    orden = [e["id"] for e, _ in chain_for(registro, "anthropic", "claude-opus-5")]
    assert orden[0] == "codex", "cross-family y verificado va primero"
    assert orden[1] == "otro-sin-verificar"
    assert orden[2] == "propio", "el de la misma familia va ultimo"


def test_independence_is_what_the_reviewer_is():
    gen, modelo = "anthropic", "claude-opus-5"
    assert independence_of(entrada("x", "openai", ["x"]), gen, modelo) == "cross_family"
    otro = entrada("x", "anthropic", ["x"], model="claude-sonnet-4")
    assert independence_of(otro, gen, modelo) == "same_family_distinct_model"
    mismo = entrada("x", "anthropic", ["x"], model=modelo)
    assert independence_of(mismo, gen, modelo) == "same_model_fresh_context"


def test_an_empty_registry_is_an_exhausted_chain():
    assert chain_for({"reviewers": []}, "anthropic", "m") == []


# --- Precondiciones del runner -------------------------------------------------

def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    d = tmp_path / "repo"
    d.mkdir()
    git(d, "init", "-q", "-b", "main")
    (d / "disensor.config.json").write_text('{"criticality_level": "B"}', encoding="utf-8")
    (d / "a.py").write_text("x = 1\n", encoding="utf-8")
    git(d, "add", "-A")
    git(d, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    # Una rama de trabajo, como un PR real: commitear sobre main dejaria el
    # rango vacio y el paso cero contestaria, con razon, que no hace falta ronda.
    git(d, "checkout", "-q", "-b", "trabajo")
    return d


def correr(repo: Path, registro: dict, monkeypatch, tmp_path: Path, **extra):
    from disensor.cli import build_parser

    monkeypatch.setattr(ronda, "load_registry", lambda: registro)
    argv = ["round", "--gate", "diff", "--generator-family", "anthropic",
            "--base", "main", "--head", "HEAD", "--repository", str(repo),
            "--result", str(tmp_path / "resultado.json"),
            "--report", str(tmp_path / "informe.md")]
    for clave, valor in extra.items():
        argv += [f"--{clave}", str(valor)]
    args = build_parser().parse_args(argv)
    monkeypatch.chdir(repo)
    return args.func(args)


def test_a_dirty_tree_stops_the_round(repo: Path, monkeypatch, tmp_path, capsys):
    """La ronda de diff revisa commits que ya existen."""
    (repo / "b.py").write_text("y = 2\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "cambio")
    (repo / "sucio.txt").write_text("sin commitear", encoding="utf-8")
    code = correr(repo, {"reviewers": []}, monkeypatch, tmp_path)
    assert code == 1
    assert "not clean" in capsys.readouterr().out


def test_without_reviewers_the_chain_is_exhausted(repo: Path, monkeypatch, tmp_path, capsys):
    (repo / "b.py").write_text("y = 2\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "cambio")
    code = correr(repo, {"reviewers": []}, monkeypatch, tmp_path)
    assert code == CHAIN_EXHAUSTED
    assert "no reviewer registered" in capsys.readouterr().out


def test_a_report_inside_the_repository_is_refused(repo: Path, monkeypatch, tmp_path, capsys):
    """Un informe adentro ensucia justo el arbol que la ronda esta midiendo."""
    (repo / "b.py").write_text("y = 2\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "cambio")
    from disensor.cli import build_parser

    monkeypatch.setattr(ronda, "load_registry", lambda: {"reviewers": [dict(
        entrada("x", "openai", revisor_falso(tmp_path, "x", ESCRIBE_Y_SALE_BIEN)),
        egress="local",
    )]})
    args = build_parser().parse_args([
        "round", "--gate", "diff", "--generator-family", "anthropic",
        "--base", "main", "--head", "HEAD", "--repository", str(repo),
        "--report", str(repo / "adentro.md"),
        "--result", str(tmp_path / "r.json"),
    ])
    monkeypatch.chdir(repo)
    assert args.func(args) == 1
    assert "inside the repository" in capsys.readouterr().out


def test_a_full_round_leaves_the_tree_clean_and_anchors_the_result(
    repo: Path, monkeypatch, tmp_path, capsys,
):
    """El circuito entero con un revisor falso: sin red, sin costo, y verificable."""
    (repo / "b.py").write_text("y = 2\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "cambio")
    head = git(repo, "rev-parse", "HEAD")
    # egress local: un script de prueba no manda nada a ningun lado, y un
    # egreso desconocido exigiria consentimiento, que es lo correcto.
    registro = {"reviewers": [dict(
        entrada("falso", "openai", revisor_falso(tmp_path, "falso", ESCRIBE_Y_SALE_BIEN)),
        egress="local",
    )]}
    assert correr(repo, registro, monkeypatch, tmp_path) == OK
    assert git(repo, "status", "--porcelain") == "", "el arbol tiene que quedar como estaba"

    r = json.loads((tmp_path / "resultado.json").read_text(encoding="utf-8"))
    assert r["anchors"]["head_oid"] == head
    assert r["declared"]["reviewer_id"] == "falso"
    assert r["declared"]["independence"] == "cross_family"
    assert r["observed"]["report_hash"].startswith("sha256:")
    assert (tmp_path / "informe.md").read_text(encoding="utf-8") == "informe legitimo"


def test_hardening_is_derived_from_the_catalog_not_read_from_the_file():
    """El registro es un JSON editable a mano: un `verified` escrito ahi
    convertiria una afirmacion sobre una prueba hostil en un campo que
    cualquiera se pone."""
    from disensor.reviewers import CATALOG
    from disensor.round import effective_hardening

    legitimo = entrada("codex", "openai", list(CATALOG["codex"]["command"]), hardening="verified")
    assert effective_hardening(legitimo) == "verified"

    falsificado = entrada("codex", "openai", ["codex", "exec"], hardening="verified")
    assert effective_hardening(falsificado) == "unverified", "el comando ya no es la receta probada"

    inventado = entrada("propio", "openai", ["x"], hardening="verified")
    assert effective_hardening(inventado) == "unverified", "no viene de ninguna receta"


def test_level_a_refuses_a_reviewer_that_does_not_meet_the_floor(
    repo: Path, monkeypatch, tmp_path, capsys,
):
    """Declarable no es admisible en el nivel reservado para lo irreversible."""
    # El nivel se escribe en MAIN, que es de donde el runner lee la politica: si
    # lo tomara del checkout, una rama podria bajarse el nivel a si misma para
    # pasar su propio filtro, que es el bypass que la politica del destino evita.
    git(repo, "checkout", "-q", "main")
    (repo / "disensor.config.json").write_text('{"criticality_level": "A"}', encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "nivel A")
    git(repo, "checkout", "-q", "trabajo")
    git(repo, "merge", "-q", "main", "-m", "traer politica")
    (repo / "b.py").write_text("y = 2\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "cambio")
    registro = {"reviewers": [
        entrada("falso", "openai", revisor_falso(tmp_path, "falso", ESCRIBE_Y_SALE_BIEN))
    ]}
    assert correr(repo, registro, monkeypatch, tmp_path) == CHAIN_EXHAUSTED
    assert "Level A demands" in capsys.readouterr().out


def test_a_cloud_reviewer_without_consent_for_this_repository_is_skipped(
    repo: Path, monkeypatch, tmp_path, capsys,
):
    """El material de un repositorio privado no sale por una autorizacion dada
    en otro proyecto. Una funcion de seguridad que existe y no se invoca es peor
    que no tenerla: se lee como si estuviera cubriendo algo."""
    (repo / "b.py").write_text("y = 2\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "cambio")
    registro = {
        "reviewers": [dict(
            entrada("nube", "openai", revisor_falso(tmp_path, "nube", ESCRIBE_Y_SALE_BIEN)),
            egress="cloud", provider="AlgunProveedor",
        )],
        "consents": [],
    }
    monkeypatch.setattr(ronda, "load_registry", lambda: registro)
    assert correr(repo, registro, monkeypatch, tmp_path) == CHAIN_EXHAUSTED
    salida = capsys.readouterr().out
    assert "was not authorised" in salida
    assert "disensor reviewer consent" in salida


def test_a_local_reviewer_needs_no_consent(repo: Path, monkeypatch, tmp_path):
    """Si nada sale de la maquina, no hay nada que autorizar."""
    (repo / "b.py").write_text("y = 2\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "cambio")
    registro = {"reviewers": [dict(
        entrada("local", "openai", revisor_falso(tmp_path, "local", ESCRIBE_Y_SALE_BIEN)),
        egress="local",
    )]}
    monkeypatch.setattr(ronda, "load_registry", lambda: registro)
    assert correr(repo, registro, monkeypatch, tmp_path) == OK
