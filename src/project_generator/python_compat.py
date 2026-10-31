"""Verify the t0003 capabilities required by the Python module."""

import hashlib
from pathlib import Path

from .plan import _directory_states, _operation_state

# These exact files at t0003 commit 6e8363a run configured project checks and
# restrict template-only tests to the template repository.
VERIFIED_FILES = {
    "scripts/check.py": "08be5d0fc5bddb6bbd9209c659a77456c785bfaa3ee24ebb06c20d390d6a2d4e",
    "scripts/projectcfg.py": "f446580597e0c3e7c46ab20cd31e8bbc609316a5a8ae65696da8814244832d20",
    ".github/workflows/ci.yml": "f54914e7f43f14acde14b33693abdbc303784c90c84c87e6bdd7f385e22731cd",
}
PYTHON_CI_SHA256 = "098dfdcb0c8981568a415e4a67c92b35f58b10b445589ec8bb856440fa412d79"


def python_capabilities(target: str) -> dict[str, object]:
    """Return conflicts and raw file/access fingerprints without exposing contents."""
    root = Path(target).expanduser().resolve(strict=True)
    directories = _directory_states(root, list(VERIFIED_FILES))
    states = []
    conflicts = []
    for name, known_digest in VERIFIED_FILES.items():
        content, attributes = _operation_state(root, name)
        digest = hashlib.sha256(content).hexdigest() if content is not None else None
        states.append({"path": name, "sha256": digest, "attributes": attributes})
        if digest != known_digest and not (name == ".github/workflows/ci.yml" and digest == PYTHON_CI_SHA256):
            conflicts.append(
                f"{name}: benötigte t0003-Check-/CI-Fähigkeiten für python@0.1.0 "
                "sind für diesen Dateistand nicht nachgewiesen."
            )
    return {"files": states, "directories": directories, "conflicts": conflicts}
