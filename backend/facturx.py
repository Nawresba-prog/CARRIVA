"""Factur-X / ZUGFeRD : PDF/A-3 visible + XML CII (profil EN 16931) incorporé, pour la facture électronique (France 2026-2027, UE).

Étapes : (1) le PDF est dessiné avec polices incorporées (invoices.invoice_pdf(embed_fonts=True)) ; (2) l'XML « CrossIndustryInvoice » est construit depuis
les MÊMES montants que le PDF (invoices.compute) ; (3) pikepdf incorpore factur-x.xml (AFRelationship /Alternative), ajoute les métadonnées XMP PDF/A-3B
+ schéma d'extension Factur-X et un profil de sortie sRGB. Types : 380 facture, 381 avoir. Les devis ne sont pas des factures : refusés.
LIMITE : pas de validation officielle dans ce code (XSD / Schematron EN 16931, veraPDF). Validez vos premiers fichiers avec Mustang
(java -jar Mustang-CLI.jar --action validate --source facture.pdf) ou le validateur Factur-X avant utilisation en production.
"""
from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from decimal import Decimal

from lxml import etree

from . import invoices

NS = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
    "qdt": "urn:un:unece:uncefact:data:standard:QualifiedDataType:100",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}
GUIDELINE = "urn:cen.eu:en16931:2017"
TYPE_CODE = {"invoice": "380", "credit_note": "381"}
CATEGORY = {"franchise": "E", "reverse_charge": "AE", "intra_eu": "K", "export": "G"}
UNIT = {"": "C62", "u": "C62", "piece": "C62", "pièce": "C62", "unité": "C62", "unit": "C62", "h": "HUR", "heure": "HUR", "heures": "HUR", "hour": "HUR", "hours": "HUR",
        "jour": "DAY", "jours": "DAY", "day": "DAY", "days": "DAY", "mois": "MON", "month": "MON", "an": "ANN", "année": "ANN", "year": "ANN",
        "kg": "KGM", "g": "GRM", "m": "MTR", "km": "KMT", "l": "LTR", "m2": "MTK", "m²": "MTK", "forfait": "C62"}
MEANS = {"card": "48", "cash": "10", "cheque": "20", "other": "1"}


def _q(tag: str) -> str:
    p, n = tag.split(":")
    return f"{{{NS[p]}}}{n}"


def _sub(parent, tag: str, text=None, **attrs):
    e = etree.SubElement(parent, _q(tag), **attrs)
    if text is not None:
        e.text = str(text)
    return e


def _amt(d: Decimal, places: int = 2) -> str:
    return format(d.quantize(Decimal(1).scaleb(-places)), "f")


def _price(d: Decimal) -> str:
    s = format(d.quantize(Decimal("0.0001")), "f").rstrip("0")
    whole, _, frac = s.partition(".")
    return f"{whole}.{frac.ljust(2, '0')}"


def _date(parent, tag: str, iso: str):
    w = _sub(parent, tag)
    _sub(w, "udt:DateTimeString", iso.replace("-", ""), format="102")


def _split_address(p: dict) -> tuple[str, str, str, list[str]]:
    lines = [x.strip() for x in str(p.get("address", "")).replace("\r", "").split("\n") if x.strip()]
    post, city = str(p.get("postcode", "")).strip(), str(p.get("city", "")).strip()
    if not (post and city) and lines:
        m = re.match(r"^(\d{4,5})\s+(.+?)(?:,\s*[A-Za-zÀ-ÿ ]+)?$", lines[-1])
        if m and len(lines) > 1:
            post, city = post or m.group(1), city or m.group(2); lines = lines[:-1]
    return post, city, str(p.get("country", "")).upper(), lines


def _legal_id(tax_id: str):
    digits = re.sub(r"\D", "", tax_id or "")
    if len(digits) == 14:
        return digits, "0009"   # SIRET
    if len(digits) == 9:
        return digits, "0002"   # SIREN
    return (tax_id.strip(), None) if tax_id.strip() else (None, None)


