"""Bouton 2 (Espace Entreprise) : messagerie WhatsApp Business & Facebook Messenger — copilote de vente sociale et de SAV.

Règles déterministes, sans IA ni tiers : analyse le message du client (intention, chaleur, tempérament), puis rédige 3 réponses prêtes à
copier (express / persuasive / réassurance-SAV) selon la structure « accroche – valeur – question fermée », et un conseil pour le gérant.
Garde-fous : aucun prix, stock ou caractéristique inventé (donnée absente → marqueur « [⚠️ À COMPLÉTER : … ] ») ; la rareté n'est mentionnée que si
le gérant l'a indiquée ; pas de remise immédiate sur une objection de prix (valeur d'abord). Le « prompt maître » rempli est aussi renvoyé pour
être collé dans une IA de son choix. Aucun envoi : le gérant copie et envoie lui-même.
"""
from __future__ import annotations

import re

LANGS = ("fr", "en", "de", "es", "it", "ar")
CHANNELS = ("whatsapp", "messenger")
INTENTS = ("curiosity", "comparison", "purchase", "objection", "complaint", "support")
HEATS = ("cold", "warm", "hot", "burning")
TEMPERS = ("rushed", "distrustful", "enthusiastic", "annoyed", "technical", "neutral")
MAX_MSG = 2000
MAX_FIELD = 300
SALES = ("curiosity", "comparison", "purchase", "objection")

# ----------------------------------------------------------------------------------------------- analyse
_W = lambda s: re.compile(r"(?<!\w)(?:" + s + r")(?!\w)", re.I)
LEX = {
    "complaint": _W(r"arnaque\w*|escroc\w*|rembours\w*|pas re[çc]u|jamais re[çc]u|cass[ée]\w*|ab[îi]m[ée]\w*|d[ée]fectueu\w*|inadmissible|scandale|plainte|litige|"
                    r"scam|refund\w*|broken|damaged|not received|never (?:arrived|received)|complaint|defective|betrug|erstattung|kaputt|besch[äa]digt|nicht erhalten|"
                    r"reclamo|reembolso|roto|da[ñn]ado|no he recibido|rimborso|rotto|danneggiato|non ricevuto|truffa|estafa|"
                    r"مشكل\w*|لم يصل\w*|استرجاع|نصب|تالف|مكسور|ماوصلنيش|ما وصلنيش|فلوسي|mochkil\w*"),
    "support": _W(r"suivi|tracking|o[uù] est (?:ma|mon)|statut|annuler|modifier ma commande|mode d'emploi|comment utiliser|where is my|how to use|cancel\w*|track\w*|"
                  r"wo ist mein\w*|stornieren|d[óo]nde est[áa] mi|cancelar|dov'[èe]|annullare|أين طلبي|إلغاء|فين طلبي"),
    "objection": _W(r"cher|trop cher|r[ée]duction|remise|promo\w*|rabais|moins cher|baisser|dernier prix|expensive|too much|discount\w*|cheaper|last price|teuer|"
                    r"rabatt|g[üu]nstiger|caro|descuento|barato|costoso|sconto|economico|غالي|تخفيض|تنقص\w*|bezzaf|ghali|t9ass|na9es|nakes"),
    "purchase": _W(r"je prends|je veux (?:commander|acheter)|je commande|commander|acheter|comment (?:commander|payer)|o[uù] payer|adresse de livraison|je valide|"
                   r"i'?ll take|i want to (?:buy|order)|buy|how (?:to|do i) (?:pay|order)|checkout|ich nehme|bestellen|kaufen|quiero (?:comprar|pedir)|lo quiero|comprar|"
                   r"lo prendo|voglio ordinare|acquistare|ordinare|أريد أن أطلب|أريد شراء|بغيت نطلب|بغيت نشري|نشري|bghit nechri|bghit ntlob"),
    "comparison": _W(r"autre marque|ailleurs|concurrent\w*|compar\w+|diff[ée]rence|versus|vs|meilleur que|other brand|elsewhere|compare|difference|better than|"
                     r"andere marke|anderswo|unterschied|otra marca|en otro lado|diferencia|altra marca|altrove|differenza|مقارنة|الفرق|عند غيركم"),
}
URGENT = _W(r"urgent\w*|vite|maintenant|aujourd'hui|asap|now|today|tout de suite|sofort|heute|ahora|hoy|subito|oggi|الآن|اليوم|دابا|فورا|daba")
AVAIL = _W(r"dispo\w*|stock|available|availability|verf[üu]gbar|disponible|disponibile|متوفر\w*|موجود\w*")
T_ANNOYED = _W(r"nul|marre|toujours pas|enfin|inadmissible|honteux|furieux|[ée]nerv\w+|terrible|awful|angry|unacceptable|still (?:no|not)|worst|schlecht|w[üu]tend|"
               r"inakzeptabel|enfadado|inaceptable|arrabbiato|inaccettabile|غاضب|سيء|مستاء")
