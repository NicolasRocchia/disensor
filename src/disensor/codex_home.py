"""The isolated home of the codex reviewer: policy `codex_home/1` (#108).

The catalogued recipe promised that the reviewer loads nothing the reviewed
material, or the machine, could tell it before the brief. Measured with
codex-cli 0.153.4, the machine half was false: with `--ignore-user-config`,
`--ignore-rules` and `project_doc_max_bytes=0` the reviewer still received the
owner's global `AGENTS.md` from `CODEX_HOME` and every skill under
`~/.agents/skills`, by name. Those are instructions the owner wrote for their
own assistant, and they reached the reviewer before the brief did; nothing of
that is in any hash.

This module closes the sources the CLI loads on its own, one by one, and
checks on disk, before every attempt, that the closure still holds. What it
does NOT do is as much part of the contract as what it does:

- it does not inspect what the model saw (that is PR 2, the detector);
- it does not protect against a process of the same user writing between the
  check and the run;
- it does not neutralise an organisation's managed configuration: when it
  finds one, the attempt stops, because the policy cannot speak for it;
- it never copies, reads or moves credentials: the owner logs the isolated
  home in, once, with `disensor reviewer login codex`.

One thing the CLI itself writes into that home is not a source and is not
left there: codex-cli 0.153.4 records the cwd of every `exec` as trusted in
`CODEX_HOME/config.toml`, even with `--ignore-user-config` and even when the
request fails before the model answers. A file with nothing but that is the
CLI's own state about directories that no longer exist; `sweep_trust_state`
removes it before the check and after the attempt, and anything else in a
`config.toml` keeps refusing the attempt as the owner's configuration.

The policy is a closed, versioned contract: which home, which environment,
which cwd, which flags, which invariants, which sources. Changing any of it is
bumping the number, and an entry registered under another number has not
earned this hardening.
"""
from __future__ import annotations

import ctypes
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

POLICY = "codex_home/1"

# Lo que no puede existir en el home aislado, ni como archivo, ni como
# directorio, ni como enlace. Es una lista de nombres PROHIBIDOS y no de
# permitidos: el CLI deja archivos de estado propios por version (sqlite,
# installation_id, .sandbox-bin, y en 0.153.4 un config.toml con la confianza
# del cwd de cada exec, que `sweep_trust_state` barre antes del chequeo porque
# no es configuracion del dueño) que no son fuentes de instrucciones, y una
# lista de permitidos dejaria la receta inusable en cada actualizacion sin
# ganar nada. Cada nombre de aca es una fuente de carga automatica: la
# configuracion de usuario y sus perfiles, los archivos de instrucciones, los
# roles de subagentes, los entornos remotos, las skills, los plugins, los
# hooks, las reglas de execpolicy, los prompts y las memorias.
FORBIDDEN_IN_HOME = (
    "config.toml",
    "AGENTS.md",
    "AGENTS.override.md",
    "agents",
    "environments.toml",
    "skills",
    "plugins",
    "hooks.json",
    "hooks",
    "rules",
    "prompts",
    "memories",
    "managed_config.toml",
    "requirements.toml",
)
FORBIDDEN_SUFFIX_IN_HOME = ".config.toml"  # perfiles: <nombre>.config.toml

# Un lanzador no es el binario: el hash tiene que cubrir lo que corre, y un
# .CMD expande %VAR% en el argv antes de que Codex lo vea.
LAUNCHER_SUFFIXES = {".cmd", ".bat", ".ps1", ".js", ".sh"}

