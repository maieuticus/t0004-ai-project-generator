"""Bounded inventory for migration decisions; never produces an apply plan."""

import os
from pathlib import Path
import shutil
import stat
import subprocess
import threading

from .config import ConfigurationError, load_metadata
from .plan import MAX_CONFIG_BYTES, PathSafetyError, SUPPORTED_TEMPLATE_RELEASES, _is_link

MAX_ENTRIES = 4000
MAX_DEPTH = 6
MAX_GIT_DEPTH = 16
MAX_METADATA_LINES = 256
MAX_METADATA_LINE_BYTES = 512
MAX_GIT_OUTPUT = 1024 * 1024
GIT_TIMEOUT = 10
EXCLUDED = {
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "vendor", "target",
    "build", "dist", "__pycache__", ".tox", ".mypy_cache", ".pytest_cache",
    ".next", ".gradle", ".idea", ".terraform",
}
LANGUAGES = {
    ".py": "Python", ".java": "Java", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript", ".go": "Go", ".rs": "Rust",
    ".cs": "C#", ".cpp": "C++", ".c": "C",
}
CONFIG_MARKERS = {
    "pyproject.toml": "pyproject.toml", "requirements.txt": "requirements.txt",
    "pom.xml": "pom.xml", "build.gradle": "build.gradle",
    "build.gradle.kts": "build.gradle.kts", "package.json": "package.json",
    "tsconfig.json": "tsconfig.json", "go.mod": "go.mod", "Cargo.toml": "Cargo.toml",
    "Dockerfile": "Dockerfile",
}
TECHNOLOGIES = {
    "pyproject.toml": "Python packaging", "requirements.txt": "Python dependencies",
    "pom.xml": "Maven", "build.gradle": "Gradle", "build.gradle.kts": "Gradle",
    "package.json": "Node.js", "tsconfig.json": "TypeScript configuration",
    "go.mod": "Go modules", "Cargo.toml": "Cargo", "Dockerfile": "Docker",
}


def _entry_stat(entry: os.DirEntry, directory: Path) -> os.stat_result:
    # Windows DirEntry.stat reports zero device/inode numbers; os.stat obtains the volume.
    if os.name == "nt":
        return os.stat(directory / entry.name, follow_symlinks=False)
    return entry.stat(follow_symlinks=False)


def _root(value: str) -> Path:
    try:
        requested = Path(value).expanduser()
        if ".." in requested.parts or str(requested).startswith(("//", "\\\\")):
            raise PathSafetyError("Quellpfad darf weder '..' noch einen Netzwerkpfad enthalten.")
        absolute = Path(os.path.abspath(requested))
        if any(_is_link(part) for part in (absolute, *absolute.parents)):
            raise PathSafetyError("Quellpfad darf keine Symlinks oder Junctions enthalten.")
        root = absolute.resolve(strict=True)
        if not root.is_dir() or root == Path(root.anchor):
            raise PathSafetyError("Quellprojekt muss ein vorhandenes Verzeichnis außerhalb des Dateisystemwurzelverzeichnisses sein.")
        return root
    except PathSafetyError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise PathSafetyError("Quellprojekt ist nicht sicher zugänglich.") from error


def _metadata(path: Path, device: int, parent_fd: int | None = None) -> tuple[str, dict[str, bool] | None]:
    """Return only a fixed classification, never values or diagnostics."""
    try:
        info = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False) if parent_fd is not None else path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_dev != device or info.st_size > MAX_CONFIG_BYTES:
            return "unreadable_or_unsupported", None
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        flags |= getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOATIME", 0)
        fd = os.open(path.name, flags, dir_fd=parent_fd) if parent_fd is not None else os.open(path, flags)
        with os.fdopen(fd, "rb") as file:
            opened = os.fstat(file.fileno())
            if (not stat.S_ISREG(opened.st_mode) or opened.st_dev != device
                    or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)):
                return "unreadable_or_unsupported", None
            content = file.read(MAX_CONFIG_BYTES + 1)
        lines = content.splitlines()
        if (len(content) > MAX_CONFIG_BYTES or len(lines) > MAX_METADATA_LINES
                or any(len(line) > MAX_METADATA_LINE_BYTES for line in lines)):
            return "unreadable_or_unsupported", None
        metadata = load_metadata(content)
        status = ("recognized_supported" if metadata["template_release"] in SUPPORTED_TEMPLATE_RELEASES
                  else "recognized_unverified_version")
        return status, {
            "generator_version_configured": metadata["generator_version"] is not None,
            "modules_configured": bool(metadata["has_modules"]),
            "sdd_configured": metadata["sdd_tool"] is not None,
        }
    except (ConfigurationError, RecursionError):
        return "not_recognized", None
    except (OSError, ValueError):
        return "unreadable_or_unsupported", None


