"""A small fault-injecting TCP proxy (in the spirit of Toxiproxy), with no extra dependency.

Placed between a client and PostgreSQL it can add latency, silently black-hole traffic
(a network partition: connections hang, nothing is delivered), refuse or reset
connections, and sever live connections abruptly (TCP RST). Faults are toggled at runtime
from the test harness, so the system under test experiences genuine socket-level failures.
"""

from __future__ import annotations

import contextlib
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
        self._stopped = threading.Event()
        self._lock = threading.Lock()
        self._live: set[socket.socket] = set()
        self.connections_accepted = 0
        self.bytes_forwarded = 0
        self.bytes_dropped = 0
        self.severed = 0
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

    def heal(self) -> None:
        self._latency_s = 0.0
        self._blackhole = False
        self._refuse = False

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
                dst.sendall(data)
                self.bytes_forwarded += len(data)
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