# Las variables que el hijo recibe, por nombre exacto o por prefijo. Todo lo
# demas se queda afuera, y en particular nada que empiece por CODEX_ ni por
# OPENAI_: `CODEX_EXEC_SERVER_URL` cambia el entorno de ejecucion del CLI,
# `CODEX_HOME` lo fija esta politica, `OPENAI_BASE_URL` cambia a donde va el
# material (que es lo que el consentimiento cubre) y `OPENAI_API_KEY` haria
# que `login status` y `exec` miraran backends de credenciales distintos.
# Lo que pasa es lo que el sistema, la red y la localizacion necesitan.
ENV_EXACT = {
    "PATH", "HOME", "USER", "USERNAME", "LOGNAME", "SHELL", "TERM", "LANG", "LANGUAGE",
    "TZ", "TMPDIR", "TEMP", "TMP",
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "all_proxy", "no_proxy",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE",
    "NODE_EXTRA_CA_CERTS",
    # Windows: lo que el sistema y los programas instalados necesitan.
    "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT",
    "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA",
    "PROGRAMDATA", "ALLUSERSPROFILE", "PUBLIC",
    "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432",
    "COMMONPROGRAMFILES", "COMMONPROGRAMFILES(X86)", "COMMONPROGRAMW6432",
    "COMPUTERNAME", "USERDOMAIN", "OS", "NUMBER_OF_PROCESSORS", "SESSIONNAME",
}
# Por prefijo solo lo que no puede cargar codigo: la localizacion, los
# directorios XDG y la descripcion del procesador. Ninguna variable de toolchain
# pasa, ni por prefijo ni por nombre: `PYTHONPATH` y `PYTHONSTARTUP` importan
# codigo al arrancar cada python que el revisor corra, `DOTNET_STARTUP_HOOKS`
# carga ensamblados, `NODE_OPTIONS` precarga modulos, `LD_PRELOAD` y `DYLD_*`
# inyectan bibliotecas. La ronda 3 sobre el plan cazo que una allowlist con
# `PYTHON*` adentro decia "entorno heredado neutralizado" mientras dejaba
# pasar un canal de ejecucion automatica. Las herramientas del revisor se
# encuentran por PATH y leen su configuracion del perfil, que es del dueño.
ENV_PREFIXES = ("LC_", "XDG_", "PROCESSOR_")

# Limites del inventario de skills y del argumento serializado. Pasarse de
# cualquiera termina el intento en `context_unverified`: un inventario que no
# termino de recorrer no puede decir que deshabilito todo, y una linea de
# comando de Windows admite 32767 caracteres con todo el argv adentro.
MAX_SKILLS = 2000
MAX_DIRS = 20000
MAX_ARG_CHARS = 24000

LOCK_TIMEOUT = 30.0
AUTH_TIMEOUT = 60

# Las combinaciones (plataforma, version del CLI) contra las que corrio la
# prueba hostil de esta politica. `verified` vale para ellas y para nada mas:
# una version nueva del CLI puede agregar una fuente de carga automatica que
# la lista de arriba no nombra, y registrar el binario que haya instalado no
# prueba nada sobre el (ronda diff 3 de #108). Con otra combinacion la
# politica se aplica igual, el intento la registra, y `new --round` declara
# el endurecimiento como no verificado, con su item. Cada release que corra
# el smoke con otra version la agrega aca.
CERTIFIED = frozenset({
    ("win32", "0.153.4"),
})
VERSION_RE = re.compile(r"codex-cli\s+(\d+\.\d+\.\d+)")

_FOLDERID_PROFILE = "{5E6C858F-0E22-4760-9AFE-EA3317B67173}"
_FOLDERID_PROGRAM_DATA = "{62AB5D82-FDC1-4DC3-A9DD-070D1D495D97}"


class Refused(Exception):
    """The attempt cannot run under the policy. `outcome` names why."""

    def __init__(self, outcome: str, detail: str) -> None:
        super().__init__(detail)
        self.outcome = outcome
        self.detail = detail


class NativeNotFound(Exception):
    """What PATH found is a wrapper this module does not know how to see through."""


@dataclass
class Launch:
    """Everything one attempt needs to start, and how to clean up after it."""

    argv: list[str]
    env: dict[str, str] | None
    cwd: Path
    observed: dict = field(default_factory=dict)
    cleanup: Callable[[], None] = lambda: None


# --- Donde vive -----------------------------------------------------------------

def base_dir(reviewer_id: str) -> Path:
    """`~/.disensor/reviewers/<id>`, resolved when asked so the tests can move it."""
    from . import reviewers

    return reviewers.REGISTRY_DIR / "reviewers" / reviewer_id


