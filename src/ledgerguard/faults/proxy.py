"""A small fault-injecting TCP proxy (in the spirit of Toxiproxy), with no extra dependency.

Placed between a client and PostgreSQL it can add latency, silently black-hole traffic
(a network partition: connections hang, nothing is delivered), refuse or reset
connections, sever live connections abruptly (TCP RST), and damage the byte stream itself:
corrupt bytes, swap adjacent chunks (reordering), duplicate chunks, or truncate a stream
mid-message. Real TCP never does the last four (its checksums and sequence numbers prevent
them), so they model a buggy middlebox or a failing NIC; the point is that the system must
stay *safe* (never wrong money), not that it must stay live. Faults are toggled at runtime
from the test harness, so the system under test experiences genuine socket-level failures.
"""

from __future__ import annotations

import contextlib
import random
import socket
import struct
import threading
import time


def _rst_close(sock: socket.socket) -> None:
    """Close with SO_LINGER(0) so the peer sees a connection reset, not a clean FIN."""
    with contextlib.suppress(OSError):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    with contextlib.suppress(OSError):
        sock.close()


class FaultProxy:
    """Transparent TCP forwarder with switchable faults."""

    def __init__(self, upstream: tuple[str, int], listen_host: str = "127.0.0.1", port: int = 0):
        self.upstream = upstream
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind((listen_host, port))
        self._listener.listen(128)
        self.host = listen_host
        self.port: int = self._listener.getsockname()[1]
        self._latency_s = 0.0
        self._blackhole = False
        self._refuse = False
        self._corrupt_rate = 0.0
        self._reorder_rate = 0.0
        self._duplicate_rate = 0.0
        self._truncate_after: int | None = None
        self._rng = random.Random(0)
        self._stopped = threading.Event()
        self._lock = threading.Lock()
        self._live: set[socket.socket] = set()
        self.connections_accepted = 0
        self.bytes_forwarded = 0
        self.bytes_dropped = 0
        self.severed = 0
        self.chunks_corrupted = 0
        self.chunks_reordered = 0
        self.chunks_duplicated = 0
        self.streams_truncated = 0
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> FaultProxy:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stopped.set()
        with contextlib.suppress(OSError):
            self._listener.close()
        self.sever()

    def __enter__(self) -> FaultProxy:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()

    # -- fault controls ----------------------------------------------------

    def set_latency(self, milliseconds: float) -> None:
        self._latency_s = max(0.0, milliseconds / 1000.0)

    def blackhole(self) -> None:
        """Network partition: accept and hold connections, deliver nothing either way."""
        self._blackhole = True

    def refuse(self) -> None:
        """Reset every new connection immediately (as if the server were down)."""
        self._refuse = True

    def corrupt(self, rate: float, seed: int = 0) -> None:
        """Flip one random bit in a forwarded chunk with probability ``rate`` (seeded)."""
        self._rng = random.Random(seed)
        self._corrupt_rate = rate

    def reorder(self, rate: float, seed: int = 0) -> None:
        """Hold a chunk back and deliver it after the next one with probability ``rate``."""
        self._rng = random.Random(seed)
        self._reorder_rate = rate

    def duplicate(self, rate: float, seed: int = 0) -> None:
        """Deliver a chunk twice with probability ``rate``."""
        self._rng = random.Random(seed)
        self._duplicate_rate = rate

    def truncate_after(self, nbytes: int) -> None:
        """Forward at most ``nbytes`` more bytes per stream, then reset it mid-message."""
        self._truncate_after = nbytes

    def heal(self) -> None:
        self._latency_s = 0.0
        self._blackhole = False
        self._refuse = False
        self._corrupt_rate = 0.0
        self._reorder_rate = 0.0
        self._duplicate_rate = 0.0
        self._truncate_after = None

    def sever(self) -> int:
        """Abruptly reset every live connection (mid-flight crash of the link)."""
        with self._lock:
            socks = list(self._live)
            self._live.clear()
        for s in socks:
            _rst_close(s)
        self.severed += len(socks)
        return len(socks)

    # -- internals ---------------------------------------------------------

    def _track(self, *socks: socket.socket) -> None:
        with self._lock:
            self._live.update(socks)

    def _untrack(self, *socks: socket.socket) -> None:
        with self._lock:
            for s in socks:
                self._live.discard(s)

    def _accept_loop(self) -> None:
        while not self._stopped.is_set():
            try:
                client, _ = self._listener.accept()
            except OSError:
                return
            self.connections_accepted += 1
            threading.Thread(target=self._serve, args=(client,), daemon=True).start()

    def _serve(self, client: socket.socket) -> None:
        if self._refuse:
            _rst_close(client)
            return
        upstream: socket.socket | None = None
        if not self._blackhole:
            try:
                upstream = socket.create_connection(self.upstream, timeout=5)
                upstream.settimeout(None)
            except OSError:
                _rst_close(client)
                return
        self._track(client, *(upstream,) if upstream else ())
        done = threading.Event()
        threading.Thread(target=self._pump, args=(client, upstream, done), daemon=True).start()
        if upstream is not None:
            threading.Thread(target=self._pump, args=(upstream, client, done), daemon=True).start()

    def _pump(self, src: socket.socket, dst: socket.socket | None, done: threading.Event) -> None:
        held: bytes | None = None  # a chunk delayed by reordering
        sent = 0
        try:
            while not self._stopped.is_set():
                data = src.recv(65536)
                if not data:
                    break
                if self._blackhole or dst is None:
                    self.bytes_dropped += len(data)
                    continue
                if self._latency_s:
                    time.sleep(self._latency_s)
                if self._corrupt_rate and self._rng.random() < self._corrupt_rate:
                    buf = bytearray(data)
                    buf[self._rng.randrange(len(buf))] ^= 1 << self._rng.randrange(8)
                    data = bytes(buf)
                    self.chunks_corrupted += 1
                limit = self._truncate_after
                if limit is not None and sent + len(data) > limit:
                    dst.sendall(data[: max(0, limit - sent)])
                    self.streams_truncated += 1
                    _rst_close(dst)
                    _rst_close(src)
                    return
                chunks = [data]
                if self._duplicate_rate and self._rng.random() < self._duplicate_rate:
                    chunks.append(data)
                    self.chunks_duplicated += 1
                if self._reorder_rate and held is None and self._rng.random() < self._reorder_rate:
                    held = chunks.pop(0)
                    self.chunks_reordered += 1
                elif held is not None:
                    chunks.append(held)  # deliver the later chunk first, then the held one
                    held = None
                for chunk in chunks:
                    dst.sendall(chunk)
                    sent += len(chunk)
                    self.bytes_forwarded += len(chunk)
        except OSError:
            pass
        finally:
            done.set()
            for s in (src, dst):
                if s is not None:
                    with contextlib.suppress(OSError):
                        s.shutdown(socket.SHUT_RDWR)
                    with contextlib.suppress(OSError):
                        s.close()
            self._untrack(src, *(dst,) if dst else ())
