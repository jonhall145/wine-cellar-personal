#!/usr/bin/env python3
"""Bump the project version (semver) across all version files.

Updates wine_cellar/__init__.py and pyproject.toml, then optionally
commits and creates a git tag.

Usage:
    python scripts/bump_version.py patch          # 0.3.0 → 0.3.1
    python scripts/bump_version.py minor          # 0.3.0 → 0.4.0
    python scripts/bump_version.py major          # 0.3.0 → 1.0.0
    python scripts/bump_version.py current        # prints current version
    python scripts/bump_version.py patch --tag    # bump, commit, and tag
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT_FILE = ROOT / "wine_cellar" / "__init__.py"
TOML_FILE = ROOT / "pyproject.toml"

INIT_RE = re.compile(r'^__version__\s*=\s*"(\d+)\.(\d+)\.(\d+)"', re.MULTILINE)
TOML_RE = re.compile(r'^version\s*=\s*"(\d+\.\d+\.\d+)"', re.MULTILINE)


def read_version() -> tuple[int, int, int]:
    text = INIT_FILE.read_text()
    m = INIT_RE.search(text)
    if not m:
        print(f"ERROR: Could not find __version__ in {INIT_FILE}", file=sys.stderr)
        sys.exit(1)
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def write_version(major: int, minor: int, patch: int) -> str:
    new_version = f"{major}.{minor}.{patch}"

    # Update __init__.py
    init_text = INIT_FILE.read_text()
    if not INIT_RE.search(init_text):
        print(f"ERROR: version pattern not found in {INIT_FILE}", file=sys.stderr)
        sys.exit(1)
    INIT_FILE.write_text(INIT_RE.sub(f'__version__ = "{new_version}"', init_text))

    # Update pyproject.toml
    toml_text = TOML_FILE.read_text()
    if not TOML_RE.search(toml_text):
        print(f"ERROR: version pattern not found in {TOML_FILE}", file=sys.stderr)
        sys.exit(1)
    TOML_FILE.write_text(TOML_RE.sub(f'version = "{new_version}"', toml_text))

    return new_version


def commit_and_tag(version: str) -> None:
    """Commit the version bump files, then create an annotated tag."""
    subprocess.run(
        ["git", "add", str(INIT_FILE), str(TOML_FILE)],
        check=True,
        cwd=ROOT,
    )
    subprocess.run(
        ["git", "commit", "-m", f"chore: bump version to {version}"],
        check=True,
        cwd=ROOT,
    )
    subprocess.run(
        ["git", "tag", "-a", version, "-m", f"Release {version}"],
        check=True,
        cwd=ROOT,
    )
    print(f"Committed and tagged: {version}")


def main() -> None:
    valid_parts = ("patch", "minor", "major", "current")
    if len(sys.argv) < 2 or sys.argv[1] not in valid_parts:
        print(__doc__.strip())
        sys.exit(1)

    part = sys.argv[1]
    do_tag = "--tag" in sys.argv

    major, minor, patch = read_version()

    if part == "current":
        print(f"{major}.{minor}.{patch}")
        return

    old = f"{major}.{minor}.{patch}"

    if part == "patch":
        patch += 1
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "major":
        major += 1
        minor = 0
        patch = 0

    new = write_version(major, minor, patch)
    print(f"{old} → {new}")

    if do_tag:
        commit_and_tag(new)


if __name__ == "__main__":
    main()
