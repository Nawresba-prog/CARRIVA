from datetime import date
from decimal import Decimal

from backend import invoices as I


def D(x): return Decimal(x)


def test_totals_vat_per_rate_and_rounding():
    c = I.compute([{"description": "a", "qty": 1, "unit_price": "1200", "vat": 20},
                   {"description": "b", "qty": 12, "unit_price": "9.90", "discount": 10, "vat": 20},
                   {"description": "c", "qty": 3, "unit_price": "19,99", "vat": "5,5"}], deposit="100")
    assert [l["net"] for l in c["lines"]] == [D("1200.00"), D("106.92"), D("59.97")]
    assert {v["rate"]: (v["base"], v["vat"]) for v in c["vat_rows"]} == {D("20"): (D("1306.92"), D("261.38")), D("5.5"): (D("59.97"), D("3.30"))}
    assert (c["total_ht"], c["total_vat"], c["total_ttc"], c["due"]) == (D("1366.89"), D("264.68"), D("1631.57"), D("1531.57"))


def test_no_float_drift_and_half_up():
    c = I.compute([{"qty": 3, "unit_price": "0.1", "vat": 0}, {"qty": 1, "unit_price": "0.125", "vat": 0}])  # 0,30 + 0,13 (0,125 arrondi demi supérieur)
    assert c["total_ht"] == D("0.43")


def test_vat_per_rate_not_per_line():
    c = I.compute([{"qty": 1, "unit_price": "0.10", "vat": 20}] * 3)  # 3 × 0,02 = 0,06 par ligne, mais 0,30 × 20 % = 0,06 : un seul arrondi par taux
    assert c["total_vat"] == D("0.06")


def test_regimes_and_errors():
    assert I.compute([{"qty": 1, "unit_price": "100", "vat": 20}], "franchise")["total_vat"] == 0
    for bad in ([], [{"qty": -1, "unit_price": 1}], [{"qty": 1, "unit_price": 1, "vat": 120}], [{"qty": 1, "unit_price": "abc"}], [{"qty": "nan", "unit_price": 1}]):
        try:
            I.compute(bad); assert False, bad
        except ValueError:
            pass
    try:
        I.compute([{"qty": 1, "unit_price": 10}], deposit="50"); assert False
    except ValueError:
        pass


def test_legal_mentions():
    fr = I.legal_mentions("FR", "standard", "fr", True)
    assert len(fr) == 1 and "L441-10" in fr[0] and "40 €" in fr[0]
    assert I.legal_mentions("FR", "standard", "fr", False) == []                      # particulier : pas de mention B2B
    assert "293 B" in I.legal_mentions("FR", "franchise", "fr", False)[0]
    assert "§ 19 UStG" in I.legal_mentions("DE", "franchise", "de")[0]
    assert "Reverse charge" in I.legal_mentions("MA", "reverse_charge", "en")[0] or "Reverse" in I.legal_mentions("MA", "reverse_charge", "en")[0]


def test_warnings():
    inv = {"seller": {"country": "DE"}, "client": {}, "regime": "intra_eu", "number": "X", "lines": []}
    calc = I.compute([{"qty": 1, "unit_price": 10, "vat": 0}], "intra_eu")
    w = " ".join(I.warnings(inv, calc))
    for key in ("Vendeur", "TVA intracommunautaire", "Client", "Numéro du document", "échéance", "IBAN", "Leistungsdatum"):
        assert key.lower() in w.lower(), key
    ok = {"seller": {"name": "A", "address": "B", "tax_id": "C", "vat_number": "D", "iban": "E", "country": "FR"}, "client": {"name": "N", "address": "A"},
          "regime": "standard", "number": "FA-2026-0001", "due_date": "2026-11-01"}
    assert I.warnings(ok, I.compute([{"qty": 1, "unit_price": 10, "vat": 20}])) == []


def test_next_number():
    d = date(2026, 10, 24)
    assert I.next_number("", d) == "FA-2026-0001" and I.next_number("FA-2026-0007", d) == "FA-2026-0008"
    assert I.next_number("FA-2025-0123", d) == "FA-2026-0001"
    assert I.next_number("INV-2026-99", d) == "INV-2026-100"


def test_pdf_all_languages_and_pagination():
    inv = {"number": "N-1", "issue_date": "2026-01-01", "due_date": "2026-01-31", "currency": "EUR", "regime": "standard", "deposit": 0,
           "seller": {"name": "S", "address": "A", "country": "FR", "iban": "FR76"}, "client": {"name": "C", "address": "B"},
           "lines": [{"description": "x", "qty": 1, "unit_price": "10", "vat": 20}]}
    for lang in ("fr", "en", "de", "es", "it", "ar"):
        pdf, _ = I.invoice_pdf(inv, lang); assert pdf[:5] == b"%PDF-", lang
    big = dict(inv, lines=inv["lines"] * 60)
    pdf, calc = I.invoice_pdf(big, "fr")
    assert pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page ") >= 2 and calc["total_ht"] == D("600.00")


def test_credit_note_and_quote_documents():
    base = {"number": "N-1", "issue_date": "2026-01-01", "currency": "EUR", "regime": "standard", "deposit": 50,
            "seller": {"name": "S", "address": "A", "country": "FR"}, "client": {"name": "C", "address": "B"}, "lines": [{"description": "x", "qty": 1, "unit_price": "100", "vat": 20}]}
    cn = dict(base, doc_type="credit_note", ref_number="FA-1", ref_date="2025-12-01", notes="Retour")
    pdf, calc = I.invoice_pdf(cn, "fr"); assert pdf[:5] == b"%PDF-" and calc["deposit"] == 0 and calc["due"] == D("120.00")   # l'acompte est ignoré hors facture
    q = dict(base, doc_type="quote", valid_until="2026-02-01")
    for lang in ("fr", "en", "de", "es", "it", "ar"):
        assert I.invoice_pdf(q, lang)[0][:5] == b"%PDF-" and I.invoice_pdf(cn, lang)[0][:5] == b"%PDF-"
    assert any("facture d'origine" in w for w in I.warnings({**base, "doc_type": "credit_note"}, calc))
    assert any("validité" in w for w in I.warnings({**base, "doc_type": "quote"}, calc))
    assert not any("IBAN" in w or "échéance" in w.lower() for w in I.warnings({**base, "doc_type": "quote"}, calc))
    assert I.legal_mentions("FR", "standard", "fr", True, "", "credit_note") == [] and I.legal_mentions("FR", "standard", "fr", True, "", "invoice")
    d = date(2026, 10, 24)
    assert I.next_number("", d, "credit_note") == "AV-2026-0001" and I.next_number("", d, "quote") == "DE-2026-0001" and I.next_number("DE-2026-0004", d, "quote") == "DE-2026-0005"
    try:
        I.invoice_pdf(dict(base, doc_type="bon"), "fr"); assert False
    except ValueError:
        pass
