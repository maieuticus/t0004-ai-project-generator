"""Bounded, read-only strategy B baseline plan; never accepted by apply."""
import hashlib
import os
from pathlib import Path
import unicodedata

from .config import MIGRATION_BASE, load_metadata
from .migrate import _git_status, _root
from .migration_plan import _migration_directories, _state
from .plan import PathSafetyError, _canonical_id, _location_fingerprint, _portable_path_collisions

PACKAGE = Path(__file__).parent / "templates" / "baseline"
# Source hashes identify Git blob bytes; result hashes identify the packaged bytes.
FILES = {
    "AGENTS.md": ("2a4ec2b90c3d2a265c56b3918be804ffe2bc7f6b50a94266fc303d19d807ce1c", "864777d1f262390cf25a55a1f7782c73eef2959b050fb8a51c207e2f09b1c9ab"),
    "config/project.yaml": ("1a54b9c1c58ceeba8786f730dac02640673bf15a785fe4296a0c0dfe780cbf26", "249715fb01a9a11588da162c7cc1a81740a82202bb762ce5626289968f6046b1"),
    "docs/DV_KONZEPT.md": ("039be51b52efefdd296ba982bc550b6c90d4fdd7bd573551d0cca315d4e3f82d", "d9da883cb98253d7ae4582a1f37c03c79cbfb8063a3cd6f771d90c020b324605"),
    "docs/PROJECT_HANDOFF.md": ("3192f80ea0c78bcd911952a25accc89c5b37173ad339fbbfc762434c0030c788", "88ed078203c2faef285f2b4f67252a2b08585aa77eb85a862997266a6a4897bd"),
    "docs/QUICKSTART.md": ("3a12c1bd77f33cb95520134de706896b46b56960faf09b5aa6c9940082cdc08d", "d251be78708cce4488d6e9ac6be891d54e3120fc08be9d84d8309d3e982a8566"),
    "docs/SDD_QUICKSTART.md": ("252a1150a37fc6473771f29a163cbb89c2c56d074613da81a661339dd29fdb66", "996b0119d4aaecac25a47f5bff0c0dd0fa6617d90cc574ee2cb11d724400ba5b"),
    "scripts/check.py": ("08be5d0fc5bddb6bbd9209c659a77456c785bfaa3ee24ebb06c20d390d6a2d4e", "08be5d0fc5bddb6bbd9209c659a77456c785bfaa3ee24ebb06c20d390d6a2d4e"),
    "scripts/projectcfg.py": ("f446580597e0c3e7c46ab20cd31e8bbc609316a5a8ae65696da8814244832d20", "f446580597e0c3e7c46ab20cd31e8bbc609316a5a8ae65696da8814244832d20"),
}


def _unicode_collisions(root: Path, names: list[str]) -> list[str]:
    collisions = []
    for name in names:
        parent = root
        for component in name.split("/"):
            try:
                with os.scandir(parent) as entries:
                    key = unicodedata.normalize("NFC", component).rstrip(" .").casefold()
                    if any(entry.name != component and
                           unicodedata.normalize("NFC", entry.name).rstrip(" .").casefold() == key
                           for entry in entries):
                        collisions.append(name)
                        break
            except FileNotFoundError:
                break
            parent = parent / component
    return collisions


def baseline_plan(target: str, version: str, agents_confirmation: str | None = None) -> dict:
    root = _root(target)
    names = sorted(FILES)
    payloads = {}
    for name, (_, expected) in FILES.items():
        data = (PACKAGE / name).read_bytes()
        if len(data) > 1024 * 1024 or hashlib.sha256(data).hexdigest() != expected:
            raise PathSafetyError("Basispaket ist beschädigt oder nicht verfügbar.")
        payloads[name] = data
    load_metadata(payloads["config/project.yaml"])
    dirs = _migration_directories(root, names + ["README.md", ".gitmodules"])
    collisions = sorted(set(_portable_path_collisions(root, names + ["README.md", ".gitmodules"])
                            + _unicode_collisions(root, names + ["README.md", ".gitmodules"])))
    git = _git_status(root, [], True)
    git_index = _state(root, ".git/index") if git["state"] == "available" else None
    git_head = _state(root, ".git/HEAD") if git["state"] == "available" else None
    readme = _state(root, "README.md", text_only=True)
    submodules = _state(root, ".gitmodules")
    states = {name: _state(root, name) for name in names}
    conflicts = []
    if git["state"] != "available" or git["tracked_changes"] or git["untracked"]:
        conflicts.append("Git-Status fehlt, ist unsicher oder enthält Änderungen.")
    if readme is None:
        conflicts.append("README.md fehlt.")
    if submodules is not None:
        conflicts.append("Submodule werden nicht unterstützt.")
    conflicts.extend(f"Pfad bereits vorhanden: {name}" for name, state in states.items() if state is not None)
    conflicts.extend(f"Portabler Pfadkonflikt: {name}" for name in collisions)
    if agents_confirmation != FILES["AGENTS.md"][1]:
        conflicts.append("AGENTS.md benötigt die Bestätigung des exakten Ergebnis-SHA-256.")
    if (_migration_directories(root, names + ["README.md", ".gitmodules"]) != dirs
            or _git_status(root, [], True) != git
            or (git["state"] == "available" and (_state(root, ".git/index") != git_index
                                                   or _state(root, ".git/HEAD") != git_head))
            or _state(root, "README.md", text_only=True) != readme
            or _state(root, ".gitmodules") != submodules
            or {name: _state(root, name) for name in names} != states
            or sorted(set(_portable_path_collisions(root, names + ["README.md", ".gitmodules"])
                          + _unicode_collisions(root, names + ["README.md", ".gitmodules"]))) != collisions):
        raise PathSafetyError("Projektzustand wurde während der Planung verändert.")
    identity = {
        "kind": "strategy_b_baseline_plan", "plan_version": 1, "package_version": "1.0.0",
        "read_only": True, "executable": False, "generator_version": version,
        "project_fingerprint": _location_fingerprint(root), "base_commit": MIGRATION_BASE,
        "git": git, "git_index": git_index, "git_head": git_head, "readme": readme, "directories": dirs,
        "agents_confirmation_sha256": FILES["AGENTS.md"][1] if agents_confirmation == FILES["AGENTS.md"][1] else None,
        "agents_preview": payloads["AGENTS.md"].decode("utf-8"),
        "operations": [{"path": n, "action": "create", "source_sha256": FILES[n][0],
                        "after_sha256": FILES[n][1], "before": states[n]} for n in names],
        "conflicts": conflicts,
        "warnings": ["Nur lesend; kein Apply oder Restore für Strategie B verfügbar.",
                     "Unabhängiges geprüftes Komplettbackup vor einem späteren Apply erforderlich.",
                     "Git-Status erfasst keine ignorierten Dateien; Zielpfade werden gesondert geprüft.",
                     "Gitlinks ohne .gitmodules und Dateien außerhalb der Paketpfade werden nicht vollständig geprüft.",
                     "Keine vollständige Template- oder Modulkompatibilität nachgewiesen."],
    }
    return {**identity, "plan_id": _canonical_id(identity)}