def _party(parent, tag: str, p: dict, country_default: str):
    pp = dict(p, country=p.get("country") or country_default)
    t = _sub(parent, tag)
    _sub(t, "ram:Name", pp["name"])
    lid, scheme = _legal_id(pp.get("tax_id", ""))
    if lid:
        lo = _sub(t, "ram:SpecifiedLegalOrganization")
        _sub(lo, "ram:ID", lid, **({"schemeID": scheme} if scheme else {}))
    post, city, country, lines = _split_address(pp)
    ad = _sub(t, "ram:PostalTradeAddress")
    if post:
        _sub(ad, "ram:PostcodeCode", post)
    if lines:
        _sub(ad, "ram:LineOne", lines[0][:150])
    if len(lines) > 1:
        _sub(ad, "ram:LineTwo", ", ".join(lines[1:])[:150])
    if city:
        _sub(ad, "ram:CityName", city)
    _sub(ad, "ram:CountryID", country)
    if str(pp.get("email", "")).strip():
        u = _sub(t, "ram:URIUniversalCommunication"); _sub(u, "ram:URIID", pp["email"].strip(), schemeID="EM")
    if str(pp.get("vat_number", "")).strip():
        r = _sub(t, "ram:SpecifiedTaxRegistration"); _sub(r, "ram:ID", re.sub(r"\s+", "", pp["vat_number"]).upper(), schemeID="VA")
    elif str(pp.get("tax_id", "")).strip() and tag == "ram:SellerTradeParty":
        r = _sub(t, "ram:SpecifiedTaxRegistration"); _sub(r, "ram:ID", pp["tax_id"].strip(), schemeID="FC")
    return t


def check_inputs(inv: dict) -> list[str]:
    """Champs OBLIGATOIRES pour un XML EN 16931 valide ; liste des manques (vide = ok)."""
    miss, s, c = [], inv.get("seller", {}), inv.get("client", {})
    if inv.get("doc_type", "invoice") not in TYPE_CODE:
        miss.append("seul une facture ou un avoir peut être émis en Factur-X (pas un devis)")
    for lab, ok in (("numéro du document", str(inv.get("number", "")).strip()), ("date d'émission", inv.get("issue_date")), ("raison sociale du vendeur", s.get("name", "").strip()),
                    ("pays du vendeur (code ISO, ex. FR)", len(str(s.get("country", ""))) == 2), ("nom du client", c.get("name", "").strip()),
                    ("adresse du vendeur", s.get("address", "").strip()), ("adresse du client", c.get("address", "").strip()),
                    ("n° de TVA ou identifiant fiscal du vendeur", str(s.get("vat_number", "")).strip() or str(s.get("tax_id", "")).strip())):
        if not ok:
            miss.append(lab)
    if inv.get("doc_type") == "credit_note" and not (str(inv.get("ref_number", "")).strip() and inv.get("ref_date")):
        miss.append("numéro et date de la facture d'origine (avoir)")
    if inv.get("regime") in ("reverse_charge", "intra_eu") and not str(c.get("vat_number", "")).strip():
        miss.append("n° de TVA du client (autoliquidation / intracommunautaire)")
    if inv.get("regime") == "intra_eu" and not str(s.get("vat_number", "")).strip():
        miss.append("n° de TVA du vendeur (intracommunautaire)")
    return miss


