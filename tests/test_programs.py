"""Los programas se buscan donde están instalados, nunca en el directorio de trabajo (#75).

Cada prueba saca `NoDefaultCurrentDirectoryInExePath`: con esa variable definida,
Windows mismo deja de mirar el directorio de trabajo, y una prueba corrida desde
un entorno que la define (la sesión de Claude Code donde se revisó #75 lo hace)
pasaría hiciera lo que hiciera este módulo.

El programa de prueba tiene un nombre inventado y es un archivo vacío: nunca se
ejecuta, solo se mira qué ruta se resuelve.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from disensor import programs

NOMBRE = "disensor-probe"


@pytest.fixture(autouse=True)
def sin_atajos(monkeypatch):
    monkeypatch.delenv("NoDefaultCurrentDirectoryInExePath", raising=False)
    if os.name == "nt":
        monkeypatch.setenv("PATHEXT", ".COM;.EXE;.BAT;.CMD")
    programs._find.cache_clear()
    yield
    programs._find.cache_clear()


def programa(directorio: Path) -> Path:
    """Un archivo vacío con el nombre del programa. No se ejecuta nunca."""
    directorio.mkdir(parents=True, exist_ok=True)
    ruta = directorio / (NOMBRE + (".exe" if os.name == "nt" else ""))
    ruta.write_bytes(b"")
    if os.name != "nt":
        # Sin permiso de ejecución, la prueba negativa pasaría también con una
        # búsqueda que mirara el directorio de trabajo: el archivo no calificaría.
        ruta.chmod(0o755)
    return ruta


def test_a_bare_name_is_found_on_path_and_never_in_the_working_directory(tmp_path, monkeypatch):
    instalado = programa(tmp_path / "bin")
    programa(tmp_path / "trabajo")
    monkeypatch.chdir(tmp_path / "trabajo")
    # `.` y la entrada vacía son el directorio de trabajo en POSIX; en Windows lo
    # es la búsqueda misma. Las dos cosas tienen que quedar afuera.
    monkeypatch.setenv("PATH", os.pathsep.join([".", "", str(tmp_path / "bin")]))
    encontrado = programs.find(NOMBRE)
    assert encontrado is not None and Path(encontrado) == instalado


def test_a_program_that_is_only_in_the_working_directory_is_not_found(tmp_path, monkeypatch):
    programa(tmp_path / "trabajo")
    (tmp_path / "vacio").mkdir()
    monkeypatch.chdir(tmp_path / "trabajo")
    monkeypatch.setenv("PATH", os.pathsep.join([".", str(tmp_path / "vacio")]))
    assert programs.find(NOMBRE) is None
    with pytest.raises(FileNotFoundError):
        programs.require(NOMBRE)


def test_a_relative_path_with_a_directory_is_refused(tmp_path, monkeypatch):
    programa(tmp_path / "trabajo" / "tools")
    monkeypatch.chdir(tmp_path / "trabajo")
    assert programs.find(os.path.join("tools", NOMBRE)) is None


def test_an_absolute_path_is_taken_as_is(tmp_path):
    ruta = programa(tmp_path / "bin")
    assert programs.find(str(ruta)) == str(ruta)


@pytest.mark.skipif(os.name == "nt", reason="en Windows todo archivo existente es ejecutable")
def test_an_absolute_path_that_cannot_run_is_not_a_program(tmp_path):
    ruta = programa(tmp_path / "bin")
    ruta.chmod(0o644)
    assert programs.find(str(ruta)) is None


@pytest.mark.parametrize("ruta,absoluta", [
    (r"C:\tools", True),
    (r"\\servidor\recurso\tools", True),
    (r"\tools", False),  # cuelga de la unidad actual; os.path.isabs la aceptaba antes de 3.13
    ("/tools", False),
    ("C:tools", False),  # relativa al directorio actual de la unidad C
    ("tools", False),
    (".", False),
    ("", False),
])
def test_windows_absolute_means_drive_and_root_or_a_share(ruta, absoluta):
    assert programs.is_absolute(ruta, windows=True) is absoluta


def test_posix_absolute_is_a_leading_slash():
    assert programs.is_absolute("/usr/bin", windows=False)
    assert not programs.is_absolute("bin", windows=False)
    assert not programs.is_absolute(".", windows=False)


def test_the_child_environment_keeps_only_absolute_path_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", os.pathsep.join([".", "", "relativo", str(tmp_path)]))
    env = programs.child_env()
    assert env["PATH"].split(os.pathsep) == [str(tmp_path)]
    if os.name == "nt":
        assert env["NODEFAULTCURRENTDIRECTORYINEXEPATH"] == "1"


def test_a_relative_git_exec_path_does_not_reach_the_child(tmp_path, monkeypatch):
    """git antepone GIT_EXEC_PATH a su propio PATH para buscar sus ayudantes."""
    monkeypatch.setenv("GIT_EXEC_PATH", ".")
    assert "GIT_EXEC_PATH" not in programs.child_env()
    monkeypatch.setenv("GIT_EXEC_PATH", str(tmp_path))
    assert programs.child_env()["GIT_EXEC_PATH"] == str(tmp_path)


def test_without_path_the_system_default_is_used_and_an_empty_path_finds_nothing(tmp_path, monkeypatch):
    """Sin PATH, el lanzador cae en `os.defpath`, y ahí se encontraba git; vacío no es lo mismo."""
    instalado = programa(tmp_path / "bin")
    monkeypatch.setattr(os, "defpath", str(tmp_path / "bin"))
    monkeypatch.delenv("PATH", raising=False)
    assert Path(programs.find(NOMBRE)) == instalado
    assert programs.child_env()["PATH"] == str(tmp_path / "bin")
    monkeypatch.setenv("PATH", "")
    assert programs.find(NOMBRE) is None


def test_a_windows_path_entry_may_come_quoted_and_a_posix_one_is_literal():
    assert programs.absolute_entries(r'"C:\Program Files\x" ; C:\y', windows=True) == [
        r"C:\Program Files\x", r"C:\y",
    ]
    # En POSIX el espacio del final es parte del nombre del directorio.
    assert programs.absolute_entries("/opt/tools :/usr/bin", windows=False) == ["/opt/tools ", "/usr/bin"]


def test_a_name_with_an_extension_outside_pathext_is_tried_as_is_first():
    assert programs._extensions("revisor.exe", ".CMD", windows=True) == ["", ".CMD"]
    assert programs._extensions("git.exe", ".COM;.EXE", windows=True) == [""]
    assert programs._extensions("git", ".COM;.EXE", windows=True) == [".COM", ".EXE"]
    assert programs._extensions("git", ".COM;.EXE", windows=False) == [""]
    # Windows agrega `.exe` a un nombre sin extensión aunque PATHEXT no lo nombre.
    assert programs._extensions("git", ".CMD", windows=True) == [".CMD", ".EXE"]


@pytest.mark.skipif(os.name != "nt", reason="PATHEXT es de Windows")
def test_an_absolute_windows_path_is_found_even_if_pathext_does_not_name_its_extension(tmp_path, monkeypatch):
    ruta = programa(tmp_path / "bin")
    monkeypatch.setenv("PATHEXT", ".CMD")
    assert programs.find(str(ruta)) == str(ruta)
