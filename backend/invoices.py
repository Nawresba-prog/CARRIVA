"""Élaboration de factures, avoirs et devis : calcul comptable exact (Decimal), mentions légales par pays, contrôles de conformité et PDF.

Règles de calcul : montant de ligne = quantité × prix unitaire × (1 − remise %), arrondi à 0,01 (demi supérieur) ; la base HT est la somme des lignes ;
la TVA est calculée PAR TAUX sur la base de ce taux (un seul arrondi par taux, méthode recommandée par la directive 2006/112/CE) ;
TTC = HT + TVA ; net à payer = TTC − acompte déjà versé. Les mentions légales sont un point de départ : à valider avec votre expert-comptable.
"""
from __future__ import annotations

import io
import re
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

from . import pdf_gen

CENT = Decimal("0.01")
REGIMES = ("standard", "franchise", "reverse_charge", "export", "intra_eu")
CURRENCIES = {"EUR": "€", "USD": "$", "GBP": "£", "CHF": "CHF", "MAD": "MAD", "TND": "TND", "DZD": "DZD", "SAR": "SAR", "AED": "AED", "CAD": "CA$"}


def D(v, default="0") -> Decimal:
    try:
        d = Decimal(str(v).replace(",", ".").replace(" ", "").strip() or default)
    except InvalidOperation:
        raise ValueError(f"nombre invalide : {v!r}")
    if not d.is_finite():
        raise ValueError(f"nombre invalide : {v!r}")
    return d


def q2(d: Decimal) -> Decimal:
    return d.quantize(CENT, rounding=ROUND_HALF_UP)


def compute(lines: list[dict], regime: str = "standard", deposit: object = 0) -> dict:
    """Totaux d'une facture. Chaque ligne : description, qty, unit_price, discount (%), vat (%). Hors régime « standard », la TVA est 0."""
    if regime not in REGIMES:
        raise ValueError("régime de TVA inconnu")
    if not lines:
        raise ValueError("Ajoutez au moins une ligne")
    out_lines, bases = [], {}
    for i, ln in enumerate(lines, 1):
        qty, price, disc = D(ln.get("qty", 1), "1"), D(ln.get("unit_price", 0)), D(ln.get("discount", 0))
        vat = D(ln.get("vat", 0)) if regime == "standard" else Decimal(0)
        if qty < 0 or price < 0:
            raise ValueError(f"ligne {i} : quantité et prix doivent être positifs (utilisez un avoir pour un remboursement)")
        if not (0 <= disc <= 100) or not (0 <= vat <= 100):
            raise ValueError(f"ligne {i} : remise et TVA doivent être entre 0 et 100 %")
        net = q2(qty * price * (Decimal(100) - disc) / Decimal(100))
        out_lines.append({"description": str(ln.get("description", ""))[:300], "unit": str(ln.get("unit", ""))[:20], "qty": qty, "unit_price": price,
                          "discount": disc, "vat": vat, "net": net})
        bases[vat] = bases.get(vat, Decimal(0)) + net
    vat_rows = [{"rate": r, "base": b, "vat": q2(b * r / Decimal(100))} for r, b in sorted(bases.items())]
    total_ht = sum((b for b in bases.values()), Decimal(0))
    total_vat = sum((v["vat"] for v in vat_rows), Decimal(0))
    ttc = total_ht + total_vat
    dep = q2(D(deposit))
    if dep < 0 or dep > ttc:
        raise ValueError("l'acompte doit être compris entre 0 et le total TTC")
    return {"lines": out_lines, "vat_rows": vat_rows, "total_ht": total_ht, "total_vat": total_vat, "total_ttc": ttc, "deposit": dep, "due": ttc - dep}


def num_json(x):  # Decimal -> str pour JSON (jamais de float)
    if isinstance(x, Decimal):
        return format(x, "f")
    if isinstance(x, dict):
        return {k: num_json(v) for k, v in x.items()}
    if isinstance(x, list):
        return [num_json(v) for v in x]
    return x


