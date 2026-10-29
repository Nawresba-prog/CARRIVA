"""Vérificateur de liens : serveur HTTP local, aucun accès Internet."""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from backend import check_links as C


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        p = self.path
        if p == "/ok":
            self._send(200, "<html><title>Cours Python</title></html>")
        elif p == "/old":
            self.send_response(301); self.send_header("Location", "/new/page"); self.end_headers()
        elif p == "/new/page":
            self._send(200, "<title>Nouvelle page</title>")
        elif p == "/soft":
            self._send(200, "<title>Page not found</title>")
        elif p == "/deny":
            self._send(403, "")
        elif p == "/boom":
            self._send(500, "")
        else:
            self._send(404, "")

    def _send(self, code, body):
        self.send_response(code); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(body.encode())


def serve():
    s = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_port}"


def test_statuses():
    s, base = serve()
    try:
        got = {p: C.check(base + p, retries=0) for p in ["/ok", "/ok#frag", "/old", "/soft", "/deny", "/gone", "/boom"]}
    finally:
        s.shutdown()
    assert got["/ok"]["status"] == "ok" and got["/ok"]["title"] == "Cours Python"
    assert got["/ok#frag"]["status"] == "ok"
    assert got["/old"]["status"] == "redirige" and got["/old"]["final_url"].endswith("/new/page")
    assert got["/soft"]["status"] == "page_vide"
    assert got["/deny"]["status"] == "bloqué"
    assert got["/gone"]["status"] == "mort"
    assert got["/boom"]["status"] == "erreur"


def test_unreachable_and_retry():
    calls = []

    def flaky(url, timeout=15):
        calls.append(1)
        if len(calls) == 1:
            raise OSError("timeout")
        return 200, url, "<title>ok</title>"
    assert C.check("http://x.test/a", flaky, retries=1, pause=0)["status"] == "ok" and len(calls) == 2
    assert C.check("http://x.test/a", lambda u, timeout=15: (_ for _ in ()).throw(OSError("dns")), retries=0)["status"] == "injoignable"


def test_trailing_slash_and_www_are_not_redirects():
    r = C.classify("https://www.exemple.org/cours/", 200, "https://exemple.org/cours", "<title>Cours</title>")
    assert r["status"] == "ok" and r["final_url"] is None


def test_catalog_urls_unique_and_https():
    items = C.catalog_urls()
    assert len(items) == len({u for u, _ in items}) >= 50
    assert all(u.startswith("https://") for u, _ in items)
