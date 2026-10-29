"""PWA : manifeste valide, icônes présentes, service worker qui ne met jamais l'API en cache, liens dans index.html, routes serveur."""
import json, re, struct
from pathlib import Path
F = Path(__file__).resolve().parent.parent / "frontend"
APP = (Path(__file__).resolve().parent.parent / "backend" / "app.py").read_text(encoding="utf-8")
HTML = (F / "index.html").read_text(encoding="utf-8")


def png_size(p):
    b = p.read_bytes(); assert b[:8] == b"\x89PNG\r\n\x1a\n"; return struct.unpack(">II", b[16:24])


def test_manifest():
    m = json.loads((F / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert m["name"] == "CARRIVA" and m["display"] == "standalone" and m["start_url"] == "/"
    sizes = {i["sizes"]: i for i in m["icons"]}
    assert "192x192" in sizes and "512x512" in sizes and any(i["purpose"] == "maskable" for i in m["icons"])
    for i in m["icons"]:
        w, h = png_size(F / i["src"].lstrip("/")); assert f"{w}x{h}" == i["sizes"]


def test_service_worker_never_caches_api():
    sw = (F / "sw.js").read_text(encoding="utf-8")
    assert 'req.method !== "GET"' in sw and "url.origin !== self.location.origin" in sw
    static = re.search(r"const STATIC = (/.+/);", sw).group(1)
    for api in ("/auth/login", "/jobs/search", "/cv/generate", "/mail/inbox", "/export/pdf", "/trainings/standard"):
        assert not re.search(static.strip("/"), api), api


def test_wiring():
    for needle in ('rel="manifest"', 'name="theme-color"', 'apple-touch-icon', 'serviceWorker'):
        assert needle in HTML, needle
    for r in ('"/manifest.webmanifest"', '"/sw.js"', '"/icons/{name}"'):
        assert r in APP, r
    assert (F / "icons" / "apple-touch-icon.png").exists()


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"): f(); print("ok", n)
    print("ALL PASS")
