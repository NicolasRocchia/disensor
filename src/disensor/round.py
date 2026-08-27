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

from . import gitctx
from .brief import brief_hash
from .gate import GateFailure, classify_requirement, resolve_context
from .pack import pack_hash, pack_text
from .reviewers import (
    CATALOG,
    ReviewerError,
    executable_fingerprint,
    has_consent,
    load_registry,
)

RESULT_VERSION = "disensor/round-result/v1"

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
    "status", "--porcelain=v1", "-z",
    "--untracked-files=all",
    # Sin esto un submodulo sucio pasa desapercibido, y la configuracion del
    # usuario puede cambiar el default.
    "--ignore-submodules=none",
]


class RoundError(Exception):
    """The round cannot run, and nothing was left half done."""


def tree_state(repo: Path) -> str:
    """The tree as git sees it right now, with flags that do not depend on config."""
    out = subprocess.run(
        ["git", *STATUS_ARGS], cwd=repo, capture_output=True, text=True, check=False,
    )
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
    ruta = entry.get("executable") or shutil.which(entry["command"][0])
    if not esperado or not ruta:
        return "unverified"
    return "verified" if executable_fingerprint(ruta) == esperado else "unverified"


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def run_reviewer(entry: dict, package: str, report: Path, timeout: int) -> dict:
    """Run one reviewer. Returns what was observed, never an opinion about it."""
    # La ruta absoluta y no el nombre: en Windows un CLI instalado por npm es un
    # .CMD que subprocess no encuentra por nombre, y la corrida fallaria con un
    # error que parece "el revisor no anda" cuando en realidad nunca arranco.
    executable = entry.get("executable") or shutil.which(entry["command"][0])
    if not executable:
        return {"id": entry["id"], "outcome": "not_found", "detail": "executable not on PATH"}

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


def _report_destination(args, repo: Path) -> Path:
    """Where the report goes, never inside the repository under review.

    A file written into the reviewed tree dirties exactly what the round is
    measuring, and the default used to do it. Refusing an explicit in-repo path
    matters as much: the caller would get a result claiming the tree was
    untouched while their own flag was the thing touching it.
    """
    if args.report:
        destino = Path(args.report).expanduser()
        if _inside(destino, repo):
            raise RoundError(
                f"--report {destino} is inside the repository under review. The report has to "
                "live outside it: written in, it dirties the very tree the round measures"
            )
        return destino
    # Un destino por corrida y no una ruta fija: dos rondas simultaneas escribian
    # sobre el mismo archivo y una podia terminar hasheando el informe de la otra.
    return Path(tempfile.mkdtemp(prefix="disensor-report-")) / f"report-{args.gate}.md"


def main_round(args) -> int:
    repo = Path(args.repository or Path.cwd())
    try:
        return _round(args, repo)
    except (RoundError, ReviewerError) as exc:
        print(f"round: {exc}")
        return ERROR
    except GateFailure as exc:
        # No poder decidir no es lo mismo que no hacer falta: contestar "no se
        # requiere ronda" aca seria el bypass mas barato del sistema.
        print(f"round: could not decide whether a round is required: {exc}")
        return UNDECIDABLE