def home_dir(reviewer_id: str) -> Path:
    return base_dir(reviewer_id) / "home"


def work_dir(reviewer_id: str) -> Path:
    return base_dir(reviewer_id) / "work"


def lock_path(reviewer_id: str) -> Path:
    return base_dir(reviewer_id) / "lock"


# --- El lock cooperativo ---------------------------------------------------------

class Lock:
    """An exclusive file lock between disensor processes that cooperate.

    A round takes it for the invariant check and the creation of its private
    cwd; `reviewer login` holds it for the whole login. It coordinates
    processes that ask for it and nothing else: it is not a boundary against
    another process of the same user, and the policy does not claim one.
    """

    def __init__(self, path: Path, timeout: float = LOCK_TIMEOUT) -> None:
        self.path = path
        self.timeout = timeout
        self._fd: int | None = None

    def __enter__(self) -> "Lock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        limite = time.monotonic() + self.timeout
        while True:
            try:
                _lock_now(fd)
                self._fd = fd
                return self
            except OSError:
                if time.monotonic() >= limite:
                    os.close(fd)
                    raise Refused(
                        "context_unverified",
                        f"the isolated home is busy: another disensor process holds {self.path} "
                        f"(waited {int(self.timeout)}s)",
                    )
                time.sleep(0.2)

    def __exit__(self, *exc) -> None:
        if self._fd is not None:
            try:
                _unlock_now(self._fd)
            finally:
                os.close(self._fd)
                self._fd = None


def _lock_now(fd: int) -> None:
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_now(fd: int) -> None:
    if os.name == "nt":
        import msvcrt

        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)


# --- Los invariantes -------------------------------------------------------------

def _is_link(path: Path) -> bool:
    if os.path.islink(path):
        return True
    isjunction = getattr(os.path, "isjunction", None)
    return bool(isjunction and isjunction(path))


def check_home(home: Path, *, create: bool = True) -> None:
    """The home is ours, is a directory, is not under the temporary directory and
    carries none of the sources the policy closes. Raises `Refused` otherwise."""
    temporal = Path(tempfile.gettempdir())
    try:
        home.resolve().relative_to(temporal.resolve())
        bajo_temporal = True
    except (ValueError, OSError):
        bajo_temporal = False
    if bajo_temporal:
        raise Refused(
            "context_unverified",
            f"the isolated home {home} is under the temporary directory, where the CLI refuses "
            "to create its helper binaries",
        )
    if _is_link(home):
        raise Refused("context_unverified", f"the isolated home {home} is a link, and the policy owns a directory")
    if not home.exists():
        if not create:
            raise Refused("not_authenticated", f"the isolated home {home} does not exist yet")
        home.mkdir(parents=True, exist_ok=True)
    elif not home.is_dir():
        raise Refused("context_unverified", f"the isolated home {home} is not a directory")
    encontrados = []
    for nombre in FORBIDDEN_IN_HOME:
        if os.path.lexists(home / nombre):
            encontrados.append(nombre)
    try:
        for hijo in os.listdir(home):
            if hijo.endswith(FORBIDDEN_SUFFIX_IN_HOME) and hijo not in encontrados:
                encontrados.append(hijo)
    except OSError as exc:
        raise Refused("context_unverified", f"the isolated home {home} cannot be listed ({exc})") from exc
    if encontrados:
        raise Refused(
            "context_unverified",
            f"the isolated home {home} carries sources the policy closes: {', '.join(sorted(encontrados))}. "
            "Nothing of the owner's codex configuration belongs there; remove them",
        )


# La unica forma de config.toml que el CLI escribe solo: una tabla por cwd con
# su nivel de confianza, y nada mas. Lineas en blanco entre medio; ningun
# comentario, ninguna otra clave, ninguna otra tabla. Lo que no tenga EXACTAMENTE
# esta forma es configuracion del dueño hasta que se demuestre lo contrario.
TRUST_TABLE_RE = re.compile(r"""^\[projects\.(?:'[^']*'|"[^"]*"|[A-Za-z0-9_.:-]+)\]$""")
TRUST_KEY_RE = re.compile(r"""^trust_level\s*=\s*"[a-z_]+"$""")


