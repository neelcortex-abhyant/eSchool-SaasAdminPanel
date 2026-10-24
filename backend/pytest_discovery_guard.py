"""Guard pytest collection against accidental filesystem-root path args.

On Windows PowerShell, bash-style line continuations like::

    python -m pytest \\
      tests/foo.py

pass a literal ``\\`` argument. Pytest then collects from the drive root
(``C:\\``), including ``site-packages`` (Alembic's own suite), stdlib tests,
and unrelated installs — tens of thousands of items and spurious errors.

This plugin drops drive-root / filesystem-root args so ``testpaths`` applies.
"""

from __future__ import annotations

from pathlib import Path


def _is_filesystem_root_arg(arg: str) -> bool:
    if arg in {"\\", "/", "\\\\"}:
        return True
    try:
        path = Path(arg)
    except (TypeError, ValueError):
        return False
    # Bare drive roots: C:\  C:/  D:\
    s = str(arg).replace("/", "\\")
    if len(s) == 3 and s[1:] == ":\\":
        return True
    if len(s) == 2 and s.endswith(":"):
        return True
    try:
        resolved = path.resolve()
    except OSError:
        return False
    # Path.resolve() of "\\" is the drive root; parent == self for roots.
    return resolved.is_absolute() and resolved.parent == resolved


def pytest_load_initial_conftests(early_config, parser, args: list[str]) -> None:  # noqa: ARG001
    kept = [a for a in args if not _is_filesystem_root_arg(a)]
    if len(kept) != len(args):
        args[:] = kept


def pytest_ignore_collect(collection_path, config):  # noqa: ARG001
    """Skip third-party / stdlib trees if they are somehow reached."""
    try:
        path = Path(collection_path)
        parts = {p.lower() for p in path.parts}
    except (TypeError, ValueError, OSError):
        return None
    blocked = {
        "site-packages",
        "dist-packages",
        "lib",
        "lib64",
        "mysql",
        "mysql workbench 8.0 CE".lower(),
        "node_modules",
        ".git",
        "__pycache__",
    }
    # Only block well-known non-project basenames when not under ./tests
    name = path.name.lower()
    if name in blocked or "site-packages" in parts or "dist-packages" in parts:
        backend = Path(__file__).resolve().parent
        tests = backend / "tests"
        try:
            path.resolve().relative_to(tests.resolve())
            return None
        except ValueError:
            return True
    return None
