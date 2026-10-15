"""El registro de revisores de la máquina: `disensor reviewer`.

Lo que estos tests protegen no es una funcionalidad, es una frontera. Un
revisor registrado es código que se va a ejecutar y que va a recibir el
material bajo revisión, así que hay dos preguntas que el sistema no puede
contestar solo: si ese ejecutable es confiable, y si ese material puede salir
de la máquina. Las dos son del dueño.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from disensor import reviewers
from disensor.cli import build_parser
from disensor.reviewers import (
    CATALOG,
    ReviewerError,
    build_entry,
    describe,
    validate_command,
)


@pytest.fixture(autouse=True)
def registro_aislado(tmp_path, monkeypatch):
    """El registro real del usuario no se toca en los tests."""
    monkeypatch.setattr(reviewers, "REGISTRY_DIR", tmp_path / ".disensor")
    monkeypatch.setattr(reviewers, "REGISTRY", tmp_path / ".disensor" / "reviewers.json")
    return tmp_path / ".disensor" / "reviewers.json"


def correr(*argv: str) -> int:
    args = build_parser().parse_args(["reviewer", *argv])
    return args.func(args)


# --- La forma del comando -----------------------------------------------------

def test_a_shell_string_is_not_a_command():
    """argv o nada: una cadena de shell es donde vive la inyección."""
    assert validate_command("codex exec --whatever")
    assert validate_command([])


def test_a_placeholder_glued_to_other_text_is_rejected():
    """`--input={pack}` deja de ser un argumento y pasa a ser armado de strings."""
    errores = validate_command(["codex", "--input={pack}"])
    assert errores and "whole argument" in errores[0]


def test_a_whole_placeholder_is_accepted():
    assert validate_command(["gemini", "--prompt", "{pack}"]) == []


def test_a_repeated_placeholder_is_rejected():
    assert validate_command(["x", "{pack}", "{pack}"])


# --- Qué se guarda ------------------------------------------------------------

def test_an_entry_built_by_the_assistant_is_always_unverified():
    """`verified` no es un valor que el que registra pueda elegir.

    Si lo fuera, el camino barato sería declararse verificado y el
    endurecimiento quedaría nominalmente visible y operacionalmente muerto.
    """
    entry = build_entry(
        "propio", "other", "modelo", [sys.executable, "-c", "pass"], from_catalog=False,
        stdin="pack",
    )
    assert entry["hardening"] == "unverified"
    assert entry["source"] == "assistant"


def test_an_entry_from_the_catalog_carries_its_tested_hardening(monkeypatch):
    monkeypatch.setattr(reviewers, "resolve_executable", lambda cmd: "/usr/bin/codex")
    monkeypatch.setattr(reviewers, "executable_fingerprint", lambda ruta: "sha256:" + "0" * 64)
    entry = build_entry("codex", "openai", "gpt-5-codex", CATALOG["codex"]["command"],
                        from_catalog=True)
    assert entry["hardening"] == CATALOG["codex"]["hardening"]
    assert entry["source"] == "catalog"


def test_an_executable_not_on_path_is_refused():
    """Una entrada que no puede correr haría caer la cadena por el motivo equivocado."""
    with pytest.raises(ReviewerError, match="not on PATH"):
        build_entry("fantasma", "other", "x", ["no-existe-este-binario"], from_catalog=False)


def test_a_relative_path_with_a_directory_is_refused_at_registration(tmp_path, monkeypatch):
    """El registro es global: una ruta relativa nombraría otro programa en cada directorio (#75)."""
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "revisor.py").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ReviewerError, match="relative path"):
        build_entry("relativo", "other", "m", [str(Path("tools") / "revisor.py"), "{pack}"],
                    from_catalog=False)


def test_the_entry_records_the_executable_and_its_hash():
    """Si el binario cambia, el consentimiento y el endurecimiento dejan de valer."""
    entry = build_entry("propio", "other", "m", [sys.executable, "-c", "pass"],
                        from_catalog=False, stdin="pack")
    assert Path(entry["executable"]).is_absolute()
    assert entry["executable_hash"].startswith("sha256:")


