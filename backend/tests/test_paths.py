from pathlib import Path

import pytest

from app.vault.paths import PathSafetyError, safe_resolve


def test_resolves_simple_path(tmp_path: Path):
    (tmp_path / "notes").mkdir()
    assert safe_resolve(tmp_path, "notes") == (tmp_path / "notes").resolve()


def test_resolves_empty_to_root(tmp_path: Path):
    assert safe_resolve(tmp_path, "") == tmp_path.resolve()


def test_rejects_traversal(tmp_path: Path):
    with pytest.raises(PathSafetyError):
        safe_resolve(tmp_path, "../etc/passwd")


def test_rejects_absolute(tmp_path: Path):
    with pytest.raises(PathSafetyError):
        safe_resolve(tmp_path, "/etc/passwd")


def test_rejects_symlink_escape(tmp_path: Path):
    outside = tmp_path.parent / "outside-target"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "sneaky"
    link.symlink_to(outside)
    with pytest.raises(PathSafetyError):
        safe_resolve(tmp_path, "sneaky/anything")
