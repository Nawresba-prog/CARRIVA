"""Contrôles statiques de l'interface : parité i18n, ids uniques, noms accessibles, brouillons sans données sensibles."""
import collections, json, pathlib, re

HTML = (pathlib.Path(__file__).resolve().parent.parent / "frontend" / "index.html").read_text(encoding="utf-8")
HTML += (pathlib.Path(__file__).resolve().parent.parent / "frontend" / "app.css").read_text(encoding="utf-8")  # CSS séparé (app.css)
LANGS = ("fr", "en", "de", "es", "it", "ar")


def _json_blocks():
    out = {}
    for name, body in re.findall(r"^const (I18N_\w+) = (\{.*?\});\n", HTML, re.S | re.M):
        out[name] = json.loads(body)
    return out


def test_every_json_block_has_the_same_keys_in_all_languages():
    for name, d in _json_blocks().items():
        assert set(d) == set(LANGS), name
        ref = set(d["fr"])
        for lang in LANGS:
            assert set(d[lang]) == ref, (name, lang, sorted(ref ^ set(d[lang]))[:8])
            assert all(isinstance(v, str) and v.strip() for v in d[lang].values()), (name, lang)


def test_placeholders_match_across_languages():
    for name, d in _json_blocks().items():
        for k in d["fr"]:
            sets = {frozenset(re.findall(r"\{(\w+)\}", d[l][k])) for l in LANGS}
            assert len(sets) == 1, (name, k)


def test_ids_unique_and_no_duplicate_top_level_consts():
    ids = re.findall(r'\bid="([^"]+)"', HTML)
    assert not [k for k, v in collections.Counter(ids).items() if v > 1]
    consts = re.findall(r"^(?:const|let) (\w+)", HTML, re.M)
    assert not [k for k, v in collections.Counter(consts).items() if v > 1]


def test_free_text_areas_have_accessible_names():
    # textarea sans label : le nom accessible vient du placeholder (copié en aria-label par applyLang)
    assert 'textarea[data-i18n-ph], input[data-i18n-ph]' in HTML and "setAttribute(\"aria-label\", e.placeholder)" in HTML


def test_drafts_never_store_sensitive_fields():
    assert "/consent/i.test(f.id)" in HTML
    for forbidden in ('"file"', '"password"'):
        assert forbidden in HTML.split("const drField")[1].split("\n")[0]
    for k in ("mail", "gMail", "invoice", "gInvoice"):      # e-mails reçus et factures : jamais en brouillon
        assert not re.search(r"drGroup = \{[^}]*%s" % k, HTML)
    assert "DR.ttl" in HTML and "30 * 864e5" in HTML
    assert 'id="drClear"' in HTML


def test_status_cleared_on_navigation_and_tabs_keyboard():
    assert 'ev.target.closest(".menu button, #gMenu .rolebtn, [role=tab]")) status("")' in HTML
    assert '"ArrowLeft", "ArrowRight", "Home", "End"' in HTML


def test_contrast_safe_badge_colours():
    assert "#7C3AED" in HTML and "#E11D48" in HTML and "#8B5CF6;color:#fff" not in HTML and "#F43F5E;color:#fff" not in HTML


def test_pdf_export_buttons_and_observer_guard():
    for src in ("liOut", "atsOut", "spOut", "rtOut", "stOut"):
        assert f'data-src="{src}"' in HTML, src
    assert "pdfBlocks" in HTML and "/export/pdf" in HTML
    assert "exp_pdf" in HTML and "exp_ar_font" in HTML


def test_voice_input_keys_translated_in_every_language():
    used = set(("vo_title vo_hint vo_guide vo_dictate vo_speak vo_repeat vo_skip vo_stop vo_stopped vo_listening vo_say vo_heard vo_done "
                "vo_more_xp vo_more_edu vo_unsupported vo_denied vo_nomic vo_net vo_nospeech vo_pick").split())
    for k in used: assert f'"{k}"' in HTML or f'{k}"' in HTML, k
    blocks = dict(re.findall(r"^const (I18N_R) = (\{.*?\});\n", HTML, re.S | re.M))
    d = json.loads(blocks["I18N_R"])
    for lang in ("fr", "en", "de", "es", "it", "ar"):
        missing = [k for k in used if not d[lang].get(k)]
        assert not missing, (lang, missing)
    assert "SpeechRecognition" in HTML and 'id="voBox"' in HTML


