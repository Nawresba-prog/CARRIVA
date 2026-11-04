import json, re, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import build_static as BS
import backend.static_api as A


def _build(tmp):
    out = Path(tmp) / "dist"
    BS.build(out, None)
    return out


def test_build_is_relative_and_complete():
    with tempfile.TemporaryDirectory() as tmp:
        out = _build(tmp)
        html = (out / "index.html").read_text(encoding="utf-8")
        for bad in ('href="/', 'src="/', 'register("/'):
            assert bad not in html, bad
        assert html.index("static-shim.js") < html.index('register("sw.js"')          # le shim est chargé avant le code de la page
        assert "cdn.jsdelivr.net/pyodide/v" + BS.PYODIDE_VERSION in html
        files = json.loads((out / "py" / "files.json").read_text(encoding="utf-8"))
        for need in ("backend/static_api.py", "backend/bootstrap_biz.py", "backend/matching.py", "backend/catalog_i18n.json", "backend/bootstrap_prompt.txt", "backend/__init__.py"):
            assert need in files, need
        assert not any(k.endswith("app.py") for k in files)                          # le serveur FastAPI n'est jamais embarqué
        man = json.loads((out / "manifest.webmanifest").read_text(encoding="utf-8"))
        assert man["start_url"] == "./" and all(not i["src"].startswith("/") for i in man["icons"])
        assert 'let TPL = "modern";' in html


def test_every_embedded_module_only_uses_embedded_or_stdlib():
    mods = set(BS.closure(BS.MODULES))
    for m in mods:
        src = (BS.ROOT / "backend" / f"{m}.py").read_text(encoding="utf-8")
        for imp in re.findall(r"^(?:from|import) ([\w.]+)", src, re.M):
            top = imp.split(".")[0]
            assert top not in ("fastapi", "pydantic", "httpx", "jwt", "qdrant_client", "langgraph", "reportlab", "numpy", "lxml", "arabic_reshaper"), (m, imp)


def test_static_api_routes():
    ok = lambda p, b: json.loads(A.handle("POST", p, "", json.dumps(b)))
    r = ok("/bootstrap/analyze", {"cv_text": "Développeur Python et SQL, 8 ans d'expérience, manager.", "idea": 1, "price": "100", "var_cost": "10", "fixed": "300"})
    assert r["status"] == 200 and r["json"]["plan"]
    assert ok("/brand/kit", {"name": "Nour", "sector": "cosmétique", "ai": True})["json"]["processing"]["ai"] == "off"
    assert ok("/chat/reply", {"message": "How much is it?"})["status"] == 200
    assert ok("/spots/campaign", {"product": "crème"})["status"] == 200
    assert "<!doctype html>" in ok("/portfolio/site", {"cv": {"full_name": "Sara"}, "lang": "fr"})["json"]["html"]
    assert ok("/bootstrap/analyze", {"cv_text": "x"})["status"] == 422
    assert ok("/cv", {"full_name": "Sara Haddad", "email": "s@x.com"})["json"]["europass"]["personal"]
    assert json.loads(A.handle("GET", "/auth/mode"))["json"]["mode"] == "dev"
    assert json.loads(A.handle("GET", "/trainings/standard", "lang=en"))["status"] == 200
    for p in ("/mail/send", "/jobs/match", "/export/pdf", "/cv/pdf", "/invoices/preview"):
        assert json.loads(A.handle("POST", p, "", "{}"))["status"] == 501, p
    assert json.loads(A.handle("POST", "/bootstrap/analyze", "", "{not json"))["status"] in (422, 500)
