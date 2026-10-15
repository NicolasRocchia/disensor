"""Which reviewers this machine can run, and how: `disensor reviewer`.

Three decisions shape this file, and all three came from attacks the plan did
not survive on its first draft.

The commands live on the machine, never in the repository. A reviewer entry is
executable code: if a pull request could add one, opening that pull request
would run arbitrary commands on the machine of whoever reviews it, and
`shell=False` protects nothing, because the binary and its arguments were
already chosen by the attacker. The analogy with a Makefile cuts the other way:
nobody runs the Makefile of an untrusted pull request.

Moving the file out of the repository was not enough. A repository can still
inject instructions that talk to the ASSISTANT, and the assistant is the one
investigating what to register. That is the same attack with a confused deputy
in the middle. So the assistant discovers and proposes, and an entry that does
not come from the packaged catalogue needs the owner to approve it: registering
an executable that will later receive private code is a security decision, not
delegable judgement.

And the catalogue is help, not the mechanism. A closed list only serves whoever
has exactly the CLIs on it, which is an absurd premise for a product. What the
catalogue buys is that the known cases do not have to be improvised, with their
hardening already tested.
"""
from __future__ import annotations

import hashlib
import json
import re
import os
import subprocess
import tempfile
import textwrap
from pathlib import Path

from . import codex_home, programs

PLACEHOLDERS = {"{pack}", "{report}"}

REGISTRY_DIR = Path.home() / ".disensor"
REGISTRY = REGISTRY_DIR / "reviewers.json"

