import hashlib

from backend import cert_design, pdf_gen


def test_theme_for_category():
    assert cert_design.theme_for({"category": "languages"}) == "languages"
    assert cert_design.theme_for({"category": "web"}) == "web"
    assert cert_design.theme_for({"category": "marketing"}) == "marketing"


def test_theme_for_skills_vote():
    assert cert_design.theme_for({"category": "skill", "skills": "aws docker python"}) == "cloud"
    assert cert_design.theme_for({"category": "skill", "skills": "cybersecurity networking"}) == "security"
    assert cert_design.theme_for({"category": "skill", "skills": "ux_design"}) == "design"
    assert cert_design.theme_for({"category": "skill", "skills": ""}) == "general"
    assert cert_design.theme_for(None) == "general"


def test_every_theme_has_label_in_every_language():
    for lang, names in cert_design.NAMES.items():
        assert len(names) == len(cert_design.THEMES), lang


def test_pdf_differs_per_training_and_accepts_str():
    mk = lambda t: pdf_gen.certificate_pdf("CU-1", "Ada", t, "01/01/2026", "https://x/v", "fr", True)
    a = mk({"title": "A", "category": "web"})
    b = mk({"title": "A", "category": "languages"})
    assert a[:5] == b"%PDF-" and hashlib.md5(a).digest() != hashlib.md5(b).digest()
    assert mk("Titre simple")[:5] == b"%PDF-"
