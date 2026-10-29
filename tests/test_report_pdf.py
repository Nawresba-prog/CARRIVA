import io
import pytest
from backend import pdf_gen, report_pdf as r

BLOCKS = [{"t": "h2", "text": "Plan de retouche"}, {"t": "p", "text": "Contrôlez la source → 2000 px ≈ 160 h ★"}, {"t": "li", "text": "Étape 1 · Upscayl"},
          {"t": "kv", "k": "Contraste", "v": "+16"}, {"t": "kv", "k": "Netteté", "v": "+55"}, {"t": "kv", "k": "Clarté", "v": "+14"}, {"t": "kv", "k": "Bruit", "v": "+20"},
          {"t": "table", "head": ["Temps", "Plan", "Voix"], "rows": [["00:00 – 00:03", "Gros plan <b>produit</b> & logo", "« Regardez »"]] * 40}, {"t": "pre", "text": "# RÔLE\nTu es mon tuteur\n- règle"}]


def _text_pages(pdf: bytes) -> int:
    import pypdf
    return len(pypdf.PdfReader(io.BytesIO(pdf)).pages)


def test_render_produces_valid_multipage_pdf():
    out = r.render("Spot vidéo — Crème bio", BLOCKS, "fr", "30 s · Reels")
    assert out[:5] == b"%PDF-" and out.rstrip().endswith(b"%%EOF")
    assert _text_pages(out) >= 2


def test_all_latin_languages_and_markup_is_escaped():
    for lang in ("fr", "en", "de", "es", "it"):
        assert r.render("Titre <b>x</b> & co", BLOCKS, lang)[:5] == b"%PDF-"


def test_clean_removes_unrenderable_and_control_chars():
    assert r.clean("a→b ≈ c ✓ \x00\x07 😀 é") == "a->b ~ c é"
    assert "\x00" not in r.clean("a\x00b") and "😀" not in r.clean("x😀y")
    assert r.clean("a→b") == "a->b" and r.clean("≤") == "<="


def test_normalise_limits_and_rejects_empty():
    for bad in ([], None, "x", [{"t": "zzz"}], [{"t": "p", "text": "   "}]):
        with pytest.raises(r.ReportError):
            r.normalise(bad)
    big = [{"t": "p", "text": "x" * 20000}] * 3 + [{"t": "table", "head": list("abcdefghij"), "rows": [list("0123456789")] * 400}]
    n = r.normalise(big)
    assert all(len(b["text"]) <= r.MAX_TEXT for b in n if b["t"] == "p")
    t = [b for b in n if b["t"] == "table"][0]
    assert len(t["rows"]) == r.MAX_ROWS and len(t["head"]) == r.MAX_COLS
    assert len(r.normalise([{"t": "p", "text": "x"}] * 5000)) == r.MAX_BLOCKS


def test_ragged_table_is_padded():
    t = r.normalise([{"t": "table", "head": ["a"], "rows": [["1", "2", "3"], ["4"]]}])[0]
    assert len(t["head"]) == 3 and all(len(x) == 3 for x in t["rows"])


def test_arabic_requires_font_when_missing():
    saved = pdf_gen._ar_ok
    try:
        pdf_gen._ar_ok = False
        with pytest.raises(r.ReportError):
            r.render("عنوان", [{"t": "p", "text": "مرحبا"}], "ar")
        assert r.render("Titre", [{"t": "p", "text": "ok"}], "ar")[:5] == b"%PDF-"      # arabe sans texte arabe : toujours possible
    finally:
        pdf_gen._ar_ok = saved
