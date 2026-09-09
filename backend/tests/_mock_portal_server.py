"""Phase 09 — stdlib HTTP bootstrap fixture for the MOCK Udyam portal.

Why stdlib instead of aiohttp?
  * ``http.server`` + ``socketserver`` ship with Python — no new
    dependency in ``requirements.txt`` for a test-only fixture.
  * The mock portal serves exactly two routes: ``/`` (HTML) and
    ``/sample_cert.pdf`` (PDF). Async I/O buys nothing here; the
    browser hit rate is one request per Playwright step.
  * ``socketserver.TCPServer`` with ``bind((host, 0))`` picks a free
    localhost port — same pattern as the aiohttp version, no TOCTOU
    race because pytest-xdist is not enabled.

Usage::

    from tests._mock_portal_server import start_mock_portal

    async def test_x():
        async with start_mock_portal() as base_url:
            settings.PORTAL_BASE_URL = base_url
            ...
"""
from __future__ import annotations

import logging
import socket
import socketserver
import threading
from contextlib import asynccontextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import AsyncIterator

logger = logging.getLogger("taxla.test.mock_portal")

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "mock_portal"


def _pick_free_port(host: str = "127.0.0.1") -> int:
    """Bind to :0 on ``host`` and read back the assigned port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, 0))
        return s.getsockname()[1]


def _make_handler(fixture_dir: Path):
    """Build a ``BaseHTTPRequestHandler`` subclass bound to ``fixture_dir``.

    We deliberately do NOT log to stderr — pytest captures stderr and
    the per-request log spam drowns out real test failures. Anything
    interesting can be added to the body of the response.
    """

    class _MockPortalHandler(BaseHTTPRequestHandler):
        # Silence the default per-request stderr access log.
        def log_message(self, format: str, *args) -> None:  # noqa: A002
            return

        def do_GET(self) -> None:  # noqa: N802 — stdlib API
            # Strip the query string for routing — the mock portal uses
            # query params to trigger error-matrix banners (?captcha=1,
            # ?invalid_aadhaar=1, ?pan_duplicate=1).
            from urllib.parse import urlsplit

            path = urlsplit(self.path).path
            if path in ("/", "/index.html"):
                self._serve_file(fixture_dir / "index.html", "text/html; charset=utf-8")
                return
            if path == "/sample_cert.pdf":
                self._serve_file(fixture_dir / "sample_cert.pdf", "application/pdf")
                return
            self.send_error(404, f"Not Found: {path}")

        def _serve_file(self, path: Path, content_type: str) -> None:
            if not path.exists():
                self.send_error(404, f"{path.name} missing")
                return
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            # Force a download for the PDF so Playwright's expect_download
            # context fires on the anchor click.
            if path.suffix == ".pdf":
                self.send_header(
                    "Content-Disposition",
                    f'attachment; filename="{path.name}"',
                )
            self.end_headers()
            self.wfile.write(body)

    return _MockPortalHandler


@asynccontextmanager
async def start_mock_portal(host: str = "127.0.0.1") -> AsyncIterator[str]:
    """Boot the MOCK portal on a free port; yield ``http://host:port``; tear down.

    The caller is responsible for assigning the yielded URL to
    ``settings.PORTAL_BASE_URL`` so ``portal_selectors.get_selectors()``
    resolves to ``http://host:port/`` for the duration of the test.
    """
    port = _pick_free_port(host)
    handler_cls = _make_handler(FIXTURE_DIR)
    server = ThreadingHTTPServer((host, port), handler_cls)
    thread = threading.Thread(target=server.serve_forever, name="mock-portal", daemon=True)
    thread.start()
    base_url = f"http://{host}:{port}"
    logger.info("mock_portal: serving %s (fixture_dir=%s)", base_url, FIXTURE_DIR)
    try:
        yield base_url
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


def fixture_dir() -> Path:
    """Public accessor for the fixture directory (used by other fixtures)."""
    return FIXTURE_DIR