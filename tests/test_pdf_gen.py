"""Lancer depuis la racine du projet : pytest -q  (après `python backend/fonts/fetch_fonts.py`)."""
import pytest

from backend import pdf_gen

EU = {
    "personal": {"name": "أحمد بن علي", "email": "a@example.com", "phone": "+212600000000", "website": "linkedin.com/in/ahmed",
                 "address": "Casablanca, المغرب", "nationality": "مغربي", "birth_date": "1994-04-12"},
    "summary": "مطوّر برمجيات لديه خبرة في بناء واجهات برمجية آمنة وقابلة للتوسع، ومهتم بالذكاء الاصطناعي. " * 3,
    "work_experience": [{"title": "مطوّر Python", "company": "Atlas Tech", "city": "Casablanca", "country": "MA", "start": "2021-03", "end": "",
                         "description": "تطوير واجهات REST.\nأتمتة الاختبارات."}],
    "education_training": [{"degree": "Master Informatique", "school": "ENSIAS", "city": "Rabat", "country": "MA", "start": "2017-09", "end": "2019-06", "level": "7", "year": ""}],
    "mother_tongue": ["العربية"],
    "language_skills": [{"name": "Français", "listening": "C1", "reading": "C1", "interaction": "B2", "production": "B2", "writing": "B2"},
                        {"name": "English", "listening": "B2", "reading": "B2", "interaction": "B2", "production": "B2", "writing": "B1"}],
    "digital_skills": ["python", "sql", "docker"],
    "driving_licence": "B",
    "additional_info": "متطوع في جمعية.",
}
needs_font = pytest.mark.skipif(not pdf_gen._ar_ok, reason="police arabe absente (fetch_fonts.py)")


def test_latin_text_is_only_escaped():
    assert pdf_gen.shape("R&D <lead>") == "R&amp;D &lt;lead&gt;"


@needs_font
def test_arabic_is_wrapped_in_font_tag_and_reshaped():
    out = pdf_gen.shape("مرحبا")
    assert f'<font name="{pdf_gen.AR_REG}">' in out
    assert "مرحبا" not in out  # remplacé par les formes de présentation (lettres liées)


@needs_font
def test_rtl_wrap_produces_multiple_lines_within_width():
    lines = pdf_gen._wrap_rtl(EU["summary"], 11, False, 200)
    assert len(lines) > 1


@pytest.mark.parametrize("lang", ["ar", "fr", "en", "de", "it", "es"])
def test_cv_pdf_all_languages(lang):
    pdf = pdf_gen.cv_pdf(EU, lang=lang)
    assert pdf.startswith(b"%PDF") and len(pdf) > 1500


@pytest.mark.parametrize("lang", ["ar", "fr"])
def test_certificate_pdf(lang):
    pdf = pdf_gen.certificate_pdf("abc123", "أحمد بن علي", "Docker & Kubernetes", "2026-10-17", "http://x/verify/abc123", lang)
    assert pdf.startswith(b"%PDF")


def test_signature_is_stable_and_sensitive():
    a = pdf_gen.sign("1", "n", "t", "d")
    assert a == pdf_gen.sign("1", "n", "t", "d") and a != pdf_gen.sign("1", "N", "t", "d")


def test_fmt_date_and_period():
    assert pdf_gen.fmt_date("2021-03") == "03/2021" and pdf_gen.fmt_date("1995-04-12") == "12/04/1995" and pdf_gen.fmt_date("2020") == "2020"
    assert pdf_gen.period("2021-03", "", "present") == "03/2021 – present"


def test_certificate_seal_differs_between_verified_and_unverified():
    a = pdf_gen.certificate_pdf("abc123def456", "Sara Haddad", "Python", "2026-10-24", "https://x/verify/abc123def456", "fr", True)
    b = pdf_gen.certificate_pdf("abc123def456", "Sara Haddad", "Python", "2026-10-24", "https://x/verify/abc123def456", "fr", False)
    assert a.startswith(b"%PDF") and b.startswith(b"%PDF") and a != b