def test_what_the_owner_reads_says_where_the_material_goes():
    entry = build_entry("propio", "other", "m", [sys.executable, "-c", "pass"],
                        from_catalog=False, stdin="pack", egress="cloud", provider="AlgunProveedor")
    texto = describe(entry)
    assert "LEAVES this machine" in texto and "AlgunProveedor" in texto
    assert entry["command"][0] in texto or "python" in texto.lower()


# --- La frontera: quién aprueba qué -------------------------------------------

def test_an_entry_outside_the_catalog_needs_the_owner(capsys, registro_aislado):
    """El diputado confundido: el asistente lee el repositorio, y el repositorio
    puede inducirlo a proponer un ejecutable cualquiera. Validar la forma no
    prueba que un binario sea seguro."""
    code = correr("add", "raro", "--family", "other", "--model", "m",
                  "--stdin", "pack", "--command", sys.executable, "-c", "pass")
    salida = capsys.readouterr().out
    assert code == 2
    assert "decision for the owner" in salida
    assert not registro_aislado.exists(), "no se escribe nada sin aprobacion"


def test_with_approval_it_is_registered(capsys, registro_aislado):
    code = correr("add", "raro", "--family", "other", "--model", "m", "--yes",
                  "--stdin", "pack", "--command", sys.executable, "-c", "pass")
    assert code == 0
    data = json.loads(registro_aislado.read_text(encoding="utf-8"))
    assert data["reviewers"][0]["id"] == "raro"
    assert "unverified" in capsys.readouterr().out


def test_a_cloud_reviewer_needs_confirmation_even_from_the_catalog(capsys, registro_aislado, monkeypatch):
    """Consentir el registro no es consentir que el código privado salga."""
    monkeypatch.setattr(reviewers, "resolve_executable", lambda cmd: sys.executable)
    code = correr("add", "codex", "--model", "un-modelo")
    assert code == 2
    assert "would leave this machine" in capsys.readouterr().out
    assert not registro_aislado.exists()


def test_a_duplicate_id_is_refused(capsys, registro_aislado):
    correr("add", "raro", "--family", "other", "--model", "m", "--yes",
           "--stdin", "pack", "--command", sys.executable, "-c", "pass")
    capsys.readouterr()
    code = correr("add", "raro", "--family", "other", "--model", "m", "--yes",
                  "--stdin", "pack", "--command", sys.executable, "-c", "pass")
    assert code == 1
    assert "already registered" in capsys.readouterr().out


def test_list_and_remove(capsys, registro_aislado):
    correr("add", "raro", "--family", "other", "--model", "m", "--yes",
           "--stdin", "pack", "--command", sys.executable, "-c", "pass")
    capsys.readouterr()
    correr("list")
    assert "raro" in capsys.readouterr().out
    assert correr("remove", "raro") == 0
    capsys.readouterr()
    correr("list")
    assert "no reviewers registered" in capsys.readouterr().out


def test_suggest_is_offline(capsys, monkeypatch):
    """La detección no invoca nada: preguntar después de haber mandado el código
    no es consentir antes de transmitir."""
    llamadas = []
    monkeypatch.setattr(
        reviewers.subprocess, "run",
        lambda *a, **k: llamadas.append(a) or pytest.fail("suggest no debe ejecutar nada"),
    )
    correr("suggest")
    salida = capsys.readouterr().out
    assert "codex" in salida
    assert not llamadas


def test_suggest_prints_the_notes_of_a_recipe_it_found(capsys, monkeypatch):
    """Las notas vivian solo en el catalogo (#112): que el sandbox de codex no
    arranca bajo algunos procesos padre en Windows lo leia quien abria el
    archivo, no quien registraba el revisor."""
    monkeypatch.setattr(
        reviewers, "resolve_executable",
        lambda cmd: "/usr/bin/codex" if cmd[0] == "codex" else None,
    )
    correr("suggest")
    salida = capsys.readouterr().out
    assert "codex: found" in salida
    # Envueltas a 78 columnas, asi que se comparan sin los saltos de linea.
    plano = " ".join(salida.split())
    assert "notes: " + " ".join(CATALOG["codex"]["notes"].split()) in plano
    # Debajo de family, hardening y egress, antes del comando sugerido.
    assert salida.index("hardening verified") < salida.index("notes:") < salida.index("reviewer add codex")
    # Y solo de lo que esta: una receta ausente no se describe.
    assert CATALOG["gemini"]["notes"] not in plano