def is_trust_state(texto: str) -> bool:
    """Whether a `config.toml` holds nothing but the trust the CLI records per cwd.

    `[projects.'<cwd>']` followed by `trust_level = "..."`, any number of
    times, blank lines allowed. An empty file, a comment, any other key or
    table, or a key before its table, is not trust state.
    """
    tablas = 0
    esperando_clave = False
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        if TRUST_TABLE_RE.match(linea):
            if esperando_clave:
                return False
            tablas += 1
            esperando_clave = True
            continue
        if TRUST_KEY_RE.match(linea) and esperando_clave:
            esperando_clave = False
            continue
        return False
    return tablas > 0 and not esperando_clave


def sweep_trust_state(home: Path) -> bool:
    """Remove the trust file the CLI writes into its home, and only that. True if it did.

    codex-cli 0.153.4 records the cwd of every `exec` as trusted in
    `CODEX_HOME/config.toml` (`[projects.'<cwd>'] trust_level = "trusted"`),
    even when the request fails before the model answers and even with
    `--ignore-user-config`; 0.162.1 does not (both measured on 2026-10-15
    with a nonexistent model, so without inference). The private cwd is fresh
    for every attempt, so every attempt left a file the next `check_home`
    refused, and the second attempt on a machine with 0.153.4 never ran; the
    first smoke with that version found it.

    What is removed is a file that parses as trust state and nothing else
    (`is_trust_state`): the CLI's own record about directories that no
    longer exist, not a source of instructions or configuration. A file with
    anything else, a link, or a file that cannot be read is left where it is,
    and `check_home` refuses the attempt as before. The contract of the
    policy did not move: the same sources stay closed and checked on disk;
    the check now tells the CLI's state from the owner's configuration.
    """
    ruta = home / "config.toml"
    if not os.path.lexists(ruta) or _is_link(ruta) or not ruta.is_file():
        return False
    try:
        texto = ruta.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if not is_trust_state(texto):
        return False
    try:
        ruta.unlink()
    except OSError:
        return False
    return True


def system_config_dir() -> Path:
    """Where the CLI reads the configuration an administrator manages."""
    if os.name == "nt":
        return program_data_dir() / "OpenAI" / "Codex"
    return Path("/etc/codex")


def check_system_config(directorio: Path | None = None) -> None:
    """Managed configuration is not neutralised: when it is there, the attempt stops."""
    base = directorio if directorio is not None else system_config_dir()
    presentes = [
        nombre for nombre in ("config.toml", "requirements.toml", "managed_config.toml", "agents")
        if os.path.lexists(base / nombre)
    ]
    if presentes:
        raise Refused(
            "context_unverified",
            f"managed codex configuration at {base} ({', '.join(presentes)}): the policy does not "
            "neutralise what an administrator configures, so it does not vouch for this machine",
        )


def check_ancestors(cwd: Path) -> None:
    """No ancestor of the private cwd is a git repository.

    The CLI reads `.codex/config.toml` from the cwd up to the project root,
    which is the first ancestor with a `.git` marker. The private cwd lives
    under the owner's home; if that home were a repository, the owner's own
    `~/.codex/config.toml` would enter that walk. It would be disabled for
    lack of trust, but the policy stops before depending on that.

    Any `.git`, directory or file: a linked worktree and a submodule carry a
    `.git` FILE (`gitdir: ...`), and checking `.git/HEAD` alone let them
    through (finding of the second diff round of #108). Whether the CLI
    counts a `.git` file as a marker is its business; the invariant says "no
    repository above", and that is what is checked.
    """
    for ancestro in (cwd, *cwd.parents):
        if os.path.lexists(ancestro / ".git"):
            raise Refused(
                "context_unverified",
                f"{ancestro} is a git repository above the reviewer's private directory, so the "
                "CLI would treat it as the project root and read its .codex/ layer",
            )


# --- Las raices de skills --------------------------------------------------------

