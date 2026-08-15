from __future__ import annotations

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


class _FixtureHTTPServer(ThreadingHTTPServer):
    def handle_error(self, request: object, client_address: object) -> None:
        error = sys.exc_info()[1]
        if isinstance(error, (BrokenPipeError, ConnectionResetError)):
            return
        super().handle_error(request, client_address)


class FixtureServer:
    """Serve packaged fixtures on loopback with reset-by-reload state."""

    def __init__(self, port: int = 0) -> None:
        fixture_directory = Path(__file__).with_name("fixtures")
        handler = partial(_QuietHandler, directory=str(fixture_directory))
        self._server = _FixtureHTTPServer(("127.0.0.1", port), handler)
        self._server.daemon_threads = True
        self._thread = Thread(target=self._server.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    def url(self, fixture: str, *, variant: str = "clean") -> str:
        query = urlencode({"variant": variant})
        return f"http://127.0.0.1:{self.port}/{fixture}?{query}"

    def __enter__(self) -> FixtureServer:
        self._thread.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