def test_the_registry_write_refuses_a_symlink(registro_aislado, monkeypatch):
    reviewers.REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "is_symlink", lambda self: True)
    with pytest.raises(ReviewerError, match="symlink"):
        reviewers.save_registry({"reviewers": []})


def test_a_broken_registry_fails_loudly(registro_aislado):
    reviewers.REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    registro_aislado.write_text("{no es json", encoding="utf-8")
    with pytest.raises(ReviewerError, match="not valid JSON"):
        reviewers.load_registry()


def test_consent_is_scoped_to_the_repository_the_recipe_and_the_bytes():
    """Consentir que salga el codigo de un proyecto no es consentir el del siguiente."""
    from disensor.reviewers import consent_key

    base = {"id": "codex", "command": ["codex", "exec"], "executable_hash": "sha256:" + "a" * 64}
    uno = consent_key(base, "github.com/mio/publico")
    otro = consent_key(base, "github.com/mio/privado")
    assert uno != otro, "otro repositorio, otro consentimiento"

    cambiado = dict(base, command=["codex", "exec", "--otra-cosa"])
    assert consent_key(cambiado, "github.com/mio/publico") != uno, "otra receta, otro consentimiento"

    binario = dict(base, executable_hash="sha256:" + "b" * 64)
    assert consent_key(binario, "github.com/mio/publico") != uno, "otros bytes, otro consentimiento"


def test_a_local_reviewer_needs_no_egress_consent():
    """Si no sale nada de la maquina, no hay nada que consentir."""
    from disensor.reviewers import has_consent

    assert has_consent({"id": "x", "egress": "local", "command": ["x"]}, "cualquiera")


def test_two_different_recipes_never_share_a_consent():
    """Aplanar el argv con espacios perdia los limites entre argumentos, asi que
    un consentimiento dado para una receta autorizaba otra distinta."""
    from disensor.reviewers import consent_key

    una = {"id": "t", "command": ["tool", "--label", "a b", "c"], "executable_hash": "h"}
    otra = {"id": "t", "command": ["tool", "--label", "a", "b c"], "executable_hash": "h"}
    assert consent_key(una, "repo") != consent_key(otra, "repo")


def test_a_repeated_flag_is_a_normal_command():
    """Repetir una bandera es una forma normal de argv: lo que no puede
    repetirse es un placeholder, porque el runner no sabria cual llenar."""
    assert validate_command(["tool", "-c", "uno", "-c", "dos", "{pack}"]) == []
    assert validate_command(["tool", "{pack}", "{pack}"])


def test_a_recipe_without_a_material_channel_is_refused():
    """Un revisor al que no se le entrega nada puede salir con codigo 0 y
    escribir algo igual: la ronda certificaria una revision que nunca miro el
    material."""
    from disensor.reviewers import has_material_channel

    assert not has_material_channel(["tool", "--flag"], None)
    assert has_material_channel(["tool", "{pack}"], None)
    assert has_material_channel(["tool"], "pack")

    with pytest.raises(ReviewerError, match="never hands the package"):
        build_entry("mudo", "other", "m", [sys.executable, "-c", "pass"], from_catalog=False)


@pytest.mark.parametrize("malo", ["x/../../target", "a/b", "..", "/abs", "C:x", "Mayus", ""])
def test_an_id_that_can_traverse_a_path_is_refused(malo):
    """El id nombra un archivo dentro del directorio privado de cada intento.

    Con `x/../../target`, el informe del revisor cae fuera de ese directorio:
    metadato del registro derrotando al confinamiento del runner.
    """
    with pytest.raises(ReviewerError, match="invalid reviewer id"):
        build_entry(malo, "other", "m", [sys.executable, "-c", "pass"],
                    from_catalog=False, stdin="pack")


def test_the_ids_we_ship_are_valid():
    from disensor.reviewers import validate_id

    for identificador in CATALOG:
        validate_id(identificador)


def test_a_recipe_that_puts_the_model_in_the_command_demands_one():
    """Sin --model el argumento queda vacio y el revisor corre su default.

    Ese es el defecto que llevo a cinco declaraciones afirmando un modelo que la
    cuenta ni siquiera puede correr.
    """
    with pytest.raises(ReviewerError, match="needs --model"):
        build_entry("codex", "openai", None, CATALOG["codex"]["command"], from_catalog=True)