T_DISTRUST = _W(r"arnaque\w*|vraiment|s[ée]rieux|fiable|garantie\w*|confiance|faux|fake|scam|trust|legit|real\?|guarantee\w*|vertrauen|seri[öo]s|confianza|fiable|fiducia|"
                r"garanzia|ثقة|مضمون\w*|ماشي نصب|machi nssab")
T_TECH = _W(r"composition|ingr[ée]dients?|dimensions?|sp[ée]cifications?|compatible|puissance|mat[ée]riau\w*|material|specs?|ingredients?|size|weight|poids|"
            r"zusammensetzung|ingredientes|composizione|مكونات|مواصفات|المقاس\w*")
T_ENTH = _W(r"j'adore|super|g[ée]nial\w*|love|great|amazing|toll|genial|encanta|bellissim\w*|رائع\w*|ممتاز\w*|top")
EMOJI_ANGRY = re.compile("[😡🤬😠👎]")
EMOJI_HAPPY = re.compile("[😍❤️🥰🤩👍🔥]")


def _caps_ratio(s: str) -> float:
    letters = [c for c in s if c.isalpha() and c.isascii()]
    return sum(c.isupper() for c in letters) / len(letters) if len(letters) >= 8 else 0.0


def analyse(message: str, channel: str = "whatsapp") -> dict:
    m = message or ""
    intent = "curiosity"
    for k in ("complaint", "support", "objection", "purchase", "comparison"):
        if LEX[k].search(m):
            intent = k
            break
    urgent = bool(URGENT.search(m))
    heat = {"curiosity": "cold", "comparison": "warm", "objection": "warm", "support": "warm", "purchase": "hot", "complaint": "warm"}[intent]
    if intent == "curiosity" and AVAIL.search(m):
        heat = "warm"
    if urgent and intent in ("purchase", "complaint", "support", "objection"):
        heat = "burning"
    if T_ANNOYED.search(m) or EMOJI_ANGRY.search(m) or _caps_ratio(m) > .6 or intent == "complaint" and "!!" in m:
        temper = "annoyed"
    elif T_DISTRUST.search(m):
        temper = "distrustful"
    elif urgent or len(m.split()) <= 3 and "?" in m:
        temper = "rushed"
    elif T_TECH.search(m):
        temper = "technical"
    elif T_ENTH.search(m) or EMOJI_HAPPY.search(m):
        temper = "enthusiastic"
    else:
        temper = "neutral"
    return {"intent": intent, "heat": heat, "temperament": temper, "channel": channel}