# --------------------------------------------------------------------------- mentions légales
LEGAL = {  # (pays vendeur, régime) -> {langue: texte}
    ("FR", "franchise"): {"fr": "TVA non applicable, art. 293 B du CGI."},
    ("FR", "reverse_charge"): {"fr": "Autoliquidation de la TVA par le preneur (art. 283-2 du CGI)."},
    ("FR", "intra_eu"): {"fr": "Exonération de TVA, art. 262 ter I du CGI (livraison intracommunautaire). Autoliquidation par le client."},
    ("FR", "export"): {"fr": "Exonération de TVA, art. 262 I du CGI (exportation)."},
    ("DE", "franchise"): {"de": "Kein Umsatzsteuerausweis gemäß § 19 UStG (Kleinunternehmer)."},
    ("DE", "reverse_charge"): {"de": "Steuerschuldnerschaft des Leistungsempfängers (§ 13b UStG)."},
    ("DE", "intra_eu"): {"de": "Steuerfreie innergemeinschaftliche Lieferung/Leistung; Steuerschuldnerschaft des Leistungsempfängers."},
    ("DE", "export"): {"de": "Steuerfreie Ausfuhrlieferung (§ 4 Nr. 1a UStG)."},
    ("IT", "franchise"): {"it": "Operazione effettuata in regime forfettario (art. 1, commi 54-89, L. 190/2014): senza IVA."},
    ("IT", "reverse_charge"): {"it": "Inversione contabile (art. 17 DPR 633/72)."},
    ("IT", "intra_eu"): {"it": "Operazione non imponibile / inversione contabile (art. 41 DL 331/93)."},
    ("IT", "export"): {"it": "Operazione non imponibile (art. 8 DPR 633/72)."},
    ("ES", "reverse_charge"): {"es": "Inversión del sujeto pasivo (art. 84 LIVA)."},
    ("ES", "intra_eu"): {"es": "Operación exenta de IVA (art. 25 LIVA) - entrega intracomunitaria."},
    ("ES", "export"): {"es": "Operación exenta de IVA (art. 21 LIVA) - exportación."},
}
GENERIC = {
    "franchise": {"fr": "TVA non applicable.", "en": "VAT not applicable (small business).", "de": "Keine Umsatzsteuer (Kleinunternehmer).", "es": "IVA no aplicable.", "it": "IVA non applicabile.", "ar": "ضريبة القيمة المضافة غير مطبقة."},
    "reverse_charge": {"fr": "Autoliquidation de la TVA par le preneur.", "en": "Reverse charge: VAT to be accounted for by the recipient.", "de": "Steuerschuldnerschaft des Leistungsempfängers.", "es": "Inversión del sujeto pasivo.", "it": "Inversione contabile.", "ar": "الاحتساب العكسي لضريبة القيمة المضافة على المستلم."},
    "intra_eu": {"fr": "Exonération de TVA - livraison intracommunautaire (art. 138 directive 2006/112/CE).", "en": "VAT exempt - intra-Community supply (Art. 138, Directive 2006/112/EC).", "de": "Steuerfreie innergemeinschaftliche Lieferung (Art. 138 MwStSystRL).", "es": "Exenta de IVA - entrega intracomunitaria (art. 138 Directiva 2006/112/CE).", "it": "Non imponibile - cessione intracomunitaria (art. 138 Direttiva 2006/112/CE).", "ar": "معفى من ضريبة القيمة المضافة - توريد داخل الاتحاد الأوروبي."},
    "export": {"fr": "Exonération de TVA - exportation.", "en": "VAT exempt - export.", "de": "Steuerfreie Ausfuhr.", "es": "Exenta de IVA - exportación.", "it": "Non imponibile - esportazione.", "ar": "معفى من ضريبة القيمة المضافة - تصدير."},
}