def _known_folder(guid: str) -> Path | None:
    """`SHGetKnownFolderPath`, which is how the CLI resolves the profile and ProgramData."""
    if os.name != "nt":
        return None
    try:
        import uuid

        rfid = ctypes.create_string_buffer(uuid.UUID(guid).bytes_le, 16)
        salida = ctypes.c_wchar_p()
        shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
        shell32.SHGetKnownFolderPath.argtypes = [
            ctypes.c_char_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p),
        ]
        if shell32.SHGetKnownFolderPath(rfid, 0, None, ctypes.byref(salida)) != 0:
            return None
        try:
            return Path(salida.value) if salida.value else None
        finally:
            ctypes.windll.ole32.CoTaskMemFree(salida)  # type: ignore[attr-defined]
    except (AttributeError, OSError, ValueError):
        return None


def profile_dir() -> Path:
    """The home the CLI uses for `~/.agents/skills`: `dirs::home_dir()`.

    On Windows that is the profile known folder, not `USERPROFILE` or `HOME`
    (measured: overriding both does not move it). On Unix it is `$HOME`, and
    the password database when that is unset.
    """
    if os.name == "nt":
        conocido = _known_folder(_FOLDERID_PROFILE)
        if conocido is not None:
            return conocido
        return Path(os.environ.get("USERPROFILE") or Path.home())
    home = os.environ.get("HOME")
    if home:
        return Path(home)
    try:
        import pwd

        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (ImportError, KeyError, OSError):
        return Path.home()


def program_data_dir() -> Path:
    conocido = _known_folder(_FOLDERID_PROGRAM_DATA)
    if conocido is not None:
        return conocido
    return Path(os.environ.get("PROGRAMDATA") or r"C:\ProgramData")


def skill_roots(cwd: Path) -> list[Path]:
    """Every directory the CLI discovers skills under, for this cwd, plus a margin.

    User: `<profile>/.agents/skills`. Repo: `.agents/skills` of the cwd and of
    each ancestor up to the filesystem root (the CLI walks from the project
    root down to the cwd; this is a superset, and disabling a skill the CLI
    never finds is harmless). Admin: the skills folder of the managed
    configuration. The home's own `skills/` cannot exist, by invariant, and
    the bundled ones are not installed (`skills.bundled.enabled=false`).
    """
    raices = [profile_dir() / ".agents" / "skills"]
    for directorio in (cwd, *cwd.parents):
        raices.append(directorio / ".agents" / "skills")
    raices.append(system_config_dir() / "skills")
    unicas: list[Path] = []
    vistas: set[str] = set()
    for raiz in raices:
        clave = os.path.normcase(str(raiz))
        if clave not in vistas:
            vistas.add(clave)
            unicas.append(raiz)
    return unicas


def inventory(raices: list[Path], *, max_skills: int = MAX_SKILLS, max_dirs: int = MAX_DIRS) -> list[str]:
    """Every `SKILL.md` under the roots, following directory links like the CLI does.

    Links and junctions are followed (USER, REPO and ADMIN scopes follow
    them), cycles are cut by real path, hidden directories are NOT skipped
    (the CLI skips them; a superset costs nothing and a miss costs the
    guarantee). The name is matched without case: a superset again.
    """
    encontrados: list[str] = []
    visitados: set[str] = set()
    directorios = 0
    for raiz in raices:
        if not raiz.is_dir():
            continue
        pila = [raiz]
        while pila:
            actual = pila.pop()
            try:
                real = os.path.realpath(actual)
            except OSError:
                continue
            clave = os.path.normcase(real)
            if clave in visitados:
                continue
            visitados.add(clave)
            directorios += 1
            if directorios > max_dirs:
                raise Refused(
                    "context_unverified",
                    f"the skill inventory visited more than {max_dirs} directories under "
                    f"{', '.join(str(r) for r in raices if r.is_dir())} and did not finish",
                )
            try:
                with os.scandir(actual) as entradas:
                    hijos = list(entradas)
            except OSError as exc:
                # Cerrado, no salteado: un subarbol que este proceso no pudo
                # leer puede tener skills que el CLI, con otra suerte o un
                # instante despues, si encuentre. Un inventario que no termino
                # de recorrer no puede decir que deshabilito todo.
                raise Refused(
                    "context_unverified",
                    f"the skill inventory could not read {actual} ({exc.strerror or exc}): "
                    "a subtree it cannot list may hold skills the CLI would find",
                ) from exc
            for hijo in hijos:
                try:
                    if hijo.is_dir(follow_symlinks=True):
                        pila.append(Path(hijo.path))
                    elif hijo.name.lower() == "skill.md" and hijo.is_file(follow_symlinks=True):
                        encontrados.append(os.path.realpath(hijo.path))
                        if len(encontrados) > max_skills:
                            raise Refused(
                                "context_unverified",
                                f"more than {max_skills} skills found: the inventory does not fit the policy",
                            )
                except OSError:
                    continue
    return sorted(set(encontrados))


