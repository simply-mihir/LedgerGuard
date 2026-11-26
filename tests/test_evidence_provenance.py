"""Evidence generators must not describe uncommitted code as a commit."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ledgerguard.evidence import DirtyTreeError, collect, require_clean_tree


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.txt").write_text("x")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_clean_tree_is_accepted(repo: Path) -> None:
    prov = require_clean_tree(False, repo)
    assert prov.working_tree_clean and len(prov.git_sha) == 40 and len(prov.git_tree) == 40


def test_dirty_tree_is_refused_unless_allowed(repo: Path) -> None:
    (repo / "a.txt").write_text("changed")
    with pytest.raises(DirtyTreeError):
        require_clean_tree(False, repo)
    prov = require_clean_tree(True, repo)
    assert prov.working_tree_clean is False


def test_untracked_file_counts_as_dirty(repo: Path) -> None:
    (repo / "new.py").write_text("print(1)")
    assert collect(repo).working_tree_clean is False