def legal_mentions(seller_country: str, regime: str, lang: str, is_business_client: bool = True, late_rate: str = "", doc_type: str = "invoice") -> list[str]:
    c = (seller_country or "").upper()
    out: list[str] = []
    if regime != "standard":
        t = LEGAL.get((c, regime), {})
        out.append(t.get(lang) or GENERIC[regime].get(lang) or GENERIC[regime]["en"])
    if doc_type != "invoice":  # avoirs et devis : pas de pénalités de retard
        return [x for x in out if x]
    if c == "FR" and is_business_client:  # art. L441-10 Code de commerce : mentions obligatoires entre professionnels
        rate = late_rate.strip() or ("3 fois le taux d'intérêt légal" if lang == "fr" else "3 times the legal interest rate")
        out.append({
            "fr": f"En cas de retard de paiement : pénalités au taux de {rate} et indemnité forfaitaire de 40 € pour frais de recouvrement (art. L441-10 et D441-5 du Code de commerce). Pas d'escompte pour paiement anticipé.",
        }.get(lang, f"Late payment: penalties at {rate} and a fixed recovery fee of EUR 40 (French Commercial Code L441-10, D441-5). No discount for early payment."))
    elif late_rate.strip():
        out.append({"fr": f"Pénalités de retard : {late_rate}.", "de": f"Verzugszinsen: {late_rate}.", "es": f"Intereses de demora: {late_rate}.", "it": f"Interessi di mora: {late_rate}.", "ar": f"غرامة التأخير: {late_rate}."}.get(lang, f"Late payment interest: {late_rate}."))
    return [x for x in out if x]


def warnings(inv: dict, calc: dict) -> list[str]:
    """Contrôles de conformité (liste de points à corriger ; non bloquants)."""
    w, s, cl = [], inv.get("seller", {}), inv.get("client", {})
    kind = inv.get("doc_type", "invoice")
    for k, msg in (("name", "raison sociale / nom du vendeur"), ("address", "adresse du vendeur"), ("tax_id", "numéro d'identification de l'entreprise (SIRET, HRB, P.IVA…)")):
        if not str(s.get(k, "")).strip():
            w.append(f"Vendeur : {msg} manquant(e).")
    regime = inv.get("regime", "standard")
    if regime in ("standard", "reverse_charge", "intra_eu") and not str(s.get("vat_number", "")).strip():
        w.append("Vendeur : numéro de TVA intracommunautaire manquant (obligatoire si vous êtes assujetti à la TVA).")
    if not str(cl.get("name", "")).strip() or not str(cl.get("address", "")).strip():
        w.append("Client : nom et adresse obligatoires.")
    if regime in ("reverse_charge", "intra_eu") and not str(cl.get("vat_number", "")).strip():
        w.append("Client : son numéro de TVA est obligatoire pour une autoliquidation / livraison intracommunautaire.")
    if not re.search(r"\d", str(inv.get("number", ""))):
        w.append("Numéro du document : séquence chronologique continue et unique obligatoire (ex. FA-2026-0001).")
    if kind == "invoice":
        if not inv.get("due_date"):
            w.append("Date d'échéance / conditions de paiement manquante.")
        if not str(s.get("iban", "")).strip() and inv.get("payment_method", "transfer") == "transfer":
            w.append("Coordonnées bancaires (IBAN) absentes pour un paiement par virement.")
        if s.get("country", "").upper() == "DE" and not inv.get("service_date"):
            w.append("Allemagne : la date de la prestation / livraison (Leistungsdatum) est obligatoire.")
    elif kind == "credit_note":
        if not str(inv.get("ref_number", "")).strip() or not inv.get("ref_date"):
            w.append("Avoir : indiquez le numéro et la date de la facture d'origine (obligatoire).")
        if not str(inv.get("notes", "")).strip():
            w.append("Avoir : précisez le motif (retour, remise, erreur de facturation…).")
    elif kind == "quote":
        if not inv.get("valid_until"):
            w.append("Devis : indiquez une durée de validité (date limite d'acceptation).")
    if regime == "standard" and any(v["rate"] == 0 for v in calc["vat_rows"]):
        w.append("Une ligne a une TVA à 0 % en régime standard : choisissez le régime d'exonération adapté pour afficher la mention légale.")
    return w
