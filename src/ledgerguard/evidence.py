"""Source provenance for generated evidence (benchmarks, comparisons, fault campaigns)."""

from __future__ import annotations

from pathlib import Path

from ledgerguard.perf.study import SourceProvenance, collect_source_provenance

REPO_ROOT = Path(__file__).resolve().parents[2]


class DirtyTreeError(RuntimeError):
    """Raised when evidence generation is attempted on an uncommitted working tree."""


def collect(repo_root: Path | None = None) -> SourceProvenance:
    return collect_source_provenance(repo_root or REPO_ROOT)


def require_clean_tree(allow_dirty: bool, repo_root: Path | None = None) -> SourceProvenance:
    """Return provenance; refuse to run on a dirty tree unless explicitly allowed."""
    prov = collect(repo_root)
    if not prov.working_tree_clean and not allow_dirty:
        raise DirtyTreeError(
            "Refusing to generate evidence from a dirty working tree: the recorded commit would "
            "not describe the code that ran. Commit or stash first, or pass --allow-dirty "
            "(recorded as working_tree_clean=false)."
        )
    return prov
