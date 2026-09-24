"""The programs this package runs, found where they are installed.

On Windows a program named without a directory is looked up in the current
directory BEFORE the PATH: `subprocess.run(["git", ...])` runs a `git.exe`
that sits in the working directory, and `shutil.which("git")` answers
`.\\git.EXE`, a relative path. Passing `path=` to `which` does not help: the
current directory is inserted inside it. disensor runs with its working
directory inside the repository it reads, so the program that answered would
depend on what that directory holds (#75).

The variable `NoDefaultCurrentDirectoryInExePath` turns that lookup off, and
some environments define it. That is the trap for whoever tests this: from
such an environment the old code looks correct.

So a program is resolved here against the absolute entries of PATH and nothing
else, and a child gets an environment in which nothing that says where to look
for programs is relative.
"""
from __future__ import annotations

import functools
import os
from pathlib import PurePosixPath, PureWindowsPath

# Lo que Windows usa cuando PATHEXT no esta definida.
_PATHEXT_DEFAULT = ".COM;.EXE;.BAT;.CMD"


def find(name: str) -> str | None:
    """Absolute path of the program `name`, or None. Never the working directory.

    A bare name is searched in the absolute entries of PATH, in order. An
    absolute path is taken as is when it names a runnable file. A relative path
    with a directory in it is refused: resolved against the working directory
    it would name a different program depending on where the next run starts,
    and the reviewer registry that records it is global.
    """
    return _find(name, _path_value(os.environ), os.environ.get("PATHEXT", ""))


def require(name: str) -> str:
    """`find`, or `FileNotFoundError`: the same exception a missing program always raised."""
    ruta = find(name)
    if ruta is None:
        raise FileNotFoundError(f"{name} was not found in the absolute entries of PATH")
    return ruta


def child_env() -> dict[str, str]:
    """The environment for a child: nothing in it points the program search back here.

    PATH keeps only its absolute entries. `GIT_EXEC_PATH` goes when it is
    relative: git puts it in front of its own PATH to find its helpers
    (`git-remote-https` and company), made absolute against the working
    directory. On Windows the child also gets
    `NoDefaultCurrentDirectoryInExePath`, so what it starts in turn skips the
    working directory too. The rest of the environment is the user's and stays.
    """
    # En Windows las claves de os.environ vienen en mayusculas; se escriben asi
    # para no dejar dos variables que Windows considera la misma.
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join(absolute_entries(_path_value(env)))
    if "GIT_EXEC_PATH" in env and not is_absolute(env["GIT_EXEC_PATH"]):
        del env["GIT_EXEC_PATH"]
    if os.name == "nt":
        env["NODEFAULTCURRENTDIRECTORYINEXEPATH"] = "1"
    return env


def is_absolute(path: str, windows: bool = os.name == "nt") -> bool:
    """Whether `path` names the same place from any working directory.

    On Windows that takes a drive and a root, or a UNC share: `\\tools` hangs
    from the current drive and `C:tools` from the current directory of drive C.
    `os.path.isabs` accepts the first one before Python 3.13.
    """
    if not path:
        return False
    if windows:
        return PureWindowsPath(path).is_absolute()
    return PurePosixPath(path).is_absolute()


def absolute_entries(path: str, windows: bool = os.name == "nt") -> list[str]:
    """The entries of a PATH value that name a directory on their own.

    An empty entry and `.` mean the working directory on POSIX, `bin` means a
    directory under it, and on Windows `C:tools` and `\\tools` depend on the
    current drive and directory. None of them is kept. Windows admits an entry
    in quotes or with spaces around it; on POSIX both are part of the name and
    the entry is taken literally.
    """
    entradas = []
    for entrada in path.split(";" if windows else ":"):
        if windows:
            entrada = entrada.strip().strip('"')
        if is_absolute(entrada, windows=windows):
            entradas.append(entrada)
    return entradas


def _path_value(env) -> str:
    """PATH, or the system default when the variable is absent.

    Absent and empty are not the same thing: without PATH the launcher falls
    back to `os.defpath`, where a bare `git` used to be found, and that has to
    keep working. An empty PATH finds nothing, and stays that way.
    """
    valor = env.get("PATH")
    return os.defpath if valor is None else valor


@functools.lru_cache(maxsize=64)
def _find(name: str, path: str, pathext: str) -> str | None:
    # La cache es por (nombre, PATH, PATHEXT): el gate llama a git cientos de
    # veces, y recorrer un PATH largo por cada extension en cada llamada se nota.
    if not name:
        return None
    extensiones = _extensions(name, pathext)
    if os.path.dirname(name):
        if not is_absolute(name):
            return None
        return next((name + ext for ext in extensiones if _runnable(name + ext)), None)
    for entrada in absolute_entries(path):
        for ext in extensiones:
            candidato = os.path.join(entrada, name + ext)
            if _runnable(candidato):
                return candidato
    return None


def _extensions(name: str, pathext: str, windows: bool = os.name == "nt") -> list[str]:
    """The suffixes to try after `name`, in order."""
    if not windows:
        return [""]
    extensiones = [e for e in (pathext or _PATHEXT_DEFAULT).split(";") if e]
    propia = os.path.splitext(name)[1].lower()
    # Con una extension de PATHEXT (`git.exe`, `codex.cmd`) se busca tal cual.
    if propia in {e.lower() for e in extensiones}:
        return [""]
    # Con otra extension (`revisor.exe` con un PATHEXT que no la nombra) se
    # prueba primero el nombre exacto, que es lo que Windows ejecutaria.
    if propia:
        return [""] + extensiones
    # Sin extension, Windows agrega `.exe` aunque PATHEXT no lo nombre: `git`
    # tiene que seguir encontrando `git.exe` con un PATHEXT recortado.
    if ".exe" not in {e.lower() for e in extensiones}:
        extensiones.append(".EXE")
    return extensiones


def _runnable(path: str) -> bool:
    return os.path.isfile(path) and os.access(path, os.X_OK)