def _safe_git_layout(git_dir: Path, device: int) -> bool:
    """Reject indirection, partial clones and config includes before invoking Git."""
    config = git_dir / "config"
    try:
        info = config.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_dev != device or info.st_size > 65536:
            return False
        flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOATIME", 0))
        fd = os.open(config, flags)
        with os.fdopen(fd, "rb") as file:
            opened = os.fstat(file.fileno())
            if ((opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)
                    or not stat.S_ISREG(opened.st_mode)):
                return False
            content = file.read(65537).lower()
        if len(content) > 65536 or any(
            word in content for word in (b"include", b"promisor", b"partialclone", b"worktreeconfig", b"filter")
        ):
            return False
        stack = [(git_dir, 0)]
        seen = 0
        while stack:
            directory, depth = stack.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    seen += 1
                    if seen > MAX_ENTRIES:
                        return False
                    info = _entry_stat(entry, directory)
                    reparse = bool(getattr(info, "st_file_attributes", 0)
                                   & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
                    if stat.S_ISLNK(info.st_mode) or reparse or info.st_dev != device:
                        return False
                    if entry.name in {"alternates", "http-alternates", "commondir", "gitdir", "config.worktree"}:
                        return False
                    if stat.S_ISDIR(info.st_mode):
                        if depth >= MAX_GIT_DEPTH or os.path.ismount(entry.path):
                            return False
                        stack.append((Path(entry.path), depth + 1))
                    elif not stat.S_ISREG(info.st_mode):
                        return False
        return True
    except OSError:
        return False


def _git_status(root: Path, exclusions: list[tuple[str, ...]], complete: bool) -> dict[str, object]:
    git_dir = root / ".git"
    try:
        if not os.path.lexists(git_dir):
            return {"state": "not_detected", "tracked_changes": None, "untracked": None}
        if not complete:
            return {"state": "unavailable", "tracked_changes": None, "untracked": None}
        index = git_dir / "index"
        if (_is_link(git_dir) or not git_dir.is_dir() or _is_link(index)
                or not index.is_file() or index.stat().st_size > 16 * 1024 * 1024):
            return {"state": "unavailable", "tracked_changes": None, "untracked": None}
        if not _safe_git_layout(git_dir, root.stat().st_dev):
            return {"state": "unavailable", "tracked_changes": None, "untracked": None}
    except OSError:
        return {"state": "unavailable", "tracked_changes": None, "untracked": None}
    git = shutil.which("git")
    if git is None:
        return {"state": "unavailable", "tracked_changes": None, "untracked": None}
    # Do not inherit Git configuration overrides or execute a configured fsmonitor.
    env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "PATHEXT", "TMP", "TEMP")
           if key in os.environ}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_OPTIONAL_LOCKS="0",
               GIT_TERMINAL_PROMPT="0", GIT_INDEX_FILE=str(index), GIT_NO_LAZY_FETCH="1",
               GIT_NO_REPLACE_OBJECTS="1", GIT_ALLOW_PROTOCOL="file", GIT_ATTR_NOSYSTEM="1")
    command = [
        git, "--no-optional-locks", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
        "-c", f"core.excludesFile={os.devnull}", "-c", f"core.attributesFile={os.devnull}",
        "-c", f"core.hooksPath={os.devnull}",
        "-c", "submodule.recurse=false", "--git-dir", str(git_dir), "--work-tree", str(root),
        "status", "--porcelain=v1", "-z", "--untracked-files=normal", "--ignore-submodules=all",
        "--", ".", *(f":(exclude,literal){'/'.join(parts)}" for parts in exclusions),
    ]
    try:
        process = subprocess.Popen(command, cwd=root, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        return {"state": "unavailable", "tracked_changes": None, "untracked": None}
    output = bytearray()
    overflow = threading.Event()

    def consume() -> None:
        assert process.stdout is not None
        while chunk := process.stdout.read(8192):
            if len(output) + len(chunk) > MAX_GIT_OUTPUT:
                overflow.set()
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                break
            output.extend(chunk)

    thread = threading.Thread(target=consume, daemon=True)
    thread.start()
    try:
        returncode = process.wait(timeout=GIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        returncode = -1
    thread.join()
    if process.stdout is not None:
        process.stdout.close()
    if returncode != 0 or overflow.is_set():
        return {"state": "unavailable", "tracked_changes": None, "untracked": None}
    records = bytes(output).split(b"\0")
    tracked = untracked = 0
    i = 0
    while i < len(records) and records[i]:
        record = records[i]
        if len(record) < 4 or record[2:3] != b" ":
            return {"state": "unavailable", "tracked_changes": None, "untracked": None}
        if record[:2] == b"??":
            untracked += 1
        else:
            tracked += 1
            if b"R" in record[:2] or b"C" in record[:2]:
                i += 1
        i += 1
    return {"state": "available", "tracked_changes": tracked, "untracked": untracked}


def analyze(value: str) -> dict[str, object]:
    root = _root(value)
    try:
        device = root.stat().st_dev
    except OSError as error:
        raise PathSafetyError("Quellprojekt ist nicht sicher zugänglich.") from error
    counts = {"files": 0, "directories": 0, "symlinks_or_special": 0, "excluded_directories": 0}
    languages: set[str] = set()
    markers: set[str] = set()
    docs = tests = ci = assets = False
    metadata = "not_observed"
    metadata_details = None
    limits: set[str] = {
        "Die Bestandsanalyse liest nur die t0003-Metadatendatei; Git kann zusätzlich Index, Git-Konfiguration, Ignore-Dateien und versionierte Dateiinhalte lesen.",
        "Quelltexte, Abhängigkeiten, ausführbare Befehle und Binärdaten werden nicht inhaltlich ausgewertet.",
        "Individuelle Dateinamen, Konfigurationswerte und Git-Diagnosen werden nicht ausgegeben.",
        "Ignorierte Git-Dateien, Submodule und ausgeschlossene Verzeichnisse werden beim Git-Status nicht erfasst; unversionierte Verzeichnisse zählen als ein Eintrag.",
    }
    seen = 0
    truncated = False
    complete = True
    exclusions: list[tuple[str, ...]] = []
    anchored = (os.scandir in os.supports_fd and os.open in os.supports_dir_fd
                and hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY"))

    def scan(directory: Path, parts: tuple[str, ...], depth: int, fd: int | None = None) -> None:
        nonlocal seen, truncated, complete, docs, tests, ci, assets, metadata, metadata_details
        try:
            with os.scandir(fd if fd is not None else directory) as entries:
                for entry in entries:
                    if seen >= MAX_ENTRIES:
                        truncated = True
                        complete = False
                        break
                    seen += 1
                    relative = (*parts, entry.name)
                    try:
                        info = _entry_stat(entry, directory)
                        reparse = bool(getattr(info, "st_file_attributes", 0)
                                       & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
                        if stat.S_ISLNK(info.st_mode) or reparse:
                            counts["symlinks_or_special"] += 1
                            exclusions.append(relative)
                            limits.add("Symlinks und Junctions wurden nicht verfolgt.")
                        elif stat.S_ISDIR(info.st_mode):
                            counts["directories"] += 1
                            if entry.name.lower() in {"test", "tests", "__tests__", "spec", "specs"}:
                                tests = True
                            child = directory / entry.name
                            if entry.name in EXCLUDED or info.st_dev != device or os.path.ismount(child):
                                counts["excluded_directories"] += 1
                                exclusions.append(relative)
                                limits.add("Abhängigkeits-, Versionsverwaltungs- und externe Verzeichnisse wurden ausgeschlossen.")
                            elif depth >= MAX_DEPTH:
                                complete = False
                                limits.add("Die maximale Verzeichnistiefe wurde erreicht.")
                            else:
                                if fd is not None:
                                    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                                    child_fd = os.open(entry.name, flags, dir_fd=fd)
                                    try:
                                        opened = os.fstat(child_fd)
                                        if ((opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)
                                                or not stat.S_ISDIR(opened.st_mode)):
                                            complete = False
                                            limits.add("Ein Verzeichnis hat sich während der Analyse geändert.")
                                        else:
                                            scan(child, relative, depth + 1, child_fd)
                                    finally:
                                        os.close(child_fd)
                                else:
                                    scan(child, relative, depth + 1)
                                if truncated:
                                    break
                        elif stat.S_ISREG(info.st_mode):
                            counts["files"] += 1
                            suffix = Path(entry.name).suffix.lower()
                            if suffix in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".webp", ".ico"}:
                                assets = True
                            if suffix in LANGUAGES:
                                languages.add(LANGUAGES[suffix])
                            if entry.name in CONFIG_MARKERS:
                                markers.add(CONFIG_MARKERS[entry.name])
                            if entry.name.lower().startswith(("readme", "contributing", "changelog")) or (
                                    parts and parts[0].lower() in {"docs", "doc"} and suffix in {".md", ".rst", ".txt"}):
                                docs = True
                            if (entry.name.lower().startswith("test_") or entry.name.lower().endswith(
                                    ("_test.py", ".test.ts", ".spec.ts", "test.java"))):
                                tests = True
                            if relative in ((".gitlab-ci.yml",), ("Jenkinsfile",), (".travis.yml",)):
                                ci = True
                            if parts == (".github", "workflows") and suffix in {".yml", ".yaml"}:
                                ci = True
                            if relative == ("config", "project.yaml"):
                                markers.add("config/project.yaml")
                                metadata, metadata_details = _metadata(directory / entry.name, device, fd)
                        else:
                            counts["symlinks_or_special"] += 1
                            limits.add("Spezialdateien wurden nicht gelesen.")
                    except OSError:
                        complete = False
                        limits.add("Einträge oder Dateimetadaten waren nicht lesbar.")
        except OSError:
            complete = False
            limits.add("Mindestens ein Verzeichnis war nicht lesbar.")
    if anchored:
        try:
            root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                opened = os.fstat(root_fd)
                root_info = root.stat()
                if (opened.st_dev, opened.st_ino) != (root_info.st_dev, root_info.st_ino):
                    raise PathSafetyError("Quellprojekt hat sich während der Analyse geändert.")
                scan(root, (), 0, root_fd)
            finally:
                os.close(root_fd)
        except OSError as error:
            raise PathSafetyError("Quellprojekt ist nicht sicher zugänglich.") from error
    else:
        scan(root, (), 0)
    if truncated:
        limits.add("Die maximale Anzahl untersuchter Verzeichniseinträge wurde erreicht.")
    git = _git_status(root, exclusions, complete)
    if git["state"] == "unavailable":
        limits.add("Git-Status nicht verfügbar; unvollständige Scans, Worktrees, Git-Indirektionen, Filter, partielle Klone und nicht lesbare oder große Git-Daten werden nicht geprüft.")
    conflicts = []
    if metadata == "not_recognized":
        conflicts.append("Vorhandene Projektmetadaten sind nicht als unterstützte t0003-Konfiguration erkennbar; mögliche Namenskollision prüfen.")
    elif metadata == "recognized_unverified_version":
        conflicts.append("Die erkannte t0003-Version ist nicht auf Kompatibilität geprüft.")
    elif metadata == "unreadable_or_unsupported":
        conflicts.append("Vorhandene Projektmetadaten konnten nicht sicher geprüft werden.")
    if git["state"] == "available" and (git["tracked_changes"] or git["untracked"]):
        conflicts.append("Lokale Git-Änderungen vor einer Migrationsentscheidung sichern und prüfen.")
    incomplete = truncated or any(
        word in limit for limit in limits for word in ("erreicht", "nicht lesbar", "geändert", "nicht verfolgt")
    )
    if incomplete or metadata in {"unreadable_or_unsupported", "not_recognized"}:
        recommendation = "offen"
        reason = "Die Bestandsaufnahme ist begrenzt oder Projektmetadaten sind unklar; vor einer Entscheidung manuell prüfen."
    elif 1 <= counts["files"] <= 100 and languages and not ci and metadata == "not_observed":
        recommendation = "A"
        reason = "Wenige beobachtete Dateien und keine erkannte CI sprechen vorläufig für selektive Übernahme; Inhalte und Betrieb sind ungeprüft."
    else:
        recommendation = "offen"
        reason = "Größe und Indikatoren allein belegen weder Betriebsabhängigkeiten noch Migrationsrisiken ausreichend."
    return {
        "report_version": 1,
        "kind": "read_only_migration_analysis",
        "facts": {"observed_entries": seen, "structure": counts, "git": git, "t0003_metadata": metadata,
                  "t0003_details": metadata_details},
        "indicators": {
            "languages": sorted(languages), "configuration_files": sorted(markers),
            "technologies": sorted({TECHNOLOGIES[marker] for marker in markers if marker in TECHNOLOGIES}),
            "documentation": docs, "tests": tests, "ci_configuration": ci, "assets": assets,
        },
        "analysis_limits": sorted(limits),
        "conflicts": conflicts,
        "prerequisites": [
            "t0003-Basis, Werkzeugversionen und Integrationskompatibilität sind vor einer Umsetzung zu prüfen.",
            "Sicherung und Wiederherstellung sowie unversionierte und ignorierte Daten sind vorab zu prüfen.",
        ],
        "strategies": {
            "A": {"name": "Neues t0003-Projekt und selektive Übernahme",
                  "risks": "Nicht übernommene Abhängigkeiten oder Verhalten können fehlen.",
                  "complexity": "Einzelne Übernahmen und Integration prüfen.",
                  "conflicts": "Weniger direkte Überschreibungen; Integrationskonflikte möglich.",
                  "fallback": "Altes Projekt bleibt als Rückfall erhalten.",
                  "effort": "Bei kleinen Projekten oft niedriger, bei vielen Abhängigkeiten höher; Tokenaufwand abhängig von der manuellen Sichtung."},
            "B": {"name": "Bestehendes Projekt schrittweise anpassen",
                  "risks": "Bestehende Abläufe oder Konfigurationen können beeinträchtigt werden.",
                  "complexity": "Bestehende Strukturen und Abhängigkeiten schrittweise abstimmen.",
                  "conflicts": "Höheres Potenzial für Namens- und Konfigurationskonflikte.",
                  "fallback": "Rückfall erfordert unabhängig geprüfte Sicherung und Wiederherstellung.",
                  "effort": "Bei etablierten Projekten oft praktikabel, Konfliktprüfung kann aufwendig sein; Tokenaufwand abhängig von der manuellen Sichtung."},
        },
        "recommendation": {"strategy": recommendation, "reason": reason,
                           "open_decisions": ["Abhängigkeiten, Betrieb, Testabdeckung und Rückfall prüfen.",
                                              "Strategie und Umfang menschlich freigeben; keine automatische Migration."]},
    }


def emit_text(report: dict[str, object]) -> None:
    print("Lesende Bestandsanalyse (kein Apply-Plan, keine Migration)")
    facts = report["facts"]
    structure = facts["structure"]
    print("\nNachgewiesene Fakten:")
    print(f"- Beobachtet: {facts['observed_entries']} Einträge, {structure['files']} Dateien, "
          f"{structure['directories']} Verzeichnisse; {structure['excluded_directories']} Verzeichnisse ausgeschlossen.")
    git = facts["git"]
    if git["state"] == "available":
        print(f"- Git: {git['tracked_changes']} geänderte und {git['untracked']} unversionierte Einträge.")
    else:
        print("- Git: " + ("nicht erkannt." if git["state"] == "not_detected" else "nicht prüfbar."))
    metadata_labels = {
        "not_observed": "nicht erkannt", "recognized_supported": "t0003-Metadaten erkannt, Version unterstützt",
        "recognized_unverified_version": "t0003-Metadaten erkannt, Version ungeprüft",
        "not_recognized": "nicht als t0003-Metadaten erkannt",
        "unreadable_or_unsupported": "nicht sicher prüfbar",
    }
    print(f"- Projektmetadaten: {metadata_labels[facts['t0003_metadata']]}.")
    details = facts["t0003_details"]
    if details is not None:
        for key, label in (("generator_version_configured", "Generator-Version"),
                           ("modules_configured", "Module"), ("sdd_configured", "SDD-Werkzeug")):
            print(f"  {label}: {'gesetzt' if details[key] else 'nicht gesetzt'}.")
    indicators = report["indicators"]
    print("\nErkannte Hinweise (nicht erkannte Bereiche können ungeprüft sein):")
    for key, label in (("languages", "Sprachen"), ("technologies", "Technologien"),
                       ("configuration_files", "Konfigurationsindikatoren")):
        print(f"- {label}: {', '.join(indicators[key]) or 'keine erkannt'}.")
    for key, label in (("documentation", "Dokumentation"), ("tests", "Tests"),
                       ("ci_configuration", "CI-Konfiguration"), ("assets", "Assets")):
        print(f"- {label}: {'Hinweise erkannt' if indicators[key] else 'keine Hinweise erkannt'}.")
    for label, key in (("Nicht untersuchte Bereiche", "analysis_limits"), ("Mögliche Konflikte", "conflicts"),
                       ("Noch zu prüfende Voraussetzungen", "prerequisites")):
        print(f"\n{label}:")
        for item in report[key]:
            print(f"- {item}")
        if not report[key]:
            print("- Keine erkannt.")
    print("\nStrategievergleich:")
    for code, strategy in report["strategies"].items():
        print(f"- {code}: {strategy['name']}")
        for key, label in (("risks", "Risiken"), ("complexity", "Komplexität"),
                           ("conflicts", "Konflikte"), ("fallback", "Rückfall"), ("effort", "Aufwand")):
            print(f"  {label}: {strategy[key]}")
    print("\nEmpfehlung und Unsicherheit:")
    recommendation = report["recommendation"]
    print(f"- Strategie: {recommendation['strategy']}. {recommendation['reason']}")
    for item in recommendation["open_decisions"]:
        print(f"- {item}")
