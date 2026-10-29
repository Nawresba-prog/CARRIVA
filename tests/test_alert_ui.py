"""L'interface d'alertes emploi : clés i18n présentes dans les 6 langues, éléments et routes branchés."""
import json, re, pathlib
HTML = (pathlib.Path(__file__).resolve().parent.parent / "frontend" / "index.html").read_text(encoding="utf-8")
KEYS = ["alTitle", "alHint", "alConsent", "alOn", "alOff", "alNone", "alActive", "alAny", "alDone", "alRemoved", "alNeedConsent"]


def test_i18n_alert_keys_all_languages():
    d = json.loads(re.search(r"const I18N_R = (\{.*?\});\n", HTML, re.S).group(1))
    for lang in ("fr", "en", "de", "es", "it", "ar"):
        for k in KEYS:
            assert d[lang].get(k, "").strip(), (lang, k)
    for lang in d:
        assert "{c}" in d[lang]["alActive"] and "{n}" in d[lang]["alActive"]


def test_alert_ui_wired():
    for el in ('id="alConsent"', 'id="alOn"', 'id="alOff"', 'id="alMsg"'):
        assert el in HTML
    assert 'api("/jobs/alerts"' in HTML and "consent: true" in HTML
    assert "r.status === 204 ? null" in HTML
