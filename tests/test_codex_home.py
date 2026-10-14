"""El home aislado del revisor codex: la política `codex_home/1` (#108).

La receta `codex` prometía que el revisor no carga nada que la máquina le
diga antes que la consigna, y era falso: con los tres flags de endurecimiento
el revisor seguía recibiendo el `AGENTS.md` global de `CODEX_HOME` y las
skills de `~/.agents/skills`. Lo que estas pruebas fijan es cada pieza del
cierre, sin red y sin costo, con un CLI de mentira que vuelca lo que recibió:
el home que el hijo ve, el entorno que le llega, el cwd desde el que corre, el
`skills.config` que el runner le agrega, y cada invariante que corta el
intento antes de pagar nada. La prueba con inferencia de que el modelo no ve
esas fuentes está en `test_hardening.py`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from disensor import codex_home, reviewers
from disensor.codex_home import (
    FORBIDDEN_IN_HOME,
    POLICY,
    Lock,
    NativeNotFound,
    Refused,
    check_home,
    child_env,
    inventory,
    native_executable,
    prepare,
    skills_config_arg,
    toml_string,
)
from disensor.round import run_reviewer


@pytest.fixture(autouse=True)
def mundo_aislado(tmp_path: Path, monkeypatch):
    """Ni el registro real, ni el perfil real, ni la configuracion de sistema real.

    `tmp_path` vive bajo el temporal del sistema, donde la politica se niega a
    poner el home (el CLI no crea ahi sus binarios auxiliares): el temporal
    "del sistema" pasa a ser otro directorio durante la prueba.
    """
    monkeypatch.setattr(reviewers, "REGISTRY_DIR", tmp_path / ".disensor")
    monkeypatch.setattr(reviewers, "REGISTRY", tmp_path / ".disensor" / "reviewers.json")
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path / "temporal-del-sistema"))
    monkeypatch.setattr(codex_home, "profile_dir", lambda: tmp_path / "perfil")
    monkeypatch.setattr(codex_home, "system_config_dir", lambda: tmp_path / "sistema" / "codex")
    return tmp_path


def cli_falso(tmp_path: Path, nombre: str, cuerpo: str) -> str:
    script = tmp_path / f"{nombre}.py"
    script.write_text(cuerpo, encoding="utf-8")
    return str(script)


# Contesta `login status` como el CLI real y, en `exec`, vuelca lo que recibio
# en el archivo de informe, que es el cuarto argumento.
VUELCA = """import json, os, sys
from pathlib import Path
if sys.argv[1:3] == ["login", "status"]:
    print("Logged in using ChatGPT")
    sys.exit(0)
informe = Path(sys.argv[4])
informe.write_text(json.dumps({
    "argv": sys.argv, "env": dict(os.environ), "cwd": os.getcwd(),
    "stdin": sys.stdin.buffer.read().decode("utf-8"),
}), encoding="utf-8")
sys.exit(0)
"""

NO_LOGUEADO = """import sys
if sys.argv[1:3] == ["login", "status"]:
    print("Not logged in")
    sys.exit(1)