def test_messaging_tab_wired_and_translated():
    for needle in ('id="mTabW"', 'id="mPanW"', 'id="chMsg"', '"/chat/reply"', "wa.me", 'data-src="chOut"'):
        assert needle in HTML, needle
    d = json.loads(re.search(r"^const I18N_R = (\{.*?\});\n", HTML, re.S | re.M).group(1))
    keys = {k for k in d["fr"] if k.startswith("ch_")}
    assert len(keys) >= 40
    for lang in ("en", "de", "es", "it", "ar"):
        assert keys <= {k for k in d[lang] if k.startswith("ch_")}, lang
    for k in re.findall(r'data-i18n(?:-ph)?="(ch_[a-z_0-9]+)"', HTML):
        assert k in keys, k


def test_brand_service_is_first_button_and_wired():
    menu = re.search(r'<div class="omenu" id="gMenu">(.*?)</div>', HTML, re.S).group(1)
    order = re.findall(r'data-svc="(\d)".*?<span class="n">(\d)</span>', menu, re.S)
    assert order == [("7", "1"), ("1", "2"), ("2", "3"), ("3", "4"), ("4", "5"), ("5", "6"), ("6", "7")], order
    for needle in ('id="gBrand"', 'id="brGo"', '"/brand/kit"', "if(n === 7)", 'data-src="brOut"'):
        assert needle in HTML, needle
    d = json.loads(re.search(r"^const I18N_R = (\{.*?\});\n", HTML, re.S | re.M).group(1))
    keys = {k for k in d["fr"] if k.startswith("br_")}
    assert len(keys) >= 55
    for lang in ("en", "de", "es", "it", "ar"):
        assert keys <= {k for k in d[lang] if k.startswith("br_")}, lang
    for k in re.findall(r'(?:data-i18n|t\()="?"?(br_[a-z_]+)', HTML): assert k in keys, k
    assert "(1 à 7)" in HTML and "(1 à 6)" not in HTML and "(1 à 4)" not in HTML


def test_ai_input_processing_wired_everywhere():
    for needle in ('id="aiGlobal"', "AI.inject(path, opts)", '"/spots/campaign": "spOut"', '"/strategy/diagnostic": "stOut"', '"/chat/reply": "chOut"', "AI.on()"):
        assert needle in HTML, needle
    d = json.loads(re.search(r"^const I18N_R = (\{.*?\});\n", HTML, re.S | re.M).group(1))
    keys = "ai_global ai_global_hint ai_s_ok ai_s_off ai_s_failed ai_s_skipped ai_n ai_changes".split()
    for lang in ("fr", "en", "de", "es", "it", "ar"):
        assert all(d[lang].get(k) for k in keys), lang
    app = (pathlib.Path(__file__).resolve().parent.parent / "backend" / "app.py").read_text(encoding="utf-8")
    assert app.count("_proc(user, req.ai") == 3 and "ai_input" in app


def test_bootstrap_button_7_is_wired():
    menu = re.search(r'<nav class="menu">(.*?)</nav>', HTML, re.S).group(1)
    assert re.findall(r'data-p="(\w+)"', menu) == ["cv", "jobs", "ats", "apply", "train", "li", "boot"]
    assert re.search(r'data-p="boot".*?<span class="n">7</span>', menu, re.S)
    for needle in ('id="p-boot"', 'id="btGo"', '"/bootstrap/analyze"', 'data-src="btOut"', 'id="btMp"'):
        assert needle in HTML, needle
    d = json.loads(re.search(r"^const I18N_R = (\{.*?\});\n", HTML, re.S | re.M).group(1))
    keys = {k for k in d["fr"] if k.startswith("bt_")} | {"b_boot"}
    assert len(keys) >= 40
    for lang in ("en", "de", "es", "it", "ar"):
        assert keys <= set(d[lang]), lang
    for k in re.findall(r'data-i18n(?:-ph)?="((?:bt_|b_boot)[a-z_0-9]*)"', HTML):
        assert k in keys, k
    assert "btCv" not in re.search(r"drGroup\(.*", HTML).group(0) if re.search(r"drGroup\(.*", HTML) else True
