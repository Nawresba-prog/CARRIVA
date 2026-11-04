import re, backend.portfolio_site as P

CV = {"full_name": "Sara Haddad", "email": "sara@example.com", "phone": "+216 20 123 456", "city": "Tunis", "country": "Tunisie", "summary": "Développeuse Python.",
      "skills": ["Python:90", "SQL:75", "Docker"],
      "experiences": [{"title": "Développeuse", "company": "ACME", "start": "2018-01", "end": "2024-01", "description": "API Python et SQL"}],
      "education": [{"degree": "Master", "school": "ENIT", "start": "2015", "end": "2017"}], "languages": [{"name": "Français", "level": "C1"}]}


def build(**k):
    return P.build({"cv": CV, "lang": "fr", "headline": "Ingénieure logicielle", "whatsapp": "+216 20 123 456", "linkedin": "https://linkedin.com/in/sara",
                    "photo_url": "https://example.com/p.jpg", "projects": "API de paie | Service REST | https://example.com", **k})


def test_page_has_all_requested_blocks():
    h = build()["html"]
    for needle in ("cdn.tailwindcss.com", "font-awesome", 'class="dark"', "avatar", "timeline", "bar-track", "IntersectionObserver", "position:fixed", "tel:+216", "wa.me/216", "linkedin.com/in/sara", "API de paie"):
        assert needle in h, needle
    assert 'name="viewport"' in h and "@media" in h


def test_all_languages_and_rtl():
    for l in P.LANGS:
        r = build(lang=l)
        assert r["html"].startswith("<!doctype html>") and r["lang"] == l
    assert 'dir="rtl"' in build(lang="ar")["html"] and 'dir="ltr"' in build(lang="fr")["html"]


def test_nothing_invented_and_placeholders_flagged():
    r = P.build({"cv": {"full_name": "Zed"}, "lang": "fr"})
    assert set(r["warnings"]) >= {"headline", "experience", "projects", "phone", "linkedin", "skills"}
    assert "À COMPLÉTER" in r["html"]


def test_user_text_is_escaped_and_links_are_safe():
    r = P.build({"cv": {**CV, "full_name": "<script>alert(1)</script>", "summary": "<img src=x onerror=alert(1)>"}, "lang": "fr", "linkedin": "javascript:alert(1)", "whatsapp": "<b>1</b>",
                 "projects": "X | <b>y</b> | javascript:alert(1)", "photo_url": "javascript:alert(1)"})
    h = r["html"]
    assert "<script>alert(1)" not in h and "<img src=x" not in h and "javascript:" not in h.lower().replace("javascript:alert(1)</", "")
    assert not re.search(r'href="javascript:', h, re.I) and not re.search(r'src="javascript:', h, re.I)


def test_portfolio_v2_nav_theme_print_vcard_qr_jsonld():
    from backend.qr_js import QR_JS
    from pathlib import Path
    assert QR_JS == (Path(__file__).resolve().parents[1] / "frontend" / "qr.js").read_text(encoding="utf-8")
    h = build()["html"]
    for needle in ("topnav", 'id="themeBtn"', 'id="printBtn"', "html.light", "@media print", "data-spy", 'id="toTop"', "CARRIVA_QR", 'id="qrDlg"', "application/ld+json", "BEGIN%3AVCARD", ".vcf"):
        assert needle in h, needle
    assert "BEGIN:VCARD" not in h.split("<body")[1].split("data:text/vcard")[0]
    x = P.build({"cv": {**CV, "full_name": "</script><b>x"}, "lang": "en"})["html"]
    assert "</script><b>" not in x and "\\u003c/script" in x


def test_brand_site_has_qr():
    from backend import brand_site
    r = brand_site.reply({"name": "Café Lune", "sector": "restaurant", "lang": "fr"})
    h = r["site_html"] if "site_html" in r else r.get("site", {}).get("html", "")
    assert 'id="qrDlg"' in h and "CARRIVA_QR" in h