# --------------------------------------------------------------------------- libellés PDF
KINDS = ("invoice", "credit_note", "quote")
PREFIX = {"invoice": "FA", "credit_note": "AV", "quote": "DE"}
T = {
    "fr": dict(invoice="FACTURE", credit_note="AVOIR", quote="DEVIS", number="N°", date="Date d'émission", due="Échéance", service="Date de prestation", seller="Émetteur", client="Client", desc="Désignation", qty="Qté", unit_price="P.U. HT",
               disc="Rem.", vat="TVA", total="Total HT", base="Base HT", vat_amt="Montant TVA", ttc="Total TTC", ht="Total HT", deposit="Acompte versé", due_amt="NET À PAYER", credit_amt="À DÉDUIRE / REMBOURSER", quote_amt="MONTANT DU DEVIS", pay="Règlement",
               ref="Avoir sur la facture n°", ref_date="du", valid="Valable jusqu'au", accept="Bon pour accord - date, nom et signature du client :", reason="Motif",
               iban="IBAN", bic="BIC", method={"transfer": "Virement bancaire", "card": "Carte bancaire", "cash": "Espèces", "cheque": "Chèque", "other": "Autre"}, vat_no="N° TVA", tax_id="Identifiant", notes="Remarques", page="Page"),
    "en": dict(invoice="INVOICE", credit_note="CREDIT NOTE", quote="QUOTE", number="No.", date="Issue date", due="Due date", service="Service date", seller="From", client="Bill to", desc="Description", qty="Qty", unit_price="Unit price",
               disc="Disc.", vat="VAT", total="Net total", base="Net base", vat_amt="VAT amount", ttc="Total incl. VAT", ht="Total excl. VAT", deposit="Deposit paid", due_amt="AMOUNT DUE", credit_amt="CREDIT TO DEDUCT / REFUND", quote_amt="QUOTE TOTAL", pay="Payment",
               ref="Credit note for invoice no.", ref_date="dated", valid="Valid until", accept="Accepted - date, name and signature of the customer:", reason="Reason",
               iban="IBAN", bic="BIC", method={"transfer": "Bank transfer", "card": "Card", "cash": "Cash", "cheque": "Cheque", "other": "Other"}, vat_no="VAT no.", tax_id="Company ID", notes="Notes", page="Page"),
    "de": dict(invoice="RECHNUNG", credit_note="GUTSCHRIFT", quote="ANGEBOT", number="Nr.", date="Rechnungsdatum", due="Fällig am", service="Leistungsdatum", seller="Rechnungssteller", client="Rechnungsempfänger", desc="Bezeichnung", qty="Menge", unit_price="Einzelpreis",
               disc="Rab.", vat="USt", total="Netto", base="Nettobetrag", vat_amt="USt-Betrag", ttc="Gesamt brutto", ht="Gesamt netto", deposit="Anzahlung", due_amt="ZAHLBETRAG", credit_amt="GUTSCHRIFTSBETRAG", quote_amt="ANGEBOTSSUMME", pay="Zahlung",
               ref="Gutschrift zur Rechnung Nr.", ref_date="vom", valid="Gültig bis", accept="Angenommen - Datum, Name und Unterschrift des Kunden:", reason="Grund",
               iban="IBAN", bic="BIC", method={"transfer": "Überweisung", "card": "Karte", "cash": "Bar", "cheque": "Scheck", "other": "Sonstige"}, vat_no="USt-IdNr.", tax_id="Steuernr./HRB", notes="Hinweise", page="Seite"),
    "es": dict(invoice="FACTURA", credit_note="NOTA DE CRÉDITO", quote="PRESUPUESTO", number="N.º", date="Fecha de emisión", due="Vencimiento", service="Fecha de servicio", seller="Emisor", client="Cliente", desc="Descripción", qty="Cant.", unit_price="Precio",
               disc="Dto.", vat="IVA", total="Total", base="Base imponible", vat_amt="Cuota IVA", ttc="Total con IVA", ht="Base total", deposit="Anticipo", due_amt="TOTAL A PAGAR", credit_amt="IMPORTE A DEDUCIR / REEMBOLSAR", quote_amt="TOTAL DEL PRESUPUESTO", pay="Pago",
               ref="Rectificativa de la factura n.º", ref_date="del", valid="Válido hasta", accept="Conforme - fecha, nombre y firma del cliente:", reason="Motivo",
               iban="IBAN", bic="BIC", method={"transfer": "Transferencia", "card": "Tarjeta", "cash": "Efectivo", "cheque": "Cheque", "other": "Otro"}, vat_no="NIF-IVA", tax_id="NIF/CIF", notes="Notas", page="Página"),
    "it": dict(invoice="FATTURA", credit_note="NOTA DI CREDITO", quote="PREVENTIVO", number="N.", date="Data emissione", due="Scadenza", service="Data prestazione", seller="Emittente", client="Cliente", desc="Descrizione", qty="Q.tà", unit_price="Prezzo",
               disc="Sc.", vat="IVA", total="Totale", base="Imponibile", vat_amt="Importo IVA", ttc="Totale IVA incl.", ht="Totale imponibile", deposit="Acconto", due_amt="DA PAGARE", credit_amt="IMPORTO DA DEDURRE / RIMBORSARE", quote_amt="TOTALE PREVENTIVO", pay="Pagamento",
               ref="Nota di credito sulla fattura n.", ref_date="del", valid="Valido fino al", accept="Per accettazione - data, nome e firma del cliente:", reason="Motivo",
               iban="IBAN", bic="BIC", method={"transfer": "Bonifico", "card": "Carta", "cash": "Contanti", "cheque": "Assegno", "other": "Altro"}, vat_no="P. IVA", tax_id="Cod. fiscale", notes="Note", page="Pagina"),
    "ar": dict(invoice="فاتورة", credit_note="إشعار دائن", quote="عرض سعر", number="رقم", date="تاريخ الإصدار", due="تاريخ الاستحقاق", service="تاريخ الخدمة", seller="المُصدِر", client="العميل", desc="البيان", qty="الكمية", unit_price="سعر الوحدة",
               disc="خصم", vat="ض.ق.م", total="المجموع", base="الأساس", vat_amt="قيمة الضريبة", ttc="الإجمالي شامل الضريبة", ht="الإجمالي بدون ضريبة", deposit="دفعة مقدمة", due_amt="المبلغ المستحق", credit_amt="المبلغ المخصوم / المسترد", quote_amt="إجمالي عرض السعر", pay="الدفع",
               ref="إشعار دائن للفاتورة رقم", ref_date="بتاريخ", valid="صالح حتى", accept="موافقة العميل - التاريخ والاسم والتوقيع:", reason="السبب",
               iban="IBAN", bic="BIC", method={"transfer": "تحويل بنكي", "card": "بطاقة", "cash": "نقداً", "cheque": "شيك", "other": "أخرى"}, vat_no="الرقم الضريبي", tax_id="السجل التجاري", notes="ملاحظات", page="صفحة"),
}


