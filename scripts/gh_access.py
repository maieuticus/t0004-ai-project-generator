"""Isolated GitHub access boundary for private template retrieval."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit


T0003_SOURCE = "https://github.com/maieuticus/t0003-private-access-test.git"
COMPATIBLE_REFERENCE = "6e8363a7ac7d99220d743eea077dcd5cefda9042"
RELEASE_REFERENCE = "964de8538d19cefcb483faff38f10124615a9783"


@dataclass(frozen=True)
class AccessResult:
    success: bool
    category: str
    message: str
    reference: str | None = None


@dataclass(frozen=True)
class ReferenceStatus:
    compatible: bool
    default_branch_drift: bool


def redact(value: str) -> str:
    """Remove credential-shaped values from diagnostics."""
    import re

    return re.sub(
        r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"glpat-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})",
        "REDACTED",
        value,
    )


def classify_error(stderr: str) -> AccessResult:
    """Classify Git failures without returning raw subprocess output."""
    text = stderr.lower()
    if "expired" in text:
        category = "expired"
    elif any(marker in text for marker in ("403", "permission denied", "access denied", "forbidden")):
        category = "forbidden"
    elif any(marker in text for marker in ("404", "repository not found", "couldn't find remote ref",
                                           "could not find remote ref", "invalid reference")):
        category = "not_found"
    elif any(marker in text for marker in ("could not read username", "could not read password",
                                           "terminal prompts disabled", "no credentials", "not logged in",
                                           "authentication failed")):
        category = "missing"
    elif any(marker in text for marker in ("could not resolve host", "connection timed out",
                                           "connection refused", "network is unreachable")):
        category = "network"
    else:
        category = "unknown"
    messages = {
        "expired": "Zugriff fehlgeschlagen: Zugangsdaten sind abgelaufen.",
        "forbidden": "Zugriff fehlgeschlagen: Berechtigung fehlt.",
        "not_found": "Zugriff fehlgeschlagen: Repository oder Referenz nicht gefunden.",
        "missing": "Zugriff fehlgeschlagen: Zugangsdaten fehlen.",
        "network": "Zugriff fehlgeschlagen: Netzwerk nicht erreichbar.",
        "unknown": "Zugriff fehlgeschlagen: Ursache konnte nicht sicher klassifiziert werden.",
    }
    return AccessResult(False, category, redact(messages[category]))


def _process_error_diagnostic(
    step: str,
    error: OSError,
    env: dict[str, str],
    cwd: Path | None = None,
) -> str:
    executable = _git_executable(env)
    executable_exists = bool(executable and Path(executable).is_file())
    workdir = cwd if cwd is not None else Path.cwd()
    cwd_exists = workdir.exists()
    cwd_is_directory = workdir.is_dir()
    version = "unavailable"
    if executable_exists and executable is not None:
        try:
            probe_env = git_environment(env)
            result = subprocess.run(
                [executable, "--version"],
                capture_output=True,
                check=False,
                env=probe_env,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            match = re.fullmatch(r"git version [A-Za-z0-9.+-]+", result.stdout.strip())
            version = match.group(0) if result.returncode == 0 and match else f"exit:{result.returncode}"
        except (OSError, subprocess.SubprocessError):
            version = "unavailable"
    return (
        f"Git process error at {step}: outcome=os-error-no-returncode, "
        f"exception={type(error).__name__}, "
        f"errno={error.errno}, winerror={getattr(error, 'winerror', None)}; "
        f"executable_resolved={executable is not None}, executable_exists={executable_exists}, "
        f"cwd_exists={cwd_exists}, cwd_is_directory={cwd_is_directory}, "
        f"git_version={version}, platform={sys.platform}/{os.name}."
    )


def _classify_process_failure(step: str, returncode: int, stderr: str) -> AccessResult:
    result = classify_error(stderr)
    return AccessResult(
        False,
        result.category,
        f"{result.message} Process {step} exited with code {returncode}.",
    )


def git_environment(
    inherited: dict[str, str] | None = None, *, include_credential_env: bool = False
) -> dict[str, str]:
    """Return a noninteractive environment isolated from caller Git configuration."""
    source = os.environ if inherited is None else inherited
    retained = ("PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "WINDIR", "PATHEXT", "TMP", "TEMP",
                "LANG", "LC_ALL", "LC_CTYPE")
    environment = {key: source[key] for key in retained if key in source}
    if include_credential_env and source.get("GH_TOKEN"):
        environment["GH_TOKEN"] = source["GH_TOKEN"]
    environment.update(
        GCM_INTERACTIVE="Never",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0",
    )
    return environment


def _git_executable(env: dict[str, str]) -> str | None:
    path = env.get("PATH")
    if not path:
        return None
    executable = shutil.which("git", path=path)
    return os.path.abspath(executable) if executable else None


def fetch_command(source: str, destination: Path, reference: str) -> list[str]:
    """Build the credential-helper-only fetch command without token arguments."""
    target = fetched_ref(reference)
    return [
        "git",
        "-c",
        "credential.helper=!gh auth git-credential",
        "fetch",
        "--no-tags",
        "--",
        source,
        f"+{reference}:{target}",
    ]


def resolve_default_branch(
    source: str, *, env: dict[str, str] | None = None, include_credential_env: bool = False
) -> AccessResult:
    """Resolve the remote default branch's commit without changing local state."""
    if _credential_bearing_source(source):
        return AccessResult(False, "unknown", "Zugriff fehlgeschlagen: Zugangsdaten in der Quelle sind nicht zulässig.")
    process_env = git_environment(env, include_credential_env=include_credential_env)
    executable = _git_executable(process_env)
    if executable is None:
        return AccessResult(False, "network", "Zugriff fehlgeschlagen: Git ist nicht verfügbar.")
    try:
        result = subprocess.run(
            [executable, "-c", "credential.helper=!gh auth git-credential", "ls-remote",
             "--symref", "--", source, "HEAD"],
            capture_output=True,
            check=False,
            env=process_env,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        diagnostic = _process_error_diagnostic(
            "git ls-remote", error, process_env
        )
        return AccessResult(
            False, "network", f"Zugriff fehlgeschlagen: Git ist nicht verfügbar. {diagnostic}"
        )
    if result.returncode:
        return _classify_process_failure("git ls-remote", result.returncode, result.stderr)
    for line in result.stdout.splitlines():
        if line.endswith("\tHEAD") and not line.startswith("ref: "):
            reference = line.split("\t", 1)[0]
            if reference and all(character in "0123456789abcdefABCDEF" for character in reference):
                return AccessResult(True, "ok", "Default-Branch wurde aufgelöst.", reference)
    return AccessResult(False, "not_found", "Zugriff fehlgeschlagen: Default-Branch nicht gefunden.")


def fetched_ref(reference: str) -> str:
    """Return a stable, safe local ref name for one fetched reference."""
    suffix = hashlib.sha256(reference.encode("utf-8")).hexdigest()
    return f"refs/t0004/private-access/{suffix}"


def _credential_bearing_source(source: str) -> bool:
    parsed = urlsplit(source)
    return bool(parsed.scheme and (parsed.username is not None or parsed.password is not None))


def fetch_reference(
    source: str,
    destination: Path,
    reference: str,
    *,
    env: dict[str, str] | None = None,
    include_credential_env: bool = False,
) -> AccessResult:
    """Fetch one reference into a new bare repository without storing a remote."""
    if _credential_bearing_source(source):
        return AccessResult(False, "unknown", "Zugriff fehlgeschlagen: Zugangsdaten in der Quelle sind nicht zulässig.")
    local_env = git_environment(env)
    executable = _git_executable(local_env)
    if executable is None:
        return AccessResult(False, "network", "Zugriff fehlgeschlagen: Git ist nicht verfügbar.")
    created = not destination.exists()
    step = "git init --bare" if created else "git rev-parse --is-bare-repository"
    try:
        if created:
            subprocess.run(
                [executable, "init", "--bare", str(destination)],
                capture_output=True,
                check=True,
                env=local_env,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        else:
            bare = subprocess.run(
                [executable, "--git-dir", str(destination), "rev-parse", "--is-bare-repository"],
                capture_output=True,
                check=False,
                env=local_env,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if bare.returncode or bare.stdout.strip() != "true":
                message = "Zugriff fehlgeschlagen: Ziel ist kein Bare-Repository."
                if bare.returncode:
                    message += f" Process git rev-parse exited with code {bare.returncode}."
                return AccessResult(False, "unknown", message)
        step = "git fetch"
        process_env = git_environment(env, include_credential_env=include_credential_env)
        command = fetch_command(source, destination, reference)
        command[0] = executable
        result = subprocess.run(
            command,
            cwd=destination,
            capture_output=True,
            check=False,
            env=process_env,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        diagnostic = _process_error_diagnostic(
            step, error, local_env, destination if step == "git fetch" else None
        )
        if created:
            shutil.rmtree(destination, ignore_errors=True)
        return AccessResult(
            False, "network", f"Zugriff fehlgeschlagen: Git ist nicht verfügbar. {diagnostic}"
        )
    except subprocess.CalledProcessError as error:
        if created:
            shutil.rmtree(destination, ignore_errors=True)
        return _classify_process_failure(step, error.returncode, error.stderr or "")
    if result.returncode == 0:
        return AccessResult(True, "ok", "Referenz wurde abgerufen.")
    if created:
        shutil.rmtree(destination, ignore_errors=True)
    return _classify_process_failure("git fetch", result.returncode, result.stderr)


def reference_status(reference: str, default_branch_reference: str) -> ReferenceStatus:
    """State compatibility and default-branch drift for a resolved reference."""
    return ReferenceStatus(
        compatible=reference == COMPATIBLE_REFERENCE,
        default_branch_drift=default_branch_reference != COMPATIBLE_REFERENCE,
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Fetch one Git reference without persisting credentials.")
    parser.add_argument("source")
    parser.add_argument("destination", type=Path)
    parser.add_argument("reference")
    args = parser.parse_args(argv)
    result = fetch_reference(args.source, args.destination, args.reference)
    print(result.message)
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
