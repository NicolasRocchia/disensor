"""`disensor new --round`: la declaración nace de lo que el runner observó.

El valor de esto no es ahorrar tipeo. Es que la declaración quede anclada a los
commits que el revisor miró de verdad, y que se niegue a existir cuando eso ya
no describe lo que hay delante. La plantilla común resuelve HEAD en el momento
de crearse, y eso es incorrecto apenas se incorporó algo: el revisor miró A, un
hallazgo se arregló, HEAD pasó a B, y una declaración construida después diría
que se revisó B.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from disensor.cli import build_parser
from disensor.template import ROUND_RESULT_VERSION, RoundMismatch, from_round


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    return tmp_path


@pytest.fixture()
def informe(tmp_path: Path) -> Path:
    ruta = tmp_path / "informe.md"
    ruta.write_text("# Findings\n\nNada que objetar.\n", encoding="utf-8")
    return ruta


def resultado_de(repo: Path, informe: Path, **cambios) -> dict:
    head = git(repo, "rev-parse", "HEAD")
    base = {
        "result_version": ROUND_RESULT_VERSION,
        "gate": "diff",
        "repository": "github.com/ejemplo/repo",
        "anchors": {"target_tip_oid": head, "merge_base_oid": head, "head_oid": head},
        "observed": {
            "attempts": [{"id": "codex", "outcome": "ok", "independence": "cross_family"}],
            "report_path": str(informe),
            "report_hash": "sha256:" + hashlib.sha256(informe.read_bytes()).hexdigest(),
            "tree_unchanged": True,
        },
        "declared": {
            "reviewer_id": "codex",
            "family": "openai",
            "model": "gpt-5-codex",
            "independence": "cross_family",
            "hardening": "verified",
        },
        "hashes": {"prompt_hash": "sha256:" + "a" * 64, "pack_hash": "sha256:" + "b" * 64},
    }
    for clave, valor in cambios.items():
        if isinstance(valor, dict) and isinstance(base.get(clave), dict):
            base[clave].update(valor)
        else:
            base[clave] = valor
    return base


def test_the_anchors_come_from_the_round(repo: Path, informe: Path):
    r = resultado_de(repo, informe)
    a = from_round(r, "diff", "B", "full", repo)
    assert a["event"]["head_commit"] == r["anchors"]["head_oid"]
    assert a["event"]["base_commit"] == r["anchors"]["merge_base_oid"]
    assert a["event"]["repository"] == "github.com/ejemplo/repo"


def test_the_reviewer_is_prefilled_from_what_ran(repo: Path, informe: Path):
    a = from_round(resultado_de(repo, informe), "diff", "B", "full", repo)
    r = a["actors"]["reviewers"][0]
    assert r["family"] == "openai"
    assert r["model"] == "gpt-5-codex"
    assert r["independence"] == "cross_family"
    assert r["hardening"] == "verified"
    assert r["prompt_hash"].startswith("sha256:")


def test_confinement_verified_is_prefilled_false(repo: Path, informe: Path):
    """Prellenarlo en true seria declarar mas de lo que el runner observo.

    El esquema define `verified` como la verificacion de que el revisor no
    modifico el repositorio. Lo que el runner hizo fue mirar `git status` antes
    y despues, que no ve escrituras fuera del arbol, ni ignorados, ni `.git/`,
    ni la red.
    """
    a = from_round(resultado_de(repo, informe), "diff", "B", "full", repo)
    assert a["actors"]["reviewers"][0]["confinement"]["verified"] is False


def test_a_moved_head_is_refused(repo: Path, informe: Path):
    """La regla es la frescura del material, no el veredicto del informe.

    Aunque el revisor haya dicho que estaba todo bien, si se incorporo algo el
    head se movio y esa ronda ya no cubre lo que se va a mergear.
    """
    r = resultado_de(repo, informe)
    (repo / "b.py").write_text("y = 2\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "otro")
    with pytest.raises(RoundMismatch, match="HEAD is now"):
        from_round(r, "diff", "B", "full", repo)


def test_a_changed_report_is_refused(repo: Path, informe: Path):
    """Lo que se declara tiene que ser lo que el revisor escribio."""
    r = resultado_de(repo, informe)
    informe.write_text("# Findings\n\nOtra cosa distinta.\n", encoding="utf-8")
    with pytest.raises(RoundMismatch, match="report changed"):
        from_round(r, "diff", "B", "full", repo)


def test_a_missing_report_is_refused(repo: Path, informe: Path):
    r = resultado_de(repo, informe)
    informe.unlink()
    with pytest.raises(RoundMismatch, match="not at"):
        from_round(r, "diff", "B", "full", repo)


def test_a_round_without_a_reviewer_has_nothing_to_declare(repo: Path, informe: Path):
    r = resultado_de(repo, informe, declared={"reviewer_id": None})
    with pytest.raises(RoundMismatch, match="no reviewer"):
        from_round(r, "diff", "B", "full", repo)


def test_an_unknown_result_version_is_refused(repo: Path, informe: Path):
    r = resultado_de(repo, informe, result_version="disensor/round-result/v99")
    with pytest.raises(RoundMismatch, match="this disensor reads"):
        from_round(r, "diff", "B", "full", repo)


def test_a_degraded_round_prefills_its_residue_and_reason(repo: Path, informe: Path):
    """El costo del modo degradado viene puesto: el que declara no tiene que
    acordarse de que existe, solo de completarlo con lo que paso."""
    r = resultado_de(
        repo, informe,
        declared={"family": "anthropic", "independence": "same_model_fresh_context"},
        observed={"attempts": [
            {"id": "codex", "outcome": "failed", "detail": "quota"},
            {"id": "propio", "outcome": "ok"},
        ]},
    )
    a = from_round(r, "diff", "B", "full", repo)
    revisor = a["actors"]["reviewers"][0]
    assert revisor["independence"] == "same_model_fresh_context"
    assert revisor["fallback_reason"]["code"]
    clases = [i["class"] for i in a["residue"]["items"]]
    assert "reviewer_correlation" in clases
    assert a["residue"]["items"][0]["reviewer_ref"] == revisor["reviewer_id"]


def test_unverified_hardening_prefills_its_own_item(repo: Path, informe: Path):
    r = resultado_de(repo, informe, declared={"hardening": "unverified"})
    a = from_round(r, "diff", "B", "full", repo)
    clases = [i["class"] for i in a["residue"]["items"]]
    assert clases == ["reviewer_hardening_gap"]


def test_both_degradations_get_one_item_each(repo: Path, informe: Path):
    r = resultado_de(
        repo, informe,
        declared={"family": "anthropic", "independence": "same_model_fresh_context",
                  "hardening": "unverified"},
    )
    a = from_round(r, "diff", "B", "full", repo)
    clases = sorted(i["class"] for i in a["residue"]["items"])
    assert clases == ["reviewer_correlation", "reviewer_hardening_gap"]
    assert len({i["id"] for i in a["residue"]["items"]}) == 2


def test_the_observed_data_travels_in_the_extension_space(repo: Path, informe: Path):
    """Lo que el runner midio queda registrado, pero fuera de los campos del
    protocolo: no es una prueba nueva, es metadato de la corrida."""
    a = from_round(resultado_de(repo, informe), "diff", "B", "full", repo)
    ext = a["extensions"]["dev.disensor.round"]
    assert ext["pack_hash"].startswith("sha256:")
    assert ext["tree_unchanged"] is True


def test_the_cli_reports_a_mismatch_without_a_traceback(repo: Path, informe: Path, tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(repo)
    archivo = tmp_path / "resultado.json"
    r = resultado_de(repo, informe)
    r["anchors"]["head_oid"] = "0" * 40
    archivo.write_text(json.dumps(r), encoding="utf-8")
    args = build_parser().parse_args(["new", "--gate", "diff", "--round", str(archivo)])
    assert args.func(args) == 1
    assert "new:" in capsys.readouterr().out


def test_a_diff_round_cannot_be_declared_as_a_plan(repo: Path, informe: Path):
    """Reetiquetar la compuerta haria que la declaracion cubriera algo que
    nadie reviso: el artefacto identifica la revision que ocurrio."""
    r = resultado_de(repo, informe)
    assert r["gate"] == "diff"
    with pytest.raises(RoundMismatch, match="diff gate and this declaration says plan"):
        from_round(r, "plan", "B", "full", repo)


def test_a_result_from_another_repository_is_refused(repo: Path, informe: Path, monkeypatch):
    """Forks y clones comparten OID: que coincida el commit no alcanza."""
    git(repo, "remote", "add", "origin", "https://github.com/mio/repo.git")
    r = resultado_de(repo, informe)
    r["repository"] = "github.com/ajeno/repo"
    with pytest.raises(RoundMismatch, match="was run in"):
        from_round(r, "diff", "B", "full", repo)


def test_the_same_repository_written_differently_is_accepted(repo: Path, informe: Path):
    """ssh y https son la misma identidad escrita distinto."""
    git(repo, "remote", "add", "origin", "git@github.com:mio/repo.git")
    r = resultado_de(repo, informe)
    r["repository"] = "https://github.com/mio/repo"
    a = from_round(r, "diff", "B", "full", repo)
    assert a["event"]["repository"] == "https://github.com/mio/repo"


def test_the_declared_generator_travels_from_the_round(tmp_path, monkeypatch):
    """La familia y el modelo del generador salen de la ronda, no de un literal.

    `round` pide las dos por linea de comandos y despues no las usaba: el
    resultado no las registraba y la plantilla tenia escrito un modelo que ni
    siquiera es un modelo. R4 contrasta familia y modelo del generador contra
    los del revisor, asi que ahi un dato inventado le miente a la regla. Lo
    encontro la primera ronda que se corrio con el runner sobre este repositorio.
    """
    from disensor.template import from_round, template

    resultado = {
        "result_version": "disensor/round-result/v1",
        "gate": "diff",
        "repository": None,
        "anchors": {},
        "observed": {},
        "declared": {
            "generator": {"family": "openai", "model": "un-modelo-concreto"},
            "reviewer_id": "x", "family": "anthropic", "model": "otro",
            "independence": "cross_family", "hardening": "verified",
        },
        "hashes": {},
    }
    monkeypatch.chdir(tmp_path)
    a = from_round(resultado, "diff", "B", "full", tmp_path)
    assert a["actors"]["generator"] == {"family": "openai", "model": "un-modelo-concreto"}

    # Y sin ronda el modelo se pide en vez de afirmarse.
    m = template("diff", "B", "full", tmp_path)
    assert m["actors"]["generator"]["model"].startswith("FILL_IN")
