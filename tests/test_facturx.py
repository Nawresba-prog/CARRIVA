import io
from datetime import datetime, timezone
from decimal import Decimal

import pikepdf
from lxml import etree

from backend import facturx as F
from backend import invoices as I

NS = F.NS
X = lambda el, path: el.xpath(path, namespaces=NS)

# ordre des enfants imposé par le schéma CII (sous-ensemble utilisé ici)
ORDER = {
    "ram:SellerTradeParty": ["ram:Name", "ram:SpecifiedLegalOrganization", "ram:PostalTradeAddress", "ram:URIUniversalCommunication", "ram:SpecifiedTaxRegistration"],
    "ram:PostalTradeAddress": ["ram:PostcodeCode", "ram:LineOne", "ram:LineTwo", "ram:CityName", "ram:CountryID"],
    "ram:ApplicableTradeTax": ["ram:CalculatedAmount", "ram:TypeCode", "ram:ExemptionReason", "ram:BasisAmount", "ram:CategoryCode", "ram:RateApplicablePercent"],
    "ram:SpecifiedLineTradeSettlement": ["ram:ApplicableTradeTax", "ram:SpecifiedTradeAllowanceCharge", "ram:SpecifiedTradeSettlementLineMonetarySummation"],
    "ram:IncludedSupplyChainTradeLineItem": ["ram:AssociatedDocumentLineDocument", "ram:SpecifiedTradeProduct", "ram:SpecifiedLineTradeAgreement", "ram:SpecifiedLineTradeDelivery", "ram:SpecifiedLineTradeSettlement"],
    "ram:ApplicableHeaderTradeSettlement": ["ram:InvoiceCurrencyCode", "ram:SpecifiedTradeSettlementPaymentMeans", "ram:ApplicableTradeTax", "ram:SpecifiedTradePaymentTerms",
                                             "ram:SpecifiedTradeSettlementHeaderMonetarySummation", "ram:InvoiceReferencedDocument"],
    "ram:SpecifiedTradeSettlementHeaderMonetarySummation": ["ram:LineTotalAmount", "ram:TaxBasisTotalAmount", "ram:TaxTotalAmount", "ram:GrandTotalAmount", "ram:TotalPrepaidAmount", "ram:DuePayableAmount"],
    "rsm:SupplyChainTradeTransaction": ["ram:IncludedSupplyChainTradeLineItem", "ram:ApplicableHeaderTradeAgreement", "ram:ApplicableHeaderTradeDelivery", "ram:ApplicableHeaderTradeSettlement"],
}


def check_order(root):
    rank = lambda parent, tag: ORDER[parent].index(tag)
    for parent, seq in ORDER.items():
        for el in X(root, "//" + parent):
            idx = [seq.index(etree.QName(c).localname and ("ram:" + etree.QName(c).localname if etree.QName(c).namespace == NS["ram"] else "rsm:" + etree.QName(c).localname)) for c in el]
            assert idx == sorted(idx), (parent, idx)


def inv(**kw):
    d = {"doc_type": "invoice", "number": "FA-2026-0007", "issue_date": "2026-10-24", "due_date": "2026-11-23", "currency": "EUR", "regime": "standard", "payment_method": "transfer", "deposit": "100", "lang": "fr",
         "seller": {"name": "Atelier Lumière SARL", "address": "12 rue des Fleurs\n69001 Lyon", "country": "FR", "tax_id": "123 456 789 00012", "vat_number": "FR12 123456789", "iban": "FR76 3000 6000 0112 3456 7890 189", "bic": "AGRIFRPP", "email": "c@l.fr"},
         "client": {"name": "Maison Dupont SA", "address": "5 avenue Foch\n75016 Paris", "vat_number": "FR98765432109", "is_business": True},
         "lines": [{"description": "Site & <vitrine>", "qty": 1, "unit_price": "1200", "vat": 20}, {"description": "Hébergement", "qty": 12, "unit": "mois", "unit_price": "9.90", "discount": 10, "vat": 20},
                   {"description": "Livre", "qty": 3, "unit_price": "19.99", "vat": 5.5}]}
    d.update(kw)
    return d


def xml_of(i):
    calc = I.compute(i["lines"], i["regime"], i.get("deposit", 0) if i["doc_type"] == "invoice" else 0)
    return etree.fromstring(F.build_xml(i, calc)), calc