# ----------------------------------------------------------------------------------------------- textes
TXT = {
 "fr": {
  "tag": "À COMPLÉTER", "ph": {"offer": "l'offre ou le produit", "price": "le prix", "cross": "un produit complémentaire", "guar": "la garantie ou la politique de retour"},
  "hook": {"curiosity": "Bonjour et merci pour votre intérêt !", "comparison": "Merci de comparer, c'est une très bonne démarche !", "purchase": "Super choix, merci pour votre confiance !",
           "objection": "Je comprends tout à fait que le budget compte.", "complaint": "Je suis vraiment désolé(e) pour ce désagrément, et merci de m'en avoir informé(e).",
           "support": "Bien sûr, je m'en occupe tout de suite."},
  "value": {"curiosity": "Chez {brand}, nous proposons {offer}. {price}", "comparison": "Ce qui fait la différence chez {brand} : {offer}. {price}",
            "purchase": "Je réserve {offer} pour vous. {price}{logi}", "objection": "Ce prix reflète la qualité et la durabilité : {offer}. {price}",
            "complaint": "Votre dossier est ma priorité : je vérifie la situation et je reviens vers vous avec une solution concrète.",
            "support": "Je vérifie les informations de votre demande et je vous réponds précisément."},
  "cta": {"curiosity": "Souhaitez-vous que je vous envoie les détails, oui ou non ?", "comparison": "Voulez-vous que je vous explique la différence principale, oui ou non ?",
          "purchase": "Je valide votre commande maintenant, oui ou non ?", "objection": "Préférez-vous (A) garder cette offre avec sa garantie ou (B) voir une option plus accessible ?",
          "complaint": "Préférez-vous (A) un remplacement ou (B) un remboursement ?", "support": "Puis-je vous demander votre numéro de commande pour vérifier, oui ou non ?"},
  "cta3": "Préférez-vous (A) continuer ici ou (B) être rappelé(e) ?", "price": "Prix : {p}. ", "logi": "Livraison et paiement : {l}. ",
  "scarce": "Le stock est limité sur cette offre.", "cross": "Beaucoup de nos clients prennent aussi {x} pour optimiser le résultat.",
  "reas_sales": "Vous pouvez acheter en confiance : {g}.", "reas_claim": "Je reste personnellement votre interlocuteur jusqu'à la résolution complète.",
  "t_annoyed": "Toutes mes excuses.", "t_rushed": "Réponse rapide :", "msgr": "Je reste disponible ici, n'hésitez pas à m'écrire à tout moment.",
  "advice": {"curiosity": "S'il répond oui, envoyez détails, prix et lien de commande dans le même message ; sans réponse sous 24 h, une relance douce avec un avantage concret.",
             "comparison": "S'il cite un concurrent, ne le dénigrez pas : comparez sur la garantie, le service et la durabilité, puis proposez l'essai.",
             "purchase": "S'il dit oui, confirmez adresse et mode de paiement dans le même message pour conclure vite ; s'il hésite, ne gardez que le choix A/B.",
             "objection": "S'il insiste sur le prix, proposez une alternative ou un format réduit plutôt qu'une remise immédiate ; votre marge est votre marge de manœuvre.",
             "complaint": "S'il se calme, proposez tout de suite la solution (remplacement ou remboursement) ; s'il reste agacé, passez à un appel et prenez la main personnellement.",
             "support": "S'il donne son numéro de commande, répondez sous 5 minutes ; sinon relancez une fois, puis clôturez poliment en laissant la porte ouverte."}},
 "en": {
  "tag": "TO COMPLETE", "ph": {"offer": "the offer or product", "price": "the price", "cross": "a complementary product", "guar": "the warranty or return policy"},
  "hook": {"curiosity": "Hello, and thank you for your interest!", "comparison": "Thanks for comparing, that's a smart move!", "purchase": "Great choice, thank you for your trust!",
           "objection": "I completely understand that budget matters.", "complaint": "I'm truly sorry for the trouble, and thank you for letting me know.",
           "support": "Of course, I'm on it right away."},
  "value": {"curiosity": "At {brand}, we offer {offer}. {price}", "comparison": "What makes the difference at {brand}: {offer}. {price}",
            "purchase": "I'm reserving {offer} for you. {price}{logi}", "objection": "This price reflects quality and durability: {offer}. {price}",
            "complaint": "Your case is my priority: I'm checking the situation and will come back with a concrete solution.",
            "support": "I'm checking the details of your request and will answer precisely."},
  "cta": {"curiosity": "Would you like me to send the details, yes or no?", "comparison": "Shall I explain the main difference, yes or no?",
          "purchase": "Shall I confirm your order now, yes or no?", "objection": "Would you prefer (A) to keep this offer with its warranty or (B) to see a more affordable option?",
          "complaint": "Would you prefer (A) a replacement or (B) a refund?", "support": "May I ask for your order number to check, yes or no?"},
  "cta3": "Would you prefer (A) to continue here or (B) to get a call back?", "price": "Price: {p}. ", "logi": "Delivery and payment: {l}. ",
  "scarce": "Stock is limited on this offer.", "cross": "Many of our customers also take {x} to get the best result.",
  "reas_sales": "You can buy with confidence: {g}.", "reas_claim": "I'll stay your personal contact until it's fully resolved.",
  "t_annoyed": "My sincere apologies.", "t_rushed": "Quick answer:", "msgr": "I'm available here, feel free to write to me any time.",
  "advice": {"curiosity": "If they say yes, send details, price and order link in the same message; no reply within 24 h, send a gentle follow-up with a concrete benefit.",
             "comparison": "If they name a competitor, don't criticise it: compare on warranty, service and durability, then offer a trial.",
             "purchase": "If they say yes, confirm address and payment method in the same message to close fast; if they hesitate, keep only the A/B choice.",
             "objection": "If they keep pushing on price, offer an alternative or smaller format rather than an immediate discount; your margin is your room to manoeuvre.",
             "complaint": "If they calm down, offer the fix (replacement or refund) right away; if they stay upset, switch to a call and take it over personally.",
             "support": "If they give the order number, reply within 5 minutes; otherwise follow up once, then close politely leaving the door open."}},
 "de": {
  "tag": "ZU ERGÄNZEN", "ph": {"offer": "das Angebot oder Produkt", "price": "den Preis", "cross": "ein passendes Zusatzprodukt", "guar": "Garantie oder Rückgaberecht"},
  "hook": {"curiosity": "Hallo und vielen Dank für Ihr Interesse!", "comparison": "Danke fürs Vergleichen, das ist sehr klug!", "purchase": "Tolle Wahl, vielen Dank für Ihr Vertrauen!",
           "objection": "Ich verstehe gut, dass das Budget zählt.", "complaint": "Es tut mir wirklich leid für die Unannehmlichkeiten, danke für den Hinweis.",
           "support": "Selbstverständlich, ich kümmere mich sofort darum."},
  "value": {"curiosity": "Bei {brand} bieten wir {offer}. {price}", "comparison": "Der Unterschied bei {brand}: {offer}. {price}",
            "purchase": "Ich reserviere {offer} für Sie. {price}{logi}", "objection": "Dieser Preis steht für Qualität und Langlebigkeit: {offer}. {price}",
            "complaint": "Ihr Anliegen hat Priorität: Ich prüfe die Lage und melde mich mit einer konkreten Lösung.",
            "support": "Ich prüfe die Angaben zu Ihrer Anfrage und antworte Ihnen genau."},
  "cta": {"curiosity": "Soll ich Ihnen die Details schicken, ja oder nein?", "comparison": "Soll ich den Hauptunterschied erklären, ja oder nein?",
          "purchase": "Soll ich Ihre Bestellung jetzt bestätigen, ja oder nein?", "objection": "Möchten Sie (A) dieses Angebot mit Garantie behalten oder (B) eine günstigere Option sehen?",
          "complaint": "Möchten Sie (A) einen Ersatz oder (B) eine Erstattung?", "support": "Darf ich Ihre Bestellnummer zur Prüfung erfragen, ja oder nein?"},
  "cta3": "Möchten Sie (A) hier weiterschreiben oder (B) zurückgerufen werden?", "price": "Preis: {p}. ", "logi": "Lieferung und Zahlung: {l}. ",
  "scarce": "Der Bestand ist bei diesem Angebot begrenzt.", "cross": "Viele unserer Kunden nehmen auch {x} für das beste Ergebnis.",
  "reas_sales": "Sie können beruhigt kaufen: {g}.", "reas_claim": "Ich bleibe bis zur vollständigen Lösung Ihr persönlicher Ansprechpartner.",
  "t_annoyed": "Entschuldigen Sie bitte.", "t_rushed": "Kurze Antwort:", "msgr": "Ich bin hier erreichbar, schreiben Sie mir jederzeit.",
  "advice": {"curiosity": "Sagt der Kunde ja, schicken Sie Details, Preis und Bestelllink in einer Nachricht; ohne Antwort nach 24 h eine sanfte Erinnerung mit konkretem Vorteil.",
             "comparison": "Nennt er einen Mitbewerber, nicht abwerten: nach Garantie, Service und Haltbarkeit vergleichen, dann einen Test anbieten.",
             "purchase": "Bei ja Adresse und Zahlungsart in derselben Nachricht bestätigen; zögert er, nur die A/B-Wahl lassen.",
             "objection": "Beharrt er auf dem Preis, eine Alternative oder kleinere Größe anbieten statt sofort Rabatt.",
             "complaint": "Beruhigt er sich, sofort die Lösung (Ersatz oder Erstattung) anbieten; bleibt er verärgert, anrufen und selbst übernehmen.",
             "support": "Nennt er die Bestellnummer, innerhalb von 5 Minuten antworten; sonst einmal nachfassen und höflich abschließen."}},
 "es": {
  "tag": "POR COMPLETAR", "ph": {"offer": "la oferta o el producto", "price": "el precio", "cross": "un producto complementario", "guar": "la garantía o política de devolución"},
  "hook": {"curiosity": "¡Hola y gracias por su interés!", "comparison": "¡Gracias por comparar, es muy buena idea!", "purchase": "¡Excelente elección, gracias por su confianza!",
           "objection": "Entiendo perfectamente que el presupuesto importa.", "complaint": "Lamento mucho el inconveniente, y gracias por avisarme.",
           "support": "Por supuesto, me ocupo ahora mismo."},
  "value": {"curiosity": "En {brand} ofrecemos {offer}. {price}", "comparison": "Lo que marca la diferencia en {brand}: {offer}. {price}",
            "purchase": "Le reservo {offer}. {price}{logi}", "objection": "Este precio refleja calidad y durabilidad: {offer}. {price}",
            "complaint": "Su caso es mi prioridad: reviso la situación y le respondo con una solución concreta.",
            "support": "Reviso los datos de su solicitud y le respondo con precisión."},
  "cta": {"curiosity": "¿Quiere que le envíe los detalles, sí o no?", "comparison": "¿Le explico la diferencia principal, sí o no?",
          "purchase": "¿Confirmo su pedido ahora, sí o no?", "objection": "¿Prefiere (A) mantener esta oferta con su garantía o (B) ver una opción más accesible?",
          "complaint": "¿Prefiere (A) un reemplazo o (B) un reembolso?", "support": "¿Puedo pedirle su número de pedido para verificar, sí o no?"},
  "cta3": "¿Prefiere (A) seguir aquí o (B) que le llamemos?", "price": "Precio: {p}. ", "logi": "Entrega y pago: {l}. ",
  "scarce": "El stock es limitado en esta oferta.", "cross": "Muchos clientes también llevan {x} para optimizar el resultado.",
  "reas_sales": "Puede comprar con confianza: {g}.", "reas_claim": "Seguiré siendo su contacto personal hasta la resolución completa.",
  "t_annoyed": "Mis más sinceras disculpas.", "t_rushed": "Respuesta rápida:", "msgr": "Sigo disponible aquí, escríbame cuando quiera.",
  "advice": {"curiosity": "Si dice que sí, envíe detalles, precio y enlace de pedido en el mismo mensaje; sin respuesta en 24 h, un recordatorio suave con un beneficio concreto.",
             "comparison": "Si nombra a un competidor, no lo critique: compare garantía, servicio y durabilidad, y ofrezca una prueba.",
             "purchase": "Si dice que sí, confirme dirección y forma de pago en el mismo mensaje; si duda, deje solo la opción A/B.",
             "objection": "Si insiste en el precio, ofrezca una alternativa o formato menor antes que un descuento inmediato.",
             "complaint": "Si se calma, proponga ya la solución (reemplazo o reembolso); si sigue molesto, pase a una llamada y asuma el caso.",
             "support": "Si da el número de pedido, responda en 5 minutos; si no, insista una vez y cierre con cortesía."}},
 "it": {
  "tag": "DA COMPLETARE", "ph": {"offer": "l'offerta o il prodotto", "price": "il prezzo", "cross": "un prodotto complementare", "guar": "la garanzia o la politica di reso"},
  "hook": {"curiosity": "Buongiorno e grazie per l'interesse!", "comparison": "Grazie per aver confrontato, ottima idea!", "purchase": "Ottima scelta, grazie per la fiducia!",
           "objection": "Capisco perfettamente che il budget conti.", "complaint": "Mi dispiace davvero per il disagio, e grazie per averlo segnalato.",
           "support": "Certo, me ne occupo subito."},
  "value": {"curiosity": "Da {brand} proponiamo {offer}. {price}", "comparison": "Ciò che fa la differenza da {brand}: {offer}. {price}",
            "purchase": "Riservo {offer} per lei. {price}{logi}", "objection": "Questo prezzo riflette qualità e durata: {offer}. {price}",
            "complaint": "La sua pratica è la mia priorità: verifico la situazione e le rispondo con una soluzione concreta.",
            "support": "Verifico i dati della sua richiesta e le rispondo con precisione."},
  "cta": {"curiosity": "Vuole che le invii i dettagli, sì o no?", "comparison": "Le spiego la differenza principale, sì o no?",
          "purchase": "Confermo ora il suo ordine, sì o no?", "objection": "Preferisce (A) tenere questa offerta con garanzia o (B) vedere un'opzione più accessibile?",
          "complaint": "Preferisce (A) una sostituzione o (B) un rimborso?", "support": "Posso chiederle il numero d'ordine per verificare, sì o no?"},
  "cta3": "Preferisce (A) continuare qui o (B) essere richiamato/a?", "price": "Prezzo: {p}. ", "logi": "Consegna e pagamento: {l}. ",
  "scarce": "Le scorte sono limitate per questa offerta.", "cross": "Molti clienti prendono anche {x} per ottimizzare il risultato.",
  "reas_sales": "Può acquistare con fiducia: {g}.", "reas_claim": "Resto il suo referente personale fino alla risoluzione completa.",
  "t_annoyed": "Le mie più sincere scuse.", "t_rushed": "Risposta rapida:", "msgr": "Resto disponibile qui, mi scriva quando vuole.",
  "advice": {"curiosity": "Se dice sì, invii dettagli, prezzo e link d'ordine nello stesso messaggio; senza risposta in 24 h, un sollecito gentile con un vantaggio concreto.",
             "comparison": "Se cita un concorrente, non lo critichi: confronti garanzia, servizio e durata, poi proponga una prova.",
             "purchase": "Se dice sì, confermi indirizzo e pagamento nello stesso messaggio; se esita, lasci solo la scelta A/B.",
             "objection": "Se insiste sul prezzo, proponga un'alternativa o un formato ridotto prima di uno sconto immediato.",
             "complaint": "Se si calma, proponga subito la soluzione (sostituzione o rimborso); se resta irritato, passi a una chiamata e se ne occupi di persona.",
             "support": "Se dà il numero d'ordine, risponda entro 5 minuti; altrimenti un solo sollecito, poi chiuda con cortesia."}},
 "ar": {
  "tag": "يُستكمل", "ph": {"offer": "العرض أو المنتج", "price": "السعر", "cross": "منتج مكمّل", "guar": "الضمان أو سياسة الإرجاع"},
  "hook": {"curiosity": "مرحباً وشكراً على اهتمامك!", "comparison": "شكراً على المقارنة، هذه خطوة ذكية!", "purchase": "اختيار ممتاز، شكراً على ثقتك!",
           "objection": "أتفهّم تماماً أن الميزانية مهمة.", "complaint": "أعتذر حقاً عن الإزعاج، وشكراً لإبلاغي.", "support": "بالطبع، سأتولى الأمر فوراً."},
  "value": {"curiosity": "في {brand} نقدّم {offer}. {price}", "comparison": "ما يصنع الفرق في {brand}: {offer}. {price}",
            "purchase": "سأحجز لك {offer}. {price}{logi}", "objection": "هذا السعر يعكس الجودة والمتانة: {offer}. {price}",
            "complaint": "طلبك أولويتي: سأتحقق من الوضع وأعود إليك بحل ملموس.", "support": "سأتحقق من تفاصيل طلبك وأجيبك بدقة."},
  "cta": {"curiosity": "هل تريد أن أرسل لك التفاصيل، نعم أم لا؟", "comparison": "هل أشرح لك الفرق الأساسي، نعم أم لا؟",
          "purchase": "هل أؤكد طلبك الآن، نعم أم لا؟", "objection": "هل تفضّل (أ) الاحتفاظ بهذا العرض مع ضمانه أم (ب) خياراً أنسب؟",
          "complaint": "هل تفضّل (أ) استبدالاً أم (ب) استرجاع المبلغ؟", "support": "هل يمكنني طلب رقم طلبك للتحقق، نعم أم لا؟"},
  "cta3": "هل تفضّل (أ) المتابعة هنا أم (ب) أن نتصل بك؟", "price": "السعر: {p}. ", "logi": "التوصيل والدفع: {l}. ",
  "scarce": "المخزون محدود لهذا العرض.", "cross": "كثير من عملائنا يأخذون أيضاً {x} للحصول على أفضل نتيجة.",
  "reas_sales": "يمكنك الشراء بثقة: {g}.", "reas_claim": "سأبقى مسؤولك الشخصي حتى الحل الكامل.",
  "t_annoyed": "أعتذر بصدق.", "t_rushed": "جواب سريع:", "msgr": "أنا متاح هنا، راسلني في أي وقت.",
  "advice": {"curiosity": "إن قال نعم أرسل التفاصيل والسعر ورابط الطلب في رسالة واحدة؛ وبلا رد خلال 24 ساعة أرسل تذكيراً لطيفاً بميزة ملموسة.",
             "comparison": "إن ذكر منافساً فلا تنتقده: قارن في الضمان والخدمة والمتانة ثم اعرض تجربة.",
             "purchase": "إن قال نعم فأكّد العنوان وطريقة الدفع في الرسالة نفسها؛ وإن تردد فأبقِ خيار أ/ب فقط.",
             "objection": "إن أصرّ على السعر فاعرض بديلاً أو حجماً أصغر بدل تخفيض فوري.",
             "complaint": "إن هدأ فاقترح الحل فوراً (استبدال أو استرجاع)؛ وإن بقي غاضباً فانتقل إلى مكالمة وتولَّ الأمر بنفسك.",
             "support": "إن أعطى رقم الطلب فأجب خلال 5 دقائق؛ وإلا تابع مرة واحدة ثم أنهِ بلطف."}},
}
EMO = {"curiosity": "😊", "comparison": "👍", "purchase": "🎉", "objection": "🙏", "complaint": "🙏", "support": "👍"}
LANGNAME = {"fr": "français", "en": "anglais", "de": "allemand", "es": "espagnol", "it": "italien", "ar": "arabe"}