def money(d: Decimal, cur: str, lang: str) -> str:
    s = f"{q2(d):,.2f}"  # 1,234.56
    if lang in ("fr", "es", "it", "de"):
        s = s.replace(",", "\u202f").replace(".", ",") if lang in ("fr",) else s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} {CURRENCIES.get(cur, cur)}"


def pct(d: Decimal) -> str:
    return (f"{d.normalize():f}" if d != d.to_integral() else str(int(d))) + " %"


_LATIN = {}


def latin_fonts() -> tuple[str, str] | None:
    """Police latine TrueType à INCORPORER (obligatoire pour PDF/A). Cherche CAREER_LATIN_FONT_*, backend/fonts/NotoSans-*.ttf puis DejaVu Sans."""
    import os
    from pathlib import Path
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    if "v" in _LATIN:
        return _LATIN["v"]
    fd = pdf_gen.FONT_DIR
    pairs = [(os.getenv("CAREER_LATIN_FONT_REGULAR"), os.getenv("CAREER_LATIN_FONT_BOLD")), (fd / "NotoSans-Regular.ttf", fd / "NotoSans-Bold.ttf"),
             ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
             ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"), ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf")]
    for r, b in pairs:
        if r and Path(r).exists():
            pdfmetrics.registerFont(TTFont("INV-Reg", str(r))); pdfmetrics.registerFont(TTFont("INV-Bold", str(b if b and Path(b).exists() else r)))
            _LATIN["v"] = ("INV-Reg", "INV-Bold"); return _LATIN["v"]
    _LATIN["v"] = None
    return None


