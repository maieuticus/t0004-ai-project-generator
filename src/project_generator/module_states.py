"""Exact CI states for the fixed generator modules and legacy projections."""

import hashlib
from itertools import combinations

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
REACT_NPM_STEP = b"      - run: npm ci --ignore-scripts --prefix react\n"
PROJECT_CHECK = b"      - run: python scripts/check.py\n"
MODULES = {
    "python": "python@0.1.0",
    "typescript": "typescript@0.1.0",
    "java": "java@0.1.0",
    "react": "react@0.1.0",
}
DOCKER_MODULES = frozenset({"python", "typescript", "java"})
JAVA_SETUP = b'      - uses: actions/setup-java@v4\n        with:\n          distribution: "temurin"\n          java-version: "25"\n'


def ci_result(modules: frozenset[str]) -> bytes:
    result = BASE_CI
    if "java" in modules:
        result = result.replace(PROJECT_CHECK, JAVA_SETUP + PROJECT_CHECK, 1)
    if "typescript" in modules:
        result = result.replace(PROJECT_CHECK, NPM_STEP + PROJECT_CHECK, 1)
    if "react" in modules:
        result = result.replace(PROJECT_CHECK, REACT_NPM_STEP + PROJECT_CHECK, 1)
    if "python" in modules:
        result += PYTHON_STEPS
    return result


CI_STATES = {frozenset(names): ci_result(frozenset(names))
             for count in range(len(MODULES) + 1) for names in combinations(MODULES, count)}
CI_DIGESTS = {
    frozenset(): VERIFIED_FILES[".github/workflows/ci.yml"],
    frozenset({"python"}): "098dfdcb0c8981568a415e4a67c92b35f58b10b445589ec8bb856440fa412d79",
    frozenset({"typescript"}): "643b88b13e6a7052e70c3503f9ca6fc2552633c23cff1ed81ae3c21d86698101",
    frozenset({"java"}): "c2af5caa5cdf839c786efb2ca26d4e0f2dc61368cdba7f0216c24dcc2760b5e6",
    frozenset({"python", "typescript"}): "81c5908fecf08773e3ba3e4d4be33b84cb168b0f24a1ca3e553253d1d7aaf0f5",
    frozenset({"python", "java"}): "431aa2bd4d65c4d4a4cfcd13af1bcbfd1159f9ca0a933af9101a4ce13828bf4f",
    frozenset({"typescript", "java"}): "8b2a950ef80b39c1af1dc69bd606a5fda4ad41e7cb5fb05bbdadfaf7e497d618",
    frozenset({"python", "typescript", "java"}): "8e6083708716b3fcedd7f6071829154850c89e15f2bae994b056099775d1fc6c",
}
assert all(hashlib.sha256(content).hexdigest() == CI_DIGESTS[names]
           for names, content in CI_STATES.items() if names in CI_DIGESTS)


def known_ci(content: bytes | None) -> frozenset[str] | None:
    return next((names for names, expected in CI_STATES.items() if content == expected), None)