# El catalogo NO es la lista de revisores admitidos: es un atajo para los casos
# que ya probamos, para que nadie tenga que improvisar lo conocido. Cualquier
# CLI que acepte un texto y devuelva texto sirve de revisor, este o no aca, y se
# registra con `disensor reviewer add`. Lo unico que cambia es el endurecimiento:
# una receta del catalogo llega con su neutralizacion de instrucciones probada
# contra un repositorio hostil, y una entrada armada en el momento viaja como
# `unverified`, que no bloquea y se declara.
CATALOG: dict[str, dict] = {
    "codex": {
        "family": "openai",
        # Sin default: ninguna receta puede saber que modelos habilita la cuenta
        # de quien la instala. Quien registra declara cual, y `-m {model}` lo fija
        # en el argv para que lo declarado y lo ejecutado sean el mismo valor.
        "model": None,
        "command": [
            "codex", "exec",
            "-m", "{model}",
            "--dangerously-bypass-approvals-and-sandbox",
            # Sin persistir sesiones fuera del repositorio.
            "--ephemeral",
            # Y sin cargar lo que el material revisado le pueda decir antes
            # que la consigna: el ataque esta probado, un AGENTS.md hostil en
            # el repositorio revisado secuestra la revision entera si estos
            # tres no estan. Lo que la MAQUINA le dice lo cierra la politica
            # `isolation` de abajo (#108): estos tres flags solos dejaban
            # pasar el AGENTS.md global de CODEX_HOME y las skills de usuario.
            "--ignore-user-config",
            "--ignore-rules",
            "-c", "project_doc_max_bytes=0",
            # El runner corre al revisor desde un directorio propio, fuera del
            # repositorio, y ese directorio no es un repo git. La version
            # instalada hoy no se queja (se probo), pero el flag existe porque
            # alguna si lo hace: ponerlo no cuesta nada y evita que la unica
            # receta verificada del catalogo deje de arrancar por una version.
            "--skip-git-repo-check",
            # Las fuentes que el CLI carga solo, apagadas por nombre: plugins
            # y su catalogo remoto, apps (el servidor MCP de apps), hooks,
            # memorias y los roles de subagentes (`<home>/agents/`, que
            # sobreviven a --ignore-user-config). Un nombre que una version
            # no reconozca hace fallar al CLI en voz alta ("Unknown feature
            # flag"), no en silencio: medido con 0.153.4.
            "--disable", "plugins",
            "--disable", "apps",
            "--disable", "hooks",
            "--disable", "memories",
            "--disable", "multi_agent",
            "--disable", "remote_plugin",
            # Sin instalar las skills de sistema en el home aislado en el
            # primer arranque; las de usuario, repo y admin las deshabilita
            # el runner por ruta, con el inventario del disco (codex_home.py).
            "-c", "skills.bundled.enabled=false",
        ],
        "stdin": "pack",
        "hardening": "verified",
        # La politica del home aislado, versionada: que home, que entorno, que
        # cwd, que invariantes. Se persiste al registrar y se compara como el
        # argv; una entrada registrada bajo otra politica no gano este
        # endurecimiento.
        "isolation": codex_home.POLICY,
        "egress": "cloud",
        "provider": "OpenAI",
        "notes": (
            "Runs in an isolated CODEX_HOME (~/.disensor/reviewers/codex/home, policy "
            "codex_home/1) that the owner signs in once with `disensor reviewer login codex`; "
            "the runner never touches credentials. Verified means that the sources the CLI "
            "loads on its own are closed and checked on disk before every attempt, measured "
            "with codex-cli 0.153.4 and 0.162.1 on Windows: the repository's instruction files, the global "
            "AGENTS.md, user, repo, admin and bundled skills, plugins, apps, hooks, memories, "
            "agent roles, and the inherited environment (nothing CODEX_* or OPENAI_* reaches "
            "it). Verified holds only on the platform and CLI version pairs that test ran on; "
            "with any other, the round records the version and the declaration carries "
            "unverified hardening and its item. Not covered: managed configuration (found on "
            "disk, the attempt stops; macOS "
            "managed preferences and a workspace's cloud bundle cannot be seen beforehand), a "
            "same-user write between the check and the run, and legacy notify. The sandbox "
            "flags of codex do not start under some parent processes on Windows, so confinement "
            "is by instruction and the runner checks the tree afterwards."
        ),
    },
    "gemini": {
        "family": "google",
        "model": "gemini",
        "command": ["gemini", "--prompt", "{pack}"],
        "hardening": "unverified",
        "egress": "cloud",
        "provider": "Google",
        "notes": "Hardening not tested against a hostile repository yet.",
    },
    "ollama": {
        "family": "other",
        "model": None,
        "command": ["ollama", "run", "{model}"],
        "stdin": "pack",
        "hardening": "unverified",
        "egress": "local",
        "provider": "local",
        "notes": (
            "Runs locally: nothing leaves the machine, which makes it the answer for a "
            "private repository that cannot send code to a third party. Hardening not tested."
        ),
    },
    "claude": {
        "family": "anthropic",
        "model": "claude-code",
        # Sin --safe-mode el revisor arranca con lo que la maquina le agrega a
        # Claude Code: los plugins instalados y, desde la 2.1.273, los que se
        # sincronizan desde la cuenta de claude.ai, con sus skills, hooks y
        # servidores MCP, mas los CLAUDE.md del usuario. Medido el 2026-10-12:
        # una sesion `-p` sin el flag cargo 11 plugins, 72 skills y 35
        # servidores MCP antes de leer nada; con el, ninguno, y conserva las
        # herramientas nativas con las que lee el checkout. Es el agujero de
        # #108 visto del lado de Claude. No cubre al repositorio revisado: esa
        # prueba hostil no se corrio, y por eso sigue `unverified`.
        "command": ["claude", "-p", "{pack}", "--safe-mode"],
        "hardening": "unverified",
        "egress": "cloud",
        "provider": "Anthropic",
        "notes": (
            "Useful as a reviewer when the generator is NOT from this family; the runner "
            "discards any reviewer whose family matches the generator before spending a run. "
            "--safe-mode starts the session without what this machine adds to Claude Code: "
            "installed and synced plugins, hooks, MCP servers, skills and CLAUDE.md. Not "
            "tested against a hostile repository yet, so the hardening stays unverified."
        ),
    },
}


class ReviewerError(Exception):
    """The entry cannot be registered as it stands."""