def toml_string(valor: str) -> str:
    """A TOML basic string: quotes and backslashes escaped, controls as \\uXXXX.

    `-c` parses its value as TOML and, when that fails, uses the raw text as a
    literal: a bad escape would leave every skill enabled without a word. The
    round-trip test with `tomllib` and the hostile test with a canary are the
    two things standing between this function and that silence.
    """
    partes = ['"']
    for ch in valor:
        codigo = ord(ch)
        if ch == '"':
            partes.append('\\"')
        elif ch == "\\":
            partes.append("\\\\")
        elif codigo < 0x20 or codigo == 0x7F:
            partes.append(f"\\u{codigo:04X}")
        else:
            partes.append(ch)
    partes.append('"')
    return "".join(partes)


def skills_config_value(rutas: list[str]) -> str:
    return "[" + ",".join(f"{{path={toml_string(r)},enabled=false}}" for r in rutas) + "]"


def skills_config_arg(rutas: list[str]) -> str:
    arg = "skills.config=" + skills_config_value(rutas)
    if len(arg) > MAX_ARG_CHARS:
        raise Refused(
            "context_unverified",
            f"the skills.config argument has {len(arg)} characters and the policy caps it at "
            f"{MAX_ARG_CHARS}: too many skills on this machine for one command line",
        )
    return arg


# --- El entorno ------------------------------------------------------------------

def child_env(home: Path, origen: dict[str, str] | None = None) -> dict[str, str]:
    """The subprocess environment, built from an allowlist and nothing else."""
    from . import programs

    fuente = os.environ if origen is None else origen
    env: dict[str, str] = {}
    for clave, valor in fuente.items():
        nombre = clave.upper() if os.name == "nt" else clave
        if nombre in ENV_EXACT or nombre.startswith(ENV_PREFIXES):
            env[clave] = valor
    path = fuente.get("PATH")
    env["PATH"] = os.pathsep.join(programs.absolute_entries(os.defpath if path is None else path))
    env["CODEX_HOME"] = str(home)
    if os.name == "nt":
        env["NODEFAULTCURRENTDIRECTORYINEXEPATH"] = "1"
    return env


# --- El binario nativo -----------------------------------------------------------

_PLATFORM_PACKAGES = {
    ("win32", "x64"): ("codex-win32-x64", "x86_64-pc-windows-msvc"),
    ("win32", "arm64"): ("codex-win32-arm64", "aarch64-pc-windows-msvc"),
    ("darwin", "x64"): ("codex-darwin-x64", "x86_64-apple-darwin"),
    ("darwin", "arm64"): ("codex-darwin-arm64", "aarch64-apple-darwin"),
    ("linux", "x64"): ("codex-linux-x64", "x86_64-unknown-linux-musl"),
    ("linux", "arm64"): ("codex-linux-arm64", "aarch64-unknown-linux-musl"),
}


def _platform_key() -> tuple[str, str]:
    sistema = "win32" if sys.platform.startswith("win") else "darwin" if sys.platform == "darwin" else "linux"
    maquina = platform.machine().lower()
    arquitectura = "arm64" if maquina in {"arm64", "aarch64"} else "x64"
    return sistema, arquitectura