def _round(args, repo: Path) -> int:
    # --- Paso cero: la politica decide, no el agente -------------------------
    if args.gate == "diff":
        ctx = resolve_context(args.directory, args.config, args.base, args.head, repo)
        requirement = classify_requirement(ctx)
        if requirement.status == "not_required":
            print(f"round: no review required ({requirement.reason})")
            return NOT_REQUIRED
        if requirement.status == "blocked":
            print(f"round: {requirement.reason}")
            return UNDECIDABLE
        if args.check:
            print(f"round: review required, gates {', '.join(requirement.accepted_gates)}")
            return OK
        # La compuerta pedida tiene que ser una de las que la politica admite
        # para estas rutas. Sin este chequeo se gastaba la corrida y el egreso
        # para producir un resultado que el gate iba a rechazar despues, con el
        # flujo ya dando exito.
        if args.gate not in requirement.accepted_gates:
            print(
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
            print(f"round: a {args.gate} gate is triggered by judgement, not by scope")
            return OK
        if not args.material:
            raise RoundError(f"a {args.gate} gate needs --material")
        base = head = merge_base = target_tip = ""
        repository = gitctx.canonical_repository(repo) or str(repo)

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

    # --- El paquete y el destino del informe ---------------------------------
    material = None
    if args.material:
        material = args.material
    package = pack_text(
        args.gate,
        repository=str(repo),
        base=merge_base or None,
        head=head or None,
        material=material,
        branch=_branch(repo),
        report=None,
    )

    registry = load_registry()
    # Paquete de referencia para el resultado cuando ningun revisor contesta:
    # el de cada intento se arma adentro del bucle, con su propia ruta de
    # informe, asi que sin intento exitoso no hay uno del cual hablar.
    paquete = package
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
            print(
                "round: Level A demands a cross-family reviewer with verified hardening, and "
                "none of the registered ones qualifies. Declarable is not the same as "
                "admissible at the level reserved for what cannot be undone."
            )
            return CHAIN_EXHAUSTED
    if not chain:
        print(
            "round: no reviewer registered on this machine. Run `disensor reviewer suggest`; "
            "an assistant can register what it finds, and an entry outside the catalogue needs "
            "your approval."
        )
        return CHAIN_EXHAUSTED

    attempts = []
    usado = None
    # Directorio privado y unico, fuera del repositorio: una ruta compartida
    # deja una carrera entre el chequeo de que no existe y su creacion, y un
    # informe dentro del repositorio ensuciaria el arbol que se esta midiendo.
    with tempfile.TemporaryDirectory(prefix="disensor-round-") as tmp:
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
            paquete = pack_text(
                args.gate,
                repository=str(repo),
                base=merge_base or None,
                head=head or None,
                material=material,
                branch=_branch(repo),
                report=str(candidato),
            )
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
        destino = _report_destination(args, repo)
        if usado is not None:
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(report.read_bytes())

        despues = tree_state(repo)
        if despues != antes:
            print(
                "round: the working tree changed during the round. The declaration is not "
                "written: a reviewer that writes is not a reviewer that only reads, and what "
                "it touched has to be looked at before anything is declared."
            )
            return TREE_MODIFIED

        if usado is None:
            sin_permiso = [a for a in attempts if a["outcome"] == "no_consent"]
            if sin_permiso:
                print(
                    "round: no reviewer ran because sending this repository's material was not "
                    "authorised. Authorise the one you want with `disensor reviewer consent "
                    f"{sin_permiso[0]['id']}`, or register a local reviewer, whose material "
                    "never leaves the machine."
                )
            else:
                print("round: every registered reviewer failed. See the attempts in the result.")
            _emit(args, _result(
                args, repository, base, head, merge_base, target_tip,
                paquete, None, None, attempts,
            ), repo)
            return CHAIN_EXHAUSTED

        entry, independence = usado
        resultado = _result(
            args, repository, base, head, merge_base, target_tip,
            paquete, entry, independence, attempts, report_path=destino,
            report_digest=file_hash(destino),
        )

    _emit(args, resultado, repo)
    print(
        f"round: reviewed by {entry['id']} ({entry['family']}, {independence}, "
        f"hardening {entry.get('hardening', 'unverified')}). Report at {destino}"
    )
    if independence != "cross_family":
        print(
            "round: DEGRADED MODE. No reviewer from another family was available, so the errors "
            "the reviewer shares with the generator were not covered. The declaration has to say "
            "so: independence, fallback_reason and a reviewer_correlation residue item."
        )
    if entry.get("hardening") != "verified":
        print(
            "round: the adapter's hardening is not verified. The material under review may have "
            "addressed the reviewer before the brief did: declare a reviewer_hardening_gap item."
        )
    return OK


def _branch(repo: Path) -> str:
    try:
        return gitctx._git(["rev-parse", "--abbrev-ref", "HEAD"], repo).strip()
    except Exception:
        return ""


def _result(
    args, repository, base, head, merge_base, target_tip, package,
    entry, independence, attempts, report_path=None, report_digest=None,
) -> dict:
    """What the runner saw, separated from what it was told.

    The declaration is built from this, so the separation has to survive the
    trip: everything under `observed` was measured by the runner, everything
    under `declared` came from the registry and nobody verified it.
    """
    return {
        "result_version": RESULT_VERSION,
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
        "hashes": {
            "prompt_hash": brief_hash(args.gate),
            "pack_hash": pack_hash(package),
        },
    }


def _emit(args, resultado: dict, repo: Path | None = None) -> None:
    data = (json.dumps(resultado, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if args.result and repo is not None and _inside(Path(args.result), repo):
        raise RoundError(
            f"--result {args.result} is inside the repository under review: writing it there "
            "dirties the tree the round just measured. Use a path outside, or a pipe"
        )
    if args.result:
        Path(args.result).write_bytes(data)
    else:
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is None:
            sys.stdout.write(data.decode("utf-8"))
        else:
            buffer.write(data)
            buffer.flush()