def validate_command(command) -> list[str]:
    """Structural checks over the argv, before anything is written.

    None of this proves an executable is safe. What it does is refuse the
    shapes that are wrong on their face: a shell string, a placeholder glued to
    other text, an argument that smuggles a second command.
    """
    errors: list[str] = []
    if not isinstance(command, list) or not command:
        return ["command has to be a non-empty list of arguments (argv), never a shell string"]
    for arg in command:
        if not isinstance(arg, str):
            errors.append(f"every argument has to be a string, found {type(arg).__name__}")
            continue
        marcas = [m for m in ("{", "}") if m in arg]
        if marcas and arg not in PLACEHOLDERS and not _is_known_placeholder(arg):
            errors.append(
                f"argument {arg!r}: a placeholder has to be the whole argument and one of "
                f"{', '.join(sorted(PLACEHOLDERS))}. Glued to other text it stops being an "
                "argument and becomes string building, which is where injection lives"
            )
    # Se cuenta CADA placeholder por separado. Mirar si hay algun elemento
    # repetido rechazaba comandos legitimos: repetir una bandera como -c es
    # una forma normal de argv, y esas integraciones no se podian registrar.
    for marca in PLACEHOLDERS:
        if command.count(marca) > 1:
            errors.append(
                f"the placeholder {marca} appears {command.count(marca)} times: the runner "
                "would not know which one to fill"
            )
    return errors


ID_VALIDO = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def validate_id(reviewer_id: str) -> None:
    """The id is not free text: it names a file and keys a consent.

    The runner builds each attempt's private report path out of it, so an id
    like `x/../../target` resolves outside the temporary directory the attempt
    was given and the reviewer writes wherever that lands. The same string also
    goes into the registry, the consent key and the declaration.
    """
    if not ID_VALIDO.match(reviewer_id or ""):
        raise ReviewerError(
            f"invalid reviewer id {reviewer_id!r}: lowercase letters, digits, '.', '-' and '_', "
            "starting with a letter or digit. The id names a file inside the round's private "
            "directory, so anything that can traverse a path can escape it"
        )


def has_material_channel(command, stdin: str | None) -> bool:
    """Whether this recipe actually hands the package to the reviewer.

    A command with neither `{pack}` nor `stdin: pack` runs the reviewer with
    nothing to review, and a reviewer given nothing can still exit zero and
    write something. The round would then certify a review that never looked at
    the material.
    """
    return stdin == "pack" or "{pack}" in list(command or [])


def _is_known_placeholder(arg: str) -> bool:
    return arg in PLACEHOLDERS or arg == "{model}"


def resolve_executable(command: list[str]) -> str | None:
    """Absolute path of what would actually run, so the owner sees it.

    From the absolute entries of PATH, or an absolute path taken as is, and
    never from the working directory (#75): on Windows `shutil.which` looked
    there first and answered a relative path, which this global registry then
    kept and ran from wherever the next round started.
    """
    return programs.find(command[0])