def native_executable(ruta: str, *, sistema: tuple[str, str] | None = None) -> str:
    """The binary behind what PATH found, resolved the way the npm launcher does.

    The launcher (`codex.cmd` on Windows, a symlink to `bin/codex.js`
    elsewhere) resolves `@openai/codex-<os>-<arch>` and runs
    `vendor/<triple>/bin/codex[.exe]` from it, with a fallback to the vendor
    folder of the package itself. A wrapper this function does not recognise
    is refused: the owner names the binary with `--executable`.
    """
    clave = sistema or _platform_key()
    if clave not in _PLATFORM_PACKAGES:
        raise NativeNotFound(f"unsupported platform {clave[0]} {clave[1]}")
    paquete, triple = _PLATFORM_PACKAGES[clave]
    binario = "codex.exe" if clave[0] == "win32" else "codex"
    camino = Path(ruta)
    sufijo = camino.suffix.lower()

    raiz_paquete: Path | None = None
    if os.path.islink(camino):
        real = Path(os.path.realpath(camino))
        if real.name == "codex.js":
            raiz_paquete = real.parent.parent
        elif real.suffix.lower() not in LAUNCHER_SUFFIXES and not _is_script(real):
            return str(real)
        else:
            raise NativeNotFound(
                f"{camino} links to {real}, which is not the npm launcher nor a binary"
            )
    elif sufijo in {".cmd", ".bat"}:
        candidato = camino.parent / "node_modules" / "@openai" / "codex"
        if (candidato / "bin" / "codex.js").is_file():
            raiz_paquete = candidato
        else:
            raise NativeNotFound(
                f"{camino} is a launcher and {candidato / 'bin' / 'codex.js'} is not next to it"
            )
    elif sufijo in LAUNCHER_SUFFIXES or _is_script(camino):
        raise NativeNotFound(f"{camino} is a script wrapper this version does not see through")
    else:
        return str(camino)

    assert raiz_paquete is not None
    candidatos = [
        raiz_paquete / "node_modules" / "@openai" / paquete,
        raiz_paquete.parent / paquete,
        raiz_paquete,
    ]
    for base in candidatos:
        nativo = base / "vendor" / triple / "bin" / binario
        if nativo.is_file() and not os.path.islink(nativo):
            return str(nativo)
    raise NativeNotFound(
        f"no native codex for {triple} under {raiz_paquete}: looked in "
        + ", ".join(str(c / 'vendor' / triple / 'bin' / binario) for c in candidatos)
    )


def _is_script(ruta: Path) -> bool:
    try:
        with open(ruta, "rb") as f:
            return f.read(2) == b"#!"
    except OSError:
        return False


# --- La autenticacion ------------------------------------------------------------

def program_of(argv: list[str]) -> list[str]:
    """The CLI itself, without its subcommand: what precedes `exec` in the recipe.

    For the real binary that is one element; for the fake CLIs of the suite,
    an interpreter and a script. Both have to answer `login status` the same
    way the recipe's `exec` will be run.
    """
    if "exec" in argv[1:]:
        return argv[:argv.index("exec", 1)]
    return argv[:1]


