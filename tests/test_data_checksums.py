"""Data checksums turn silent page corruption into a detected error."""

from __future__ import annotations

from pathlib import Path

import pytest

from ledgerguard.faults.checksum_demo import corrupt_and_read
from ledgerguard.faults.disk_full import docker_available

ROOT = Path(__file__).resolve().parents[1]


def test_every_compose_database_is_initialised_with_data_checksums() -> None:
    text = (ROOT / "docker-compose.yml").read_text()
    assert text.count("image: postgres:17-alpine") == 3
    assert text.count('POSTGRES_INITDB_ARGS: "--data-checksums"') == 3


@pytest.mark.skipif(not docker_available(), reason="docker or postgres:17-alpine not available")
def test_corruption_is_detected_with_checksums_and_silent_without() -> None:
    protected = corrupt_and_read(checksums=True)
    unprotected = corrupt_and_read(checksums=False)

    assert protected.detected, protected
    assert protected.read_error is not None and protected.read_error.startswith("XX001")
    assert "invalid page" in protected.read_error  # DETAIL names the checksum mismatch

    # The control: the same flipped bytes are returned to the caller as if they were correct.
    assert unprotected.silently_wrong, unprotected
    assert unprotected.value_read is not None and "XXXX" in unprotected.value_read