def test_the_claude_recipe_does_not_load_what_the_machine_adds():
    """Un plugin instalado, o sincronizado desde la cuenta de claude.ai, carga en
    toda sesion de Claude Code, `claude -p` incluida: sin este flag el revisor
    arrancaria con las skills, los hooks y los servidores MCP del dueño de la
    maquina en contexto antes de leer la consigna. La medicion real esta en
    test_hardening; esto fija el argv para que un retoque no lo pierda.
    """
    assert "--safe-mode" in CATALOG["claude"]["command"]


def test_the_catalogued_recipes_do_not_invent_a_default_model():
    """Ninguna receta puede saber que modelos habilita la cuenta de quien instala."""
    for identificador, receta in CATALOG.items():
        if "{model}" in receta["command"]:
            assert receta["model"] is None, f"{identificador} trae un modelo que no puede garantizar"


def test_what_is_declared_as_model_is_what_reaches_the_command(monkeypatch):
    """Lo declarado y lo ejecutado son el mismo valor, por construccion."""
    monkeypatch.setattr(reviewers, "resolve_executable", lambda cmd: sys.executable)
    monkeypatch.setattr(reviewers, "executable_fingerprint", lambda ruta: "sha256:" + "0" * 64)
    entry = build_entry("codex", "openai", "un-modelo", CATALOG["codex"]["command"],
                        from_catalog=True)
    assert "{model}" in entry["command"]
    i = entry["command"].index("{model}")
    assert entry["command"][i - 1] == "-m"
    assert entry["model"] == "un-modelo"


def test_changing_the_model_invalidates_the_egress_consent():
    """Desde que el argv lleva el modelo por {model}, el comando registrado es el
    mismo para dos modelos distintos: sin esto, consentir que el codigo salga
    hacia uno autorizaria mandarlo al otro."""
    from disensor.reviewers import consent_key

    base = {"id": "codex", "command": ["codex", "exec", "-m", "{model}"],
            "executable_hash": "sha256:" + "0" * 64}
    uno = consent_key({**base, "model": "un-modelo"}, "github.com/x/y")
    otro = consent_key({**base, "model": "otro-modelo"}, "github.com/x/y")
    assert uno != otro


# --- El home aislado (#108) ----------------------------------------------------

def test_suggest_tells_the_owner_about_the_login_of_the_isolated_home(capsys, monkeypatch):
    monkeypatch.setattr(
        reviewers, "resolve_executable",
        lambda cmd: "/usr/bin/codex" if cmd[0] == "codex" else None,
    )
    correr("suggest")
    salida = capsys.readouterr().out
    assert salida.index("reviewer add codex") < salida.index("reviewer login codex")


def test_login_refuses_an_entry_without_an_isolated_home(capsys, registro_aislado):
    correr("add", "raro", "--family", "other", "--model", "m", "--yes",
           "--stdin", "pack", "--command", sys.executable, "-c", "pass")
    capsys.readouterr()
    assert correr("login", "raro") == 1
    assert "no isolated home" in capsys.readouterr().out
    assert correr("login", "fantasma") == 1


VUELCA_LOGIN = """import json, os, sys
from pathlib import Path
Path(sys.argv[-1]).write_text(json.dumps({"argv": sys.argv, "home": os.environ.get("CODEX_HOME")}), encoding="utf-8")
sys.exit(0)
"""