def login_status(programa: list[str], env: dict[str, str], cwd: Path, timeout: int = AUTH_TIMEOUT) -> None:
    """`codex login status` under the policy. Raises `Refused` unless it says logged in.

    Exit 0 is logged in. Exit 1 with "Not logged in" in the output is the one
    case classified as missing credentials, with the command the owner runs.
    Anything else is a check that could not be made, not an absence.
    """
    try:
        out = subprocess.run(
            [*programa, "login", "status"],
            cwd=str(cwd), env=env, capture_output=True, timeout=timeout, check=False,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as exc:
        raise Refused("context_unverified", f"`login status` gave no answer within {timeout}s") from exc
    except OSError as exc:
        raise Refused("context_unverified", f"`login status` could not start: {exc}") from exc
    if out.returncode == 0:
        return
    texto = ((out.stdout or b"") + b"\n" + (out.stderr or b"")).decode("utf-8", "replace")
    if out.returncode == 1 and "Not logged in" in texto:
        raise Refused(
            "not_authenticated",
            "the isolated home has no credentials. The owner logs it in once, from a terminal: "
            "disensor reviewer login codex",
        )
    raise Refused(
        "context_unverified",
        f"`login status` exited {out.returncode}: {texto.strip()[-300:]!r}",
    )


def cli_version(programa: list[str], env: dict[str, str], cwd: Path, timeout: int = AUTH_TIMEOUT) -> str | None:
    """What `--version` answers, as `codex-cli X.Y.Z`, or None when it cannot be read.

    None is not an error: the attempt runs under the policy anyway. What it
    cannot do is claim a hostile test it never had, and that is what
    `certified` decides from this value.
    """
    try:
        out = subprocess.run(
            [*programa, "--version"],
            cwd=str(cwd), env=env, capture_output=True, timeout=timeout, check=False,
            stdin=subprocess.DEVNULL,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    texto = ((out.stdout or b"") + b"\n" + (out.stderr or b"")).decode("utf-8", "replace")
    encontrado = VERSION_RE.search(texto)
    return encontrado.group(1) if encontrado else None


def certified(version: str | None, sistema: str | None = None) -> bool:
    """Whether the hostile test of this policy ran on this platform and CLI version."""
    if version is None:
        return False
    return (sistema or _platform_key()[0], version) in CERTIFIED


# --- La preparacion de un intento ------------------------------------------------

def prepare(
    reviewer_id: str,
    argv: list[str],
    *,
    relax: frozenset[str] = frozenset(),
    cwd: Path | None = None,
) -> Launch:
    """Everything the policy adds to one attempt, or `Refused` with the outcome.

    `argv` is the recipe as `fill_argv` built it, native executable first. The
    result appends the machine's `skills.config`, fixes the environment and
    the private cwd, and records what it did. `relax` exists for the hostile
    test and nowhere else; the runner never passes it. Each value switches
    off one rule so that a control differs from the recipe in that rule alone:

    - `home_invariants`: the home is not checked for the sources the policy
      forbids (the control of the planted `AGENTS.md`);
    - `skills_config`: the inventory is not appended (the control of the
      planted user skill);
    - `private_cwd`: the attempt runs from `cwd` instead of a fresh private
      directory (the hostile repository only attacks from inside);
    - `ancestors`: the ancestors of that cwd are not checked for a git
      repository. The hostile repository IS one, so with `private_cwd` alone
      `check_ancestors` refused the attempt before the inference the test
      pays for. Only the two tests that run from inside that repository relax
      it; nothing else does, and `check_ancestors` itself did not change.
    """
    home = home_dir(reviewer_id)
    barrido = False
    with Lock(lock_path(reviewer_id)):
        if "home_invariants" in relax:
            home.mkdir(parents=True, exist_ok=True)
        else:
            barrido = home.is_dir() and sweep_trust_state(home)
            check_home(home)
        check_system_config()
        if cwd is not None and "private_cwd" in relax:
            privado = cwd
            limpiar: Callable[[], None] = lambda: sweep_trust_state(home)
        else:
            work_dir(reviewer_id).mkdir(parents=True, exist_ok=True)
            privado = Path(tempfile.mkdtemp(prefix="attempt-", dir=work_dir(reviewer_id)))

            def limpiar() -> None:
                shutil.rmtree(privado, ignore_errors=True)
                # Lo que el CLI dejo en el home al correr, para que entre
                # intentos el home este como la politica lo describe.
                sweep_trust_state(home)
        if "ancestors" not in relax:
            try:
                check_ancestors(privado)
            except Refused:
                limpiar()
                raise
    env = child_env(home)
    try:
        programa = program_of(argv)
        login_status(programa, env, privado)
        version = cli_version(programa, env, privado)
        completo = list(argv)
        observado = {
            "isolation": POLICY,
            "codex_home": str(home),
            "cli_version": version,
            "certified": certified(version),
        }
        if barrido:
            observado["trust_state_swept"] = True
        if "skills_config" not in relax:
            rutas = inventory(skill_roots(privado))
            completo += ["-c", skills_config_arg(rutas)]
            observado["skills_disabled"] = len(rutas)
    except Refused:
        limpiar()
        raise
    return Launch(argv=completo, env=env, cwd=privado, observed=observado, cleanup=limpiar)
