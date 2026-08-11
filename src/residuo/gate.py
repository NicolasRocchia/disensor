"""Gate de CI: valida las declaraciones de residuo de un PR y aplica politica.

Chequeos del gate (sobre los R0 a R10 por artefacto de reglas.py):
  G1: al menos un artefacto valido en el rango del PR, salvo que la
      configuracion declare el gate como no requerido (tipico en Nivel C).
  G2: el nivel del artefacto coincide con el nivel declarado del repositorio
      (seccion 12.2: nivel de criticidad declarado en un archivo del repo).
  G3: Nivel A bloqueado mientras la gobernanza no este validada
      (seccion 3.1: el Nivel A no arranca hasta que la seccion 10 este validada).
  G4: politica de confinamiento por nivel (seccion 10: el revisor solo lee,
      y eso se garantiza con permisos y no con la consigna).
  G5: el commit revisado pertenece al rango del PR.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

from .reglas import cargar_schema, validar_artefacto
from .render import MARCADOR, render_comentario

CONFIG_DEFECTO = {
    "nivel_criticidad": "B",
    "nivel_A_habilitado": False,
    "gate": {
        "requerido": True,
        "confinamiento_aceptado_nivel_A": ["permisos", "sandbox"],
        "advertir_confinamiento_no_verificado": True,
    },
}


def cargar_config(ruta: Path) -> dict:
    if not ruta.exists():
        return dict(CONFIG_DEFECTO)
    with ruta.open(encoding="utf-8") as f:
        config = json.load(f)
    combinada = dict(CONFIG_DEFECTO)
    combinada.update({k: v for k, v in config.items() if k != "gate"})
    gate = dict(CONFIG_DEFECTO["gate"])
    gate.update(config.get("gate", {}))
    combinada["gate"] = gate
    return combinada


def rango_del_pr(base: str | None, cabeza: str | None) -> tuple[str | None, str | None]:
    """Base y cabeza del PR: flags primero, despues el evento de GitHub."""
    if base and cabeza:
        return base, cabeza
    ruta_evento = os.environ.get("GITHUB_EVENT_PATH")
    if ruta_evento and Path(ruta_evento).exists():
        with open(ruta_evento, encoding="utf-8") as f:
            evento = json.load(f)
        pr = evento.get("pull_request") or {}
        return (
            base or (pr.get("base") or {}).get("sha"),
            cabeza or (pr.get("head") or {}).get("sha"),
        )
    return base, cabeza


def commits_del_rango(base: str, cabeza: str, cwd: Path) -> list[str] | None:
    """Commits del rango base..cabeza, incluida la cabeza.

    Devuelve None si git no puede resolver el rango (clon superficial, shas
    desconocidos): eso es una advertencia. Una lista vacia es un resultado
    valido y significa que el rango no contiene commits: G5 debe evaluarse
    igual, porque un rango vacio no puede contener el commit revisado.
    """
    r = subprocess.run(
        ["git", "rev-list", f"{base}..{cabeza}"],
        capture_output=True, text=True, cwd=cwd, check=False,
    )
    if r.returncode != 0:
        return None
    return [linea.strip() for linea in r.stdout.splitlines() if linea.strip()]


def numero_de_pr() -> int | None:
    ruta_evento = os.environ.get("GITHUB_EVENT_PATH")
    if ruta_evento and Path(ruta_evento).exists():
        with open(ruta_evento, encoding="utf-8") as f:
            evento = json.load(f)
        pr = evento.get("pull_request") or {}
        return pr.get("number")
    return None


def publicar_comentario(cuerpo: str) -> str:
    """Crea o actualiza el comentario del gate en el PR. Devuelve un estado legible."""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    pr = numero_de_pr()
    if not (token and repo and pr):
        return "sin token, repositorio o numero de PR: comentario no publicado"
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    cabeceras = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "residuo-gate",
    }
    try:
        req = urllib.request.Request(
            f"{api}/repos/{repo}/issues/{pr}/comments?per_page=100", headers=cabeceras
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            comentarios = json.load(resp)
        existente = next((c for c in comentarios if MARCADOR in (c.get("body") or "")), None)
        datos = json.dumps({"body": cuerpo}).encode("utf-8")
        if existente:
            req = urllib.request.Request(
                f"{api}/repos/{repo}/issues/comments/{existente['id']}",
                data=datos, headers=cabeceras, method="PATCH",
            )
        else:
            req = urllib.request.Request(
                f"{api}/repos/{repo}/issues/{pr}/comments",
                data=datos, headers=cabeceras, method="POST",
            )
        with urllib.request.urlopen(req, timeout=30):
            pass
        return "comentario actualizado" if existente else "comentario publicado"
    except Exception as exc:  # el gate no debe caerse por la red
        return f"no se pudo publicar el comentario: {exc}"


def escribir_resumen(cuerpo: str) -> None:
    ruta = os.environ.get("GITHUB_STEP_SUMMARY")
    if ruta:
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(cuerpo + "\n")


def correr_gate(directorio: Path, config_ruta: Path, base: str | None,
                cabeza: str | None, repo_dir: Path, publicar: bool = True) -> int:
    config = cargar_config(config_ruta)
    schema = cargar_schema()
    gate_cfg = config["gate"]

    errores_gate: list[str] = []
    advertencias: list[str] = []
    errores_por_archivo: dict[str, list[str]] = {}
    validos: list[dict] = []

    base, cabeza = rango_del_pr(base, cabeza)
    commits = commits_del_rango(base, cabeza, repo_dir) if (base and cabeza) else None
    if commits is None and base and cabeza:
        advertencias.append(
            "no se pudo resolver el rango de commits (checkout con fetch-depth 0): G5 no se evalua"
        )

    archivos = sorted(p for p in directorio.glob("*.json")) if directorio.exists() else []
    for ruta in archivos:
        with ruta.open(encoding="utf-8") as f:
            try:
                artefacto = json.load(f)
            except json.JSONDecodeError as exc:
                errores_por_archivo[ruta.name] = [f"JSON invalido: {exc}"]
                continue
        errores = validar_artefacto(artefacto, schema)
        if errores:
            errores_por_archivo[ruta.name] = errores
            continue

        ev = artefacto["evento"]
        propios: list[str] = []

        # G2: nivel del artefacto contra nivel declarado del repositorio.
        if ev["nivel_criticidad"] != config["nivel_criticidad"]:
            propios.append(
                f"[G2] nivel del artefacto ({ev['nivel_criticidad']}) distinto del declarado "
                f"en el repositorio ({config['nivel_criticidad']})"
            )

        # G3: Nivel A bloqueado hasta validar la gobernanza (seccion 3.1).
        if ev["nivel_criticidad"] == "A" and not config.get("nivel_A_habilitado", False):
            propios.append(
                "[G3] Nivel A bloqueado: la gobernanza de datos (seccion 10) no esta validada "
                "en este repositorio (nivel_A_habilitado=false). Aplicar el protocolo en Nivel A "
                "en esta situacion no es cumplirlo a medias: es violarlo."
            )

        # G4: politica de confinamiento por nivel.
        for r in artefacto["actores"]["revisores"]:
            conf = r["confinamiento"]
            if ev["nivel_criticidad"] == "A" and conf["modo"] not in gate_cfg["confinamiento_aceptado_nivel_A"]:
                propios.append(
                    f"[G4] revisor {r['id_revisor']}: confinamiento '{conf['modo']}' no admitido en Nivel A "
                    f"(el revisor solo lee, y eso se garantiza con permisos y no con la consigna)"
                )
            if not conf["verificado"] and gate_cfg.get("advertir_confinamiento_no_verificado", True):
                advertencias.append(
                    f"{ruta.name}: confinamiento del revisor {r['id_revisor']} sin verificacion posterior"
                )

        # G5: el commit revisado pertenece al rango del PR.
        if commits is not None:
            cc = ev["commit_cabeza"]
            if not any(c.startswith(cc) or cc.startswith(c) for c in commits):
                propios.append(
                    f"[G5] commit revisado {cc} fuera del rango del PR ({base[:7]}..{cabeza[:7]})"
                )

        if propios:
            errores_por_archivo[ruta.name] = propios
        else:
            validos.append(artefacto)

    # G1: al menos un artefacto valido, salvo gate no requerido.
    if gate_cfg.get("requerido", True) and not validos:
        errores_gate.append(
            "[G1] ningun artefacto de residuo valido para este PR "
            f"(directorio '{directorio}'). La declaracion lista residuo concreto o dice "
            "explicitamente que no hubo ninguno; un campo vacio no es una declaracion."
        )

    cuerpo = render_comentario(validos, errores_por_archivo, errores_gate)
    if advertencias:
        cuerpo += "\n\nAdvertencias:\n" + "\n".join(f"- {a}" for a in advertencias)

    escribir_resumen(cuerpo)
    if publicar:
        estado = publicar_comentario(cuerpo)
        print(f"[gate] {estado}")

    fallo = bool(errores_gate or errores_por_archivo)
    print(cuerpo)
    print(f"\n[gate] {'FALLO' if fallo else 'OK'}: {len(validos)} artefacto(s) valido(s), "
          f"{len(errores_por_archivo)} con errores, {len(errores_gate)} error(es) globales")
    return 1 if fallo else 0


def main_gate(args) -> int:
    return correr_gate(
        directorio=Path(args.directorio),
        config_ruta=Path(args.config),
        base=args.base,
        cabeza=args.cabeza,
        repo_dir=Path.cwd(),
        publicar=not args.sin_comentario,
    )