def invoice_pdf(inv: dict, lang: str = "fr", embed_fonts: bool = False) -> tuple[bytes, dict]:
    """PDF A4 d'une facture, d'un avoir ou d'un devis (`inv["doc_type"]`) ; retourne (octets, calcul). embed_fonts : polices incorporées (Factur-X / PDF/A)."""
    kind = inv.get("doc_type", "invoice")
    if kind not in KINDS:
        raise ValueError("type de document inconnu")
    credit = kind == "credit_note"; quote = kind == "quote"
    calc = compute(inv["lines"], inv.get("regime", "standard"), inv.get("deposit", 0) if kind == "invoice" else 0)
    lb = T.get(lang, T["en"]); rtl = lang == "ar"; cur = inv.get("currency", "EUR")
    FR_, FB_ = (latin_fonts() or ("Helvetica", "Helvetica-Bold")) if embed_fonts else ("Helvetica", "Helvetica-Bold")
    sg = Decimal(-1) if credit else Decimal(1)  # avoir : montants affichés en négatif
    M = lambda d: money(sg * d, cur, lang)
    s, cl = inv.get("seller", {}), inv.get("client", {})
    w, h = A4; m = 1.8 * cm; cw = w - 2 * m
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4, invariant=1 if embed_fonts else 0, initialFontName=FR_); c.setTitle(f"{lb[kind]} {inv.get('number', '')}")
    c.setAuthor(s.get("name", "")); c.setCreator("CARRIVA"); c.setProducer("CARRIVA")
    ACC = colors.HexColor("#7C2D12" if credit else "#0F4C3A" if quote else "#0F2A4F"); LINE = colors.HexColor("#d5dce8"); BG = colors.HexColor("#F1F5FB")
    al = TA_RIGHT if rtl else TA_LEFT
    base = ParagraphStyle("i", fontName=FR_, fontSize=9, leading=12, textColor=colors.black, alignment=al)
    bold = ParagraphStyle("ib", parent=base, fontName=FB_)
    gray = ParagraphStyle("ig", parent=base, textColor=pdf_gen.GRAY, fontSize=8, leading=11)
    ttl = ParagraphStyle("it", parent=base, fontName=FB_, fontSize=24, leading=28, textColor=ACC)
    P = lambda t, st, wd: pdf_gen.para(t, st, wd, lang, st.alignment)
    state = {"y": h - m, "page": 1}

    def draw(p, x, wd):
        _, ph = p.wrap(wd, h); p.drawOn(c, x, state["y"] - ph); return ph

    def party(title, d, x, wd):
        lines = [d.get("name", ""), d.get("address", "")]
        city = " ".join(x for x in (str(d.get("postcode", "")).strip(), str(d.get("city", "")).strip()) if x)
        if city and city not in str(d.get("address", "")):
            lines.append(city)
        for k, lab in (("tax_id", lb["tax_id"]), ("vat_number", lb["vat_no"])):
            if str(d.get(k, "")).strip():
                lines.append(f"{lab} : {d[k]}")
        for k in ("email", "phone"):
            if str(d.get(k, "")).strip():
                lines.append(str(d[k]))
        y0 = state["y"]; ph = draw(P(title.upper(), ParagraphStyle("pt", parent=gray, fontName=FB_, textColor=ACC), wd), x, wd)
        state["y"] -= ph + 2
        ph2 = draw(P(d.get("name", ""), bold, wd), x, wd); state["y"] -= ph2
        ph3 = draw(P("\n".join(l for l in lines[1:] if l), base, wd), x, wd)
        used = y0 - (state["y"] - ph3); state["y"] = y0; return used

    # en-tête : titre + n° / dates (+ facture d'origine / validité)
    ph = draw(P(lb[kind], ttl, cw), m, cw)
    meta = [f"{lb['number']} {inv.get('number', '')}", f"{lb['date']} : {inv.get('issue_date', '')}"]
    if kind == "invoice":
        meta.append(f"{lb['due']} : {inv.get('due_date', '')}")
        if inv.get("service_date"):
            meta.append(f"{lb['service']} : {inv['service_date']}")
    elif credit:
        meta.append(f"{lb['ref']} {inv.get('ref_number', '')} {lb['ref_date']} {inv.get('ref_date', '')}")
    else:
        meta.append(f"{lb['valid']} : {inv.get('valid_until', '')}")
    state["y"] -= ph + 6
    ph = draw(P("\n".join(meta), bold, cw), m, cw); state["y"] -= ph + 16
    colw = (cw - 1 * cm) / 2
    xs = (m + colw + 1 * cm, m) if rtl else (m, m + colw + 1 * cm)
    used = max(party(lb["seller"], s, xs[0], colw), party(lb["client"], cl, xs[1], colw)); state["y"] -= used + 18

    # tableau des lignes (peut s'étendre sur plusieurs pages)
    cols = [cw * 0.39, cw * 0.08, cw * 0.13, cw * 0.08, cw * 0.08, cw * 0.24]
    head = [lb["desc"], lb["qty"], lb["unit_price"], lb["disc"], lb["vat"], lb["total"]]
    rows = [[P(x, ParagraphStyle("h", parent=bold, textColor=colors.white, fontSize=8, alignment=TA_RIGHT if (i and not rtl) else al), cols[i]) for i, x in enumerate(head)]]
    for ln in calc["lines"]:
        d = ln["description"] + (f"\n({ln['unit']})" if ln["unit"] else "")
        cells = [d, f"{ln['qty'].normalize():f}", money(ln["unit_price"], cur, lang), pct(ln["discount"]) if ln["discount"] else "", pct(ln["vat"]) if inv.get("regime", "standard") == "standard" else "—", M(ln["net"])]
        rows.append([P(x, ParagraphStyle("c", parent=base, alignment=TA_RIGHT if (i and not rtl) else al), cols[i]) for i, x in enumerate(cells)])
    if rtl:
        rows = [r[::-1] for r in rows]; cols = cols[::-1]
    tb = Table(rows, colWidths=cols, repeatRows=1)
    tb.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FR_), ("BACKGROUND", (0, 0), (-1, 0), ACC), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
                            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG])]))
    avail = state["y"] - 6 * cm
    parts = tb.split(cw, max(avail, 1)) or [tb]
    for i, part in enumerate(parts):
        _, th = part.wrap(cw, h)
        if i and state["y"] - th < m + 2 * cm:  # pas de place : nouvelle page
            c.showPage(); state["y"] = h - m; state["page"] += 1
        part.drawOn(c, m, state["y"] - th); state["y"] -= th + 4
        if i < len(parts) - 1:
            c.showPage(); state["y"] = h - m; state["page"] += 1
    if state["y"] < 9 * cm:
        c.showPage(); state["y"] = h - m; state["page"] += 1
    state["y"] -= 12

    # totaux (à droite, à gauche en arabe) : base / TVA par taux
    std = inv.get("regime", "standard") == "standard"
    trows = [[lb["ht"], M(calc["total_ht"])]]
    if std:
        for v in calc["vat_rows"]:
            trows.append([f"{lb['vat']} {pct(v['rate'])} ({lb['base']} {M(v['base'])})", M(v["vat"])])
    trows.append([lb["ttc"], M(calc["total_ttc"])])
    if calc["deposit"]:
        trows.append([lb["deposit"], "− " + money(calc["deposit"], cur, lang)])
    tw = 9.2 * cm
    tr = [[P(a, ParagraphStyle("t", parent=base, alignment=al), tw * 0.64), P(b, ParagraphStyle("tv", parent=bold, alignment=TA_LEFT if rtl else TA_RIGHT), tw * 0.36)] for a, b in trows]
    t2 = Table(tr, colWidths=[tw * 0.64, tw * 0.36]); t2.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FR_), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    tx = m if rtl else w - m - tw
    _, th = t2.wrap(tw, h); t2.drawOn(c, tx, state["y"] - th); state["y"] -= th + 4
    final_label = lb["credit_amt"] if credit else lb["quote_amt"] if quote else lb["due_amt"]
    bt = Table([[P(final_label, ParagraphStyle("bd", parent=bold, textColor=colors.white, alignment=al), tw * 0.5), P(M(calc["due"]), ParagraphStyle("bv", parent=bold, textColor=colors.white, fontSize=11, alignment=TA_LEFT if rtl else TA_RIGHT), tw * 0.5)]], colWidths=[tw * 0.5, tw * 0.5])
    bt.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FR_), ("BACKGROUND", (0, 0), (-1, -1), ACC), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    _, bh = bt.wrap(tw, h); bt.drawOn(c, tx, state["y"] - bh); state["y"] -= bh + 18

    # règlement + mentions légales + remarques
    notes = []
    if kind == "invoice":
        notes.append(f"{lb['pay']} : {lb['method'].get(inv.get('payment_method', 'transfer'), '')}")
        if str(s.get("iban", "")).strip():
            notes.append(f"{lb['iban']} : {s['iban']}" + (f"   {lb['bic']} : {s['bic']}" if str(s.get("bic", "")).strip() else ""))
    notes += legal_mentions(s.get("country", ""), inv.get("regime", "standard"), lang, bool(cl.get("is_business", True)), str(inv.get("late_rate", "")), kind)
    if str(inv.get("notes", "")).strip():
        notes.append(f"{lb['reason'] if credit else lb['notes']} : {inv['notes']}")
    for i, n in enumerate(notes):
        st = base if i == 0 else gray
        p = P(n, st, cw); _, ph = p.wrap(cw, h)
        if state["y"] - ph < m:
            c.showPage(); state["y"] = h - m; state["page"] += 1
        p.drawOn(c, m, state["y"] - ph); state["y"] -= ph + 4
    if quote:  # cadre « Bon pour accord »
        bw, bh2 = cw, 2.6 * cm
        if state["y"] - bh2 - 0.6 * cm < m:
            c.showPage(); state["y"] = h - m; state["page"] += 1
        state["y"] -= 0.4 * cm
        c.setStrokeColor(LINE); c.setLineWidth(0.8); c.roundRect(m, state["y"] - bh2, bw, bh2, 6, stroke=1, fill=0)
        p = P(lb["accept"], gray, bw - 0.8 * cm); _, ph = p.wrap(bw - 0.8 * cm, h); p.drawOn(c, m + 0.4 * cm, state["y"] - 0.3 * cm - ph); state["y"] -= bh2
    c.setFont(FR_, 7); c.setFillColor(pdf_gen.GRAY)
    c.drawCentredString(w / 2, 0.9 * cm, f"{inv.get('number', '')} · {lb['page']} {state['page']}")
    c.showPage(); c.save()
    return buf.getvalue(), calc


def next_number(last: str, today: date | None = None, kind: str = "invoice") -> str:
    """Numéro suivant dans la séquence : « FA-2026-0007 » -> « FA-2026-0008 » ; nouvelle année : repart à 0001. Préfixes : FA / AV (avoir) / DE (devis)."""
    today = today or date.today()
    pfx = PREFIX.get(kind, "FA")
    m = re.fullmatch(r"(.*?)(\d{4})[-/](\d+)", (last or "").strip())
    if not m:
        return f"{pfx}-{today.year}-0001"
    pre, year, n = m.groups()
    if int(year) != today.year:
        return f"{pre}{today.year}-{'1'.zfill(len(n))}"
    return f"{pre}{year}-{str(int(n) + 1).zfill(len(n))}"


def due_from(issue: str, days: int) -> str:
    return (date.fromisoformat(issue) + timedelta(days=days)).isoformat()
