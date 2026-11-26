"""Real fault injection: SIGKILL, TCP partitions/resets/latency, API crash, container crash.

Nothing here is simulated in-process: workers and the API are separate OS processes killed
with SIGKILL, and database traffic crosses a fault-injecting TCP proxy.
"""

from __future__ import annotations

import os
import socket
import threading
import time

import pytest

from ledgerguard.faults import FaultProxy
from ledgerguard.faults.harness import (
    FaultEnv,
    WorkerProcess,
    check_invariants,
    transfer_state,
)
from ledgerguard.faults.scenarios import (
    api_kill_idempotent_replay,
    connection_reset_storm,
    kill_after_durable_commit,
    latency_burst,
    partition_destination,
    postgres_crash,
    random_kill_burst,
    stream_corruption,
    stream_reorder_duplicate,
    stream_truncation,
)

# ---------------------------------------------------------------------------
# Proxy unit tests (no database)
# ---------------------------------------------------------------------------


@pytest.fixture
def echo_server():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    stop = threading.Event()

    def serve() -> None:
        srv.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = srv.accept()
            except (TimeoutError, OSError):
                continue
            threading.Thread(target=_echo, args=(conn,), daemon=True).start()

    def _echo(conn: socket.socket) -> None:
        try:
            while data := conn.recv(4096):
                conn.sendall(data)
        except OSError:
            pass
        finally:
            conn.close()

    threading.Thread(target=serve, daemon=True).start()
    yield srv.getsockname()
    stop.set()
    srv.close()


def _roundtrip(port: int, payload: bytes = b"ping", timeout: float = 2.0) -> bytes:
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as c:
        c.settimeout(timeout)
        c.sendall(payload)
        return c.recv(4096)


def test_proxy_forwards_traffic_transparently(echo_server) -> None:
    with FaultProxy(echo_server) as proxy:
        assert _roundtrip(proxy.port, b"hello") == b"hello"
        assert proxy.bytes_forwarded >= 10


def test_proxy_latency_is_applied_and_heals(echo_server) -> None:
    with FaultProxy(echo_server) as proxy:
        proxy.set_latency(150)
        t0 = time.perf_counter()
        assert _roundtrip(proxy.port) == b"ping"
        assert time.perf_counter() - t0 >= 0.28  # both directions delayed
        proxy.heal()
        # The injected 2 x 150 ms must be gone. A busy CI runner can delay any single roundtrip,
        # so take the fastest of several: if latency were still injected, every sample would be
        # >= 0.28 s, whereas an unloaded loopback roundtrip takes a few milliseconds.
        samples = []
        for _ in range(5):
            t1 = time.perf_counter()
            _roundtrip(proxy.port)
            samples.append(time.perf_counter() - t1)
        assert min(samples) < 0.15, samples


def test_proxy_blackhole_delivers_nothing_then_heals(echo_server) -> None:
    with FaultProxy(echo_server) as proxy:
        proxy.blackhole()
        with pytest.raises(TimeoutError):
            _roundtrip(proxy.port, timeout=0.5)
        assert proxy.bytes_dropped > 0
        proxy.heal()
        assert _roundtrip(proxy.port) == b"ping"


def test_proxy_sever_resets_live_connections(echo_server) -> None:
    with FaultProxy(echo_server) as proxy:
        c = socket.create_connection(("127.0.0.1", proxy.port), timeout=2)
        c.sendall(b"x")
        assert c.recv(10) == b"x"
        assert proxy.sever() >= 1
        c.settimeout(2)
        with pytest.raises((ConnectionResetError, BrokenPipeError)):
            for _ in range(5):
                c.sendall(b"y")
                if c.recv(10) == b"":
                    raise ConnectionResetError
        c.close()


def test_proxy_refuse_resets_new_connections(echo_server) -> None:
    with FaultProxy(echo_server) as proxy:
        proxy.refuse()
        with pytest.raises((ConnectionResetError, BrokenPipeError, OSError)):
            assert _roundtrip(proxy.port) == b""
            raise ConnectionResetError
        proxy.heal()
        assert _roundtrip(proxy.port) == b"ping"


def test_proxy_corrupt_flips_bits_and_heals(echo_server) -> None:
    with FaultProxy(echo_server) as proxy:
        proxy.corrupt(1.0, seed=1)
        payload = bytes(range(64))
        got = _roundtrip(proxy.port, payload)
        assert got != payload and len(got) == len(payload)
        assert proxy.chunks_corrupted >= 1
        proxy.heal()
        assert _roundtrip(proxy.port, payload) == payload


def test_proxy_duplicate_delivers_chunk_twice(echo_server) -> None:
    with FaultProxy(echo_server) as proxy:
        proxy.duplicate(1.0)
        with socket.create_connection(("127.0.0.1", proxy.port), timeout=2) as c:
            c.settimeout(1.0)
            c.sendall(b"ab")
            got = b""
            with pytest.raises(TimeoutError):
                while True:
                    chunk = c.recv(64)
                    if not chunk:
                        break
                    got += chunk
        assert got.startswith(b"abab") and proxy.chunks_duplicated >= 1


