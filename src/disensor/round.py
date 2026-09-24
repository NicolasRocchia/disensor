"""The runner of a round: `disensor round`.

What this file does and what it deliberately does not do is the whole design.

It DOES the mechanical part, the part that has to happen the same way every
time: ask the policy whether a round is even required, build the package, pick
the best reviewer available, run it, capture the report, look at the tree
before and after, and emit a structured result. Done by an assistant following
instructions, each run is an interpretation, and a step that is skipped is not
visible afterwards.

It does NOT read the report. Judging what a reviewer said, checking each
finding against the code, deciding what to incorporate: that is judgement and
it belongs to the assistant. A runner that started summarising reports would be
putting a model in the middle of the only part of this system that has no model
in it.

And it does not pretend to prove more than it saw. What it observes is the exit
code, whether a fresh report appeared, and whether the tree changed. Which
model actually ran on the other side is declared, not proven: an entry can say
`openai` and invoke something else, and no amount of wrapping changes that.
`git status` does not see writes outside the tree, ignored files, `.git/`, the
index or the network. The result separates what was observed from what was
declared, and the declaration inherits that separation.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import __version__, gitctx, programs
from .brief import brief_text, hash_of
from .gate import GateFailure, classify_requirement, resolve_context
from .pack import canonical_pack_text, deliver, material_hash, pack_hash, read_material
from .reviewers import (
    CATALOG,
    ReviewerError,
    executable_fingerprint,
    has_consent,
    load_registry,
)

# v2: `pack_hash` es canonico. El v1 hasheaba el paquete tal como se entrego,
# con la ruta local del worktree, la rama y la ruta temporal del informe
# adentro, asi que nadie fuera de esa maquina podia recomputarlo (#73).
# El ordinal FIJA LA FORMA del texto canonico: quien recomputa el hash
# necesita esta forma y el brief que `prompt_hash` nombra, y nada mas. Si la
# forma cambia, esto sube a v3 junto con `ROUND_RESULT_ORDINAL` en
# template.py; el golden de tests/test_pack.py rompe si se cambia una sola.
RESULT_VERSION = "disensor/round-result/v2"

# Codigos de salida, uno por desenlace. Un llamador automatizado no deberia
# tener que leer prosa para saber que paso, y "no se requiere ronda" no puede
# confundirse con "no pude decidir": el primero sigue al PR, el segundo para.
OK = 0
ERROR = 1
NOT_REQUIRED = 3
CHAIN_EXHAUSTED = 4
TREE_MODIFIED = 5
UNDECIDABLE = 6

STATUS_ARGS = [
    # `gitctx.run_git` antepone READ_ONLY: mirar el arbol no escribe el indice
    # ni consulta el monitor del sistema de archivos (#77).
    "status", "--porcelain=v1", "-z",
    "--untracked-files=all",
    # Sin esto un submodulo sucio pasa desapercibido, y la configuracion del
    # usuario puede cambiar el default. Se queda en `none` a proposito: `dirty`
    # perderia las escrituras dentro de un submodulo y no evitaria los filtros,
    # que el status del propio superproyecto tambien aplica.
    "--ignore-submodules=none",
]


class RoundError(Exception):
    """The round cannot run, and nothing was left half done."""


def tree_state(repo: Path) -> str:
    """The tree as git sees it right now, with flags that do not depend on config."""
    out = gitctx.run_git(STATUS_ARGS, repo)
    if out.returncode != 0:
        raise RoundError(f"git status failed: {out.stderr.strip()}")
    return out.stdout


def independence_of(entry: dict, generator_family: str, generator_model: str) -> str:
    """What this reviewer is, not what somebody would like it to be."""
    if entry["family"] != generator_family:
        return "cross_family"
    if entry.get("model") and entry["model"] != generator_model:
        return "same_family_distinct_model"
    return "same_model_fresh_context"


ORDER = {"cross_family": 0, "same_family_distinct_model": 1, "same_model_fresh_context": 2}


def _usable(entry: dict) -> bool:
    """Una entrada desactualizada no entra en la cadena: mentiria al declarar."""
    return stale_model_entry(entry) is None


def chain_for(
    registry: dict, generator_family: str, generator_model: str,
) -> list[tuple[dict, str]]:
    """The reviewers to try, best first.

    Independence first, hardening second. Exhausting the better entries before
    degrading is what keeps the degraded mode from becoming the default path:
    if a cheaper reviewer could be picked while a cross-family one was sitting
    right there, the record would show a degradation that never had to happen.
    """
    entries = [
        (e, independence_of(e, generator_family, generator_model))
        for e in registry.get("reviewers", [])
        if _usable(e)
    ]
    # El endurecimiento se DERIVA del catalogo en el momento de correr, no se
    # lee del registro: ese archivo es un JSON editable a mano, y un `verified`
    # escrito ahi convertiria una afirmacion sobre una prueba hostil en un campo
    # que cualquiera se pone. Solo lo conserva quien sigue coincidiendo con la
    # receta catalogada que lo gano.
    for entry, _ in entries:
        entry["hardening"] = effective_hardening(entry)
    return sorted(
        entries,
        key=lambda par: (ORDER[par[1]], 0 if par[0].get("hardening") == "verified" else 1),
    )


def stale_model_entry(entry: dict) -> str | None:
    """Si la receta fija el modelo en el argv y la entrada registrada no.

    Pasa con los registros anteriores al arreglo: declaran un modelo que nada
    pone en el comando, asi que el revisor corre el que tenga por defecto y la
    declaracion afirma otro. Degradar el endurecimiento no lo cubre, porque el
    valor falso viaja igual.
    """
    # Solo las que dicen venir del catalogo: un revisor propio puede llamarse
    # igual que una receta y no le debe nada a su forma.
    if entry.get("source") != "catalog":
        return None
    receta = CATALOG.get(entry.get("id"))
    if not receta or "{model}" not in list(receta.get("command", [])):
        return None
    if "{model}" in list(entry.get("command", [])):
        return None
    return (
        f"the registered entry {entry.get('id')!r} declares model "
        f"{entry.get('model')!r} but its command does not pass it, so the reviewer would run "
        "whatever default the account has while the declaration claims otherwise. Register it "
        f"again: disensor reviewer remove {entry.get('id')} && disensor reviewer add "
        f"{entry.get('id')} --model <the model your account runs>"
    )


def effective_hardening(entry: dict) -> str:
    """The hardening this entry has EARNED, not the one its file claims.

    A catalogued recipe was tested against a hostile repository; an entry whose
    command drifted from that recipe, or that never came from it, has not been
    tested no matter what the JSON says.
    """
    receta = CATALOG.get(entry.get("id"))
    if not receta or receta.get("hardening") != "verified":
        return "unverified"
    # Coincidir el argv no alcanza. La prueba hostil se corrio contra una
    # identidad concreta: ese comando, invocando a ese proveedor, con esa
    # familia. Una entrada armada por el asistente podia copiar el argv de la
    # receta, declarar otra familia cualquiera y quedar cross_family Y verified,
    # con lo cual pasaba el piso de nivel A sin haber venido nunca del catalogo.
    if entry.get("source") != "catalog":
        return "unverified"
    if entry.get("family") != receta.get("family"):
        return "unverified"
    if entry.get("stdin") != receta.get("stdin"):
        return "unverified"
    # Si la receta trae un modelo fijo, la entrada tiene que declarar ese. Cuando
    # no lo trae, el modelo lo elige quien registra y va al argv por `{model}`,
    # asi que lo declarado es lo que corre y no hay nada que comparar.
    if receta.get("model") is not None and entry.get("model") != receta.get("model"):
        return "unverified"
    if entry.get("egress") != receta.get("egress"):
        return "unverified"
    if list(entry.get("command", [])) != list(receta["command"]):
        return "unverified"
    # Y el binario tiene que estar atado. Sin hash guardado no hay con que
    # comparar, y el runner ejecutaria lo que diga `executable` sin chequear
    # nada: alcanzaba con editar el registro a mano dejando la identidad de la
    # receta intacta para que un programa cualquiera corriera declarado como el
    # adaptador probado.
    esperado = entry.get("executable_hash")
    ruta = entry.get("executable") or programs.find(entry["command"][0])
    # Una ruta relativa, como las que se registraban antes de #75, nombra lo que
    # haya en el directorio de trabajo de cada corrida: no ata ningun binario.
    if not esperado or not ruta or not programs.is_absolute(ruta):
        return "unverified"
    return "verified" if executable_fingerprint(ruta) == esperado else "unverified"


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def run_reviewer(entry: dict, package: str, report: Path, timeout: int) -> dict:
    """Run one reviewer. Returns what was observed, never an opinion about it."""
    # La ruta absoluta y no el nombre: en Windows un CLI instalado por npm es un
    # .CMD que subprocess no encuentra por nombre, y la corrida fallaria con un
    # error que parece "el revisor no anda" cuando en realidad nunca arranco.
    executable = entry.get("executable") or programs.find(entry["command"][0])
    if not executable:
        return {"id": entry["id"], "outcome": "not_found", "detail": "executable not on PATH"}
    # Las entradas registradas antes de #75 pueden guardar una ruta relativa al
    # directorio donde se corrio `reviewer add`. Correrla aca ejecutaria lo que
    # ese nombre encuentre desde el directorio de esta corrida.
    if not programs.is_absolute(executable):
        return {
            "id": entry["id"],
            "outcome": "not_runnable",
            "detail": (
                f"the registered executable {executable!r} is a relative path, so it would run "
                "whatever that name finds from the current directory. Remove the reviewer and "
                "add it again"
            ),
        }

    # El binario que corre tiene que ser el que el dueño aprobo. La entrada
    # guarda su hash justamente para eso, y no compararlo lo volvia decorativo:
    # un ejecutable actualizado o reemplazado despues del registro corria igual
    # y seguia saliendo declarado como `verified`, atando la prueba hostil a
    # unos bytes que ya no eran los que se ejecutaban.
    # Limite conocido: en Windows un CLI instalado por npm es un launcher .CMD
    # que llama al codigo real en otro lado, asi que este hash cubre el lanzador
    # y no lo que termina ejecutandose. Detecta que cambien el binario, no que
    # actualicen el paquete debajo. Es una atestacion mas, no una prueba, y por
    # eso `confinement.verified` sigue declarandose en false.
    esperado = entry.get("executable_hash")
    if esperado:
        actual = executable_fingerprint(executable)
        if actual != esperado:
            return {
                "id": entry["id"],
                "outcome": "executable_changed",
                "detail": (
                    "the executable is not the one that was approved. Re-register the reviewer "
                    "so its hardening and the consent to send material are decided again"
                ),
            }

    argv = [executable]
    for arg in entry["command"][1:]:
        if arg == "{report}":
            argv.append(str(report))
        elif arg == "{pack}":
            argv.append(package)
        elif arg == "{model}":
            argv.append(entry.get("model", ""))
        else:
            argv.append(arg)

    # BYTES UTF-8 y no texto: text=True codifica en la pagina local del sistema
    # y el revisor recibe algo que no puede decodificar. Ya paso: el CLI
    # contesto "input is not valid UTF-8" y la corrida parecia un fallo del
    # revisor.
    entrada = package.encode("utf-8") if entry.get("stdin") == "pack" else None
    try:
        out = subprocess.run(
            argv,
            cwd=str(Path(tempfile.gettempdir())),  # el cwd lo fija el runner
            input=entrada,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"id": entry["id"], "outcome": "timeout", "detail": f"no answer within {timeout}s"}
    except OSError as exc:
        return {"id": entry["id"], "outcome": "not_runnable", "detail": str(exc)}

    salida = (out.stdout or b"").decode("utf-8", "replace")
    error = (out.stderr or b"").decode("utf-8", "replace")
    if out.returncode != 0:
        return {
            "id": entry["id"],
            "outcome": "failed",
            "exit_code": out.returncode,
            "detail": (error or salida)[-400:].strip(),
        }

    if not report.exists() and salida.strip():
        # El revisor escribio por stdout: el informe es esa salida.
        report.write_bytes(salida.encode("utf-8"))

    # Exit 0 no alcanza: un adaptador puede salir bien sin escribir nada, y un
    # informe preexistente satisfaria "existe y no esta vacio" sin que el
    # revisor lo haya tocado. Por eso el destino no existia al empezar.
    if not report.exists():
        return {"id": entry["id"], "outcome": "no_report", "detail": "exit 0 without writing a report"}
    if report.is_symlink() or not report.is_file():
        return {"id": entry["id"], "outcome": "bad_report", "detail": "the report is not a regular file"}
    if report.stat().st_size == 0:
        return {"id": entry["id"], "outcome": "empty_report", "detail": "the report is empty"}
    return {"id": entry["id"], "outcome": "ok", "exit_code": 0}


def _inside(path: Path, repo: Path) -> bool:
    try:
        path.resolve().relative_to(repo.resolve())
        return True
    except ValueError:
        return False


def _report_destination(args, repo: Path) -> Path | None:
    """Where the report goes, never inside the repository under review.

    A file written into the reviewed tree dirties exactly what the round is
    measuring, and the default used to do it. Refusing an explicit in-repo path
    matters as much: the caller would get a result claiming the tree was
    untouched while their own flag was the thing touching it.

    Checked before anybody runs (#80). None is the default: a private directory
    that is created only when there is a report to put in it.
    """
    if not args.report:
        return None
    # El informe es un archivo, y la salida estandar ya lleva el resultado:
    # `-` terminaba en un archivo llamado asi en el directorio de trabajo.
    if args.report == "-":
        raise RoundError(
            "--report - is not supported: the report is a file, and standard output carries "
            "the result. Point --report at a path outside the repository, or leave it out"
        )
    destino = Path(args.report).expanduser()
    # Un destino que ya existe no se pisa. La ronda escribe una sola vez y lo
    # que hubiera ahi es de otro: perderlo en silencio para dejar un informe es
    # exactamente lo que una herramienta que promete no tocar nada no puede
    # hacer. `lexists` y no `exists`: un enlace roto tambien es de otro.
    if os.path.lexists(destino):
        raise RoundError(
            f"--report {destino} already exists. The round does not overwrite: move it, "
            "delete it, or point somewhere else"
        )
    if _inside(destino, repo):
        raise RoundError(
            f"--report {destino} is inside the repository under review. The report has to "
            "live outside it: written in, it dirties the very tree the round measures"
        )
    # Los directorios que falten se crean al escribir; pero si el ancestro mas
    # cercano que existe es un archivo, el informe no va a tener donde ir, y eso
    # se sabe antes de pagar la corrida.
    ancestro = destino.parent
    while not os.path.lexists(ancestro) and ancestro != ancestro.parent:
        ancestro = ancestro.parent
    if not ancestro.is_dir():
        raise RoundError(
            f"--report {destino}: {ancestro} is not a directory, so the report would have "
            "nowhere to go"
        )
    return destino


def _result_destination(args, repo: Path) -> Path | None:
    """Where the result goes: a file outside the repository, or standard output (None).

    `-` is standard output, the convention anyone tries and the one `--material -`
    already follows; it used to create a file literally named `-`. Checked before
    anybody runs, like the report (#80): a destination that cannot take the
    result used to fail after the reviewer had been paid for.
    """
    if not args.result or args.result == "-":
        return None
    destino = Path(args.result).expanduser()
    if _inside(destino, repo):
        raise RoundError(
            f"--result {args.result} is inside the repository under review: writing it there "
            "dirties the tree the round measures. Use a path outside, or standard output"
        )
    if destino.is_dir():
        raise RoundError(f"--result {destino} is a directory. Name the file the result goes to")
    if not destino.parent.is_dir():
        raise RoundError(
            f"--result {destino}: the directory {destino.parent} does not exist, and the result "
            "would be lost after the round"
        )
    return destino


def _place_report(report: Path, pedido: Path | None, repo: Path, gate: str) -> Path:
    """Copy the report out of the round's private directory.

    An explicit destination was checked before the reviewer ran; it is checked
    again here and created exclusively, because a round takes minutes and
    whatever appeared there meanwhile is somebody else's. When the copy cannot
    be made, the error names the report where the reviewer left it, and the
    caller keeps that directory: the run was already paid for, and losing its
    report with the temporary directory was the other half of #80. A second
    copy as a rescue could fail as well, and then it took the only one with it.
    """
    try:
        datos = report.read_bytes()
        if pedido is None:
            # Un destino por corrida y no una ruta fija: dos rondas simultaneas
            # escribian sobre el mismo archivo y una podia terminar hasheando el
            # informe de la otra.
            destino = Path(tempfile.mkdtemp(prefix="disensor-report-")) / f"report-{gate}.md"
            destino.write_bytes(datos)
            return destino
    except OSError as exc:
        raise RoundError(
            f"the report could not be copied out of the round ({exc.strerror or exc}). "
            f"{_paid_for(report)}"
        ) from exc
    if _inside(pedido, repo):
        motivo = "it resolves inside the repository under review now"
    else:
        motivo = _write_new(pedido, datos)
        if motivo is None:
            return pedido
    raise RoundError(f"--report {pedido}: {motivo}. {_paid_for(report)}")


def _write_new(path: Path, datos: bytes) -> str | None:
    """Create `path` with `datos`, never over something that exists. None if it worked."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return f"its directory could not be created ({exc.strerror or exc})"
    creado = False
    try:
        with open(path, "xb") as f:
            creado = True
            f.write(datos)
    except FileExistsError:
        return "it appeared during the round, and it is not overwritten"
    except OSError as exc:
        # Lo creo el runner y quedo a medias: no se deja un informe cortado.
        if creado:
            try:
                path.unlink()
            except OSError:
                pass
        return f"it could not be written ({exc.strerror or exc})"
    return None


def main_round(args) -> int:
    # La raiz del worktree, no lo que vino por --repository. Un subdirectorio
    # deja pasar un --result que cae en el repo pero fuera de ese subdirectorio:
    # el archivo se crea despues del ultimo git status y el resultado sale
    # diciendo tree_unchanged sobre un arbol que el propio runner acaba de
    # ensuciar. Todo lo que contiene o mide el arbol se pregunta desde la raiz.
    pedido = Path(args.repository or Path.cwd())
    try:
        repo = gitctx.repo_root(pedido)
    except gitctx.GitError:
        repo = pedido
    try:
        return _round(args, repo)
    except (RoundError, ReviewerError) as exc:
        estado(f"round: {exc}")
        return ERROR
    except gitctx.GitError as exc:
        # Correr esto fuera de un repo, o con un rango que git no resuelve, es
        # un error de uso corriente y merece una linea, no un traceback.
        estado(f"round: git could not answer: {exc}")
        return ERROR
    except GateFailure as exc:
        # No poder decidir no es lo mismo que no hacer falta: contestar "no se
        # requiere ronda" aca seria el bypass mas barato del sistema.
        estado(f"round: could not decide whether a round is required: {exc}")
        return UNDECIDABLE


def _round(args, repo: Path) -> int:
    # Un documento de material no entra al paquete de una compuerta diff, asi
    # que hashearlo pondria en el resultado, y de ahi en la declaracion, un
    # `material_hash` de algo que el revisor nunca vio.
    if args.gate == "diff" and args.material:
        raise RoundError(
            "a diff gate has no material document: its material is the range. "
            "--material is for plan and architecture"
        )
    # --- Paso cero: la politica decide, no el agente -------------------------
    if args.gate == "diff":
        ctx = resolve_context(args.directory, args.config, args.base, args.head, repo)
        requirement = classify_requirement(ctx)
        if requirement.status == "not_required":
            estado(f"round: no review required ({requirement.reason})")
            return NOT_REQUIRED
        if requirement.status == "blocked":
            estado(f"round: {requirement.reason}")
            return UNDECIDABLE
        if args.check:
            estado(f"round: review required, gates {', '.join(requirement.accepted_gates)}")
            return OK
        # La compuerta pedida tiene que ser una de las que la politica admite
        # para estas rutas. Sin este chequeo se gastaba la corrida y el egreso
        # para producir un resultado que el gate iba a rechazar despues, con el
        # flujo ya dando exito.
        if args.gate not in requirement.accepted_gates:
            estado(
                f"round: the policy admits {', '.join(requirement.accepted_gates)} for these "
                f"paths, not {args.gate}. Running it would spend the reviewer on something the "
                "gate is going to reject."
            )
            return UNDECIDABLE
        base, head, merge_base = ctx.base_oid, ctx.head_oid, ctx.merge_base
        target_tip = ctx.base_oid
        repository = gitctx.canonical_repository(repo) or str(repo)
    else:
        # Un plan o una decision de arquitectura no vive en el rango: el
        # disparador ahi es de quien conoce el impacto, y `round` orquesta.
        if args.check:
            estado(f"round: a {args.gate} gate is triggered by judgement, not by scope")
            return OK
        if not args.material:
            raise RoundError(f"a {args.gate} gate needs --material")
        base = head = merge_base = target_tip = ""
        repository = gitctx.canonical_repository(repo) or str(repo)

    # --- Los destinos, antes de correr a nadie -------------------------------
    # Se miraban despues del bucle de revisores: un --report que ya existia o
    # un --result adentro del repositorio fallaban con la corrida pagada y el
    # material ya enviado, y el informe se borraba con el temporal (#80). Los
    # chequeos son los de siempre; lo que cambia es cuando corren.
    informe_pedido = _report_destination(args, repo)
    destino_resultado = _result_destination(args, repo)
    if (informe_pedido is not None and destino_resultado is not None
            and informe_pedido.resolve() == destino_resultado.resolve()):
        raise RoundError(
            "--report and --result name the same file: the result would overwrite the report "
            "whose hash it declares"
        )

    # --- Precondicion: arbol limpio ------------------------------------------
    # La ronda de diff revisa COMMITS YA HECHOS. Comparar estados antes y
    # despues parecia mas flexible y tenia falsos negativos propios: un archivo
    # ya modificado que el revisor vuelve a tocar sigue diciendo "M", y un
    # directorio sin trackear cambia por dentro sin cambiar su linea.
    antes = tree_state(repo)
    if antes.strip():
        raise RoundError(
            "the working tree is not clean. A diff round reviews commits that already exist: "
            "commit or stash first. The runner never stashes on its own, because deciding what "
            "to do with unfinished work is not its call"
        )

    # --- El material y el paquete canonico -----------------------------------
    # El material se lee UNA vez, aca: volver a leer `-` devolveria vacio del
    # segundo intento en adelante. El brief tambien, y de esa unica lectura
    # salen el paquete y `prompt_hash`. Y el paquete canonico se arma ANTES de
    # correr a nadie: cada intento recibe este texto mas su entrega, asi que el
    # hash que va al resultado es el de los bytes que el revisor vio, y no el
    # de un brief que pudo cambiar en disco mientras el revisor trabajaba.
    material_text = read_material(args.material) if args.material else None
    brief = brief_text(args.gate)
    canonical = canonical_pack_text(
        args.gate,
        repository=repository,
        base=merge_base or None,
        head=head or None,
        material_text=material_text,
        brief=brief,
    )
    hashes = {"prompt_hash": hash_of(brief), "pack_hash": pack_hash(canonical)}
    if material_text is not None:
        hashes["material_hash"] = material_hash(material_text)

    registry = load_registry()
    generator_family = args.generator_family
    generator_model = args.generator_model or ""
    chain = chain_for(registry, generator_family, generator_model)
    # Piso por nivel: el nivel que el protocolo reserva para lo que no se puede
    # deshacer no admite un revisor que el material bajo revision podria
    # secuestrar, ni uno de la propia familia del generador. Declarable no es lo
    # mismo que admisible, y filtrar aca evita gastar la corrida para que la
    # declaracion la rechace despues.
    # El nivel sale de la politica del DESTINO, la misma que el gate va a
    # aplicar, y no del archivo que hay en el working tree: leer el checkout
    # dejaria que la rama bajara su propio nivel para pasar su propio filtro.
    nivel = ctx.config.get("criticality_level", "B") if args.gate == "diff" else "B"
    if nivel == "A":
        chain = [
            (e, ind) for e, ind in chain
            if ind == "cross_family" and e.get("hardening") == "verified"
        ]
        if not chain:
            estado(
                "round: Level A demands a cross-family reviewer with verified hardening, and "
                "none of the registered ones qualifies. Declarable is not the same as "
                "admissible at the level reserved for what cannot be undone."
            )
            return CHAIN_EXHAUSTED
    if not chain:
        # Una entrada desactualizada se excluye de la cadena, y quedarse con
        # "no hay revisor" cuando hay uno registrado manda a buscar el problema
        # donde no esta.
        viejas = [
            stale_model_entry(e) for e in registry.get("reviewers", []) if stale_model_entry(e)
        ]
        for aviso in viejas:
            estado(f"round: {aviso}")
        if not viejas:
            estado(
                "round: no reviewer registered on this machine. Run `disensor reviewer suggest`; "
                "an assistant can register what it finds, and an entry outside the catalogue "
                "needs your approval."
            )
        return CHAIN_EXHAUSTED

    attempts = []
    usado = None
    # Directorio privado y unico, fuera del repositorio: una ruta compartida
    # deja una carrera entre el chequeo de que no existe y su creacion, y un
    # informe dentro del repositorio ensuciaria el arbol que se esta midiendo.
    # Se borra al terminar salvo en un caso: si el informe no se pudo copiar a
    # su destino, se queda ahi, porque es la unica copia de una corrida pagada.
    tmp = tempfile.mkdtemp(prefix="disensor-round-")
    conservar = False
    try:
        # Un archivo POR INTENTO. Con una ruta compartida, un revisor que
        # escribe y despues falla deja su informe ahi, y el siguiente que sale
        # con codigo 0 sin escribir nada lo hereda: el resultado nombraria a
        # este ultimo, con su familia y su independencia, y hashearia el texto
        # del anterior. Un informe de la misma familia podia terminar figurando
        # como una revision cross-family.
        report = None
        for numero, (entry, independence) in enumerate(chain, start=1):
            # El consentimiento es por repositorio, receta y bytes: haberlo dado
            # alguna vez en otro proyecto no autoriza mandar ESTE codigo afuera.
            # Sin esto, el material de un repositorio privado salia por una
            # autorizacion concedida en uno publico.
            if not has_consent(entry, repository):
                attempts.append({
                    "id": entry["id"],
                    "outcome": "no_consent",
                    "independence": independence,
                    "detail": (
                        f"sending the material of {repository} to {entry.get('provider') or 'a third party'} "
                        f"was not authorised. Run: disensor reviewer consent {entry['id']}"
                    ),
                })
                continue
            candidato = Path(tmp) / f"report-{numero}-{entry['id']}.md"
            # El revisor corre desde un directorio temporal y solo sabe donde
            # esta el codigo por este texto: la ruta local del checkout viaja
            # como entrega, junto con la ruta de su informe, fuera del hash.
            # El hash cubre el texto canonico, con la identidad del repositorio
            # y sin la rama: lo unico que otro puede recomputar.
            paquete = deliver(canonical, checkout=str(repo), report=str(candidato))
            intento = run_reviewer(entry, paquete, candidato, args.timeout)
            intento["independence"] = independence
            attempts.append(intento)
            if intento["outcome"] == "ok":
                usado = (entry, independence)
                report = candidato
                break

        # El informe se copia a su destino ANTES del ultimo chequeo del arbol.
        # Al reves, una ronda exitosa escribia despues de haber medido y el
        # resultado declaraba tree_unchanged sobre un arbol que el propio runner
        # acababa de ensuciar.
        destino = None
        if usado is not None:
            try:
                destino = _place_report(report, informe_pedido, repo, args.gate)
            except RoundError:
                conservar = True
                raise
    finally:
        if not conservar:
            shutil.rmtree(tmp, ignore_errors=True)

    # De aca en adelante la corrida ya se pago: si algo falla, el mensaje dice
    # donde quedo el informe, que es lo unico que no se vuelve a pedir gratis.
    try:
        despues = tree_state(repo)
    except (RoundError, gitctx.GitError) as exc:
        if destino is None:
            raise
        raise RoundError(f"{exc}. {_paid_for(destino)}") from exc
    if despues != antes:
        estado(
            "round: the working tree changed during the round. The declaration is not "
            "written: a reviewer that writes is not a reviewer that only reads, and what "
            "it touched has to be looked at before anything is declared."
        )
        if destino is not None:
            estado(f"round: {_paid_for(destino)}")
        return TREE_MODIFIED

    if usado is None:
        sin_permiso = [a for a in attempts if a["outcome"] == "no_consent"]
        if sin_permiso:
            estado(
                "round: no reviewer ran because sending this repository's material was not "
                "authorised. Authorise the one you want with `disensor reviewer consent "
                f"{sin_permiso[0]['id']}`, or register a local reviewer, whose material "
                "never leaves the machine."
            )
        else:
            estado("round: every registered reviewer failed. See the attempts in the result.")
        _emit(_result(
            args, repository, base, head, merge_base, target_tip,
            hashes, None, None, attempts,
        ), destino_resultado, repo)
        return CHAIN_EXHAUSTED

    entry, independence = usado
    resultado = _result(
        args, repository, base, head, merge_base, target_tip,
        hashes, entry, independence, attempts, report_path=destino,
        report_digest=file_hash(destino),
    )
    try:
        _emit(resultado, destino_resultado, repo)
    except RoundError as exc:
        raise RoundError(f"{exc}. {_paid_for(destino)}") from exc
    estado(
        f"round: reviewed by {entry['id']} ({entry['family']}, {independence}, "
        f"hardening {entry.get('hardening', 'unverified')}). Report at {destino}"
    )
    if independence != "cross_family":
        estado(
            "round: DEGRADED MODE. No reviewer from another family was available, so the errors "
            "the reviewer shares with the generator were not covered. The declaration has to say "
            "so: independence, fallback_reason and a reviewer_correlation residue item."
        )
    if entry.get("hardening") != "verified":
        estado(
            "round: the adapter's hardening is not verified. The material under review may have "
            "addressed the reviewer before the brief did: declare a reviewer_hardening_gap item."
        )
    return OK


def _result(
    args, repository, base, head, merge_base, target_tip, hashes,
    entry, independence, attempts, report_path=None, report_digest=None,
) -> dict:
    """What the runner saw, separated from what it was told.

    The declaration is built from this, so the separation has to survive the
    trip: everything under `observed` was measured by the runner, everything
    under `declared` came from the registry and nobody verified it.
    """
    # Los hashes vienen calculados de antes de correr al revisor, sobre el
    # texto que se le entrego: recomputables desde lo que el propio resultado
    # dice (gate, repositorio, anclas, la forma que `result_version` fija, el
    # brief que `prompt_hash` nombra y, para plan o arquitectura, el
    # material). La version de disensor es procedencia, no contrato: es el
    # literal del codigo que corrio, y en un checkout entre releases es el de
    # la ultima publicada, que puede no contener este codigo.
    return {
        "result_version": RESULT_VERSION,
        "disensor_version": __version__,
        "gate": args.gate,
        "repository": repository,
        "anchors": {
            "target_tip_oid": target_tip,
            "merge_base_oid": merge_base,
            "head_oid": head,
        },
        "observed": {
            "attempts": attempts,
            "report_path": str(report_path) if report_path else None,
            "report_hash": report_digest,
            "tree_unchanged": True,
            "tree_check": (
                "git status before and after the run, with untracked files and submodules. "
                "It does not see ignored files, .git/, the index, writes outside the tree, "
                "or the network: it is a snapshot, not a barrier."
            ),
        },
        "declared": {
            # El generador va aca y no en `observed` por el mismo motivo que el
            # revisor: el runner no puede probar que modelo produjo el material,
            # solo transcribir lo que le dijeron. Y tiene que viajar: la
            # declaracion contrasta familia y modelo del generador contra los del
            # revisor (R4), asi que un dato inventado ahi le miente a la regla.
            "generator": {
                "family": args.generator_family,
                "model": getattr(args, "generator_model", None),
            },
            "reviewer_id": entry["id"] if entry else None,
            "family": entry["family"] if entry else None,
            "model": entry.get("model") if entry else None,
            "independence": independence,
            "hardening": entry.get("hardening", "unverified") if entry else None,
            "note": (
                "The identity of the reviewer comes from the registry entry. The runner cannot "
                "prove which model answered."
            ),
        },
        "hashes": hashes,
    }


def estado(*args, **kwargs) -> None:
    """Diagnostics go to stderr, always.

    Without `--result`, or with `--result -`, the structured result is written
    to stdout, and the CLI help offers exactly that as a pipe. Any prose printed
    to the same channel lands after the JSON and `json.load` rejects it as extra
    data: the machine-readable path advertised in the help would not parse.
    """
    kwargs.setdefault("file", sys.stderr)
    print(*args, **kwargs)


def _paid_for(destino: Path) -> str:
    return f"The round already ran: its report is at {destino}"


def _emit(resultado: dict, destino: Path | None, repo: Path) -> None:
    """Write the result to its file, or to stdout when there is none (None)."""
    data = (json.dumps(resultado, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if destino is None:
        # Un pipe cerrado del otro lado no puede terminar en un traceback: el
        # error sube como los demas, y quien lo recibe nombra el informe.
        try:
            buffer = getattr(sys.stdout, "buffer", None)
            if buffer is None:
                sys.stdout.write(data.decode("utf-8"))
                sys.stdout.flush()
            else:
                buffer.write(data)
                buffer.flush()
        except OSError as exc:
            raise RoundError(
                f"the result could not be written to standard output ({exc.strerror or exc})"
            ) from exc
        return
    # Se vuelve a mirar al escribir: el resultado va despues del ultimo git
    # status, y un destino que ahora resolviera adentro ensuciaria el arbol que
    # el propio resultado declara intacto.
    if _inside(destino, repo):
        raise RoundError(
            f"--result {destino} is inside the repository under review: writing it there "
            "dirties the tree the round just measured. Use a path outside, or standard output"
        )
    # Un temporal al lado y un reemplazo, nunca una escritura sobre lo que haya:
    # si durante la ronda el destino paso a ser un enlace, por ejemplo al
    # informe, se reemplaza el enlace y no se trunca lo que apunta. Y un
    # resultado a medias no queda nunca con el nombre del destino.
    temporal = None
    try:
        fd, temporal = tempfile.mkstemp(prefix=".disensor-result-", dir=destino.parent)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(temporal, destino)
    except OSError as exc:
        if temporal is not None:
            try:
                os.unlink(temporal)
            except OSError:
                pass
        raise RoundError(f"--result {destino} could not be written ({exc.strerror or exc})") from exc
