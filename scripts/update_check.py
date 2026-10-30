"""Compare the adopted template release with the published upstream releases.

Read-only and non-blocking: never changes a file and never fails because the
upstream is unreachable (exit code 0 with the message "nicht geprüft").
"""

import os
import re
import subprocess
import sys

import projectcfg

SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse(version: str | None):
    match = SEMVER.match(version or "")
    return tuple(int(part) for part in match.groups()) if match else None


def latest_tag(source: str) -> str | None:
    result = subprocess.run(
        ["git", "ls-remote", "--tags", "--refs", source],
        capture_output=True, text=True, timeout=20, check=False,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if result.returncode:
        raise OSError(result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "git ls-remote fehlgeschlagen")
    tags = [line.split("refs/tags/")[-1] for line in result.stdout.splitlines()]
    versions = [(parse(tag), tag) for tag in tags if parse(tag)]
    return max(versions)[1] if versions else None


def main() -> int:
    config = projectcfg.read_text()
    source = projectcfg.get(config, "template", "source")
    release = projectcfg.get(config, "template", "release")
    if not source:
        print("Template-Update: nicht geprüft (template.source ist nicht gesetzt).")
        return 0
    try:
        latest = latest_tag(source)
    except (OSError, subprocess.SubprocessError) as error:
        print(f"Template-Update: nicht geprüft (Quelle nicht erreichbar: {error}).")
        return 0
    if latest is None:
        print("Template-Update: nicht geprüft (Quelle veröffentlicht noch keine SemVer-Tags).")
    elif parse(release) is None:
        print(f"Template-Update: nicht vergleichbar (übernommen: {release}; verfügbar: {latest}).")
    elif parse(latest) > parse(release):
        print(f"Template-Update: neue Version {latest} verfügbar (übernommen: {release}). "
              "Keine Änderung vorgenommen; Änderungsplan nur nach Freigabe erstellen.")
    else:
        print(f"Template-Update: keine neue Version (übernommen: {release}, verfügbar: {latest}).")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(f"Template-Update: nicht geprüft ({error}).")
        sys.exit(0)
