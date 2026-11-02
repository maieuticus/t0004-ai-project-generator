"""Exact, supported CI states for the two fixed starter modules."""

import hashlib

from .python_compat import VERIFIED_FILES

BASE_CI = b'''name: Template-Pr\xc3\xbcfung
on:
  push:
    branches: ["**"]
    tags: ["v*"]
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  template:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - uses: actions/setup-node@v4
        with:
          node-version: "24"
      - run: python scripts/check.py
      - if: github.repository == 'maieuticus/t0003-ai-project-template'
        run: python -m unittest discover -s .github/template-tests -v
'''
PYTHON_STEPS = b"      - run: python -m pip install --no-deps .\n      - run: python -m project_app\n"
NPM_STEP = b"      - run: npm ci --ignore-scripts --prefix typescript\n"
PROJECT_CHECK = b"      - run: python scripts/check.py\n"
MODULES = {"python": "python@0.1.0", "typescript": "typescript@0.1.0"}


def ci_result(modules: frozenset[str]) -> bytes:
    result = BASE_CI
    if "typescript" in modules:
        result = result.replace(PROJECT_CHECK, NPM_STEP + PROJECT_CHECK, 1)
    if "python" in modules:
        result += PYTHON_STEPS
    return result


CI_STATES = {frozenset(names): ci_result(frozenset(names)) for names in
             ((), ("python",), ("typescript",), ("python", "typescript"))}
CI_DIGESTS = {
    frozenset(): VERIFIED_FILES[".github/workflows/ci.yml"],
    frozenset({"python"}): "098dfdcb0c8981568a415e4a67c92b35f58b10b445589ec8bb856440fa412d79",
    frozenset({"typescript"}): "643b88b13e6a7052e70c3503f9ca6fc2552633c23cff1ed81ae3c21d86698101",
    frozenset({"python", "typescript"}): "81c5908fecf08773e3ba3e4d4be33b84cb168b0f24a1ca3e553253d1d7aaf0f5",
}
assert all(hashlib.sha256(content).hexdigest() == CI_DIGESTS[names]
           for names, content in CI_STATES.items())


def known_ci(content: bytes | None) -> frozenset[str] | None:
    return next((names for names, expected in CI_STATES.items() if content == expected), None)
