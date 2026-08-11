"""Interfaz de linea de comandos: residuo {nuevo, validar, gate}."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .gate import main_gate
from .plantilla import main_nuevo
from .reglas import cargar_schema, validar_artefacto


def main_validar(args) -> int:
    schema = cargar_schema()
    fallo = False
    for ruta in args.archivos:
        with open(ruta, encoding="utf-8") as f:
            artefacto = json.load(f)
        errores = validar_artefacto(artefacto, schema)
        print(f"{ruta}: {'VALIDO' if not errores else 'INVALIDO'}")
        for msg in errores:
            print(f"  {msg}")
        fallo = fallo or bool(errores)
    return 1 if fallo else 0


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="residuo",
        description="Declaracion de residuo de revision adversarial (desacuerdo controlado).",
    )
    sub = p.add_subparsers(dest="comando", required=True)

    nuevo = sub.add_parser("nuevo", help="Crea una plantilla de artefacto para el evento en curso.")
    nuevo.add_argument("--directorio", default=".residuo")
    nuevo.add_argument("--compuerta", choices=["plan", "diff", "arquitectura"], default="diff")
    nuevo.add_argument("--nivel", choices=["A", "B", "C"], default="B")
    nuevo.add_argument("--perfil", choices=["completo", "minimizado"], default="completo")
    nuevo.set_defaults(func=main_nuevo)

    validar = sub.add_parser("validar", help="Valida artefactos contra el schema y las reglas R0 a R10.")
    validar.add_argument("archivos", nargs="+")
    validar.set_defaults(func=main_validar)

    gate = sub.add_parser("gate", help="Gate de CI: valida el PR completo y aplica politica G1 a G5.")
    gate.add_argument("--directorio", default=".residuo")
    gate.add_argument("--config", default="residuo.config.json")
    gate.add_argument("--base", default=None, help="SHA base del PR (por defecto, el evento de GitHub).")
    gate.add_argument("--cabeza", default=None, help="SHA cabeza del PR (por defecto, el evento de GitHub).")
    gate.add_argument("--sin-comentario", action="store_true", help="No publicar comentario en el PR.")
    gate.set_defaults(func=main_gate)
    return p


def main() -> None:
    args = construir_parser().parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