def test_login_runs_the_cli_with_the_isolated_home_and_checks_it_after(tmp_path, monkeypatch, capsys, registro_aislado):
    """El login corre el CLI con CODEX_HOME aislado y la terminal heredada, bajo
    el lock, y mira el home antes y despues: un login que dejo algo prohibido
    se dice en voz alta."""
    import tempfile

    from disensor import codex_home

    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path / "temporal"))
    monkeypatch.setattr(codex_home, "system_config_dir", lambda: tmp_path / "sistema")
    script = tmp_path / "codex.py"
    script.write_text(VUELCA_LOGIN, encoding="utf-8")
    volcado = tmp_path / "volcado.json"
    entry = {
        "id": "codex", "family": "openai", "model": "m",
        "command": ["codex", "exec", "-m", "{model}"],
        "executable": sys.executable,
        "executable_hash": reviewers.executable_fingerprint(sys.executable),
        "hardening": "verified", "egress": "cloud", "source": "catalog", "stdin": "pack",
        "isolation": codex_home.POLICY,
    }
    reviewers.save_registry({"reviewers": [entry]})
    original = reviewers.subprocess.run

    def corre(argv, **kwargs):
        # El ejecutable registrado es el interprete: se le antepone el script
        # de mentira y se le agrega el archivo del volcado, y todo lo demas
        # (argv, entorno, cwd) es lo que `login` armo.
        assert argv[0] == sys.executable and argv[1] == "login"
        assert argv[-2:] == ["-c", "skills.bundled.enabled=false"]
        assert kwargs["env"]["CODEX_HOME"] == str(codex_home.home_dir("codex"))
        assert Path(kwargs["cwd"]).resolve().parent == codex_home.work_dir("codex").resolve()
        return original([sys.executable, str(script), *argv[1:], str(volcado)], **kwargs)

    monkeypatch.setenv("CODEX_HOME", "C:/hostil")
    monkeypatch.setattr(reviewers.subprocess, "run", corre)
    assert correr("login", "codex") == 0
    datos = json.loads(volcado.read_text(encoding="utf-8"))
    assert datos["home"] == str(codex_home.home_dir("codex"))
    assert "has its own credentials now" in capsys.readouterr().out

    def deja_config(argv, **kwargs):
        (codex_home.home_dir("codex") / "config.toml").write_text("", encoding="utf-8")
        return original([sys.executable, "-c", "pass"], **kwargs)

    monkeypatch.setattr(reviewers.subprocess, "run", deja_config)
    assert correr("login", "codex") == 1
    assert "config.toml" in capsys.readouterr().out


def test_login_refuses_a_swapped_executable(tmp_path, monkeypatch, capsys, registro_aislado):
    from disensor import codex_home

    entry = {
        "id": "codex", "family": "openai", "model": "m", "command": ["codex", "exec"],
        "executable": sys.executable, "executable_hash": "sha256:" + "0" * 64,
        "hardening": "verified", "egress": "cloud", "source": "catalog", "stdin": "pack",
        "isolation": codex_home.POLICY,
    }
    reviewers.save_registry({"reviewers": [entry]})
    assert correr("login", "codex") == 1
    assert "not the one that was approved" in capsys.readouterr().out


def test_the_login_parser_forwards_the_flags_the_cli_offers():
    args = build_parser().parse_args(["reviewer", "login", "codex", "--device-auth"])
    assert args.reviewer_action == "login" and args.device_auth and not args.with_api_key
    args = build_parser().parse_args(["reviewer", "login", "codex", "--status"])
    assert args.status


def test_executable_is_only_for_a_catalogued_recipe(capsys, registro_aislado):
    code = correr("add", "raro", "--family", "other", "--model", "m", "--yes",
                  "--stdin", "pack", "--executable", sys.executable,
                  "--command", sys.executable, "-c", "pass")
    assert code == 1
    assert "--executable is for a catalogued recipe" in capsys.readouterr().out
    assert not registro_aislado.exists()


def test_a_relative_or_missing_executable_override_is_refused():
    with pytest.raises(ReviewerError, match="absolute path of an existing file"):
        build_entry("codex", "openai", "m", CATALOG["codex"]["command"], from_catalog=True,
                    executable="codex.exe")


# --- La procedencia del consentimiento (#84) ----------------------------------

def _consentir(capsys, *extra: str) -> str:
    """Registra un revisor en la nube y le da el consentimiento desde el cwd."""
    correr("add", "nube", "--family", "other", "--model", "m", "--egress", "cloud", "--yes",
           "--stdin", "pack", "--command", sys.executable, "-c", "pass")
    capsys.readouterr()
    assert correr("consent", "nube", *extra) == 0
    return capsys.readouterr().out


