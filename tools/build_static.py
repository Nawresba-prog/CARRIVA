"""Construit la version 100 % navigateur dans dist/ (HTML + agents Python exécutés par Pyodide), prête pour GitHub Pages.

Usage :  python tools/build_static.py [--pyodide DOSSIER] [--out dist]
  --pyodide : dossier du « pyodide-core » (pyodide.js, pyodide.asm.wasm, python_stdlib.zip…) copié dans dist/pyodide/ ;
              sans cette option, la page charge Pyodide depuis le CDN jsDelivr (version épinglée)."""
from __future__ import annotations
import argparse, json, re, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYODIDE_VERSION = "0.27.7"
CDN = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
# modules purs (sans serveur, sans dépendance externe) utilisés par backend/static_api.py
MODULES = ["__init__", "static_api"]   # les dépendances internes (from . import x) sont ajoutées automatiquement
DATA = ["catalog_i18n.json", "bootstrap_prompt.txt"]

SW = '''/* Service worker de la version statique : page d'abord réseau (copie hors ligne en secours), moteur Pyodide mis en cache pour le hors-ligne. */
const VERSION = "carriva-static-v1";
const SHELL = ["./", "cv-templates.js", "qr.js", "app.css", "manifest.webmanifest", "static-shim.js", "py/files.json", "icons/icon-192.png", "icons/icon-512.png"];
self.addEventListener("install", e => { e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", e => {
  const req = e.request; if(req.method !== "GET") return;
  const url = new URL(req.url);
  if(url.pathname.includes("/pyodide/") || url.hostname === "cdn.jsdelivr.net"){
    e.respondWith(caches.match(req).then(h => h || fetch(req).then(r => { if(r.ok){ const c = r.clone(); caches.open(VERSION).then(x => x.put(req, c)); } return r; })));
    return;
  }
  if(url.origin !== location.origin) return;
  e.respondWith(fetch(req).then(r => { if(r.ok){ const c = r.clone(); caches.open(VERSION).then(x => x.put(req, c)); } return r; }).catch(() => caches.match(req).then(h => h || caches.match("./"))));
});
'''


def closure(mods: list[str]) -> list[str]:
    """Ajoute récursivement les modules du paquet importés par `from . import a, b` ou `from .a import …`."""
    seen, todo = [], list(mods)
    while todo:
        m = todo.pop()
        if m in seen:
            continue
        seen.append(m)
        src = (ROOT / "backend" / f"{m}.py").read_text(encoding="utf-8")
        for g in re.findall(r"^\s*from \. import ([\w, ]+)", src, re.M):
            todo += [x.strip() for x in g.split(",") if x.strip()]
        todo += re.findall(r"^\s*from \.(\w+) import", src, re.M)
    return sorted(seen)


def build(out: Path, pyodide: Path | None) -> None:
    if out.exists():
        shutil.rmtree(out)
    (out / "py").mkdir(parents=True)
    fe = ROOT / "frontend"
    for name in ("app.css", "cv-templates.js", "qr.js", "static-shim.js"):
        shutil.copy(fe / name, out / name)
    shutil.copytree(fe / "icons", out / "icons")
    html = (fe / "index.html").read_text(encoding="utf-8")
    for a, b in (('href="/manifest.webmanifest"', 'href="manifest.webmanifest"'), ('href="/icons/', 'href="icons/'), ('href="/app.css"', 'href="app.css"'), ('register("/sw.js"', 'register("sw.js"')):
        assert a in html, a
        html = html.replace(a, b)
    assert 'let TPL = "europass";' in html
    html = html.replace('let TPL = "europass";', 'let TPL = "modern";')   # le PDF « Europass » est fait par le serveur : la version navigateur démarre sur un modèle dessiné dans le navigateur
    base = "pyodide/" if pyodide else CDN
    shim = f'<script>window.PYODIDE_BASE = {json.dumps(base)};</script>\n<script src="static-shim.js"></script>\n'
    html = html.replace("<script>", shim + "<script>", 1)   # avant le premier script de la page
    (out / "index.html").write_text(html, encoding="utf-8")
    man = json.loads((fe / "manifest.webmanifest").read_text(encoding="utf-8"))
    man["start_url"], man["scope"] = "./", "./"
    for ic in man.get("icons", []):
        ic["src"] = ic["src"].lstrip("/")
    (out / "manifest.webmanifest").write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "sw.js").write_text(SW, encoding="utf-8")
    files = {f"backend/{m}.py": (ROOT / "backend" / f"{m}.py").read_text(encoding="utf-8") for m in closure(MODULES)}
    for d in DATA:
        files[f"backend/{d}"] = (ROOT / "backend" / d).read_text(encoding="utf-8")
    (out / "py" / "files.json").write_text(json.dumps(files, ensure_ascii=False), encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    if pyodide:
        (out / "pyodide").mkdir()
        for name in ("pyodide.js", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json", "package.json"):
            shutil.copy(pyodide / name, out / "pyodide" / name)
    print("OK :", out, "|", sum(len(v) for v in files.values()) // 1024, "Ko de Python |", "Pyodide local" if pyodide else "Pyodide via CDN")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pyodide"); ap.add_argument("--out", default="dist")
    a = ap.parse_args()
    build(ROOT / a.out, Path(a.pyodide) if a.pyodide else None)