def test_invoice_xml_structure_and_amounts():
    root, calc = xml_of(inv())
    check_order(root)
    assert X(root, "string(//ram:GuidelineSpecifiedDocumentContextParameter/ram:ID)") == "urn:cen.eu:en16931:2017"
    assert X(root, "string(//rsm:ExchangedDocument/ram:TypeCode)") == "380" and X(root, "string(//rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString)") == "20261024"
    assert X(root, 'string(//ram:SellerTradeParty/ram:SpecifiedLegalOrganization/ram:ID/@schemeID)') == "0009"
    assert X(root, "string(//ram:SellerTradeParty/ram:SpecifiedTaxRegistration/ram:ID)") == "FR12123456789"
    assert X(root, "string(//ram:SpecifiedTradeSettlementPaymentMeans/ram:PayeePartyCreditorFinancialAccount/ram:IBANID)") == "FR7630006000011234567890189"
    s = lambda p: Decimal(X(root, f"string({p})"))
    hs = "//ram:SpecifiedTradeSettlementHeaderMonetarySummation/"
    lines = [Decimal(x) for x in X(root, "//ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount/text()")]
    assert sum(lines) == s(hs + "ram:LineTotalAmount") == s(hs + "ram:TaxBasisTotalAmount") == calc["total_ht"]
    bases = [Decimal(x) for x in X(root, "//ram:ApplicableHeaderTradeSettlement/ram:ApplicableTradeTax/ram:BasisAmount/text()")]
    vats = [Decimal(x) for x in X(root, "//ram:ApplicableHeaderTradeSettlement/ram:ApplicableTradeTax/ram:CalculatedAmount/text()")]
    assert sum(bases) == s(hs + "ram:TaxBasisTotalAmount") and sum(vats) == s(hs + "ram:TaxTotalAmount")
    assert s(hs + "ram:GrandTotalAmount") == s(hs + "ram:TaxBasisTotalAmount") + s(hs + "ram:TaxTotalAmount") == Decimal("1631.57")
    assert s(hs + "ram:DuePayableAmount") == s(hs + "ram:GrandTotalAmount") - s(hs + "ram:TotalPrepaidAmount") == Decimal("1531.57")
    # remise de ligne : quantité × prix − remise = montant net
    ac = X(root, "//ram:IncludedSupplyChainTradeLineItem[2]//ram:SpecifiedTradeAllowanceCharge/ram:ActualAmount/text()")
    assert ac == ["11.88"] and X(root, "//ram:IncludedSupplyChainTradeLineItem[2]//ram:BilledQuantity/@unitCode") == ["MON"]
    assert "Site &" in X(root, "string(//ram:IncludedSupplyChainTradeLineItem[1]//ram:Name)")      # caractères spéciaux correctement échappés (XML bien formé)


def test_credit_note_is_381_with_reference_and_positive_amounts():
    i = inv(doc_type="credit_note", ref_number="FA-2026-0001", ref_date="2026-09-01", notes="Retour")
    root, calc = xml_of(i); check_order(root)
    assert X(root, "string(//rsm:ExchangedDocument/ram:TypeCode)") == "381"
    assert X(root, "string(//ram:InvoiceReferencedDocument/ram:IssuerAssignedID)") == "FA-2026-0001" and X(root, "string(//ram:InvoiceReferencedDocument/ram:FormattedIssueDateTime/udt:DateTimeString)") == "20260901"
    assert Decimal(X(root, "string(//ram:GrandTotalAmount)")) > 0 and not X(root, "//ram:TotalPrepaidAmount") and not X(root, "//ram:SpecifiedTradePaymentTerms")
    assert any("Retour" in t for t in X(root, "//ram:IncludedNote/ram:Content/text()"))


def test_exemption_categories_need_reason_and_ids():
    for regime, cat in (("franchise", "E"), ("reverse_charge", "AE"), ("intra_eu", "K"), ("export", "G")):
        root, _ = xml_of(inv(regime=regime)); check_order(root)
        assert X(root, "//ram:ApplicableHeaderTradeSettlement/ram:ApplicableTradeTax/ram:CategoryCode/text()") == [cat]
        assert X(root, "string(//ram:ApplicableHeaderTradeSettlement/ram:ApplicableTradeTax/ram:ExemptionReason)").strip()
        assert not X(root, "//ram:ApplicableHeaderTradeSettlement/ram:ApplicableTradeTax/ram:RateApplicablePercent")
    root, _ = xml_of(inv(deposit=0, lines=[{"description": "x", "qty": 1, "unit_price": "10", "vat": 0}]))
    assert X(root, "//ram:ApplicableHeaderTradeSettlement/ram:ApplicableTradeTax/ram:CategoryCode/text()") == ["Z"]


def test_missing_fields_and_quote_refused():
    bad = inv(); bad["seller"] = dict(bad["seller"], vat_number="", tax_id=""); bad["client"] = dict(bad["client"], address="")
    miss = " ".join(F.check_inputs(bad)); assert "TVA ou identifiant fiscal" in miss and "adresse du client" in miss
    try:
        F.generate(bad); assert False
    except ValueError as e:
        assert "Factur-X impossible" in str(e)
    try:
        F.generate(inv(doc_type="quote")); assert False
    except ValueError as e:
        assert "devis" in str(e)
    assert F.check_inputs(inv(doc_type="credit_note"))  # avoir sans facture d'origine


def test_pdf_attachment_xmp_and_pdfa_ingredients():
    now = datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc)
    pdf, info = F.generate(inv(), "fr", now)
    p = pikepdf.open(io.BytesIO(pdf))
    assert list(p.attachments) == ["factur-x.xml"] and p.Root.AF[0].AFRelationship == "/Alternative"
    xml = p.attachments["factur-x.xml"].get_file().read_bytes()
    etree.fromstring(xml)
    meta = bytes(p.Root.Metadata.read_bytes()).decode()
    for k in ("<pdfaid:part>3</pdfaid:part>", "<pdfaid:conformance>B</pdfaid:conformance>", "<fx:ConformanceLevel>EN 16931</fx:ConformanceLevel>", "<fx:DocumentFileName>factur-x.xml</fx:DocumentFileName>", "pdfaExtension:schemas"):
        assert k in meta, k
    assert info["profile"] == "EN 16931" and info["xml_bytes"] == len(xml)
    if info["fonts_embedded"]:  # toutes les polices utilisées doivent être incorporées
        for pg in p.pages:
            for f in pg.Resources.Font.values():
                assert "/FontDescriptor" in f and ("/FontFile2" in f.FontDescriptor or "/FontFile3" in f.FontDescriptor or "/FontFile" in f.FontDescriptor), f.BaseFont
    assert info["pdfa_ready"] == (info["fonts_embedded"] and info["output_intent"])
    assert bool(p.Root.get("/OutputIntents")) == info["output_intent"]
