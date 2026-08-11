"""Scaffolding de un artefacto nuevo: `disensor nuevo`.

Genera una plantilla prellenada con lo que git ya sabe (repositorio, commits,
timestamp) y marcadores que no pasan la validacion hasta completarse. Una
plantilla que valida vacia seria cumplimiento cosmetico de fabrica.
"""
from __future__ import annotations

import datetime
import json
import subprocess
import uuid
from pathlib import Path


def _git(args: list[str], cwd: Path) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd, check=False)
    return r.stdout.strip() if r.returncode == 0 else ""


def plantilla(compuerta: str, nivel: str, perfil: str, cwd: Path) -> dict:
    ahora = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    remoto = _git(["config", "--get", "remote.origin.url"], cwd) or "COMPLETAR_repositorio"
    cabeza = _git(["rev-parse", "HEAD"], cwd) or "COMPLETAR"
    base = _git(["merge-base", "HEAD", "origin/main"], cwd) or _git(
        ["merge-base", "HEAD", "origin/master"], cwd
    )
    a: dict = {
        "esquema": "residuo/v0.1",
        "perfil": perfil,
        "evento": {
            "id_evento": str(uuid.uuid4()),
            "creado_en": ahora,
            "repositorio": remoto,
            "commit_cabeza": cabeza,
            "compuerta": compuerta,
            "nivel_criticidad": nivel,
            "ruta_abreviada": {"usada": False},
        },
        "actores": {
            "generador": {"familia": "anthropic", "modelo": "claude-code"},
            "revisores": [
                {
                    "id_revisor": "r1",
                    "familia": "openai",
                    "modelo": "COMPLETAR_modelo_del_revisor",
                    "confinamiento": {
                        "modo": "solo_lectura_por_instruccion",
                        "verificado": False,
                        "metodo_verificacion": "git_status_limpio",
                    },
                }
            ],
            "arbitro_humano": {"presente": True},
        },
        "hallazgos": [],
        "residuo": {
            "ausencia_declarada": True,
            "declaracion": "COMPLETAR: declaracion expresa de ausencia, o reemplazar este objeto por items",
        },
        "metricas": {
            "conteos": {
                "total_hallazgos": 0,
                "validos": {"incorporado": 0, "deuda_registrada": 0, "decision_del_dueno": 0},
                "falsos_positivos": {"refutado_verificable": 0, "refutado_interpretativo": 0},
                "escalados_abiertos": 0,
            }
        },
    }
    if base:
        a["evento"]["commit_base"] = base
    return a


def main_nuevo(args) -> int:
    directorio = Path(args.directorio)
    directorio.mkdir(parents=True, exist_ok=True)
    a = plantilla(args.compuerta, args.nivel, args.perfil, Path.cwd())
    ruta = directorio / f"{a['evento']['id_evento']}.json"
    with ruta.open("w", encoding="utf-8") as f:
        json.dump(a, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Plantilla creada: {ruta}")
    print("Completar los campos COMPLETAR_ y los hallazgos del evento; despues: disensor validar", ruta)
    print("Nota: la plantilla no valida hasta completarse. Es intencional.")
    return 0
