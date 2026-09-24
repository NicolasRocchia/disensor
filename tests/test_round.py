"""El runner de la ronda, con revisores falsos que reproducen los casos malos.

El caso que da nombre a este archivo es el primero: un informe compartido entre
los intentos de la cadena se atribuye al revisor equivocado. Lo encontró la
propia ronda de esta versión, y es exactamente la clase de defecto que la
herramienta existe para hacer imposible, porque la evidencia terminaba firmada
por alguien que no la escribió.
"""
from __future__ import annotations

import json
import os
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



def entrada_catalogada(nombre: str) -> dict:
    """Una entrada como la que produce el registro desde el catalogo.

    El endurecimiento heredado exige la receta ENTERA, no solo el argv: copiar
    el comando y declarar otra familia no hereda la prueba hostil.
    """
    from disensor.reviewers import CATALOG

    receta = CATALOG[nombre]
    import sys as _sys

    from disensor.reviewers import executable_fingerprint

    # El binario tambien tiene que estar atado: se usa el interprete actual como
    # ejecutable de mentira, con su hash real, porque el endurecimiento heredado
    # exige que lo que va a correr sea lo que se aprobo.
    return entrada(
        nombre, receta["family"], list(receta["command"]),
        source="catalog", stdin=receta.get("stdin"), egress=receta["egress"],
        model=receta["model"], executable=_sys.executable,
        executable_hash=executable_fingerprint(_sys.executable),
    )


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
    registro = {"reviewers": [
        entrada("propio", "anthropic", ["x"], model="claude-opus-5"),
        entrada("otro-sin-verificar", "google", ["x"]),
        entrada_catalogada("codex"),
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


def test_tree_state_does_not_rewrite_the_index(repo: Path):
    """Mirar el árbol no escribe el índice (#77).

    Con la entrada del índice desactualizada, un `git status` común la refresca
    y reescribe el índice, y reescribirlo dispara post-index-change desde donde
    diga core.hooksPath. Verificado: sin `--no-optional-locks` esta prueba falla.
    """
    indice = repo / ".git" / "index"
    st = (repo / "a.py").stat()
    os.utime(repo / "a.py", ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    antes = indice.read_bytes()
    assert ronda.tree_state(repo) == ""
    assert indice.read_bytes() == antes


def test_tree_state_does_not_consult_the_filesystem_monitor(repo: Path, tmp_path: Path):
    """El monitor del sistema de archivos es un programa que nombra la configuración (#77).

    El monitor de esta prueba solo deja una marca al lado suyo, fuera del repo.
    Verificado: sin `core.fsmonitor=` vacío, la marca aparece.
    """
    monitor = tmp_path / "monitor.py"
    monitor.write_text(
        'import pathlib, sys\npathlib.Path(sys.argv[0]).with_name("consultado").write_text("x")\n',
        encoding="utf-8",
    )
    python = sys.executable.replace("\\", "/")
    git(repo, "config", "core.fsmonitor", f"'{python}' '{monitor.as_posix()}'")
    assert ronda.tree_state(repo) == ""
    assert not (tmp_path / "consultado").exists()


def test_a_relative_executable_from_an_old_registry_does_not_run(tmp_path):
    """Antes de #75, `reviewer add` podía guardar `.\\codex.CMD`: eso no se corre."""
    comando = revisor_falso(tmp_path, "viejo", ESCRIBE_Y_SALE_BIEN)
    vieja = entrada("viejo", "openai", comando, executable=str(Path(".") / "viejo.cmd"))
    informe = tmp_path / "informe.md"
    intento = run_reviewer(vieja, "paquete", informe, timeout=30)
    assert intento["outcome"] == "not_runnable"
    assert "relative path" in intento["detail"]
    assert not informe.exists()


def test_a_relative_executable_has_no_verified_hardening(tmp_path, monkeypatch):
    """Una ruta relativa no ata ningún binario, aunque el que encuentre hoy coincida.

    El archivo existe y su hash es el registrado: sin el rechazo de la ruta
    relativa, la entrada saldría `verified` y esta prueba fallaría.
    """
    from disensor.reviewers import executable_fingerprint
    from disensor.round import effective_hardening

    monkeypatch.chdir(tmp_path)
    (tmp_path / "binario-de-prueba").write_bytes(b"bytes que coinciden")
    vieja = entrada_catalogada("codex")
    vieja["executable"] = str(Path(".") / "binario-de-prueba")
    vieja["executable_hash"] = executable_fingerprint(vieja["executable"])
    assert vieja["executable_hash"] is not None
    assert effective_hardening(vieja) == "unverified"


def test_a_dirty_tree_stops_the_round(repo: Path, monkeypatch, tmp_path, capsys):
    """La ronda de diff revisa commits que ya existen."""
    (repo / "b.py").write_text("y = 2\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "cambio")
    (repo / "sucio.txt").write_text("sin commitear", encoding="utf-8")
    code = correr(repo, {"reviewers": []}, monkeypatch, tmp_path)
    assert code == 1
    assert "not clean" in capsys.readouterr().err


def test_without_reviewers_the_chain_is_exhausted(repo: Path, monkeypatch, tmp_path, capsys):
    (repo / "b.py").write_text("y = 2\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "cambio")
    code = correr(repo, {"reviewers": []}, monkeypatch, tmp_path)
    assert code == CHAIN_EXHAUSTED
    assert "no reviewer registered" in capsys.readouterr().err


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
    assert "inside the repository" in capsys.readouterr().err


def test_a_full_round_leaves_the_tree_clean_and_anchors_the_result(
    repo: Path, monkeypatch, tmp_path, capsys,
):
    """El circuito entero con un revisor falso: sin red, sin costo, y verificable."""
    from disensor import __version__, gitctx
    from disensor.pack import canonical_pack_hash

    (repo / "b.py").write_text("y = 2\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "cambio")
    head = git(repo, "rev-parse", "HEAD")
    # Con remoto, para que el paquete lleve la identidad canonica y no el
    # directorio de esta maquina.
    git(repo, "remote", "add", "origin", "https://github.com/mio/repo.git")
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

    # El resultado es v2 y dice con que version se armo el paquete.
    assert r["result_version"] == "disensor/round-result/v2"
    assert r["disensor_version"] == __version__
    assert r["repository"] == gitctx.normalize_repository("https://github.com/mio/repo.git")
    # Y su pack_hash se recomputa desde el propio resultado: sin la ruta local
    # del worktree, sin la rama y sin la ruta temporal del informe (#73).
    assert r["hashes"]["pack_hash"] == canonical_pack_hash(
        "diff", repository=r["repository"],
        base=r["anchors"]["merge_base_oid"], head=r["anchors"]["head_oid"],
    )
    assert "material_hash" not in r["hashes"], "una ronda de diff no tiene material propio"


def test_hardening_is_derived_from_the_catalog_not_read_from_the_file():
    """El registro es un JSON editable a mano: un `verified` escrito ahi
    convertiria una afirmacion sobre una prueba hostil en un campo que
    cualquiera se pone."""
    from disensor.reviewers import CATALOG
    from disensor.round import effective_hardening

    assert effective_hardening(entrada_catalogada("codex")) == "verified"

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
    assert "Level A demands" in capsys.readouterr().err


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
    salida = capsys.readouterr().err
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


def test_an_assistant_entry_cannot_forge_catalogued_hardening():
    """Copiar el argv de una receta no hereda su prueba hostil.

    La entrada del asistente podia usar el comando catalogado, declarar
    cualquier familia, y quedar cross_family Y verified: con eso pasaba el piso
    de nivel A sin haber venido nunca del catalogo. El endurecimiento ganado se
    ata a la identidad completa que se probo, no al argv suelto.
    """
    from disensor.reviewers import CATALOG
    from disensor.round import effective_hardening

    forjada = entrada(
        "codex", "google", list(CATALOG["codex"]["command"]),
        source="assistant", stdin=CATALOG["codex"].get("stdin"),
        egress=CATALOG["codex"]["egress"],
    )
    assert effective_hardening(forjada) == "unverified"

    otra_familia = entrada(
        "codex", "google", list(CATALOG["codex"]["command"]),
        source="catalog", stdin=CATALOG["codex"].get("stdin"),
        egress=CATALOG["codex"]["egress"],
    )
    assert effective_hardening(otra_familia) == "unverified", "la familia es parte de la identidad"

    assert effective_hardening(entrada_catalogada("codex")) == "verified"


def test_catalog_hardening_needs_the_binary_bound_and_matching(tmp_path: Path):
    """Sin hash guardado no hay con que comparar, y el runner ejecutaria lo que
    diga `executable`: alcanzaba con editar el registro a mano dejando la
    identidad de la receta intacta."""
    from disensor.round import effective_hardening
    from disensor.reviewers import executable_fingerprint

    base = entrada_catalogada("codex")

    sin_hash = dict(base, executable=sys.executable)
    sin_hash.pop("executable_hash", None)
    assert effective_hardening(sin_hash) == "unverified", "sin hash no hay atadura"

    otro_binario = dict(base, executable=sys.executable,
                        executable_hash="sha256:" + "0" * 64)
    assert effective_hardening(otro_binario) == "unverified", "el hash no coincide"

    atado = dict(base, executable=sys.executable,
                 executable_hash=executable_fingerprint(sys.executable))
    assert effective_hardening(atado) == "verified"


def test_a_plan_round_from_stdin_reaches_every_reviewer(repo: Path, monkeypatch, tmp_path, capsys):
    """El paquete se arma una vez por intento, y stdin se lee una sola vez.

    Sin leerlo por adelantado, del segundo intento en adelante el revisor
    recibia un paquete sin material y podia devolver un informe perfectamente
    formado sobre nada: una ronda de plan quedaba registrada como exitosa sin
    que el revisor hubiera visto el plan.
    """
    from disensor.cli import build_parser

    ECO_DEL_PAQUETE = """import sys
from pathlib import Path
Path(sys.argv[1]).write_bytes(sys.stdin.buffer.read())
sys.exit(0)
"""
    primero = dict(
        entrada("cae", "openai", revisor_falso(tmp_path, "cae", SALE_BIEN_SIN_ESCRIBIR)),
        egress="local",
    )
    segundo = dict(
        entrada("eco", "google", revisor_falso(tmp_path, "eco", ECO_DEL_PAQUETE), stdin="pack"),
        egress="local",
    )
    monkeypatch.setattr(ronda, "load_registry", lambda: {"reviewers": [primero, segundo]})

    material = "# Mi plan\n\nEl contenido que el revisor tiene que ver.\n"
    monkeypatch.setattr("sys.stdin", type("E", (), {"read": staticmethod(lambda: material)})())

    informe = tmp_path / "informe-plan.md"
    args = build_parser().parse_args([
        "round", "--gate", "plan", "--generator-family", "anthropic",
        "--material", "-", "--repository", str(repo),
        "--report", str(informe), "--result", str(tmp_path / "r.json"),
    ])
    monkeypatch.chdir(repo)
    assert args.func(args) == OK
    assert "El contenido que el revisor tiene que ver." in informe.read_text(encoding="utf-8"), (
        "el segundo revisor de la cadena tiene que recibir el material igual que el primero"
    )

    # El material no vive en git: viaja su hash, y el del paquete se recomputa
    # con el material en la mano (#73).
    from disensor.pack import canonical_pack_hash, material_hash

    r = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert r["hashes"]["material_hash"] == material_hash(material)
    assert r["hashes"]["pack_hash"] == canonical_pack_hash(
        "plan", repository=r["repository"], material_text=material,
    )


def test_an_existing_report_destination_is_not_overwritten(repo: Path, monkeypatch, tmp_path, capsys):
    """Lo que haya en ese archivo es de otro: perderlo en silencio para dejar un
    informe es lo que una herramienta que promete no tocar nada no puede hacer."""
    (repo / "b.py").write_text("y = 2\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "cambio")
    ocupado = tmp_path / "informe.md"
    ocupado.write_text("algo importante que ya estaba", encoding="utf-8")
    registro = {"reviewers": [dict(
        entrada("falso", "openai", revisor_falso(tmp_path, "falso", ESCRIBE_Y_SALE_BIEN)),
        egress="local",
    )]}
    assert correr(repo, registro, monkeypatch, tmp_path) == 1
    assert "already exists" in capsys.readouterr().err
    assert ocupado.read_text(encoding="utf-8") == "algo importante que ya estaba"


def test_without_result_stdout_is_json_and_nothing_else(repo: Path, monkeypatch, tmp_path, capsys):
    """La ayuda del CLI ofrece el pipe: `round ... | disensor new --round -`.

    Cualquier prosa en el mismo canal cae despues del JSON y `json.load` la
    rechaza como extra data, asi que el camino que anunciamos no parsea.
    """
    (repo / "c.py").write_text("z = 3\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "cambio")
    registro = {"reviewers": [dict(
        entrada("falso", "openai", revisor_falso(tmp_path, "falso", ESCRIBE_Y_SALE_BIEN)),
        egress="local",
    )]}
    from disensor.cli import build_parser

    monkeypatch.setattr(ronda, "load_registry", lambda: registro)
    args = build_parser().parse_args([
        "round", "--gate", "diff", "--generator-family", "anthropic",
        "--base", "main", "--head", "HEAD", "--repository", str(repo),
        "--report", str(tmp_path / "informe.md"),
    ])
    monkeypatch.chdir(repo)
    assert args.func(args) == 0
    salida = capsys.readouterr()
    resultado = json.loads(salida.out)
    assert resultado["declared"]["reviewer_id"] == "falso"
    assert "round:" in salida.err


def test_a_nested_repository_argument_still_protects_the_whole_worktree(repo: Path, monkeypatch, tmp_path, capsys):
    """`--repository <subdir>` no achica el arbol que hay que cuidar.

    El resultado se escribe despues del ultimo git status: si cae dentro del
    repo, el JSON sale afirmando tree_unchanged sobre un arbol que el propio
    runner acaba de ensuciar.
    """
    from disensor.cli import build_parser

    sub = repo / "sub"
    sub.mkdir()
    monkeypatch.setattr(ronda, "load_registry", lambda: {"reviewers": []})
    args = build_parser().parse_args([
        "round", "--gate", "diff", "--generator-family", "anthropic",
        "--base", "main", "--head", "HEAD", "--repository", str(sub),
        "--result", str(repo / "resultado.json"),
        "--report", str(tmp_path / "informe.md"),
    ])
    monkeypatch.chdir(repo)
    assert args.func(args) != 0
    assert not (repo / "resultado.json").exists()


def test_outside_a_git_repository_the_round_fails_without_blowing_up(monkeypatch, tmp_path, capsys):
    """Normalizar a la raiz no puede convertir 'esto no es un repo' en un crash."""
    from disensor.cli import build_parser

    afuera = tmp_path / "no-es-repo"
    afuera.mkdir()
    monkeypatch.setattr(ronda, "load_registry", lambda: {"reviewers": []})
    args = build_parser().parse_args([
        "round", "--gate", "diff", "--generator-family", "anthropic",
        "--base", "main", "--head", "HEAD", "--repository", str(afuera),
        "--result", str(tmp_path / "r.json"), "--report", str(tmp_path / "i.md"),
    ])
    monkeypatch.chdir(afuera)
    assert args.func(args) != 0
    assert "round:" in capsys.readouterr().err


def test_an_entry_registered_before_the_fix_is_not_used(repo: Path, monkeypatch, tmp_path, capsys):
    """Declara un modelo que su comando no fija: correria el default y declararia otro.

    Degradar el endurecimiento no alcanza, porque el modelo falso viaja igual a
    la declaracion. La entrada se excluye y el runner dice por que.
    """
    from disensor.reviewers import CATALOG

    (repo / "d.py").write_text("w = 4\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "cambio")
    vieja = {
        "id": "codex", "family": "openai", "model": "gpt-5-codex", "source": "catalog",
        "stdin": "pack", "egress": "cloud", "executable": "x", "executable_hash": "sha256:0",
        "command": [c for c in CATALOG["codex"]["command"] if c not in ("-m", "{model}")],
    }
    assert correr(repo, {"reviewers": [vieja]}, monkeypatch, tmp_path) == 4
    salida = capsys.readouterr().err
    assert "does not pass it" in salida
    assert "reviewer add codex --model" in salida


def test_the_suggested_command_includes_the_model_when_the_recipe_needs_it(capsys, monkeypatch):
    """Lo primero que hace quien llega es copiar esa linea.

    El ejecutable se simula presente: suggest solo muestra el comando de las
    recetas que encuentra, y en CI no hay ningun CLI de revisor instalado.
    """
    from disensor import reviewers as revs
    from disensor.cli import build_parser

    monkeypatch.setattr(revs, "resolve_executable", lambda cmd: "/usr/bin/" + cmd[0])
    args = build_parser().parse_args(["reviewer", "suggest"])
    args.func(args)
    salida = capsys.readouterr().out
    assert "disensor reviewer add codex --model" in salida
    assert "disensor reviewer add gemini" in salida, (
        "una receta que no fija el modelo en el argv no lo pide"
    )


def test_a_custom_reviewer_named_like_a_recipe_stays_in_the_chain():
    """Un revisor propio puede llamarse igual que una receta y no le debe nada a su forma."""
    from disensor.round import stale_model_entry

    propio = {"id": "codex", "source": "assistant", "model": "m", "command": ["mio", "{pack}"]}
    assert stale_model_entry(propio) is None


def test_the_reviewer_is_told_where_the_checkout_is(repo: Path, monkeypatch, tmp_path, capsys):
    """El revisor corre desde un directorio temporal y solo sabe donde esta el
    codigo por el paquete. La identidad canonica reemplazo a la ruta local en
    el hash (#73), pero la ruta tiene que seguir viajando, como entrega; y lo
    que se hashea es exactamente lo entregado menos esas lineas, sin una
    segunda lectura del brief despues de la revision."""
    import re

    from disensor import gitctx
    from disensor.pack import canonical_pack_text, deliver, pack_hash

    ECO_DEL_PAQUETE = """import sys
from pathlib import Path
Path(sys.argv[1]).write_bytes(sys.stdin.buffer.read())
sys.exit(0)
"""
    (repo / "b.py").write_text("y = 2\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "cambio")
    git(repo, "remote", "add", "origin", "git@github.com:mio/repo.git")
    registro = {"reviewers": [dict(
        entrada("eco", "openai", revisor_falso(tmp_path, "eco", ECO_DEL_PAQUETE), stdin="pack"),
        egress="local",
    )]}
    assert correr(repo, registro, monkeypatch, tmp_path) == OK

    paquete = (tmp_path / "informe.md").read_text(encoding="utf-8")
    raiz = str(gitctx.repo_root(repo))
    assert f"Local checkout: {raiz}" in paquete
    assert f"Repository: {gitctx.normalize_repository('git@github.com:mio/repo.git')}" in paquete
    assert "Branch:" not in paquete, "la rama local no identifica nada"
    # La linea entera despues de la sangria: una ruta temporal puede llevar
    # espacios (un usuario llamado "Juan Perez") y seguir siendo una ruta.
    informe = re.search(r"^ {4}(.+report-1-eco\.md)$", paquete, re.M)
    assert informe, "el paquete le dice al revisor donde escribir"

    r = json.loads((tmp_path / "resultado.json").read_text(encoding="utf-8"))
    canonico = canonical_pack_text(
        "diff", repository=r["repository"],
        base=r["anchors"]["merge_base_oid"], head=r["anchors"]["head_oid"],
    )
    assert paquete == deliver(canonico, checkout=raiz, report=informe.group(1))
    assert r["hashes"]["pack_hash"] == pack_hash(canonico)


def test_a_diff_round_refuses_a_material_document(repo: Path, monkeypatch, tmp_path, capsys):
    """El material de una compuerta diff es el rango. Un documento pasado ademas
    no entra al paquete, y hashearlo dejaria en la declaracion un
    `material_hash` de algo que el revisor nunca vio."""
    material = tmp_path / "plan.md"
    material.write_text("# un plan que nadie va a ver\n", encoding="utf-8")
    registro = {"reviewers": [dict(
        entrada("falso", "openai", revisor_falso(tmp_path, "falso", ESCRIBE_Y_SALE_BIEN)),
        egress="local",
    )]}
    assert correr(repo, registro, monkeypatch, tmp_path, material=str(material)) == ronda.ERROR
    assert "material" in capsys.readouterr().err
    assert not (tmp_path / "resultado.json").exists()


# --- Los destinos, antes de correr a nadie (#80) --------------------------------

def anota_y_escribe(antes: str = "") -> str:
    """Un revisor que deja una marca por invocacion al lado de su script.

    `antes` es codigo que corre durante la ronda, para simular lo que pasa
    mientras el revisor trabaja.
    """
    return (
        "import sys\n"
        "from pathlib import Path\n"
        "with open(Path(__file__).with_name('llamadas.txt'), 'a', encoding='utf-8') as f:\n"
        "    f.write('x')\n"
        f"{antes}"
        "Path(sys.argv[1]).write_text('informe legitimo', encoding='utf-8')\n"
    )


def llamadas(tmp_path: Path) -> int:
    marca = tmp_path / "llamadas.txt"
    return len(marca.read_text(encoding="utf-8")) if marca.exists() else 0


def un_cambio(repo: Path) -> None:
    (repo / "b.py").write_text("y = 2\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "cambio")


def que_anota(tmp_path: Path, antes: str = "") -> dict:
    return {"reviewers": [dict(
        entrada("anota", "openai", revisor_falso(tmp_path, "anota", anota_y_escribe(antes))),
        egress="local",
    )]}


def _ocupado(repo: Path, tmp: Path) -> dict:
    (tmp / "ocupado.md").write_text("de otro", encoding="utf-8")
    return {"report": tmp / "ocupado.md"}


def _bajo_un_archivo(repo: Path, tmp: Path) -> dict:
    (tmp / "archivo.txt").write_text("x", encoding="utf-8")
    return {"report": tmp / "archivo.txt" / "sub" / "informe.md"}


DESTINOS_INVALIDOS = {
    "el informe ya existe": (_ocupado, "already exists"),
    "el informe adentro del repositorio": (
        lambda repo, tmp: {"report": repo / "adentro.md"}, "inside the repository"),
    "el informe por la salida estandar": (lambda repo, tmp: {"report": "-"}, "--report -"),
    "el informe bajo un archivo": (_bajo_un_archivo, "is not a directory"),
    "el resultado adentro del repositorio": (
        lambda repo, tmp: {"result": repo / "resultado.json"}, "inside the repository"),
    "el resultado en un directorio que no existe": (
        lambda repo, tmp: {"result": tmp / "no-existe" / "r.json"}, "does not exist"),
    "el resultado es un directorio": (lambda repo, tmp: {"result": tmp}, "is a directory"),
    "informe y resultado en el mismo archivo": (
        lambda repo, tmp: {"report": tmp / "mismo.json", "result": tmp / "mismo.json"},
        "the same file"),
}


@pytest.mark.parametrize("caso", list(DESTINOS_INVALIDOS))
def test_an_invalid_destination_fails_before_the_reviewer_runs(
    caso, repo: Path, monkeypatch, tmp_path, capsys,
):
    """Los chequeos corrian despues del bucle de revisores: la corrida se pagaba,
    el material salia, y el informe se borraba con el temporal (#80)."""
    un_cambio(repo)
    armar, motivo = DESTINOS_INVALIDOS[caso]
    extra = armar(repo, tmp_path)
    assert correr(repo, que_anota(tmp_path), monkeypatch, tmp_path, **extra) == ronda.ERROR
    assert motivo in capsys.readouterr().err
    assert llamadas(tmp_path) == 0, "el revisor no se invoca si su informe o el resultado no tienen donde ir"
    assert git(repo, "status", "--porcelain") == ""
    if caso == "el informe ya existe":
        assert (tmp_path / "ocupado.md").read_text(encoding="utf-8") == "de otro"


@pytest.mark.parametrize("afuera", [False, True], ids=["parado adentro", "parado afuera"])
def test_result_dash_is_standard_output(afuera, repo: Path, monkeypatch, tmp_path, capsys):
    """`--result -` es la salida estandar, igual que omitir el flag.

    Parado adentro fallaba despues de la ronda; parado afuera, con --repository,
    creaba un archivo llamado `-` en el directorio de trabajo (#80).
    """
    from disensor.cli import build_parser

    un_cambio(repo)
    monkeypatch.setattr(ronda, "load_registry", lambda: que_anota(tmp_path))
    donde = tmp_path / "afuera" if afuera else repo
    donde.mkdir(exist_ok=True)
    args = build_parser().parse_args([
        "round", "--gate", "diff", "--generator-family", "anthropic",
        "--base", "main", "--head", "HEAD", "--repository", str(repo),
        "--report", str(tmp_path / "informe.md"), "--result", "-",
    ])
    monkeypatch.chdir(donde)
    assert args.func(args) == OK
    assert json.loads(capsys.readouterr().out)["declared"]["reviewer_id"] == "anota"
    assert not (donde / "-").exists()
    assert llamadas(tmp_path) == 1
    assert git(repo, "status", "--porcelain") == ""


def _informe_nombrado(err: str) -> Path:
    """La ruta que el mensaje da como el lugar donde quedo el informe."""
    import re

    hallado = re.search(r"its report is at (.+?)\s*$", err, re.M)
    assert hallado, err
    return Path(hallado.group(1))


def _conservado(err: str) -> str:
    """El informe que la ronda conservo en su directorio privado, que la prueba borra."""
    import shutil

    nombrado = _informe_nombrado(err)
    assert nombrado.parent.name.startswith("disensor-round-"), nombrado
    contenido = nombrado.read_text(encoding="utf-8")
    shutil.rmtree(nombrado.parent)
    return contenido


def test_a_report_destination_that_appears_during_the_round_is_not_overwritten(
    repo: Path, monkeypatch, tmp_path, capsys,
):
    """El destino se valida antes y se crea en exclusiva despues: lo que aparecio
    en el medio es de otro. El informe no se pierde: queda donde lo dejo el
    revisor, y el mensaje dice donde."""
    un_cambio(repo)
    ocupa = tmp_path / "informe.md"
    antes = f"Path({str(ocupa)!r}).write_text('de otro', encoding='utf-8')\n"
    assert correr(repo, que_anota(tmp_path, antes), monkeypatch, tmp_path) == ronda.ERROR
    err = capsys.readouterr().err
    assert "appeared during the round" in err
    assert ocupa.read_text(encoding="utf-8") == "de otro"
    assert _conservado(err) == "informe legitimo"


def test_when_the_report_cannot_be_copied_the_only_copy_is_kept(
    repo: Path, monkeypatch, tmp_path, capsys,
):
    """Una copia de rescate podia fallar igual que la primera, y entonces el
    directorio privado se borraba con la unica copia adentro."""
    import tempfile

    un_cambio(repo)
    original = tempfile.mkdtemp

    def sin_lugar(*args, **kwargs):
        if kwargs.get("prefix") == "disensor-report-":
            raise OSError(28, "No space left on device")
        return original(*args, **kwargs)

    monkeypatch.setattr(ronda.tempfile, "mkdtemp", sin_lugar)
    from disensor.cli import build_parser

    monkeypatch.setattr(ronda, "load_registry", lambda: que_anota(tmp_path))
    args = build_parser().parse_args([
        "round", "--gate", "diff", "--generator-family", "anthropic",
        "--base", "main", "--head", "HEAD", "--repository", str(repo),
        "--result", str(tmp_path / "r.json"),
    ])
    monkeypatch.chdir(repo)
    assert args.func(args) == ronda.ERROR
    err = capsys.readouterr().err
    assert "could not be copied out of the round" in err
    assert _conservado(err) == "informe legitimo"
    assert not (tmp_path / "r.json").exists()


def test_the_result_does_not_write_through_a_link(repo: Path, monkeypatch, tmp_path, capsys):
    """El resultado se escribe en un temporal y reemplaza el nombre: si el destino
    es un enlace a otro archivo, el enlace se reemplaza y el otro queda como estaba."""
    import os

    un_cambio(repo)
    ajeno = tmp_path / "ajeno.txt"
    ajeno.write_text("de otro", encoding="utf-8")
    resultado = tmp_path / "r.json"
    os.link(ajeno, resultado)
    assert correr(repo, que_anota(tmp_path), monkeypatch, tmp_path, result=resultado) == OK
    assert ajeno.read_text(encoding="utf-8") == "de otro"
    assert json.loads(resultado.read_text(encoding="utf-8"))["declared"]["reviewer_id"] == "anota"


def test_a_result_turned_into_a_link_to_the_report_leaves_the_report_alone(
    repo: Path, monkeypatch, tmp_path, capsys,
):
    """Durante la ronda, el destino del resultado pasa a ser un enlace simbolico al
    destino del informe: escribir a traves de el truncaba el informe ya hasheado."""
    import os

    try:
        os.symlink(tmp_path / "prueba-destino", tmp_path / "prueba-enlace")
    except (OSError, NotImplementedError):
        pytest.skip("esta maquina no crea enlaces simbolicos sin privilegios")
    un_cambio(repo)
    informe, resultado = tmp_path / "informe.md", tmp_path / "r.json"
    antes = f"import os\nos.symlink({str(informe)!r}, {str(resultado)!r})\n"
    code = correr(repo, que_anota(tmp_path, antes), monkeypatch, tmp_path, result=resultado)
    assert code == OK, capsys.readouterr().err
    assert informe.read_text(encoding="utf-8") == "informe legitimo"
    assert not resultado.is_symlink()
    r = json.loads(resultado.read_text(encoding="utf-8"))
    assert r["observed"]["report_hash"] == ronda.file_hash(informe)


def test_a_result_that_lands_in_the_tree_is_seen_by_the_last_check(
    repo: Path, monkeypatch, tmp_path, capsys,
):
    """h1 de la ronda de este PR: el resultado se escribia por ruta despues del
    ultimo git status. Si entre los chequeos y la escritura el destino pasaba a
    caer adentro del repositorio (su directorio cambiado por un enlace), el
    runner ensuciaba el arbol con un resultado que decia tree_unchanged.

    La carrera se simula haciendo que los chequeos crean que el destino esta
    afuera: la escritura cae adentro, y ahora pasa antes del ultimo chequeo, que
    la ve y retira el resultado.
    """
    un_cambio(repo)
    real = ronda._inside
    monkeypatch.setattr(
        ronda, "_inside", lambda path, r: False if Path(path).name == "r.json" else real(path, r),
    )
    code = correr(repo, que_anota(tmp_path), monkeypatch, tmp_path, result=repo / "r.json")
    assert code == ronda.TREE_MODIFIED
    assert not (repo / "r.json").exists(), "un resultado que afirma un arbol intacto se retira"
    assert git(repo, "status", "--porcelain") == ""
    assert _informe_nombrado(capsys.readouterr().err) == tmp_path / "informe.md"


def test_a_closed_pipe_names_the_report(repo: Path, monkeypatch, tmp_path, capsys):
    """Con el resultado por stdout, un pipe cerrado del otro lado terminaba en un
    traceback, sin decir donde quedo el informe de una corrida ya pagada."""
    un_cambio(repo)

    class PipeCerrado:
        def write(self, _):
            raise BrokenPipeError(32, "Broken pipe")

        def flush(self):
            pass

    class Salida:
        buffer = PipeCerrado()

    monkeypatch.setattr(ronda.sys, "stdout", Salida())
    assert correr(repo, que_anota(tmp_path), monkeypatch, tmp_path, result="-") == ronda.ERROR
    err = capsys.readouterr().err
    assert "standard output" in err
    assert _informe_nombrado(err) == tmp_path / "informe.md"


def test_a_result_that_cannot_be_written_names_the_report(repo: Path, monkeypatch, tmp_path, capsys):
    """Validado antes, el destino del resultado se vuelve un directorio durante la
    ronda: la corrida ya se pago, y el mensaje dice donde quedo el informe."""
    un_cambio(repo)
    resultado = tmp_path / "r.json"
    antes = f"Path({str(resultado)!r}).mkdir()\n"
    code = correr(repo, que_anota(tmp_path, antes), monkeypatch, tmp_path, result=resultado)
    assert code == ronda.ERROR
    err = capsys.readouterr().err
    assert "could not be written" in err
    assert _informe_nombrado(err).read_text(encoding="utf-8") == "informe legitimo"


def test_a_tree_changed_by_the_reviewer_names_the_report(repo: Path, monkeypatch, tmp_path, capsys):
    """Sin declaracion, pero con el informe a mano: hay que leer que toco."""
    un_cambio(repo)
    antes = f"Path({str(repo / 'tocado.txt')!r}).write_text('x', encoding='utf-8')\n"
    assert correr(repo, que_anota(tmp_path, antes), monkeypatch, tmp_path) == ronda.TREE_MODIFIED
    err = capsys.readouterr().err
    assert "working tree changed" in err
    assert _informe_nombrado(err) == tmp_path / "informe.md"
    assert not (tmp_path / "resultado.json").exists()