def build_xml(inv: dict, calc: dict) -> bytes:
    kind, regime, cur = inv.get("doc_type", "invoice"), inv.get("regime", "standard"), inv.get("currency", "EUR")
    miss = check_inputs(inv)
    if miss:
        raise ValueError("Factur-X impossible, il manque : " + " ; ".join(miss))
    s, c = inv["seller"], inv["client"]
    root = etree.Element(_q("rsm:CrossIndustryInvoice"), nsmap={k: v for k, v in NS.items() if k != "qdt"})
    ctx = _sub(root, "rsm:ExchangedDocumentContext")
    _sub(_sub(ctx, "ram:GuidelineSpecifiedDocumentContextParameter"), "ram:ID", GUIDELINE)
    doc = _sub(root, "rsm:ExchangedDocument")
    _sub(doc, "ram:ID", inv["number"]); _sub(doc, "ram:TypeCode", TYPE_CODE[kind])
    _date(doc, "ram:IssueDateTime", inv["issue_date"])
    mentions = invoices.legal_mentions(s.get("country", ""), regime, inv.get("lang", "fr"), bool(c.get("is_business", True)), str(inv.get("late_rate", "")), kind)
    for n in mentions + ([f"{inv['notes']}"] if str(inv.get("notes", "")).strip() else []):
        _sub(_sub(doc, "ram:IncludedNote"), "ram:Content", n[:1000])
    tx = _sub(root, "rsm:SupplyChainTradeTransaction")
    cat_of = (lambda rate: ("S" if rate > 0 else "Z")) if regime == "standard" else (lambda rate, k=CATEGORY.get(regime): k)
    for i, ln in enumerate(calc["lines"], 1):
        li = _sub(tx, "ram:IncludedSupplyChainTradeLineItem")
        _sub(_sub(li, "ram:AssociatedDocumentLineDocument"), "ram:LineID", i)
        _sub(_sub(li, "ram:SpecifiedTradeProduct"), "ram:Name", ln["description"] or f"Ligne {i}")
        ag = _sub(li, "ram:SpecifiedLineTradeAgreement")
        _sub(_sub(ag, "ram:NetPriceProductTradePrice"), "ram:ChargeAmount", _price(ln["unit_price"]))
        dl = _sub(li, "ram:SpecifiedLineTradeDelivery")
        _sub(dl, "ram:BilledQuantity", format(ln["qty"].normalize(), "f"), unitCode=UNIT.get(ln["unit"].strip().lower(), "C62"))
        st = _sub(li, "ram:SpecifiedLineTradeSettlement")
        tax = _sub(st, "ram:ApplicableTradeTax"); _sub(tax, "ram:TypeCode", "VAT"); _sub(tax, "ram:CategoryCode", cat_of(ln["vat"]))
        if cat_of(ln["vat"]) in ("S",):
            _sub(tax, "ram:RateApplicablePercent", _amt(ln["vat"]))
        elif cat_of(ln["vat"]) == "Z":
            _sub(tax, "ram:RateApplicablePercent", "0.00")
        gross = invoices.q2(ln["qty"] * ln["unit_price"])
        if gross != ln["net"]:  # remise de ligne : BT-136, pour que quantité × prix − remise = montant net exact
            ac = _sub(st, "ram:SpecifiedTradeAllowanceCharge")
            _sub(_sub(ac, "ram:ChargeIndicator"), "udt:Indicator", "false")
            _sub(ac, "ram:ActualAmount", _amt(gross - ln["net"])); _sub(ac, "ram:Reason", "Remise")
        _sub(_sub(st, "ram:SpecifiedTradeSettlementLineMonetarySummation"), "ram:LineTotalAmount", _amt(ln["net"]))
    ag = _sub(tx, "ram:ApplicableHeaderTradeAgreement")
    _party(ag, "ram:SellerTradeParty", s, s.get("country", ""))
    _party(ag, "ram:BuyerTradeParty", c, c.get("country") or s.get("country", ""))
    dv = _sub(tx, "ram:ApplicableHeaderTradeDelivery")
    if inv.get("service_date") or regime == "intra_eu":
        ev = _sub(dv, "ram:ActualDeliverySupplyChainEvent"); _date(ev, "ram:OccurrenceDateTime", inv.get("service_date") or inv["issue_date"])
    stl = _sub(tx, "ram:ApplicableHeaderTradeSettlement")
    _sub(stl, "ram:InvoiceCurrencyCode", cur)
    method = inv.get("payment_method", "transfer")
    pm = _sub(stl, "ram:SpecifiedTradeSettlementPaymentMeans")
    iban = re.sub(r"\s+", "", str(s.get("iban", ""))).upper()
    if method == "transfer" and iban:
        _sub(pm, "ram:TypeCode", "58" if cur == "EUR" else "30")
        _sub(_sub(pm, "ram:PayeePartyCreditorFinancialAccount"), "ram:IBANID", iban)
        if str(s.get("bic", "")).strip():
            _sub(_sub(pm, "ram:PayeeSpecifiedCreditorFinancialInstitution"), "ram:BICID", s["bic"].strip().upper())
    else:
        _sub(pm, "ram:TypeCode", MEANS.get(method, "1"))
    for v in calc["vat_rows"]:
        cat = cat_of(v["rate"])
        tax = _sub(stl, "ram:ApplicableTradeTax")
        _sub(tax, "ram:CalculatedAmount", _amt(v["vat"])); _sub(tax, "ram:TypeCode", "VAT")
        if cat in ("E", "AE", "K", "G"):
            _sub(tax, "ram:ExemptionReason", (mentions[0] if mentions else "VAT exempt")[:300])
        _sub(tax, "ram:BasisAmount", _amt(v["base"])); _sub(tax, "ram:CategoryCode", cat)
        if cat in ("S", "Z"):
            _sub(tax, "ram:RateApplicablePercent", _amt(v["rate"]))
    if kind == "invoice":
        pt = _sub(stl, "ram:SpecifiedTradePaymentTerms")
        if inv.get("due_date"):
            _sub(pt, "ram:Description", f"Échéance {inv['due_date']}"); _date(pt, "ram:DueDateDateTime", inv["due_date"])
    sm = _sub(stl, "ram:SpecifiedTradeSettlementHeaderMonetarySummation")
    _sub(sm, "ram:LineTotalAmount", _amt(sum((l["net"] for l in calc["lines"]), Decimal(0))))
    _sub(sm, "ram:TaxBasisTotalAmount", _amt(calc["total_ht"]))
    _sub(sm, "ram:TaxTotalAmount", _amt(calc["total_vat"]), currencyID=cur)
    _sub(sm, "ram:GrandTotalAmount", _amt(calc["total_ttc"]))
    if calc["deposit"]:
        _sub(sm, "ram:TotalPrepaidAmount", _amt(calc["deposit"]))
    _sub(sm, "ram:DuePayableAmount", _amt(calc["due"]))
    if kind == "credit_note":
        ir = _sub(stl, "ram:InvoiceReferencedDocument")
        _sub(ir, "ram:IssuerAssignedID", inv["ref_number"]); _date(ir, "ram:FormattedIssueDateTime", inv["ref_date"])
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def xmp(inv: dict, now: datetime) -> bytes:
    iso = now.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    esc = lambda t: (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    title = f"{inv.get('seller', {}).get('name', '')} - {inv.get('number', '')}"
    prop = lambda n, d: f'<rdf:li rdf:parseType="Resource"><pdfaProperty:name>{n}</pdfaProperty:name><pdfaProperty:valueType>Text</pdfaProperty:valueType><pdfaProperty:category>external</pdfaProperty:category><pdfaProperty:description>{d}</pdfaProperty:description></rdf:li>'
    return f'''<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<rdf:Description rdf:about="" xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/"><pdfaid:part>3</pdfaid:part><pdfaid:conformance>B</pdfaid:conformance></rdf:Description>
<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title><rdf:Alt><rdf:li xml:lang="x-default">{esc(title)}</rdf:li></rdf:Alt></dc:title><dc:creator><rdf:Seq><rdf:li>{esc(inv.get("seller", {}).get("name", ""))}</rdf:li></rdf:Seq></dc:creator></rdf:Description>
<rdf:Description rdf:about="" xmlns:pdf="http://ns.adobe.com/pdf/1.3/"><pdf:Producer>CARRIVA</pdf:Producer></rdf:Description>
<rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/"><xmp:CreatorTool>CARRIVA</xmp:CreatorTool><xmp:CreateDate>{iso}</xmp:CreateDate><xmp:ModifyDate>{iso}</xmp:ModifyDate><xmp:MetadataDate>{iso}</xmp:MetadataDate></rdf:Description>
<rdf:Description rdf:about="" xmlns:fx="urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#"><fx:DocumentType>INVOICE</fx:DocumentType><fx:DocumentFileName>factur-x.xml</fx:DocumentFileName><fx:Version>1.0</fx:Version><fx:ConformanceLevel>EN 16931</fx:ConformanceLevel></rdf:Description>
<rdf:Description rdf:about="" xmlns:pdfaExtension="http://www.aiim.org/pdfa/ns/extension/" xmlns:pdfaSchema="http://www.aiim.org/pdfa/ns/schema#" xmlns:pdfaProperty="http://www.aiim.org/pdfa/ns/property#"><pdfaExtension:schemas><rdf:Bag><rdf:li rdf:parseType="Resource"><pdfaSchema:schema>Factur-X PDFA Extension Schema</pdfaSchema:schema><pdfaSchema:namespaceURI>urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#</pdfaSchema:namespaceURI><pdfaSchema:prefix>fx</pdfaSchema:prefix><pdfaSchema:property><rdf:Seq>{prop("DocumentFileName", "name of the embedded XML invoice file")}{prop("DocumentType", "INVOICE")}{prop("Version", "The actual version of the Factur-X XML schema")}{prop("ConformanceLevel", "The conformance level of the embedded Factur-X data")}</rdf:Seq></pdfaSchema:property></rdf:li></rdf:Bag></pdfaExtension:schemas></rdf:Description>
</rdf:RDF></x:xmpmeta>
<?xpacket end="w"?>'''.encode("utf-8")


def _srgb_icc() -> bytes | None:
    try:
        from PIL import ImageCms
        return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    except Exception:  # noqa: BLE001 — Pillow absent : pas de profil de sortie
        return None


def _drop_unused_fonts(pdf) -> int:
    """reportlab déclare toujours Helvetica (non incorporée) dans les ressources : on retire les polices non incorporées jamais utilisées (PDF/A)."""
    removed = 0
    for page in pdf.pages:
        fonts = page.Resources.get("/Font")
        if fonts is None:
            continue
        used = b"".join(c.read_bytes() for c in ([page.Contents] if not isinstance(page.Contents, __import__("pikepdf").Array) else list(page.Contents)))
        for key in list(fonts.keys()):
            f = fonts[key]
            embedded = "/FontDescriptor" in f and any(k in f.FontDescriptor for k in ("/FontFile", "/FontFile2", "/FontFile3"))
            if not embedded and (key.encode() + b" ") not in used:
                del fonts[key]; removed += 1
    return removed


def generate(inv: dict, lang: str = "fr", now: datetime | None = None) -> tuple[bytes, dict]:
    """(PDF Factur-X, infos). infos : profile, xml_bytes, fonts_embedded, output_intent, pdfa_ready (True si polices incorporées ET profil sRGB)."""
    import pikepdf
    now = now or datetime.now(timezone.utc)
    if inv.get("doc_type", "invoice") not in TYPE_CODE:
        raise ValueError("Factur-X : seules les factures et les avoirs sont concernés (pas les devis)")
    base_pdf, calc = invoices.invoice_pdf(inv, lang, embed_fonts=True)
    xml = build_xml(inv, calc)
    fonts = invoices.latin_fonts() is not None
    pdf = pikepdf.open(io.BytesIO(base_pdf))
    _drop_unused_fonts(pdf)
    spec = pikepdf.AttachedFileSpec(pdf, xml, mime_type="text/xml", description="Factur-X invoice", filename="factur-x.xml", relationship=pikepdf.Name.Alternative,
                                    creation_date=now.strftime("D:%Y%m%d%H%M%SZ"), mod_date=now.strftime("D:%Y%m%d%H%M%SZ"))
    pdf.attachments["factur-x.xml"] = spec
    pdf.Root.AF = pdf.make_indirect(pikepdf.Array([spec.obj]))
    pdf.Root.Metadata = pdf.make_stream(xmp(inv, now)); pdf.Root.Metadata.Type = pikepdf.Name.Metadata; pdf.Root.Metadata.Subtype = pikepdf.Name.XML
    icc = _srgb_icc()
    if icc:
        prof = pdf.make_stream(icc); prof.N = 3
        pdf.Root.OutputIntents = pikepdf.Array([pikepdf.Dictionary(Type=pikepdf.Name.OutputIntent, S=pikepdf.Name.GTS_PDFA1, OutputConditionIdentifier=pikepdf.String("sRGB IEC61966-2.1"),
                                                                    Info=pikepdf.String("sRGB IEC61966-2.1"), DestOutputProfile=prof)])
    stamp = "D:" + now.strftime("%Y%m%d%H%M%S") + "Z"
    pdf.docinfo = pdf.make_indirect(pikepdf.Dictionary(Title=pikepdf.String(f"{inv['seller'].get('name', '')} - {inv.get('number', '')}"), Author=pikepdf.String(inv["seller"].get("name", "")),
                                     Producer=pikepdf.String("CARRIVA"), Creator=pikepdf.String("CARRIVA"), CreationDate=pikepdf.String(stamp), ModDate=pikepdf.String(stamp)))
    out = io.BytesIO(); pdf.save(out, min_version="1.7"); pdf.close()
    return out.getvalue(), {"profile": "EN 16931", "xml_bytes": len(xml), "fonts_embedded": fonts, "output_intent": bool(icc), "pdfa_ready": fonts and bool(icc), "total": _amt(calc["total_ttc"])}