class _Ph:
    def __init__(self, lang):
        self.lang, self.found = lang, []

    def __call__(self, key):
        x = TXT[self.lang]
        s = f"[⚠️ {x['tag']} : {x['ph'][key]}]"
        if s not in self.found:
            self.found.append(s)
        return s


def _clean(v, n=MAX_FIELD):
    return re.sub(r"\s+", " ", str(v or "")).strip()[:n]


def replies(cfg: dict, an: dict, lang: str) -> dict:
    x, ph = TXT[lang], _Ph(lang)
    intent, ch, temp = an["intent"], an["channel"], an["temperament"]
    brand = cfg["brand"] or "…"
    offer = cfg["offer"] or ph("offer")
    price = x["price"].format(p=cfg["price"] or ph("price")) if intent in ("curiosity", "comparison", "objection", "purchase") else ""
    logi = x["logi"].format(l=cfg["logistics"]) if cfg["logistics"] and intent in ("purchase", "curiosity") else ""
    emo = (" " + EMO[intent]) if cfg["emoji"] else ""
    fmt = lambda s: re.sub(r"\s+", " ", s.format(brand=brand, offer=offer, price=price, logi=logi)).strip()
    hook, value, cta = x["hook"][intent], fmt(x["value"][intent]), x["cta"][intent]
    sales = intent in SALES

    pre = {"annoyed": x["t_annoyed"] + " ", "rushed": x["t_rushed"] + " "}.get(temp, "")
    short_value = value if intent in ("complaint", "support") else fmt(x["value"][intent]).split(". ")[0].rstrip(".") + "."
    o1 = f"{pre}{hook}{emo} {short_value} {cta}"
    parts = [hook + emo, value]
    if sales and cfg["limited_stock"] and intent in ("curiosity", "purchase", "objection"):
        parts.append(x["scarce"])
    if sales and intent != "objection":
        parts.append(x["cross"].format(x=cfg["cross"] or ph("cross")))
    if ch == "messenger":
        parts.append(x["msgr"])
    parts.append(cta)
    o2 = " ".join(parts)
    guar = cfg["guarantee"] or ph("guar")
    mid = x["reas_sales"].format(g=guar) if sales else x["reas_claim"]
    o3 = " ".join([x["t_annoyed"] if temp == "annoyed" else hook + emo, mid, x["cta3"]])
    if ch == "whatsapp" and len(o1) > 420:
        o1 = f"{pre}{hook}{emo} {cta}"
    clean = lambda s: re.sub(r"\s+", " ", s).strip()
    return {"options": [{"id": "express", "text": clean(o1)}, {"id": "persuasive", "text": clean(o2)}, {"id": "reassure", "text": clean(o3)}],
            "advice": x["advice"][intent], "placeholders": ph.found}