sys.exit(0)
"""

STATUS_ROTO = """import sys
if sys.argv[1:3] == ["login", "status"]:
    print("error: could not read auth storage", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
"""


def entrada(script: str) -> dict:
    return {
        "id": "codex",
        "family": "openai",
        "model": "un-modelo",
        "command": [sys.executable, script, "exec", "-m", "{model}", "{report}"],
        "executable": sys.executable,
        "stdin": "pack",
        "isolation": POLICY,
    }


def volcado(tmp_path: Path, script: str) -> dict:
    informe = tmp_path / "informe.json"
    intento = run_reviewer(entrada(script), "el paquete", informe, 60)
    assert intento["outcome"] == "ok", intento
    datos = json.loads(informe.read_text(encoding="utf-8"))
    datos["intento"] = intento
    return datos


# --- El entorno -----------------------------------------------------------------

HOSTILES = {
    "CODEX_HOME": "C:/hostil/home",
    "CODEX_EXEC_SERVER_URL": "http://hostil",
    "OPENAI_BASE_URL": "http://hostil/v1",
    "OPENAI_API_KEY": "sk-hostil",
    "PYTHONPATH": "C:/hostil/sitecustomize",
    "PYTHONSTARTUP": "C:/hostil/arranque.py",
    "DOTNET_STARTUP_HOOKS": "C:/hostil/gancho.dll",
    "NODE_OPTIONS": "--require C:/hostil/precarga.js",
    "LD_PRELOAD": "/hostil/inyectada.so",
    "DYLD_INSERT_LIBRARIES": "/hostil/inyectada.dylib",
}


def test_the_child_gets_the_isolated_home_and_none_of_the_inherited_channels(tmp_path, monkeypatch):
    """Lo que el padre trae no llega: ni el CODEX_HOME de otro, ni las variables
    que cargan codigo al arrancar (hallazgo 1 de la ronda 3 sobre el plan)."""
    for clave, valor in HOSTILES.items():
        monkeypatch.setenv(clave, valor)
    datos = volcado(tmp_path, cli_falso(tmp_path, "vuelca", VUELCA))
    env = datos["env"]
    for clave in HOSTILES:
        assert env.get(clave) != HOSTILES[clave], f"{clave} llego al hijo con el valor del padre"
        if clave != "CODEX_HOME":
            assert clave not in env, f"{clave} llego al hijo"
    assert env["CODEX_HOME"] == str(codex_home.home_dir("codex"))
    assert all(os.path.isabs(e) for e in env["PATH"].split(os.pathsep) if e), env["PATH"]
    if os.name == "nt":
        assert "SYSTEMROOT" in {k.upper() for k in env}
        assert env["NODEFAULTCURRENTDIRECTORYINEXEPATH"] == "1"
    assert datos["stdin"] == "el paquete", "el paquete sigue viajando por stdin"


def test_the_private_cwd_is_under_the_policys_work_directory_and_goes_away(tmp_path):
    datos = volcado(tmp_path, cli_falso(tmp_path, "vuelca", VUELCA))
    cwd = Path(datos["cwd"])
    assert cwd.resolve().parent == codex_home.work_dir("codex").resolve()
    assert not cwd.exists(), "el cwd privado se borra al terminar el intento"
    assert datos["intento"]["isolation"] == POLICY
    assert datos["intento"]["codex_home"] == str(codex_home.home_dir("codex"))


def test_the_catalogued_recipe_keeps_the_machine_specific_argument_out_of_the_command():
    """`skills.config` lo agrega el runner, por intento: en la receta no cabe,
    porque la receta se compara con el catalogo y el inventario es de cada
    maquina."""
    assert not any(arg.startswith("skills.config=") for arg in reviewers.CATALOG["codex"]["command"])
    assert reviewers.CATALOG["codex"]["isolation"] == POLICY
    for feature in ("plugins", "apps", "hooks", "memories", "multi_agent", "remote_plugin"):
        i = reviewers.CATALOG["codex"]["command"].index(feature)
        assert reviewers.CATALOG["codex"]["command"][i - 1] == "--disable"
    assert "skills.bundled.enabled=false" in reviewers.CATALOG["codex"]["command"]


# --- El inventario de skills -----------------------------------------------------

def plantar(raiz: Path, *partes: str) -> Path:
    archivo = raiz.joinpath(*partes)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text("---\nname: x\n---\n", encoding="utf-8")
    return archivo


def _enlace_de_directorio(destino: Path, enlace: Path) -> bool:
    """Un enlace de directorio como los que Codex sigue; False si no se pudo crear."""
    try:
        if os.name == "nt":
            import _winapi

            _winapi.CreateJunction(str(destino), str(enlace))
        else:
            os.symlink(destino, enlace, target_is_directory=True)
        return True
    except (OSError, AttributeError, NotImplementedError):
        return False


def test_skills_config_names_every_skill_of_every_root(tmp_path):
    """Usuario (perfil), repo (cwd y ancestros), admin: cada SKILL.md por ruta,
    anidado o no, con el nombre en cualquier caja, y detras de un enlace."""
    perfil = tmp_path / "perfil"
    a = plantar(perfil, ".agents", "skills", "a", "SKILL.md")
    b = plantar(perfil, ".agents", "skills", "grupo", "b", "SKILL.md")
    minuscula = plantar(perfil, ".agents", "skills", "c", "skill.md")
    oculta = plantar(perfil, ".agents", "skills", ".oculta", "SKILL.md")
    admin = plantar(tmp_path / "sistema" / "codex", "skills", "corp", "SKILL.md")
    # Un ancestro del cwd privado: el propio tmp_path esta por encima de
    # ~/.disensor/reviewers/codex/work/<intento>.
    arriba = plantar(tmp_path, ".agents", "skills", "arriba", "SKILL.md")
    afuera = plantar(tmp_path / "afuera", "enlazada", "SKILL.md")
    enlazada = _enlace_de_directorio(afuera.parent.parent, perfil / ".agents" / "skills" / "link")

    datos = volcado(tmp_path, cli_falso(tmp_path, "vuelca", VUELCA))
    argv = datos["argv"]
    assert argv[-2] == "-c" and argv[-1].startswith("skills.config=")
    rutas = {os.path.normcase(r) for r in _rutas_de(argv[-1])}
    for esperado in (a, b, minuscula, oculta, admin, arriba):
        assert os.path.normcase(os.path.realpath(esperado)) in rutas, esperado
    if enlazada:
        assert os.path.normcase(os.path.realpath(afuera)) in rutas, "detras del enlace"
    assert datos["intento"]["skills_disabled"] == len(rutas)


def _rutas_de(arg: str) -> list[str]:
    """Las rutas del valor TOML de `skills.config`, con el parser de verdad si lo hay."""
    valor = arg[len("skills.config="):]
    tomllib = pytest.importorskip("tomllib")
    tabla = tomllib.loads("x=" + valor)
    assert all(e["enabled"] is False for e in tabla["x"])
    return [e["path"] for e in tabla["x"]]


def test_a_cycle_of_links_ends(tmp_path):
    perfil = tmp_path / "perfil"
    raiz = perfil / ".agents" / "skills"
    plantar(raiz, "a", "SKILL.md")
    if not _enlace_de_directorio(raiz, raiz / "a" / "vuelta"):
        pytest.skip("sin enlaces de directorio en esta maquina")
    encontrados = inventory([raiz], max_dirs=50)
    assert len(encontrados) == 1


def test_an_inventory_that_does_not_finish_is_refused(tmp_path):
    raiz = tmp_path / "perfil" / ".agents" / "skills"
    for i in range(5):
        plantar(raiz, f"s{i}", "SKILL.md")
    with pytest.raises(Refused) as exc:
        inventory([raiz], max_dirs=3)
    assert exc.value.outcome == "context_unverified"
    with pytest.raises(Refused):
        inventory([raiz], max_skills=2)


def test_an_argument_that_does_not_fit_the_command_line_is_refused():
    muchas = [f"C:/perfil/.agents/skills/{i:05d}/SKILL.md" for i in range(1000)]
    with pytest.raises(Refused) as exc:
        skills_config_arg(muchas)
    assert exc.value.outcome == "context_unverified"
    assert "characters" in exc.value.detail


@pytest.mark.parametrize("ruta", [
    r"C:\Users\Nombre Con Espacios\.agents\skills\a\SKILL.md",
    "/home/u/.agents/skills/100%/SKILL.md",
    'C:/perfil/con"comillas"/SKILL.md',
    "C:/perfil/con\\barras\\SKILL.md",
    "C:/perfil/control\x07\x1f\x7f/SKILL.md",
    "C:/perfil/ñandú/日本語/SKILL.md",
    "C:/perfil/fuera-del-bmp-\U0001F600/SKILL.md",
])
def test_the_toml_string_survives_the_round_trip(ruta):
    """`-c` parsea el valor como TOML y, si no parsea, lo usa como texto
    literal: un escape mal hecho dejaria las skills habilitadas en silencio."""
    tomllib = pytest.importorskip("tomllib")
    assert tomllib.loads("x=" + toml_string(ruta))["x"] == ruta
    valor = skills_config_arg([ruta])[len("skills.config="):]
    assert tomllib.loads("x=" + valor)["x"] == [{"path": ruta, "enabled": False}]


# --- Los invariantes del home ----------------------------------------------------

@pytest.mark.parametrize("nombre", [*FORBIDDEN_IN_HOME, "trabajo.config.toml"])
@pytest.mark.parametrize("como", ["archivo", "directorio"])
def test_each_source_the_policy_closes_breaks_the_home(tmp_path, nombre, como):
    home = codex_home.home_dir("codex")
    home.mkdir(parents=True)
    if como == "archivo":
        (home / nombre).write_text("", encoding="utf-8")
    else:
        (home / nombre).mkdir()
    with pytest.raises(Refused) as exc:
        check_home(home)
    assert exc.value.outcome == "context_unverified"
    assert nombre in exc.value.detail
    intento = run_reviewer(entrada(cli_falso(tmp_path, "vuelca", VUELCA)), "p", tmp_path / "i", 60)
    assert intento["outcome"] == "context_unverified"
    assert not (tmp_path / "i").exists(), "el intento se corto antes de correr nada"


def test_a_link_in_the_home_with_a_closed_name_breaks_it_too(tmp_path):
    home = codex_home.home_dir("codex")
    home.mkdir(parents=True)
    afuera = tmp_path / "afuera-agents"
    afuera.mkdir()
    if not _enlace_de_directorio(afuera, home / "agents"):
        pytest.skip("sin enlaces de directorio en esta maquina")
    with pytest.raises(Refused, match="agents"):
        check_home(home)


def test_the_state_files_the_cli_leaves_are_tolerated(tmp_path):
    """Un exec deja sqlite, installation_id y sus binarios auxiliares: estado,
    no fuentes de instrucciones. Medido con 0.153.4 en un home nuevo."""
    home = codex_home.home_dir("codex")
    home.mkdir(parents=True)
    for nombre in ("goals_1.sqlite", "logs_2.sqlite-wal", "memories_1.sqlite", "installation_id",
                   "auth.json", "version.json", ".codex-global-state.json"):
        (home / nombre).write_text("", encoding="utf-8")
    (home / ".sandbox-bin").mkdir()
    (home / "log").mkdir()
    check_home(home)


def test_a_home_under_the_system_temp_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    with pytest.raises(Refused, match="temporary directory"):
        check_home(codex_home.home_dir("codex"))


def test_a_home_that_is_a_link_is_refused(tmp_path):
    destino = tmp_path / "otro-home"
    destino.mkdir()
    home = codex_home.home_dir("codex")
    home.parent.mkdir(parents=True)
    if not _enlace_de_directorio(destino, home):
        pytest.skip("sin enlaces de directorio en esta maquina")
    with pytest.raises(Refused, match="is a link"):
        check_home(home)


def test_a_missing_home_is_created_by_the_round_and_demanded_by_login(tmp_path):
    home = codex_home.home_dir("codex")
    check_home(home)
    assert home.is_dir()
    home.rmdir()
    with pytest.raises(Refused) as exc:
        check_home(home, create=False)
    assert exc.value.outcome == "not_authenticated"


def test_managed_configuration_stops_the_attempt(tmp_path):
    sistema = tmp_path / "sistema" / "codex"
    sistema.mkdir(parents=True)
    (sistema / "requirements.toml").write_text("", encoding="utf-8")
    intento = run_reviewer(entrada(cli_falso(tmp_path, "vuelca", VUELCA)), "p", tmp_path / "i", 60)
    assert intento["outcome"] == "context_unverified"
    assert "managed" in intento["detail"] and "requirements.toml" in intento["detail"]


def test_a_git_repository_above_the_private_cwd_stops_the_attempt(tmp_path):
    """Si `~` fuera un repositorio, `~/.codex/config.toml` entraria en la
    caminata de capas de proyecto del CLI. Se corta antes de depender de que
    el CLI la deshabilite por falta de confianza."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    intento = run_reviewer(entrada(cli_falso(tmp_path, "vuelca", VUELCA)), "p", tmp_path / "i", 60)
    assert intento["outcome"] == "context_unverified"
    assert "git repository" in intento["detail"]


def test_a_linked_worktree_or_submodule_above_the_private_cwd_stops_it_too(tmp_path):
    """Un worktree enlazado y un submodulo llevan `.git` como ARCHIVO
    (`gitdir: ...`): mirar solo `.git/HEAD` los dejaba pasar (ronda diff 2 de
    #108). El invariante dice "ningun repositorio arriba", y eso se chequea."""
    (tmp_path / ".git").write_text("gitdir: C:/en/otro/lado/.git/worktrees/x\n", encoding="utf-8")
    with pytest.raises(Refused, match="git repository"):
        codex_home.check_ancestors(codex_home.work_dir("codex") / "intento")
    intento = run_reviewer(entrada(cli_falso(tmp_path, "vuelca", VUELCA)), "p", tmp_path / "i", 60)
    assert intento["outcome"] == "context_unverified"


# --- La autenticacion ------------------------------------------------------------

def test_a_home_without_credentials_names_the_command_the_owner_runs(tmp_path):
    intento = run_reviewer(entrada(cli_falso(tmp_path, "nolog", NO_LOGUEADO)), "p", tmp_path / "i", 60)
    assert intento["outcome"] == "not_authenticated"
    assert "disensor reviewer login codex" in intento["detail"]


def test_a_status_check_that_fails_for_another_reason_is_not_an_absence(tmp_path):
    """Exit 1 con "Not logged in" es la falta de credenciales; cualquier otra
    salida es un chequeo que no se pudo hacer (hallazgo 5 de la ronda 2)."""
    intento = run_reviewer(entrada(cli_falso(tmp_path, "roto", STATUS_ROTO)), "p", tmp_path / "i", 60)
    assert intento["outcome"] == "context_unverified"
    assert "could not read auth storage" in intento["detail"]


# --- El lock ---------------------------------------------------------------------

def test_the_lock_refuses_when_another_process_holds_it(tmp_path):
    ruta = codex_home.lock_path("codex")
    with Lock(ruta):
        with pytest.raises(Refused) as exc:
            with Lock(ruta, timeout=0.5):
                pass
    assert exc.value.outcome == "context_unverified"
    assert "busy" in exc.value.detail
    with Lock(ruta, timeout=0.5):
        pass  # liberado: se vuelve a conseguir


# --- Lo que la prueba hostil relaja, y nada mas ----------------------------------

def test_relaxing_the_skills_config_omits_only_that_argument(tmp_path):
    plantar(tmp_path / "perfil", ".agents", "skills", "a", "SKILL.md")
    script = cli_falso(tmp_path, "vuelca", VUELCA)
    argv = [sys.executable, script, "exec", "-m", "m", str(tmp_path / "i")]
    con = prepare("codex", argv)
    con.cleanup()
    sin = prepare("codex", argv, relax=frozenset({"skills_config"}))
    sin.cleanup()
    assert con.argv[:-2] == sin.argv == argv
    assert con.argv[-1].startswith("skills.config=")
    assert "skills_disabled" not in sin.observed and sin.observed["isolation"] == POLICY


def test_relaxing_the_private_cwd_runs_from_the_given_directory(tmp_path):
    script = cli_falso(tmp_path, "vuelca", VUELCA)
    argv = [sys.executable, script, "exec", "-m", "m", str(tmp_path / "i")]
    repo = tmp_path / "hostil"
    repo.mkdir()
    lanzamiento = prepare("codex", argv, relax=frozenset({"private_cwd"}), cwd=repo)
    lanzamiento.cleanup()
    assert lanzamiento.cwd == repo and repo.exists()


def test_relaxing_the_home_invariants_lets_a_planted_agents_file_through(tmp_path):
    home = codex_home.home_dir("codex")
    home.mkdir(parents=True)
    (home / "AGENTS.md").write_text("hostil", encoding="utf-8")
    script = cli_falso(tmp_path, "vuelca", VUELCA)
    argv = [sys.executable, script, "exec", "-m", "m", str(tmp_path / "i")]
    with pytest.raises(Refused):
        prepare("codex", argv)
    lanzamiento = prepare("codex", argv, relax=frozenset({"home_invariants"}))
    lanzamiento.cleanup()
    assert lanzamiento.env["CODEX_HOME"] == str(home)


# --- El binario nativo -----------------------------------------------------------

def layout_npm(base: Path, *, anidado=True, hoisted=False, propio=False, sistema=("win32", "x64")) -> Path:
    """El arbol que deja `npm install -g @openai/codex`, en sus tres formas."""
    paquete, triple = codex_home._PLATFORM_PACKAGES[sistema]
    binario = "codex.exe" if sistema[0] == "win32" else "codex"
    raiz = base / "node_modules" / "@openai" / "codex"
    (raiz / "bin").mkdir(parents=True)
    (raiz / "bin" / "codex.js").write_text("// lanzador\n", encoding="utf-8")
    lugares = []
    if anidado:
        lugares.append(raiz / "node_modules" / "@openai" / paquete)
    if hoisted:
        lugares.append(base / "node_modules" / "@openai" / paquete)
    if propio:
        lugares.append(raiz)
    nativo = None
    for lugar in lugares:
        nativo = lugar / "vendor" / triple / "bin" / binario
        nativo.parent.mkdir(parents=True, exist_ok=True)
        nativo.write_bytes(b"MZ binario de mentira")
    lanzador = base / ("codex.cmd" if sistema[0] == "win32" else "codex")
    lanzador.write_text("@ECHO off\nnode codex.js %*\n", encoding="utf-8")
    return lanzador


@pytest.mark.parametrize("forma", ["anidado", "hoisted", "propio"])
def test_the_native_binary_is_found_behind_the_npm_launcher(tmp_path, forma):
    lanzador = layout_npm(tmp_path / "npm", anidado=forma == "anidado",
                          hoisted=forma == "hoisted", propio=forma == "propio")
    nativo = native_executable(str(lanzador), sistema=("win32", "x64"))
    assert nativo.endswith("codex.exe") and Path(nativo).is_file()
    assert "x86_64-pc-windows-msvc" in nativo


def test_a_launcher_without_the_package_next_to_it_is_refused(tmp_path):
    lanzador = tmp_path / "codex.cmd"
    lanzador.write_text("@ECHO off\n", encoding="utf-8")
    with pytest.raises(NativeNotFound, match="codex.js"):
        native_executable(str(lanzador), sistema=("win32", "x64"))


def test_a_launcher_whose_package_has_no_binary_for_this_platform_is_refused(tmp_path):
    lanzador = layout_npm(tmp_path / "npm", anidado=False)
    with pytest.raises(NativeNotFound, match="no native codex"):
        native_executable(str(lanzador), sistema=("win32", "x64"))


@pytest.mark.parametrize("nombre", ["codex.ps1", "codex.js", "codex.sh"])
def test_a_script_wrapper_this_version_does_not_know_is_refused(tmp_path, nombre):
    wrapper = tmp_path / nombre
    wrapper.write_text("", encoding="utf-8")
    with pytest.raises(NativeNotFound, match="wrapper"):
        native_executable(str(wrapper), sistema=("win32", "x64"))


def test_a_shebang_script_without_a_suffix_is_a_wrapper_too(tmp_path):
    wrapper = tmp_path / "codex"
    wrapper.write_bytes(b"#!/bin/sh\nexec node codex.js\n")
    with pytest.raises(NativeNotFound, match="wrapper"):
        native_executable(str(wrapper), sistema=("linux", "x64"))


def test_a_binary_is_taken_as_it_is(tmp_path):
    binario = tmp_path / "codex.exe"
    binario.write_bytes(b"MZ")
    assert native_executable(str(binario), sistema=("win32", "x64")) == str(binario)


def test_a_symlink_to_the_launcher_is_followed(tmp_path):
    """npm en Unix deja `bin/codex -> ../lib/node_modules/@openai/codex/bin/codex.js`."""
    layout_npm(tmp_path / "lib", sistema=("linux", "x64"))
    enlace = tmp_path / "bin" / "codex"
    enlace.parent.mkdir()
    try:
        os.symlink(tmp_path / "lib" / "node_modules" / "@openai" / "codex" / "bin" / "codex.js", enlace)
    except (OSError, NotImplementedError):
        pytest.skip("sin enlaces simbolicos en esta maquina")
    nativo = native_executable(str(enlace), sistema=("linux", "x64"))
    assert nativo.endswith(os.path.join("x86_64-unknown-linux-musl", "bin", "codex"))


@pytest.mark.skipif(not __import__("shutil").which("codex"), reason="codex no esta instalado")
def test_the_installed_launcher_resolves_to_a_real_binary():
    """Contra la instalacion de esta maquina, sin correrla: lo que PATH da se
    resuelve a un archivo que no es un lanzador."""
    import shutil

    nativo = native_executable(shutil.which("codex"))
    assert Path(nativo).is_file()
    assert Path(nativo).suffix.lower() not in codex_home.LAUNCHER_SUFFIXES


# --- Lo que el registro guarda ---------------------------------------------------

def test_the_catalogued_entry_persists_the_policy_and_the_native_binary(tmp_path, monkeypatch):
    lanzador = layout_npm(tmp_path / "npm")
    monkeypatch.setattr(reviewers, "resolve_executable", lambda cmd: str(lanzador))
    monkeypatch.setattr(codex_home, "_platform_key", lambda: ("win32", "x64"))
    entry = reviewers.build_entry("codex", "openai", "m", reviewers.CATALOG["codex"]["command"],
                                 from_catalog=True)
    assert entry["isolation"] == POLICY
    assert entry["executable"].endswith("codex.exe")
    assert entry["executable_hash"].startswith("sha256:")
    assert "isolation:  codex_home/1" in reviewers.describe(entry)
    assert str(codex_home.home_dir("codex")) in reviewers.describe(entry)


def test_an_unresolvable_launcher_asks_for_the_binary_by_hand(tmp_path, monkeypatch):
    lanzador = tmp_path / "codex.cmd"
    lanzador.write_text("@ECHO off\n", encoding="utf-8")
    monkeypatch.setattr(reviewers, "resolve_executable", lambda cmd: str(lanzador))
    monkeypatch.setattr(codex_home, "_platform_key", lambda: ("win32", "x64"))
    with pytest.raises(reviewers.ReviewerError, match="--executable"):
        reviewers.build_entry("codex", "openai", "m", reviewers.CATALOG["codex"]["command"],
                             from_catalog=True)
    binario = tmp_path / "codex.exe"
    binario.write_bytes(b"MZ")
    entry = reviewers.build_entry("codex", "openai", "m", reviewers.CATALOG["codex"]["command"],
                                 from_catalog=True, executable=str(binario))
    assert entry["executable"] == str(binario)
    assert entry["isolation"] == POLICY, "la politica se aplica igual"
    # Pero no hereda el endurecimiento: la prueba hostil corrio contra el
    # binario que la instalacion resuelve, no contra un archivo nombrado a
    # mano (hallazgo de la ronda diff 1 de #108). Ni al registrar, ni al
    # decidirlo de nuevo en la ronda con el registro editado a mano.
    from disensor.round import effective_hardening

    assert entry["hardening"] == "unverified"
    assert entry["executable_source"] == "manual"
    assert effective_hardening(entry) == "unverified"
    editada = dict(entry, hardening="verified")
    assert effective_hardening(editada) == "unverified"
    assert "named by hand" in reviewers.describe(entry)


def test_any_file_named_by_hand_would_otherwise_inherit_the_catalogue_identity(tmp_path, monkeypatch):
    """Lo que el revisor reprodujo: `python.exe` como ejecutable de la receta
    codex salia registrado como OpenAI con endurecimiento verificado."""
    from disensor.round import effective_hardening

    monkeypatch.setattr(codex_home, "_platform_key", lambda: ("win32", "x64"))
    entry = reviewers.build_entry("codex", "openai", "m", reviewers.CATALOG["codex"]["command"],
                                 from_catalog=True, executable=sys.executable)
    assert entry["source"] == "catalog" and entry["family"] == "openai"
    assert entry["hardening"] == "unverified"
    assert effective_hardening(entry) == "unverified"


def test_an_entry_under_an_unknown_policy_does_not_run(tmp_path):
    e = dict(entrada(cli_falso(tmp_path, "vuelca", VUELCA)), isolation="codex_home/99")
    intento = run_reviewer(e, "p", tmp_path / "i", 60)
    assert intento["outcome"] == "not_runnable"
    assert "codex_home/99" in intento["detail"]


def test_a_child_env_built_from_a_given_environment_keeps_only_the_allowlist(tmp_path):
    origen = {"PATH": os.pathsep.join([str(tmp_path), "relativa"]), "HOME": "/h",
              "CODEX_HOME": "/otro", "OPENAI_API_KEY": "k", "LC_ALL": "C", "PYTHONPATH": "x",
              "SYSTEMROOT": "C:/Windows", "XDG_CONFIG_HOME": "/x", "TOTALMENTE_AJENA": "1"}
    env = child_env(tmp_path / "home", origen)
    assert env["CODEX_HOME"] == str(tmp_path / "home")
    assert env["PATH"] == str(tmp_path)
    assert {"HOME", "LC_ALL", "SYSTEMROOT", "XDG_CONFIG_HOME"} <= set(env)
    assert not {"OPENAI_API_KEY", "PYTHONPATH", "TOTALMENTE_AJENA"} & set(env)