def executable_fingerprint(path: str) -> str | None:
    """Hash of the executable, so a swap invalidates smoke, hardening and consent."""
    try:
        with open(path, "rb") as f:
            return "sha256:" + hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def load_registry() -> dict:
    if not REGISTRY.exists():
        return {"reviewers": []}
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReviewerError(f"{REGISTRY} is not valid JSON ({exc}). Fix it or remove it.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("reviewers"), list):
        raise ReviewerError(f"{REGISTRY} does not have the expected shape")
    return data


def save_registry(data: dict) -> None:
    """Atomic write, refusing a symlink: the target is a file we own."""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    if REGISTRY.is_symlink():
        raise ReviewerError(f"{REGISTRY} is a symlink: refusing to write through it")
    temporal = REGISTRY.with_suffix(".json.tmp")
    temporal.write_bytes((json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    os.replace(temporal, REGISTRY)


def build_entry(
    reviewer_id: str,
    family: str,
    model: str,
    command: list[str],
    *,
    from_catalog: bool,
    stdin: str | None = None,
    egress: str = "unknown",
    provider: str = "",
    executable: str | None = None,
) -> dict:
    """The entry as it will be stored, with hardening decided rather than declared.

    `verified` is not a value the caller may choose: it comes from a catalogued
    recipe whose neutralisation was tested. Anything the assistant assembled is
    `unverified`, and that travels all the way to the declaration.

    `executable` names the binary by hand, for a recipe under an isolation
    policy whose launcher this version cannot see through. It is taken as the
    owner typed it, absolute, and shown back before anything is written.
    """
    validate_id(reviewer_id)
    errors = validate_command(command)
    if errors:
        raise ReviewerError("; ".join(errors))
    if "{model}" in list(command) and not model:
        raise ReviewerError(
            "this recipe puts the model in the command, so it needs --model: without uno el "
            "argumento queda vacio y el revisor corre lo que tenga por defecto mientras la "
            "declaracion afirma otra cosa"
        )
    if executable is not None:
        if not programs.is_absolute(executable) or not os.path.isfile(executable):
            raise ReviewerError(
                f"--executable {executable!r} has to be the absolute path of an existing file"
            )
        ruta: str | None = executable
    else:
        ruta = resolve_executable(command)
    if ruta is None and os.path.dirname(command[0]) and not programs.is_absolute(command[0]):
        raise ReviewerError(
            f"{command[0]!r} is a relative path. The registry is global, so the program has to "
            "be on PATH or given as an absolute path: a relative one would name a different "
            "program depending on the directory each round starts from"
        )
    if ruta is None:
        raise ReviewerError(
            f"{command[0]!r} is not on PATH. An entry that cannot run is worse than no entry: "
            "the chain would fall through to the next reviewer for the wrong reason"
        )
    canal = stdin or (CATALOG.get(reviewer_id, {}).get("stdin") if from_catalog else None)
    if not has_material_channel(command, canal):
        raise ReviewerError(
            "this recipe never hands the package to the reviewer: it needs {pack} in the "
            "command, or --stdin pack. Without one of them the reviewer runs with nothing to "
            "review and can still return a report"
        )
    receta = CATALOG.get(reviewer_id) if from_catalog else None
    if receta and receta.get("isolation"):
        # Bajo la politica corre el binario nativo, nunca el lanzador: en
        # Windows el .CMD de npm expande %VAR% en el argv antes de que Codex
        # lo vea, y el hash de un lanzador no cubre lo que termina corriendo.
        # `command` sigue siendo la receta literal, para que la igualdad con
        # el catalogo y la clave del consentimiento no cambien de forma.
        try:
            ruta = codex_home.native_executable(ruta)
        except codex_home.NativeNotFound as exc:
            raise ReviewerError(
                f"{exc}. Name the native binary yourself: disensor reviewer add {reviewer_id} "
                "--executable <absolute path>"
            ) from exc
    # Un ejecutable nombrado a mano no hereda el endurecimiento de la receta:
    # la prueba hostil corrio contra el binario que el lanzador de la
    # instalacion resuelve, y un archivo cualquiera con la identidad de la
    # receta encima seria una revision de otro programa declarada como la del
    # adaptador probado (hallazgo de la ronda diff 1 de #108). La politica del
    # home aislado se aplica igual; lo que no viaja es `verified`.
    a_mano = executable is not None
    entry = {
        "id": reviewer_id,
        "family": family,
        "model": model,
        "command": list(command),
        "executable": ruta,
        "executable_hash": executable_fingerprint(ruta),
        "hardening": receta["hardening"] if receta and not a_mano else "unverified",
        "egress": receta["egress"] if receta else egress,
        "provider": receta.get("provider", "") if receta else provider,
        "source": "catalog" if receta else "assistant",
    }
    if stdin or (receta and receta.get("stdin")):
        entry["stdin"] = stdin or receta["stdin"]
    if receta and receta.get("isolation"):
        entry["isolation"] = receta["isolation"]
    if a_mano:
        entry["executable_source"] = "manual"
    return entry


def consent_key(entry: dict, repository: str) -> str:
    """What a consent covers: this repository, this recipe, these bytes.

    Anything else invalidates it. Consenting that the code of a public project
    leaves the machine is not consenting that a private one does, and a swapped
    executable is not the program that was approved.
    """
    # El argv se codifica ESTRUCTURALMENTE. Aplanarlo con espacios pierde los
    # limites entre argumentos: ["tool", "--label", "a b", "c"] y
    # ["tool", "--label", "a", "b c"] daban la misma clave, asi que un
    # consentimiento dado para una receta autorizaba otra distinta.
    # Y el modelo: desde que el argv lo lleva por `{model}`, el comando
    # registrado es el mismo para dos modelos distintos, asi que sin esto un
    # consentimiento dado para uno autorizaria mandar el codigo al otro.
    material = json.dumps(
        [repository, entry["id"], list(entry.get("command", [])),
         entry.get("model") or "", entry.get("executable_hash") or ""],
        ensure_ascii=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def has_consent(entry: dict, repository: str) -> bool:
    if entry.get("egress") == "local":
        return True  # no sale nada de la maquina: no hay nada que consentir
    return consent_key(entry, repository) in set(load_registry().get("consents", []))


def grant_consent(entry: dict, repository: str) -> None:
    data = load_registry()
    consents = set(data.get("consents", []))
    consents.add(consent_key(entry, repository))
    data["consents"] = sorted(consents)
    save_registry(data)


def describe(entry: dict) -> str:
    """What the owner reads before approving. Everything that will run, in full."""
    lineas = [
        f"  id:         {entry['id']}",
        f"  family:     {entry['family']} ({entry['model']})",
        f"  executable: {entry['executable']}",
        f"  command:    {' '.join(entry['command'])}",
        f"  hardening:  {entry['hardening']}",
    ]
    if entry.get("isolation"):
        lineas.append(
            f"  isolation:  {entry['isolation']}, home {codex_home.home_dir(entry['id'])} "
            f"(signed in by the owner with `disensor reviewer login {entry['id']}`)"
        )
    if entry.get("executable_source") == "manual":
        lineas.append(
            "  note:       the executable was named by hand, so the hardening stays unverified: "
            "the hostile test ran against the binary the installation resolves, not this file"
        )
    if entry.get("egress") == "cloud":
        lineas.append(
            f"  EGRESS:     the material under review LEAVES this machine towards "
            f"{entry.get('provider') or 'a third party'}"
        )
    elif entry.get("egress") == "local":
        lineas.append("  egress:     local, nothing leaves the machine")
    else:
        lineas.append("  EGRESS:     unknown, assume it may use the network")
    return "\n".join(lineas)


def main_reviewer(args) -> int:
    accion = args.reviewer_action
    try:
        if accion == "suggest":
            return _suggest()
        if accion == "list":
            return _list()
        if accion == "add":
            return _add(args)
        if accion == "remove":
            return _remove(args)
        if accion == "consent":
            return _consent(args)
        if accion == "login":
            return _login(args)
    except ReviewerError as exc:
        print(f"reviewer: {exc}")
        return 1
    return 1


def _suggest() -> int:
    """What this machine already has, from the recipes that travel with disensor.

    Detection is OFFLINE: presence on PATH and version, nothing invoked over the
    network. Consenting to a smoke run is not the same as consenting to send
    private code, and asking the second question before the first would be
    asking after the fact.
    """
    encontrados = 0
    for reviewer_id, receta in CATALOG.items():
        ruta = resolve_executable(receta["command"])
        estado = "found" if ruta else "not on PATH"
        print(f"{reviewer_id}: {estado}")
        if ruta:
            encontrados += 1
            print(f"  family {receta['family']}, hardening {receta['hardening']}, "
                  f"egress {receta['egress']}")
            # Las notas de la receta vivian solo en el catalogo (#112): que el
            # sandbox de codex no arranca bajo algunos procesos padre en
            # Windows, o que un endurecimiento no se probo, lo leia quien abria
            # este archivo, y no quien registraba el revisor y chocaba con eso
            # el primer dia.
            if receta.get("notes"):
                print(textwrap.fill(
                    f"notes: {receta['notes']}", width=78,
                    initial_indent="  ", subsequent_indent="    ",
                ))
            # Con el modelo cuando la receta lo fija en el argv: sin el, el
            # comando sugerido falla, y lo primero que hace quien llega es
            # copiar esta linea.
            sufijo = " --model <the model your account runs>" if "{model}" in receta["command"] else ""
            print(f"  disensor reviewer add {reviewer_id}{sufijo}")
            # El login del home aislado es del dueño, como el consentimiento:
            # quien copia estas lineas tiene que saber que hay un paso mas.
            if receta.get("isolation"):
                print(
                    f"  disensor reviewer login {reviewer_id}   # once, as the owner: its "
                    "isolated home signs in"
                )
    print(
        "\nThis catalogue is a shortcut, not the list of allowed reviewers: any CLI that "
        "takes a text and returns a text can be one. Register what you have with\n"
        "  disensor reviewer add <id> --family <family> --model <model> --command <argv...>\n"
        "It will be recorded with unverified hardening, which does not block and does travel "
        "to the declaration."
    )
    if not encontrados:
        print(
            "Nothing from the catalogue is installed here, which does not mean you cannot run "
            "a round: it means the reviewer you do have has to be registered by hand, once."
        )
    return 0


def _list() -> int:
    data = load_registry()
    if not data["reviewers"]:
        print("no reviewers registered. Run `disensor reviewer suggest`.")
        return 0
    for entry in data["reviewers"]:
        print(describe(entry))
        print()
    return 0


def _add(args) -> int:
    data = load_registry()
    if any(r["id"] == args.id for r in data["reviewers"]):
        print(f"reviewer: {args.id} is already registered (remove it first to replace it)")
        return 1

    receta = CATALOG.get(args.id)
    del_catalogo = receta is not None and not args.command
    if del_catalogo:
        entry = build_entry(
            args.id, receta["family"], args.model or receta["model"],
            receta["command"], from_catalog=True,
            executable=getattr(args, "executable", None),
        )
    else:
        if getattr(args, "executable", None):
            print(
                "reviewer: --executable is for a catalogued recipe whose launcher hides the "
                "binary; an entry given with --command names its program directly"
            )
            return 1
        if not (args.command and args.family and args.model):
            print(
                "reviewer: an entry outside the catalogue needs --family, --model and "
                "--command. Everything after --command is the argv, one argument per token"
            )
            return 1
        entry = build_entry(
            args.id, args.family, args.model, args.command,
            from_catalog=False, stdin=args.stdin, egress=args.egress,
        )

    print("About to register this reviewer:\n")
    print(describe(entry))
    print()

    # Una entrada que no viene del catalogo la propuso el asistente, y el
    # asistente lee el repositorio: un repositorio hostil puede inducirlo a
    # proponer un ejecutable cualquiera, que despues va a recibir codigo
    # privado. Validar la forma no prueba que un binario sea seguro, asi que
    # esa decision es del dueño y no se delega.
    if not del_catalogo and not args.yes:
        print(
            "This entry was not built from the packaged catalogue. Registering an executable "
            "that will later receive the material under review is a decision for the owner of "
            "the machine, not for the assistant that proposed it.\n"
            "Re-run with --yes if you approve exactly what is printed above."
        )
        return 2
    if entry.get("egress") != "local" and not args.yes:
        print(
            "The material under review would leave this machine. Re-run with --yes to confirm, "
            "or register a local reviewer instead.\n"
            "That confirmation covers THIS repository, this recipe and this executable: "
            "consenting that one project leaves the machine is not consenting for the next one."
        )
        return 2

    data["reviewers"].append(entry)
    save_registry(data)
    print(f"registered {args.id} in {REGISTRY}")
    if entry["hardening"] == "unverified":
        print(
            "hardening: unverified. It does not block, and every declaration produced with "
            "this reviewer will carry a reviewer_hardening_gap residue item: the material "
            "under review can address the reviewer before your brief does."
        )
    return 0


def _remove(args) -> int:
    data = load_registry()
    quedan = [r for r in data["reviewers"] if r["id"] != args.id]
    if len(quedan) == len(data["reviewers"]):
        print(f"reviewer: {args.id} is not registered")
        return 1
    data["reviewers"] = quedan
    save_registry(data)
    print(f"removed {args.id}")
    return 0


def _login(args) -> int:
    """Sign the reviewer's isolated home in, as the owner, without touching credentials.

    The CLI runs with the terminal inherited: the OAuth flow opens the
    browser, `--device-auth` prints a code, and `--with-api-key` reads the key
    from the owner's standard input, which this process never reads. Before
    and after, the home is checked against the policy's invariants, under the
    lock, so a login that left something behind is said out loud.
    """
    data = load_registry()
    entry = next((r for r in data["reviewers"] if r["id"] == args.id), None)
    if entry is None:
        print(f"reviewer: {args.id} is not registered")
        return 1
    if entry.get("isolation") != codex_home.POLICY:
        print(
            f"reviewer: {args.id} has no isolated home: only an entry under the policy "
            f"{codex_home.POLICY} has one, and this one carries {entry.get('isolation')!r}"
        )
        return 1
    ejecutable = entry.get("executable")
    if not ejecutable or not programs.is_absolute(ejecutable):
        print(f"reviewer: {args.id} has no absolute executable registered; register it again")
        return 1
    esperado = entry.get("executable_hash")
    if esperado and executable_fingerprint(ejecutable) != esperado:
        print(
            "reviewer: the executable is not the one that was approved. Re-register the "
            "reviewer so its hardening and the consent to send material are decided again"
        )
        return 1
    home = codex_home.home_dir(entry["id"])
    argv = [ejecutable, "login"]
    if getattr(args, "status", False):
        argv.append("status")
    else:
        if getattr(args, "device_auth", False):
            argv.append("--device-auth")
        if getattr(args, "with_api_key", False):
            argv.append("--with-api-key")
        argv += ["-c", "skills.bundled.enabled=false"]
    try:
        with codex_home.Lock(codex_home.lock_path(entry["id"])):
            codex_home.check_home(home)
            codex_home.check_system_config()
            env = codex_home.child_env(home)
            codex_home.work_dir(entry["id"]).mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix="login-", dir=codex_home.work_dir(entry["id"]),
            ) as cwd:
                codex_home.check_ancestors(Path(cwd))
                print(f"running: {' '.join(argv)}\n  with CODEX_HOME={home}\n")
                codigo = subprocess.run(argv, cwd=cwd, env=env, check=False).returncode
            codex_home.check_home(home, create=False)
    except codex_home.Refused as exc:
        print(f"reviewer: {exc.outcome}: {exc.detail}")
        return 1
    if codigo == 0 and not getattr(args, "status", False):
        print(
            f"\nthe isolated home {home} has its own credentials now. Nothing of your codex "
            "configuration lives there, and the runner checks that before every round."
        )
    return codigo


def _consent(args) -> int:
    """Authorise, or withdraw, sending THIS repository's material to a reviewer."""
    from . import gitctx

    data = load_registry()
    entry = next((r for r in data["reviewers"] if r["id"] == args.id), None)
    if entry is None:
        print(f"reviewer: {args.id} is not registered")
        return 1

    repositorio = gitctx.canonical_repository(Path.cwd()) or str(Path.cwd())
    clave = consent_key(entry, repositorio)
    consents = set(data.get("consents", []))

    if args.revoke:
        if clave not in consents:
            print(f"reviewer: there was no consent for {args.id} in {repositorio}")
            return 1
        consents.discard(clave)
        data["consents"] = sorted(consents)
        save_registry(data)
        print(f"withdrawn: {args.id} can no longer receive the material of {repositorio}")
        return 0

    if entry.get("egress") == "local":
        print(f"{args.id} runs locally: nothing leaves the machine, so there is nothing to authorise")
        return 0

    print(describe(entry))
    print(f"\n  repository: {repositorio}\n")
    consents.add(clave)
    data["consents"] = sorted(consents)
    save_registry(data)
    print(
        f"authorised: the material of {repositorio} may be sent to "
        f"{entry.get('provider') or 'this reviewer'}.\n"
        "This covers this repository, this recipe and these executable bytes. Another project, "
        "a changed command or a replaced binary needs its own authorisation."
    )
    return 0