PROMPT_FR = """MASTER SYSTEM PROMPT : AI SOCIAL SELLING & OMNICHANNEL SUPPORT CO-PILOT
Plateformes cibles : WhatsApp Business (ultra-direct) et Facebook Messenger (social et conversationnel).
Niveau d'expertise : Directeur Commercial, Growth Marketer et Responsable Expérience Client (CX).

## 1. CONFIGURATION DU COMPTE
- Marque : {brand}
- Secteur / industrie : {sector}
- Catalogue / offre phare : {offer}
- Prix : {price}
- Persona client : {persona}
- Ton et voix de la marque : {tone}
- Règles linguistiques : {langrules}
- Logistique et paiement : {logistics}
- Garantie / retours : {guarantee}
- Produit complémentaire (vente croisée) : {cross}
- Stock limité (rareté autorisée) : {limited}

## 2. ANALYSE AVANT TOUTE RÉPONSE (en interne)
1. Intention réelle : curiosité / comparaison / achat imminent / objection / réclamation / SAV.
2. Niveau de chaleur : froid / tiède / chaud / brûlant.
3. Tempérament : pressé / méfiant / enthousiaste / agacé / technique.
4. Canal détecté : WhatsApp = plus court et percutant ; Messenger = légèrement plus contextuel.

## 3. RÈGLES DE CONVERSION ET DE COPYWRITING
1. Structure « Hook – Value – CTA » : empathie/validation, réponse claire, puis question fermée (oui/non ou choix A/B).
2. Anti-hallucination : n'invente jamais un prix, un stock ou une caractéristique. Donnée manquante : « [⚠️ À COMPLÉTER : … ] ».
3. Vente douce : rareté uniquement si le stock limité est confirmé ci-dessus ; vente croisée naturelle ; jamais de promesse non vérifiable.
4. Objection de prix : ne jamais brader tout de suite ; justifier la valeur, la durabilité ou la garantie avant d'envisager une alternative.
5. Réponds dans la langue du client ({lang}) ; n'envoie rien toi-même : le gérant relit, copie et envoie.

## 4. FORMAT DE RESTITUTION OBLIGATOIRE
[ANALYSE] : Intention : [...] | Chaleur : [...] | Tempérament : [...]
OPTION 1 : EXPRESS ET DIRECTE (idéal WhatsApp / client pressé)
OPTION 2 : PERSUASIVE ET SOCIAL SELLING (argumentaire + suggestion de vente croisée)
OPTION 3 : RÉASSURANCE / SAV (client hésitant, méfiant ou en litige ; écoute et désescalade)
CONSEIL STRATÉGIQUE (pour le gérant) : une phrase pour orienter la conversation selon la réponse du client.
Message client à traiter : {message}"""