def test_proxy_reorder_swaps_adjacent_chunks() -> None:
    received: list[bytes] = []
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)

    def sink() -> None:
        conn, _ = srv.accept()
        conn.settimeout(1.0)
        try:
            while data := conn.recv(64):
                received.append(data)
        except OSError:
            pass
        finally:
            conn.close()

    t = threading.Thread(target=sink, daemon=True)
    t.start()
    with FaultProxy(srv.getsockname()) as proxy:
        proxy.reorder(1.0)
        with socket.create_connection(("127.0.0.1", proxy.port), timeout=2) as c:
            c.sendall(b"first")
            time.sleep(0.2)  # force a separate chunk
            c.sendall(b"second")
            t.join(timeout=3)
        assert b"".join(received) == b"secondfirst" and proxy.chunks_reordered == 1
    srv.close()


def test_proxy_truncate_cuts_stream_mid_message(echo_server) -> None:
    with FaultProxy(echo_server) as proxy:
        proxy.truncate_after(4)
        with socket.create_connection(("127.0.0.1", proxy.port), timeout=2) as c:
            c.settimeout(2.0)
            c.sendall(b"0123456789")
            got = b""
            with pytest.raises((ConnectionResetError, TimeoutError)):
                while chunk := c.recv(64):
                    got += chunk
                raise ConnectionResetError
        assert len(got) <= 4 and proxy.streams_truncated >= 1


# ---------------------------------------------------------------------------
# Real-database fault scenarios
# ---------------------------------------------------------------------------


def _assert_all_invariants(result) -> None:  # type: ignore[no-untyped-def]
    failed = [(i.name, i.detail) for i in result.invariants if not i.passed]
    assert not failed, failed
    assert result.invariants, "scenario produced no invariant results"


@pytest.mark.integration
def test_sigkill_after_durable_commit_recovers_forward() -> None:
    r = kill_after_durable_commit(rounds=3)
    _assert_all_invariants(r)
    hits = int(str(r.facts["kills_inside_commit_window"]).split("/")[0])
    assert hits >= 2, r.facts  # the crash really landed after COMMIT, before settlement
    assert r.settled == r.transfers and r.recovered_by_recovery_loop >= 1


@pytest.mark.integration
def test_random_sigkill_bursts_never_break_invariants() -> None:
    r = random_kill_burst(seed=11, rounds=3)
    _assert_all_invariants(r)
    assert r.facts["worker_kills"] >= 1


@pytest.mark.integration
def test_network_latency_does_not_affect_correctness() -> None:
    r = latency_burst()
    _assert_all_invariants(r)
    assert r.facts["worker_finished"] and r.settled == r.transfers == 8


@pytest.mark.integration
def test_partition_of_destination_ledger_blocks_progress_but_not_safety() -> None:
    r = partition_destination()
    _assert_all_invariants(r)
    assert r.facts["progress_during_partition"] == 0  # the partition was effective
    assert r.facts["bytes_dropped_by_partition"] > 0


@pytest.mark.integration
def test_tcp_reset_storm_never_breaks_invariants() -> None:
    r = connection_reset_storm(seed=5)
    _assert_all_invariants(r)
    assert r.facts["connections_reset"] >= 1


@pytest.mark.integration
@pytest.mark.parametrize("fn", [stream_corruption, stream_reorder_duplicate, stream_truncation])
def test_damaged_byte_streams_never_break_safety_invariants(fn) -> None:
    r = fn(seed=7)
    _assert_all_invariants(r)
    # Not vacuous: transfers really ran, the damage really landed, and nothing is left non-terminal.
    assert r.transfers >= 2, r.facts
    assert int(r.facts["chunks_or_streams_damaged"]) >= 1, r.facts


@pytest.mark.integration
def test_api_sigkill_with_idempotent_replay_applies_each_key_once() -> None:
    r = api_kill_idempotent_replay(seed=3, n=24)
    _assert_all_invariants(r)
    assert r.settled == 24


@pytest.mark.integration
def test_negative_control_invariants_detect_unrecovered_crash() -> None:
    """Without recovery, a crash after COMMIT must be *caught* by the invariant checks."""
    env = FaultEnv.create(pair_count=1)
    try:
        env.proxies["ledger-1"].set_latency(120)
        w = WorkerProcess(env, count=1)
        try:
            w.wait_for(lambda: w.count("start") >= 1, 30)
            tid = w.started_ids()[0]
            assert w.wait_for(lambda: transfer_state(tid)[1] == "COMMIT", 30, poll_s=0.002)
            w.kill()
        finally:
            w.kill()
        env.heal_all()
        broken = {i.name: i for i in check_invariants(env)}
        assert not broken["all_transfers_terminal"].passed
        # A committed transfer whose confirms never ran leaves its hold active.
        assert not broken["no_orphaned_holds"].passed
    finally:
        env.close()


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("LEDGERGUARD_ALLOW_CONTAINER_FAULTS") != "1",
    reason="set LEDGERGUARD_ALLOW_CONTAINER_FAULTS=1 to SIGKILL the dev PostgreSQL containers",
)
@pytest.mark.parametrize("service", ["postgres-ledger2", "postgres-coordinator"])
def test_postgres_container_sigkill_and_restart(service: str) -> None:
    from ledgerguard.config import settings

    url = settings.ledger2_db_url if service == "postgres-ledger2" else settings.coordinator_db_url
    _assert_all_invariants(postgres_crash(service, url))