def test_consent_records_how_it_was_given(tmp_path, monkeypatch, capsys, registro_aislado):
    """Sin esto, "el dueño consintio" y "un agente decidio que el dueño consintio"
    dejaban exactamente el mismo registro (#84)."""
    from disensor import __version__

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(reviewers, "_terminal", lambda stream: False)
    salida = _consentir(capsys)
    data = json.loads(registro_aislado.read_text(encoding="utf-8"))
    [clave] = data["consents"]
    assert isinstance(clave, str), "consents sigue siendo una lista de claves: la leen las versiones anteriores"
    registro = data["consent_provenance"][clave]
    assert registro["disensor_version"] == __version__
    assert registro["stdin_terminal"] is False and registro["stdout_terminal"] is False
    assert registro["given_at"].endswith("Z")
    assert "without an interactive terminal" in salida


def test_consent_given_again_records_the_last_act(tmp_path, monkeypatch, capsys, registro_aislado):
    """Un agente que repite el consentimiento sin terminal sobre uno que el dueño
    dio desde la suya queda a la vista, en vez de quedar tapado por el primero."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(reviewers, "_terminal", lambda stream: True)
    assert "from an interactive terminal" in _consentir(capsys)
    monkeypatch.setattr(reviewers, "_terminal", lambda stream: False)
    assert correr("consent", "nube") == 0
    data = json.loads(registro_aislado.read_text(encoding="utf-8"))
    [registro] = data["consent_provenance"].values()
    assert registro["stdin_terminal"] is False


def test_revoking_a_consent_removes_its_provenance(tmp_path, monkeypatch, capsys, registro_aislado):
    monkeypatch.chdir(tmp_path)
    _consentir(capsys)
    assert correr("consent", "nube", "--revoke") == 0
    data = json.loads(registro_aislado.read_text(encoding="utf-8"))
    assert data["consents"] == [] and data["consent_provenance"] == {}


def test_a_key_without_provenance_is_said_to_have_none(registro_aislado):
    """Una clave sin procedencia puede ser de antes de 0.15 o estar escrita a mano:
    no hay como distinguirlas, y el texto no elige una."""
    from disensor.reviewers import consent_key, consent_record, describe_consent

    entry = {"id": "nube", "command": ["x"], "model": "m", "executable_hash": "h"}
    clave = consent_key(entry, "repo")
    reviewers.save_registry({"reviewers": [], "consents": [clave]})
    registro = consent_record(entry, "repo")
    assert registro == {"recorded": False}
    texto = describe_consent(registro)
    assert "not recorded" in texto and "before 0.15" in texto and "outside" in texto


@pytest.mark.parametrize("malo", [
    {"given_at": "2026-10-15T00:00:00Z", "disensor_version": "0.15.0", "stdin_terminal": "yes",
     "stdout_terminal": True},
    {"given_at": "2026-10-15T00:00:00Z", "stdin_terminal": True, "stdout_terminal": True},
    "texto suelto",
])
def test_a_malformed_provenance_counts_as_not_recorded(malo, registro_aislado):
    """El registro se edita a mano: uno a medio llenar se leeria como mas de lo que es."""
    from disensor.reviewers import consent_key, consent_record

    entry = {"id": "nube", "command": ["x"], "model": "m", "executable_hash": "h"}
    clave = consent_key(entry, "repo")
    reviewers.save_registry({"reviewers": [], "consents": [clave],
                             "consent_provenance": {clave: malo}})
    assert consent_record(entry, "repo") == {"recorded": False}


def test_the_provenance_of_a_key_no_longer_consented_is_dropped(tmp_path, monkeypatch, capsys, registro_aislado):
    """Si la misma clave volviera por una version anterior, que no escribe
    procedencia, una huerfana describiria el acto equivocado."""
    monkeypatch.chdir(tmp_path)
    _consentir(capsys)
    data = json.loads(registro_aislado.read_text(encoding="utf-8"))
    data["consent_provenance"]["huerfana"] = {"given_at": "x"}
    reviewers.save_registry(data)
    assert correr("consent", "nube") == 0
    data = json.loads(registro_aislado.read_text(encoding="utf-8"))
    assert "huerfana" not in data["consent_provenance"]


def test_the_null_device_is_not_a_terminal():
    """En Windows `isatty()` contesta true para NUL, que es donde apunta la entrada
    de la herramienta de un agente: medido el 2026-10-15 con Python 3.14.2."""
    import os

    with open(os.devnull, "r", encoding="utf-8") as nulo:
        assert not reviewers._terminal(nulo)
    assert not reviewers._terminal(None)