def system_prompt(cfg: dict, lang: str, message: str) -> str:
    tag = TXT["fr"]["tag"]
    f = lambda k, d: cfg[k] or f"[⚠️ {tag} : {d}]"
    return PROMPT_FR.format(brand=f("brand", "nom de la marque"), sector=f("sector", "secteur"), offer=f("offer", "offre phare"), price=f("price", "prix"),
                            persona=f("persona", "persona client"), tone=f("tone", "ton de la marque"), langrules=cfg["langrules"] or "langue du client ; tolérance aux expressions locales si le client les utilise",
                            logistics=f("logistics", "livraison et paiement"), guarantee=f("guarantee", "garantie / retours"), cross=f("cross", "produit complémentaire"),
                            limited="oui" if cfg["limited_stock"] else "non / non confirmé", lang=LANGNAME[lang], message=message)


def respond(p: dict) -> dict:
    lang = p.get("lang", "fr")
    if lang not in LANGS:
        raise ValueError("langue non prise en charge")
    ch = p.get("channel", "whatsapp")
    if ch not in CHANNELS:
        raise ValueError("canal non pris en charge")
    msg = str(p.get("message") or "").strip()
    if not msg:
        raise ValueError("Collez le message du client.")
    if len(msg) > MAX_MSG:
        raise ValueError(f"Message trop long (max {MAX_MSG} caractères).")
    cfg = {k: _clean(p.get(k)) for k in ("brand", "sector", "offer", "price", "persona", "tone", "langrules", "logistics", "guarantee", "cross")}
    cfg["limited_stock"] = bool(p.get("limited_stock"))
    cfg["emoji"] = bool(p.get("emoji", True))
    an = analyse(msg, ch)
    out = replies(cfg, an, lang)
    out.update({"analysis": an, "lang": lang, "system_prompt": system_prompt(cfg, lang, msg),
                "warnings": (["placeholders"] if out["placeholders"] else []) + (["no_brand"] if not cfg["brand"] else [])})
    return out
