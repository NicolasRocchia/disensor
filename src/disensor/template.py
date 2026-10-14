"""Scaffolding of a new artifact: `disensor new`.

Generates a template prefilled with what git already knows (repository,
commits, timestamp) and markers that do not pass validation until filled in.
A template that validates while empty would be cosmetic compliance from
the factory.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import sys
import uuid

from . import gitctx
from pathlib import Path
from .reviewers import CATALOG
from .rules import CURRENT


def _git(args: list[str], cwd: Path) -> str:
    r = gitctx.run_git(args, cwd)
    return r.stdout.strip() if r.returncode == 0 else ""


def template(gate: str, level: str, profile: str, cwd: Path) -> dict:
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    remote = _git(["config", "--get", "remote.origin.url"], cwd) or "FILL_IN_repository"
    head = _git(["rev-parse", "HEAD"], cwd) or "FILL_IN"
    base = _git(["merge-base", "HEAD", "origin/main"], cwd) or _git(
        ["merge-base", "HEAD", "origin/master"], cwd
    )
    a: dict = {
        "schema": CURRENT,
        "profile": profile,
        "event": {
            "event_id": str(uuid.uuid4()),
            "created_at": now,
            "repository": remote,
            "head_commit": head,
            "gate": gate,
            "criticality_level": level,
            "abbreviated_path": {"used": False},
        },
        "actors": {
            # El modelo se pide, no se inventa: estaba escrito un valor concreto
            # que no es un modelo, y R4 contrasta familia y modelo del generador
            # contra los del revisor, asi que ahi un dato inventado le miente a
            # la regla. La familia queda con el caso mayoritario porque es un
            # enum y no admite marcador; el hueco de al lado obliga a mirarla.
            # Con `new --round` las dos vienen de lo que se declaro en la ronda.
            "generator": {"family": "anthropic", "model": "FILL_IN_generator_model"},
            "reviewers": [
                {
                    "reviewer_id": "r1",
                    "family": "openai",
                    "model": "FILL_IN_reviewer_model",
                    # La independencia se declara siempre: el valor que viene es
                    # el que el metodo espera, y si la ronda fue degradada hay
                    # que corregirlo Y agregar su item de residuo. Dejarlo como
                    # viene cuando no fue asi es declarar algo que no paso.
                    "independence": "cross_family",
                    "confinement": {
                        "mode": "read_only_by_instruction",
                        "verified": False,
                        "verification_method": "clean_git_status",
                    },
                }
            ],
            "human_arbiter": {"present": True},
        },
        "findings": [],
        "residue": {
            "declared_absence": True,
            "declaration": "FILL_IN: express declaration of absence, or replace this object with items",
        },
        "metrics": {
            "counts": {
                "total_findings": 0,
                "valid": {"incorporated": 0, "debt_recorded": 0, "owner_decision": 0},
                "false_positives": {"refuted_verifiable": 0, "refuted_interpretive": 0},
                "escalated_open": 0,
            }
        },
    }
    if base:
        a["event"]["base_commit"] = base
    return a


def main_new(args) -> int:
    directory = Path(args.directory)
    directory.mkdir(parents=True, exist_ok=True)
    if getattr(args, "round", None):
        try:
            crudo = sys.stdin.read() if args.round == "-" else Path(args.round).read_text(encoding="utf-8")
            a = from_round(json.loads(crudo), args.gate, args.level, args.profile, Path.cwd())
        except (RoundMismatch, OSError, json.JSONDecodeError) as exc:
            print(f"new: {exc}")
            return 1
    else:
        a = template(args.gate, args.level, args.profile, Path.cwd())
    path = directory / f"{a['event']['event_id']}.json"
    # Bytes y no modo texto: en Windows el modo texto escribe CRLF, y sin
    # .gitattributes la declaracion se versionaba asi (#82).
    path.write_bytes((json.dumps(a, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(f"Template created: {path}")
    print("Fill in the FILL_IN_ fields and the findings of the event; then: disensor validate", path)
    print("Note: the template does not validate until filled in. That is intentional.")
    return 0


class RoundMismatch(Exception):
    """The result does not describe what is in front of us right now."""


def from_round(resultado: dict, gate: str, level: str, profile: str, cwd: Path) -> dict:
    """Build the template from what the runner observed, anchored to that round.

    The template resolves HEAD and the merge base when it is created, and that
    is wrong the moment anything was incorporated: the reviewer looked at A, a
    finding got fixed, HEAD moved to B, and a declaration built afterwards would
    say B was reviewed. The gate would catch it later by staleness, but by then
    the record already claimed something that did not happen. The anchors come
    from the result, literally, and a moved HEAD is refused here.
    """
    version = resultado.get("result_version")
    if version != ROUND_RESULT_VERSION:
        if version == "disensor/round-result/v1":
            # Con nombre, porque es el caso que va a pasar: un resultado guardado
            # antes del cambio. Su pack_hash llevaba la ruta local del worktree,
            # la rama y la ruta temporal del informe, y no se puede convertir:
            # la ronda se corre de nuevo.
            raise RoundMismatch(
                "the result is a v1 round: its pack_hash covered the local path of the "
                "worktree, the branch name and the temporary path of the report, so nobody "
                "but that machine could recompute it. Run the round again with this disensor"
            )
        if version == "disensor/round-result/v2":
            # El preambulo del paquete cambio (#91): la regla contra
            # instrucciones en el material distingue destinatario. El
            # pack_hash de un resultado v2 es de una forma que este disensor
            # ya no arma, asi que no se convierte: la ronda se corre de nuevo.
            raise RoundMismatch(
                "the result is a v2 round: the preamble of the package changed after 0.11.0 "
                "(#91), so the pack_hash it records is not the one this disensor would build "
                "for the same event. Run the round again with this disensor"
            )
        if version == "disensor/round-result/v3":
            # El preambulo cambio otra vez (#88): dice como correr la suite sin
            # dejar nada nuevo adentro del checkout. Mismo criterio que v2: el
            # pack_hash de un resultado v3 es de una forma que este disensor ya
            # no arma, asi que no se convierte y la ronda se corre de nuevo.
            raise RoundMismatch(
                "the result is a v3 round: the confinement of the package changed after 0.12.1 "
                "(#88), so the pack_hash it records is not the one this disensor would build "
                "for the same event. Run the round again with this disensor"
            )
        raise RoundMismatch(
            f"the result declares {version!r} and this disensor reads {ROUND_RESULT_VERSION}"
        )
    anclas = resultado.get("anchors", {})
    observado = resultado.get("observed", {})
    declarado = resultado.get("declared", {})

    if declarado.get("reviewer_id") is None:
        raise RoundMismatch(
            "the result records no reviewer: that round never got an answer, and there is "
            "nothing to declare about it"
        )

    # La compuerta declarada tiene que ser la que se corrio. Sin esto, una ronda
    # de diff se podia declarar como plan: el artefacto decia `gate: plan` con
    # el revisor y el hash de una ronda que miro un rango de git, y servia donde
    # la politica acepta compuerta de plan sin que nadie hubiera visto un plan.
    if resultado.get("gate") and resultado["gate"] != gate:
        raise RoundMismatch(
            f"the round was a {resultado['gate']} gate and this declaration says {gate}. "
            "The artifact identifies the review that happened, and relabelling it would make "
            "it cover something nobody reviewed"
        )

    # Y el repositorio, porque forks y clones comparten OID todo el tiempo: sin
    # comparar la identidad, un resultado producido en otro repositorio pasaba
    # solo por coincidir el commit, y la declaracion copiaba la identidad ajena.
    esperado = resultado.get("repository")
    if esperado:
        actual = gitctx.canonical_repository(cwd)
        if actual and not _same_repository(esperado, actual):
            raise RoundMismatch(
                f"the round was run in {esperado} and this is {actual}. Commit ids are shared "
                "between forks and clones, so matching HEAD is not enough to say it is the "
                "same repository"
            )

    head_actual = _git(["rev-parse", "HEAD"], cwd)
    if anclas.get("head_oid") and head_actual and anclas["head_oid"] != head_actual:
        raise RoundMismatch(
            f"the round reviewed {anclas['head_oid'][:9]} and HEAD is now {head_actual[:9]}. "
            "Whatever moved it was not reviewed: run the round again over what is going to be "
            "merged. The rule is the freshness of the material, not the verdict of the report"
        )

    informe = observado.get("report_path")
    if informe and observado.get("report_hash"):
        ruta = Path(informe)
        if not ruta.exists():
            raise RoundMismatch(f"the report of the round is not at {ruta}")
        actual = "sha256:" + hashlib.sha256(ruta.read_bytes()).hexdigest()
        if actual != observado["report_hash"]:
            raise RoundMismatch(
                "the report changed since the round emitted its result. What is declared has to "
                "be what the reviewer wrote"
            )

    a = template(gate, level, profile, cwd)
    if resultado.get("repository"):
        a["event"]["repository"] = resultado["repository"]
    if anclas.get("head_oid"):
        a["event"]["head_commit"] = anclas["head_oid"]
    if anclas.get("merge_base_oid"):
        a["event"]["base_commit"] = anclas["merge_base_oid"]
    elif "base_commit" in a["event"]:
        del a["event"]["base_commit"]

    # El generador que la ronda declaro, si lo trae: la plantilla dejo de
    # inventarlo, asi que sin este dato el hueco queda a la vista en vez de
    # llenarse solo con una familia y un modelo que nadie dijo.
    generador = declarado.get("generator") or {}
    if generador.get("family"):
        a["actors"]["generator"]["family"] = generador["family"]
    if generador.get("model"):
        a["actors"]["generator"]["model"] = generador["model"]

    revisor = a["actors"]["reviewers"][0]
    revisor["reviewer_id"] = "r1"
    revisor["family"] = declarado["family"]
    revisor["model"] = declarado.get("model") or "FILL_IN_reviewer_model"
    revisor["independence"] = declarado["independence"]
    # UN solo endurecimiento efectivo, para el revisor y para su item de
    # residuo: consultado dos veces, uno podia decir `verified` mientras el
    # otro no abria el item, o al reves. Y `verified` se conserva solo con la
    # evidencia de la politica vigente (#108): un resultado de un runner
    # anterior lo declara sin haber aislado nada, y baja.
    efectivo = _effective_hardening(resultado)
    if efectivo:
        revisor["hardening"] = efectivo
    hashes = resultado.get("hashes", {})
    if hashes.get("prompt_hash"):
        revisor["prompt_hash"] = hashes["prompt_hash"]

    # `verified` en false, y no por prudencia decorativa: el esquema define ese
    # campo como la verificacion de que el revisor no modifico el repositorio, y
    # lo que el runner hizo fue mirar `git status` antes y despues. Eso no ve
    # escrituras fuera del arbol, ni ignorados, ni .git/, ni la red. Prellenarlo
    # en true seria declarar mas de lo que se observo.
    revisor["confinement"] = {
        "mode": "read_only_by_instruction",
        "verified": False,
        "verification_method": "clean_git_status",
    }

    razon = _fallback_from(resultado)
    if declarado["independence"] != "cross_family":
        revisor["fallback_reason"] = razon

    items = []
    if declarado["independence"] != "cross_family":
        items.append({
            "id": f"r{len(items) + 1}",
            "class": "reviewer_correlation",
            "reviewer_ref": "r1",
            "requires_human_attention": True,
            "description": FILL_CORRELATION,
        })
    if efectivo == "unverified":
        degradado = declarado.get("hardening") == "verified"
        items.append({
            "id": f"r{len(items) + 1}",
            "class": "reviewer_hardening_gap",
            "reviewer_ref": "r1",
            "requires_human_attention": True,
            "description": FILL_HARDENING_EVIDENCE if degradado else FILL_HARDENING,
        })
    if items:
        a["residue"] = {"items": items}

    # Solo lo que un tercero puede contrastar: los hashes. `tree_unchanged` era
    # un literal (si el arbol cambia no hay resultado) y ya viaja como
    # `confinement.verified: false`; la cantidad de intentos no deja rastro en
    # ningun lado. El ordinal de la version va en numero, no en texto, para que
    # el perfil minimizado lo admita y un lector distinga un pack_hash v1, que
    # nadie puede recomputar, de uno canonico. Con el ordinal y `prompt_hash`
    # del revisor la declaracion lleva lo que hace falta para recomputar: la
    # forma del paquete y el brief. La version de disensor queda en el
    # resultado y no entra aca: es texto, el perfil minimizado exige valores
    # opacos, y es procedencia, no contrato (un checkout entre releases lleva
    # el literal de la ultima publicada); el campo `run` de v0.5 la llevara.
    # Los segundos del revisor (#98) son la excepcion a "solo hashes": no los
    # contrasta nadie, pero el runner los midio, y sin ellos el costo de la
    # ronda no tenia ningun numero en ningun lado.
    ronda = {
        "result_version": ROUND_RESULT_ORDINAL,
        "pack_hash": hashes.get("pack_hash"),
        "report_hash": observado.get("report_hash"),
    }
    if hashes.get("material_hash"):
        ronda["material_hash"] = hashes["material_hash"]
    # El tiempo de pared del revisor que escribio el informe, en segundos
    # enteros: lo unico del costo de la ronda que el runner vio. No es
    # `metrics.extra_time_sec`, que el esquema define de punta a punta
    # (verificacion, reescritura, refutacion) y que solo la persona puede
    # medir; es su piso, y va aca como numero para que el perfil minimizado lo
    # admita. Un resultado anterior a #98 no lo trae, y entonces no va.
    segundos = _reviewer_seconds(resultado)
    if segundos is not None:
        ronda["reviewer_seconds"] = segundos
    a["extensions"] = {"dev.disensor.round": ronda}
    return a


FILL_CORRELATION = (
    "FILL_IN: the reviewer did not come from another model family, so the errors it shares "
    "with the generator were not covered by this round. Say which ones you consider open."
)
FILL_HARDENING = (
    "FILL_IN: the adapter's hardening is not verified, so the material under review could "
    "have addressed the reviewer before the brief did. Say what you did about it."
)
FILL_HARDENING_EVIDENCE = (
    "FILL_IN: the round declared verified hardening, but its result carries no evidence of "
    "the isolation policy the recipe requires now, so it ran with an earlier adapter: the "
    "machine's own instruction sources (global AGENTS.md, user skills) may have reached the "
    "reviewer before the brief did. Say what you did about it."
)
ROUND_RESULT_VERSION = "disensor/round-result/v4"
ROUND_RESULT_ORDINAL = 4


def _effective_hardening(resultado: dict) -> str | None:
    """The hardening this round EARNED, from what the runner recorded.

    `verified` needs three things: the round declared it, the recipe behind
    the declared reviewer is a verified one, and, when that recipe runs under
    an isolation policy, the successful attempt recorded that very policy. A
    result from a runner that predates the policy declares `verified` without
    the evidence, and it is not converted: it is degraded, with its item.
    """
    declarado = resultado.get("declared", {})
    valor = declarado.get("hardening")
    if valor != "verified":
        return valor
    receta = CATALOG.get(declarado.get("reviewer_id") or "")
    if not receta or receta.get("hardening") != "verified":
        return "unverified"
    politica = receta.get("isolation")
    if not politica:
        return "verified"
    for intento in resultado.get("observed", {}).get("attempts", []):
        if intento.get("outcome") == "ok" and intento.get("id") == declarado.get("reviewer_id"):
            return "verified" if intento.get("isolation") == politica else "unverified"
    return "unverified"


def _reviewer_seconds(resultado: dict) -> int | None:
    """Seconds of the attempt that produced the report, if the runner timed it."""
    revisor = resultado.get("declared", {}).get("reviewer_id")
    for intento in resultado.get("observed", {}).get("attempts", []):
        if intento.get("outcome") == "ok" and intento.get("id") == revisor:
            segundos = intento.get("seconds")
            if isinstance(segundos, int) and not isinstance(segundos, bool) and segundos >= 0:
                return segundos
            return None
    return None


def _fallback_from(resultado: dict) -> dict:
    """Why the round settled for less, taken from the attempts when possible.

    Every failed attempt, in order, with its outcome and the start of its
    detail: the previous version kept the first failure only, so a context
    failure in second place vanished, and it mapped anything it did not know
    to `quota_exhausted`, which the runner never observes. The code is
    `reviewer_unavailable` for all of them: that is what the runner saw, a
    reviewer that did not answer; why it did not is in the detail.
    """
    intentos = resultado.get("observed", {}).get("attempts", [])
    fallidos = [i for i in intentos if i.get("outcome") != "ok"]
    if not fallidos:
        return {"code": "no_other_family_available"}
    partes = []
    for intento in fallidos:
        detalle = " ".join(str(intento.get("detail") or "").split())
        parte = f"{intento.get('id')}: {intento.get('outcome')}"
        if detalle:
            parte += f" ({detalle[:160]})"
        partes.append(parte)
    return {
        "code": "reviewer_unavailable",
        "detail": "the better reviewers were tried first and failed: " + "; ".join(partes),
    }


def _same_repository(uno: str, otro: str) -> bool:
    """Two spellings of the same identity, or two different repositories.

    Both sides go through the same normalisation: `git@host:owner/name.git` and
    `https://host/owner/name` are the same place. The HOST stays part of the
    identity, because a mirror on another service shares the commits and is not
    the same repository, which is precisely what this check separates.
    """
    return gitctx.normalize_repository(uno) == gitctx.normalize_repository(otro)
