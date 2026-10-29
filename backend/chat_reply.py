"""Service 2 (onglet Messagerie) : copilote de vente sociale et de support pour WhatsApp Business et Facebook Messenger.

Règles pures (aucune IA, aucun tiers, aucune donnée conservée) : analyse du message client (intention, chaleur, tempérament, canal)
puis 3 réponses prêtes à copier (express / persuasive / réassurance), un conseil stratégique et le « master prompt » rempli avec la
configuration du compte. Anti-hallucination : jamais de prix ni de caractéristique inventés → marqueur « À COMPLÉTER »."""
from __future__ import annotations
import re

LANGS = ("fr", "en", "de", "es", "it", "ar")
CHANNELS = ("whatsapp", "messenger")
INTENTS = ("curiosity", "comparison", "buy", "objection", "complaint")
MAX_MSG, MAX_FIELD = 2000, 300

# ---- détection (toutes langues confondues : un client peut écrire dans une autre langue que l'interface, ou mélanger) ------------------
KW = {
    "complaint": "problème,probleme,pas reçu,pas recu,jamais reçu,retard,remboursement,arnaque,cassé,casse,défectueux,déçu,decu,réclamation,erreur,nul,"
                 "problem,not received,never received,late,refund,scam,broken,damaged,disappointed,complaint,wrong,"
                 "nicht erhalten,verspätet,erstattung,betrug,kaputt,beschädigt,enttäuscht,beschwerde,falsch,"
                 "no recibí,no recibi,retraso,reembolso,estafa,roto,dañado,decepcion,queja,"
                 "non ricevuto,ritardo,rimborso,truffa,rotto,danneggiato,deluso,reclamo,errore,"
                 "مشكل,لم يصل,تأخر,استرجاع,نصب,مكسور,تالف,خيبة,شكوى,خطأ,mchkil,ma wslnich,ma wsalnich",
    "objection": "cher,trop cher,réduction,reduction,remise,moins cher,rabais,budget,"
                 "expensive,too much,discount,cheaper,"
                 "teuer,rabatt,günstiger,preiswerter,"
                 "caro,descuento,más barato,mas barato,"
                 "costoso,sconto,più economico,piu economico,"
                 "غالي,تخفيض,أرخص,ارخص,خصم,ghali,3ali",
    "buy": "commander,je prends,je le prends,acheter,dispo,disponible,livraison,comment payer,je veux,"
           "order,buy,i'll take,i will take,available,i want,"
           "bestellen,kaufen,ich nehme,verfügbar,ich möchte,"
           "pedir,comprar,lo quiero,lo llevo,"
           "ordinare,comprare,lo prendo,disponibile,voglio,"
           "أريد,اطلب,أشتري,اشتري,متوفر,نحب نشري,bghit,nakhod",
    "comparison": "différence,difference,comparer,comparé,versus,mieux que,concurrent,ailleurs,"
                  "compare,better than,alternative,"
                  "unterschied,vergleich,besser als,"
                  "diferencia,comparar,mejor que,"
                  "differenza,confronto,meglio di,"
                  "الفرق,مقارنة,أفضل من",
}
PRICE_ASK = "prix,combien,tarif,price,how much,cost,preis,wie viel,kostet,precio,cuánto,cuanto,prezzo,quanto costa,سعر,ثمن,كم,bch7al,bchhal,b9ch"
URGENT = "urgent,vite,maintenant,aujourd'hui,tout de suite,asap,now,today,immediately,sofort,jetzt,heute,ahora,hoy,ya mismo,subito,adesso,oggi,الآن,بسرعة,اليوم,db,daba"
DISTRUST = "arnaque,vraiment,garantie,fiable,sérieux,confiance,c'est sûr,scam,really,trust,fake,legit,reliable,betrug,wirklich,vertrauen,seriös,estafa,confianza,fiable,truffa,fidato,affidabile,نصب,موثوق,ثقة,حقيقي"
TECH = "composition,ingrédient,ingredient,dimension,taille,matière,spec,material,size,weight,poids,größe,material,tamaño,talla,materiale,misura,مكونات,مقاس,حجم,وزن"
HAPPY = "super,génial,genial,parfait,merci,great,love,wow,awesome,perfect,thanks,toll,danke,perfekt,gracias,perfecto,grazie,ottimo,رائع,ممتاز,شكرا,شكراً,😍,❤,👍,🙏,😊"
ANNOYED = "!!,???,inadmissible,ridicule,honte,marre,unacceptable,ridiculous,disgrace,fed up,unglaublich,inakzeptable,vergüenza,inaceptable,vergogna,inaccettabile,غير مقبول,عيب"


def _has(text: str, csv: str) -> bool:
    return any(k and k in text for k in csv.split(","))


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", text, re.U)


NEG = re.compile(r"pas de probl[eè]me|aucun probl[eè]me|sans probl[eè]me|pas (?:trop )?cher|no problem|no issue|not (?:too )?expensive|kein problem|nicht (?:zu )?teuer|"
                 r"no hay problema|sin problema|no es (?:muy )?caro|nessun problema|senza problemi|non [èe] (?:troppo )?caro|لا مشكل|بدون مشكل|ماشي غالي|machi ghali|mamchkil", re.I)


def analyse(message: str) -> dict:
    m = NEG.sub(" ", message.lower())
    intent = next((i for i in ("complaint", "objection", "buy", "comparison") if _has(m, KW[i])), "curiosity")
    asks_price = _has(m, PRICE_ASK)
    urgent = _has(m, URGENT)
    letters = [c for c in message if c.isalpha()]
    shout = len(letters) > 8 and sum(c.isupper() for c in letters) / len(letters) > .6
    if _has(m, ANNOYED) or shout or (intent == "complaint" and message.count("!") >= 2):
        temper = "annoyed"
    elif _has(m, DISTRUST):
        temper = "wary"
    elif urgent or len(_words(message)) <= 3:
        temper = "rushed"
    elif _has(m, TECH):
        temper = "technical"
    elif _has(m, HAPPY):
        temper = "enthusiast"
    else:
        temper = "neutral"
    if intent == "buy":
        heat = "burning" if urgent else "hot"
    elif intent == "complaint":
        heat = "burning" if (urgent or temper == "annoyed") else "warm"
    elif intent in ("objection", "comparison") or asks_price:
        heat = "warm"
    else:
        heat = "cold"
    return {"intent": intent, "heat": heat, "temper": temper, "asks_price": asks_price}


# ---- textes par langue ---------------------------------------------------------------------------------------------------------------
# ordre des listes : INTENTS = curiosity, comparison, buy, objection, complaint
L = {
 "fr": dict(
  F="Bonjour, je me permets de revenir vers vous : souhaitez-vous que je vous réserve l'article (A) ou que je vous laisse y réfléchir encore (B) ?", Fc='Je reviens vers vous pour savoir si la solution proposée vous convient : oui ou non ?',
  intent=["Curiosité", "Comparaison", "Achat imminent", "Objection prix", "Réclamation / SAV"],
  heat=dict(cold="Froid", warm="Tiède", hot="Chaud", burning="Brûlant"),
  temper=dict(rushed="Pressé", wary="Méfiant", enthusiast="Enthousiaste", annoyed="Agacé", technical="Technique", neutral="Neutre"),
  V=["Merci pour votre message et votre intérêt !", "Excellente question : comparer avant de choisir est très sage !", "Super, merci pour votre confiance !",
     "Je comprends tout à fait votre réflexion sur le budget.", "Je suis vraiment désolé(e) pour cette situation, et merci de nous l'avoir signalée."],
  A=["Voici l'essentiel : {offer}.", "Ce qui nous distingue : {offer}.", "Parfait, c'est possible : {offer}. {logi}",
     "Notre prix reflète la qualité et la durabilité : {offer}. {guar}", "Je prends votre dossier en charge personnellement et je vérifie cela tout de suite. {guar}"],
  C=["Souhaitez-vous que je vous envoie le détail, oui ou non ?", "Voulez-vous que je vous compare les options : A (la plus simple) ou B (la plus complète) ?",
     "Je valide votre commande maintenant : oui ou non ?", "Préférez-vous voir la valeur en détail (A) ou une alternative adaptée (B) ?",
     "Je peux régler cela ici (A) ou vous appeler dans l'heure (B) : que préférez-vous ?"],
  R=["Aucune pression : je reste disponible pour répondre à toutes vos questions.", "Prenez le temps de comparer : je reste à votre écoute, sans engagement.",
     "Votre commande est sécurisée et vous gardez la main à chaque étape.", "Votre confiance compte plus qu'une vente : je veux que ce soit le bon choix pour vous.",
     "Votre satisfaction est ma priorité et je ne vous laisse pas sans solution."],
  C3="Est-ce que cela vous rassure, oui ou non ?", C3c="Souhaitez-vous que je traite cela en priorité dès maintenant, oui ou non ?",
  P="Prix : {price}.", X="Beaucoup de nos clients prennent aussi {cross} pour de meilleurs résultats.", S="Le stock est limité sur cet article.",
  ALT="Si le budget est la contrainte, je peux regarder avec vous {alt}.",
  PH="[⚠️ À COMPLÉTER : {x}]", PHX=dict(offer="offre / caractéristiques", price="prix", logi="livraison et paiement", guar="garantie / retours", cross="produit complémentaire", alt="une alternative adaptée"),
  ADV=["Si le client demande le prix ou répond « je réfléchis » : donnez le prix + la garantie, puis proposez de lui réserver l'article ; sans réponse sous 24 h, relancez avec une question A/B.",
       "S'il cite un concurrent moins cher : ne baissez pas le prix, mettez en avant garantie, livraison et avis clients, puis proposez un essai ou un petit format.",
       "S'il hésite sur le paiement ou la livraison : rappelez les modalités et confirmez tout de suite ; s'il dit oui, envoyez le récapitulatif de commande.",
       "S'il insiste sur le prix : ne bradez pas, proposez un format plus petit ou un pack plutôt qu'une remise immédiate ; sans réponse, relancez dans 24 h.",
       "Répondez dans l'heure et ne vendez rien dans ce message ; proposez une solution concrète (échange, remboursement, suivi) et passez à un appel s'il reste agacé."]),
 "en": dict(
  F='Hello, just following up: shall I reserve the item for you (A) or leave you more time to think (B)?', Fc="I'm following up to check whether the proposed solution works for you: yes or no?",
  intent=["Curiosity", "Comparison", "Ready to buy", "Price objection", "Complaint / support"],
  heat=dict(cold="Cold", warm="Warm", hot="Hot", burning="Burning"),
  temper=dict(rushed="In a hurry", wary="Wary", enthusiast="Enthusiastic", annoyed="Annoyed", technical="Technical", neutral="Neutral"),
  V=["Thanks for your message and your interest!", "Great question: comparing before choosing is smart!", "Great, thank you for your trust!",
     "I completely understand your thinking about the budget.", "I'm really sorry about this, and thank you for letting us know."],
  A=["Here is the essentials: {offer}.", "What sets us apart: {offer}.", "Perfect, that's possible: {offer}. {logi}",
     "Our price reflects quality and durability: {offer}. {guar}", "I'm taking your case personally and checking this right now. {guar}"],
  C=["Would you like me to send the details, yes or no?", "Shall I compare the options: A (simplest) or B (most complete)?",
     "Shall I confirm your order now: yes or no?", "Would you rather see the value in detail (A) or a suitable alternative (B)?",
     "I can sort this out here (A) or call you within the hour (B): which do you prefer?"],
  R=["No pressure: I'm here for any question you have.", "Take your time to compare: I'm here, no commitment.",
     "Your order is secure and you stay in control at every step.", "Your trust matters more than a sale: I want this to be the right choice for you.",
     "Your satisfaction is my priority and I won't leave you without a solution."],
  C3="Does that reassure you, yes or no?", C3c="Shall I handle this as a priority right now, yes or no?",
  P="Price: {price}.", X="Many of our customers also take {cross} for better results.", S="Stock is limited on this item.",
  ALT="If budget is the constraint, I can look at {alt} with you.",
  PH="[⚠️ TO COMPLETE: {x}]", PHX=dict(offer="offer / features", price="price", logi="delivery and payment", guar="warranty / returns", cross="complementary product", alt="a suitable alternative"),
  ADV=["If they ask the price or say “I'll think about it”: give the price + guarantee, then offer to reserve the item; no reply in 24 h, follow up with an A/B question.",
       "If they mention a cheaper competitor: don't cut the price, stress guarantee, delivery and reviews, then offer a trial or a smaller size.",
       "If they hesitate on payment or delivery: restate the terms and confirm straight away; if they say yes, send the order summary.",
       "If they keep pushing on price: don't discount, offer a smaller size or a bundle instead of an instant reduction; no reply, follow up in 24 h.",
       "Reply within the hour and sell nothing in this message; offer a concrete fix (exchange, refund, tracking) and move to a call if they stay upset."]),
 "de": dict(
  F='Guten Tag, ich melde mich noch einmal: Soll ich den Artikel für Sie reservieren (A) oder Ihnen mehr Bedenkzeit lassen (B)?', Fc='Ich melde mich, um zu fragen, ob die vorgeschlagene Lösung für Sie passt: ja oder nein?',
  intent=["Neugier", "Vergleich", "Kaufbereit", "Preiseinwand", "Reklamation / Support"],
  heat=dict(cold="Kalt", warm="Lauwarm", hot="Heiß", burning="Brennend"),
  temper=dict(rushed="Eilig", wary="Misstrauisch", enthusiast="Begeistert", annoyed="Verärgert", technical="Technisch", neutral="Neutral"),
  V=["Danke für Ihre Nachricht und Ihr Interesse!", "Gute Frage: Vergleichen vor dem Kauf ist sehr klug!", "Prima, danke für Ihr Vertrauen!",
     "Ich verstehe Ihre Überlegung zum Budget sehr gut.", "Es tut mir wirklich leid, und danke, dass Sie uns informiert haben."],
  A=["Das Wichtigste: {offer}.", "Das unterscheidet uns: {offer}.", "Perfekt, das ist möglich: {offer}. {logi}",
     "Unser Preis steht für Qualität und Langlebigkeit: {offer}. {guar}", "Ich kümmere mich persönlich um Ihren Fall und prüfe das sofort. {guar}"],
  C=["Soll ich Ihnen die Details schicken, ja oder nein?", "Soll ich die Optionen vergleichen: A (einfachste) oder B (umfassendste)?",
     "Soll ich Ihre Bestellung jetzt bestätigen: ja oder nein?", "Möchten Sie den Nutzen im Detail sehen (A) oder eine passende Alternative (B)?",
     "Ich kann das hier klären (A) oder Sie innerhalb einer Stunde anrufen (B): was ist Ihnen lieber?"],
  R=["Kein Druck: Ich bin für alle Fragen da.", "Nehmen Sie sich Zeit zum Vergleichen: unverbindlich, ich bin da.",
     "Ihre Bestellung ist sicher und Sie behalten bei jedem Schritt die Kontrolle.", "Ihr Vertrauen ist wichtiger als ein Verkauf: Es soll die richtige Wahl für Sie sein.",
     "Ihre Zufriedenheit hat Priorität, und ich lasse Sie nicht ohne Lösung."],
  C3="Beruhigt Sie das, ja oder nein?", C3c="Soll ich das jetzt vorrangig bearbeiten, ja oder nein?",
  P="Preis: {price}.", X="Viele unserer Kunden nehmen auch {cross} für bessere Ergebnisse.", S="Der Bestand ist bei diesem Artikel begrenzt.",
  ALT="Wenn das Budget die Hürde ist, schaue ich gern mit Ihnen auf {alt}.",
  PH="[⚠️ ZU ERGÄNZEN: {x}]", PHX=dict(offer="Angebot / Eigenschaften", price="Preis", logi="Lieferung und Zahlung", guar="Garantie / Rückgabe", cross="Ergänzungsprodukt", alt="eine passende Alternative"),
  ADV=["Fragt der Kunde nach dem Preis oder sagt „ich überlege“: Preis + Garantie nennen, Reservierung anbieten; ohne Antwort nach 24 h mit A/B-Frage nachfassen.",
       "Nennt er einen günstigeren Wettbewerber: Preis nicht senken, Garantie, Lieferung und Bewertungen betonen, dann Test oder kleine Größe anbieten.",
       "Zögert er bei Zahlung oder Lieferung: Konditionen wiederholen und sofort bestätigen; bei „ja“ die Bestellübersicht senden.",
       "Beharrt er auf dem Preis: nicht verramschen, lieber kleinere Größe oder Paket statt sofortigem Rabatt; ohne Antwort nach 24 h nachfassen.",
       "Innerhalb einer Stunde antworten und in dieser Nachricht nichts verkaufen; konkrete Lösung (Umtausch, Erstattung, Sendungsverfolgung) und bei Verärgerung anrufen."]),
 "es": dict(
  F='Hola, le escribo de nuevo: ¿le reservo el artículo (A) o prefiere pensarlo un poco más (B)?', Fc='Le escribo para saber si la solución propuesta le conviene: ¿sí o no?',
  intent=["Curiosidad", "Comparación", "Compra inminente", "Objeción de precio", "Reclamación / SAC"],
  heat=dict(cold="Frío", warm="Tibio", hot="Caliente", burning="Urgente"),
  temper=dict(rushed="Con prisa", wary="Desconfiado", enthusiast="Entusiasta", annoyed="Molesto", technical="Técnico", neutral="Neutro"),
  V=["¡Gracias por su mensaje y su interés!", "Excelente pregunta: comparar antes de elegir es muy sensato.", "¡Genial, gracias por su confianza!",
     "Entiendo perfectamente su reflexión sobre el presupuesto.", "Lamento mucho esta situación y gracias por avisarnos."],
  A=["Lo esencial: {offer}.", "Lo que nos distingue: {offer}.", "Perfecto, es posible: {offer}. {logi}",
     "Nuestro precio refleja calidad y durabilidad: {offer}. {guar}", "Me encargo personalmente de su caso y lo reviso ahora mismo. {guar}"],
  C=["¿Quiere que le envíe el detalle, sí o no?", "¿Comparo las opciones: A (la más sencilla) o B (la más completa)?",
     "¿Confirmo su pedido ahora: sí o no?", "¿Prefiere ver el valor en detalle (A) o una alternativa adecuada (B)?",
     "Puedo resolverlo aquí (A) o llamarle en una hora (B): ¿qué prefiere?"],
  R=["Sin presión: estoy disponible para cualquier duda.", "Tómese su tiempo para comparar: sin compromiso, aquí estoy.",
     "Su pedido es seguro y usted controla cada paso.", "Su confianza vale más que una venta: quiero que sea la elección correcta para usted.",
     "Su satisfacción es mi prioridad y no le dejo sin solución."],
  C3="¿Le tranquiliza esto, sí o no?", C3c="¿Lo trato como prioridad ahora mismo, sí o no?",
  P="Precio: {price}.", X="Muchos clientes también llevan {cross} para mejores resultados.", S="El stock es limitado en este artículo.",
  ALT="Si el presupuesto es el límite, puedo ver con usted {alt}.",
  PH="[⚠️ POR COMPLETAR: {x}]", PHX=dict(offer="oferta / características", price="precio", logi="entrega y pago", guar="garantía / devoluciones", cross="producto complementario", alt="una alternativa adecuada"),
  ADV=["Si pregunta el precio o dice «lo pienso»: dé el precio + la garantía y ofrezca reservarle el artículo; sin respuesta en 24 h, insista con una pregunta A/B.",
       "Si cita un competidor más barato: no baje el precio, destaque garantía, entrega y opiniones, y ofrezca una prueba o un formato pequeño.",
       "Si duda con el pago o la entrega: repita las condiciones y confirme ya; si dice sí, envíe el resumen del pedido.",
       "Si insiste en el precio: no regale, ofrezca un formato menor o un pack en vez de un descuento inmediato; sin respuesta, insista en 24 h.",
       "Responda en una hora y no venda nada en este mensaje; proponga una solución concreta (cambio, reembolso, seguimiento) y llame si sigue molesto."]),
 "it": dict(
  F="Buongiorno, la ricontatto: le riservo l'articolo (A) o preferisce pensarci ancora (B)?", Fc='La ricontatto per sapere se la soluzione proposta le va bene: sì o no?',
  intent=["Curiosità", "Confronto", "Acquisto imminente", "Obiezione sul prezzo", "Reclamo / assistenza"],
  heat=dict(cold="Freddo", warm="Tiepido", hot="Caldo", burning="Urgente"),
  temper=dict(rushed="Di fretta", wary="Diffidente", enthusiast="Entusiasta", annoyed="Irritato", technical="Tecnico", neutral="Neutro"),
  V=["Grazie per il messaggio e per l'interesse!", "Ottima domanda: confrontare prima di scegliere è molto saggio!", "Perfetto, grazie per la fiducia!",
     "Capisco perfettamente la riflessione sul budget.", "Mi dispiace davvero per l'accaduto e grazie per la segnalazione."],
  A=["L'essenziale: {offer}.", "Ciò che ci distingue: {offer}.", "Perfetto, è possibile: {offer}. {logi}",
     "Il nostro prezzo riflette qualità e durata: {offer}. {guar}", "Mi occupo personalmente del suo caso e verifico subito. {guar}"],
  C=["Vuole che le invii i dettagli, sì o no?", "Confronto le opzioni: A (la più semplice) o B (la più completa)?",
     "Confermo ora il suo ordine: sì o no?", "Preferisce vedere il valore nel dettaglio (A) o un'alternativa adatta (B)?",
     "Posso risolvere qui (A) o chiamarla entro un'ora (B): cosa preferisce?"],
  R=["Nessuna pressione: sono a disposizione per ogni domanda.", "Si prenda il tempo per confrontare: senza impegno, io ci sono.",
     "Il suo ordine è sicuro e lei controlla ogni passaggio.", "La sua fiducia vale più di una vendita: voglio che sia la scelta giusta per lei.",
     "La sua soddisfazione è la mia priorità e non la lascio senza soluzione."],
  C3="Questo la rassicura, sì o no?", C3c="Lo gestisco subito in via prioritaria, sì o no?",
  P="Prezzo: {price}.", X="Molti clienti prendono anche {cross} per risultati migliori.", S="Le scorte di questo articolo sono limitate.",
  ALT="Se il budget è il limite, posso valutare con lei {alt}.",
  PH="[⚠️ DA COMPLETARE: {x}]", PHX=dict(offer="offerta / caratteristiche", price="prezzo", logi="consegna e pagamento", guar="garanzia / resi", cross="prodotto complementare", alt="un'alternativa adatta"),
  ADV=["Se chiede il prezzo o dice «ci penso»: dia prezzo + garanzia e proponga di riservare l'articolo; senza risposta in 24 h, rilanci con una domanda A/B.",
       "Se cita un concorrente più economico: non abbassi il prezzo, valorizzi garanzia, consegna e recensioni, poi proponga una prova o un formato piccolo.",
       "Se esita su pagamento o consegna: ripeta le condizioni e confermi subito; se dice sì, invii il riepilogo dell'ordine.",
       "Se insiste sul prezzo: non svenda, proponga un formato più piccolo o un pack invece di uno sconto immediato; senza risposta, rilanci in 24 h.",
       "Risponda entro un'ora e non venda nulla in questo messaggio; proponga una soluzione concreta (cambio, rimborso, tracking) e chiami se resta irritato."]),
 "ar": dict(
  F='مرحباً، أعود إليك: هل أحجز لك المنتج (أ) أم تفضّل التفكير أكثر (ب)؟', Fc='أعود إليك لأتأكد إن كان الحل المقترح مناسباً لك: نعم أم لا؟',
  intent=["فضول / استفسار", "مقارنة", "شراء وشيك", "اعتراض على السعر", "شكوى / خدمة ما بعد البيع"],
  heat=dict(cold="بارد", warm="فاتر", hot="ساخن", burning="عاجل"),
  temper=dict(rushed="مستعجل", wary="متردد / متشكك", enthusiast="متحمس", annoyed="منزعج", technical="تقني", neutral="محايد"),
  V=["شكراً على رسالتك واهتمامك!", "سؤال ممتاز: المقارنة قبل الاختيار قرار حكيم!", "رائع، شكراً على ثقتك!",
     "أتفهّم تماماً تفكيرك في الميزانية.", "أعتذر حقاً عن هذا الموقف، وشكراً لإبلاغنا."],
  A=["الخلاصة: {offer}.", "ما يميّزنا: {offer}.", "ممتاز، هذا ممكن: {offer}. {logi}",
     "سعرنا يعكس الجودة والمتانة: {offer}. {guar}", "سأتكفّل بحالتك شخصياً وأتحقق منها الآن. {guar}"],
  C=["هل تريد أن أرسل لك التفاصيل، نعم أم لا؟", "هل أقارن لك الخيارات: أ (الأبسط) أم ب (الأشمل)؟",
     "هل أؤكد طلبك الآن: نعم أم لا؟", "هل تفضّل رؤية القيمة بالتفصيل (أ) أم بديلاً مناسباً (ب)؟",
     "يمكنني حل الأمر هنا (أ) أو الاتصال بك خلال ساعة (ب): ماذا تفضّل؟"],
  R=["بلا أي ضغط: أنا متاح لأي سؤال.", "خذ وقتك في المقارنة: بلا التزام وأنا هنا.",
     "طلبك مؤمَّن وتبقى متحكماً في كل خطوة.", "ثقتك أهم من أي عملية بيع: أريد أن يكون هذا الاختيار الصحيح لك.",
     "رضاك أولويتي ولن أتركك بلا حل."],
  C3="هل هذا يطمئنك، نعم أم لا؟", C3c="هل أعالج الأمر بأولوية الآن، نعم أم لا؟",
  P="السعر: {price}.", X="كثير من زبائننا يأخذون أيضاً {cross} للحصول على نتائج أفضل.", S="المخزون محدود لهذا المنتج.",
  ALT="إذا كانت الميزانية هي العائق، يمكنني أن أبحث معك عن {alt}.",
  PH="[⚠️ يُستكمل: {x}]", PHX=dict(offer="العرض / المواصفات", price="السعر", logi="التوصيل والدفع", guar="الضمان / الإرجاع", cross="منتج مكمّل", alt="بديل مناسب"),
  ADV=["إذا سأل عن السعر أو قال «سأفكر»: اذكر السعر مع الضمان ثم اعرض حجز المنتج؛ وإن لم يرد خلال 24 ساعة تابع بسؤال أ/ب.",
       "إذا ذكر منافساً أرخص: لا تخفّض السعر، أبرز الضمان والتوصيل وآراء الزبائن ثم اعرض تجربة أو حجماً أصغر.",
       "إذا تردد في الدفع أو التوصيل: ذكّره بالشروط وأكّد الطلب فوراً؛ وإن وافق أرسل ملخص الطلب.",
       "إذا أصرّ على السعر: لا تبِع بخسارة، اقترح حجماً أصغر أو باقة بدل خصم فوري؛ وإن صمت تابع بعد 24 ساعة.",
       "ردّ خلال ساعة ولا تبِع شيئاً في هذه الرسالة؛ اقترح حلاً ملموساً (استبدال، استرجاع، تتبّع) واتصل به إن بقي منزعجاً."]),
}

MARK = {
    "fr": " le , la , les , des , je , vous , est , pas , bonjour , merci , c'est , quel , avez , pour , une , mon , ma , combien ",
    "en": " the , is , are , you , hello , hi , thanks , what , how , do , my , your , please , order , can ",
    "de": " ich , sie , ist , nicht , bitte , danke , hallo , wie , was , der , die , das , und , haben , mein ",
    "es": " el , la , que , quiero , hola , gracias , cuánto , está , tengo , pedido , por , una , mi , tienen ",
    "it": " il , che , sono , ciao , grazie , voglio , quanto , è , ho , ordine , per , una , mio , avete , buongiorno ",
}


def detect_lang(text: str, fallback: str = "fr") -> str:
    letters = [c for c in text if c.isalpha()]
    if letters and sum("\u0600" <= c <= "\u06ff" for c in letters) / len(letters) > .3:
        return "ar"
    padded = " " + " ".join(re.findall(r"[\w']+", text.lower())) + " "
    hits = {k: sum(padded.count(f" {w.strip()} ") for w in v.split(",")) for k, v in MARK.items()}
    best = max(hits, key=hits.get); score = hits[best]
    return best if score >= 1 else (fallback if fallback in LANGS else "fr")


YESW = "oui,ouais,ok,okay,d'accord,volontiers,yes,yeah,sure,ja,klar,gern,sí,si,vale,claro,sì,certo,نعم,أجل,اوكي,wakha,iyeh"
HEAT_ORDER = ("cold", "warm", "hot", "burning")
MAX_HIST = 10
ADV2 = {
    "fr": "Deuxième objection de prix : arrêtez de justifier, proposez un appel, un pack ou une option plus petite, ou laissez poliment la porte ouverte.",
    "en": "Second price objection: stop justifying, offer a call, a bundle or a smaller option, or politely leave the door open.",
    "de": "Zweiter Preiseinwand: nicht weiter rechtfertigen, Anruf, Paket oder kleinere Option anbieten oder höflich die Tür offen lassen.",
    "es": "Segunda objeción de precio: deje de justificar, ofrezca una llamada, un pack o una opción menor, o deje la puerta abierta con cortesía.",
    "it": "Seconda obiezione sul prezzo: smetta di giustificare, proponga una chiamata, un pack o un'opzione più piccola, o lasci cortesemente la porta aperta.",
    "ar": "اعتراض ثانٍ على السعر: توقّف عن التبرير، اقترح مكالمة أو باقة أو خياراً أصغر، أو اترك الباب مفتوحاً بلباقة.",
}
ADV3 = {
    "fr": "Le client semblait prêt à acheter puis hésite : rassurez (garantie, paiement à la livraison) avant toute nouvelle offre.",
    "en": "The customer seemed ready to buy and now hesitates: reassure (warranty, cash on delivery) before any new offer.",
    "de": "Der Kunde wirkte kaufbereit und zögert jetzt: erst beruhigen (Garantie, Zahlung bei Lieferung), dann neues Angebot.",
    "es": "El cliente parecía listo para comprar y ahora duda: tranquilícelo (garantía, pago contra entrega) antes de otra oferta.",
    "it": "Il cliente sembrava pronto ad acquistare e ora esita: lo rassicuri (garanzia, pagamento alla consegna) prima di una nuova offerta.",
    "ar": "بدا الزبون جاهزاً للشراء ثم تردد: طمئنه (الضمان، الدفع عند الاستلام) قبل أي عرض جديد.",
}

FIELDS = ("brand", "sector", "offer", "persona", "tone", "rules", "logistics", "price", "cross", "guarantee", "alt")


def _c(v, n=MAX_FIELD) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()[:n]


def master_prompt(cfg: dict) -> str:
    g = lambda k, d="[⚠️ À COMPLÉTER]": cfg.get(k) or d
    return f"""MASTER SYSTEM PROMPT : AI SOCIAL SELLING & OMNICHANNEL SUPPORT CO-PILOT
Plateformes cibles : WhatsApp Business (ultra-direct) & Facebook Messenger (social et conversationnel)
Niveau d'expertise : Directeur Commercial, Growth Marketer & Responsable Expérience Client (CX)

1. CONFIGURATION DU COMPTE
- Marque : {g('brand')}
- Secteur / industrie : {g('sector')}
- Catalogue / offre phare : {g('offer')}
- Persona client : {g('persona')}
- Ton et voix de la marque : {g('tone')}
- Règles linguistiques : {g('rules')}
- Logistique et paiement : {g('logistics')}

2. ANALYSE AVANT TOUTE RÉPONSE (en interne)
1. Intention réelle : curiosité / comparaison / achat imminent / objection / réclamation-SAV
2. Chaleur : froid / tiède / chaud / brûlant
3. Tempérament : pressé / méfiant / enthousiaste / agacé / technique
4. Canal : WhatsApp = plus court et percutant ; Messenger = légèrement plus contextuel

3. RÈGLES DE CONVERSION
1. Structure Hook - Value - CTA : empathie/validation, réponse claire, puis question fermée (oui/non ou choix A/B).
2. Anti-hallucination : interdiction d'inventer prix ou caractéristiques ; si une donnée manque, écrire [⚠️ À COMPLÉTER : ...].
3. Vente douce : rareté seulement si le stock est réellement limité ; suggestion complémentaire naturelle (cross-sell / up-sell).
4. Objection de prix : ne jamais brader immédiatement ; justifier la valeur, la durabilité ou la garantie avant d'éventuellement proposer une alternative.
5. En cas de réclamation : ne rien vendre dans le message, proposer une solution concrète.

4. FORMAT DE RESTITUTION OBLIGATOIRE (pour chaque message client)
[ANALYSE] : Intention | Chaleur | Tempérament
OPTION 1 : EXPRESS & DIRECTE (idéal WhatsApp / client pressé) - texte prêt à copier-coller
OPTION 2 : PERSUASIVE & SOCIAL SELLING - argumentaire + suggestion de vente croisée
OPTION 3 : RÉASSURANCE / SAV - écoute et désescalade
CONSEIL STRATÉGIQUE (pour le gérant) : une phrase sur la suite selon la réponse du client

Message client à traiter : [coller ici le message]"""


def reply(p: dict) -> dict:
    msg = str(p.get("message") or "").strip()
    if not msg:
        raise ValueError("Collez le message du client.")
    if len(msg) > MAX_MSG:
        raise ValueError(f"Message trop long ({MAX_MSG} caractères au plus).")
    fb = p.get("fallback") if p.get("fallback") in LANGS else "fr"
    lang = p.get("lang") if p.get("lang") in LANGS else detect_lang(msg, fb)      # « auto » : langue du message du client
    channel = p.get("channel") if p.get("channel") in CHANNELS else "whatsapp"
    cfg = {k: _c(p.get(k)) for k in FIELDS}
    cfg["limited"] = bool(p.get("limited"))
    hist = [str(h).strip()[:MAX_MSG] for h in (p.get("history") or []) if str(h).strip()][-MAX_HIST:]
    past = [analyse(h) for h in hist]
    a = analyse(msg)
    toks = _words(msg.lower())
    if past and a["intent"] == "curiosity" and len(toks) <= 3 and any(w in YESW.split(",") for w in toks) and any(x["intent"] in ("buy", "objection", "comparison") for x in past[-2:]):
        a["intent"], a["heat"] = "buy", "hot"                       # « oui » / « ok » après une offre = accord d'achat
    prev_heat = past[-1]["heat"] if past else None
    trend = "none" if not past else ("up" if HEAT_ORDER.index(a["heat"]) > HEAT_ORDER.index(prev_heat) else "down" if HEAT_ORDER.index(a["heat"]) < HEAT_ORDER.index(prev_heat) else "same")
    objections = sum(x["intent"] == "objection" for x in past) + (a["intent"] == "objection")
    had_complaint = any(x["intent"] == "complaint" for x in past)
    was_buying = any(x["intent"] == "buy" for x in past)
    T = L[lang]; i = INTENTS.index(a["intent"])
    ph = lambda k: T["PH"].format(x=T["PHX"][k])
    miss = set()
    def val(k, ck=None):
        v = cfg.get(ck or k)
        if not v: miss.add(k)
        return v or ph(k)
    offer = val("offer"); logi = val("logi", "logistics") if a["intent"] == "buy" else ""
    guar = val("guar", "guarantee") if a["intent"] in ("objection", "complaint") else ""
    price = T["P"].format(price=val("price")) if (a["asks_price"] or a["intent"] in ("objection", "buy")) else ""
    calm = a["intent"] != "complaint" and not had_complaint           # jamais de vente croisée ni de rareté juste après un litige
    cross = T["X"].format(cross=val("cross")) if calm else ""
    scarcity = T["S"] if cfg["limited"] and calm and a["intent"] in ("curiosity", "comparison", "buy") else ""
    body = T["A"][i].format(offer=offer, logi=logi, guar=guar)
    body = re.sub(r"\s+", " ", body).strip()
    join = lambda *xs: " ".join(x for x in xs if x)
    sign = f"\n— {cfg['brand']}" if channel == "messenger" and cfg["brand"] else ""
    alt = T["ALT"].format(alt=val("alt")) if a["intent"] == "objection" else ""
    o1 = join(T["V"][i], body, price, T["C"][i]) if channel == "messenger" else join(body, price, T["C"][i])
    o2 = join(T["V"][i], body, price, cross, scarcity, T["C"][i])
    o3 = join(T["R"][i], alt, guar if a["intent"] != "objection" else "", T["C3c"] if a["intent"] == "complaint" else T["C3"])
    opts = [re.sub(r"\s+", " ", o).strip() + sign for o in (o1, o2, o3)]
    warnings = []
    advice = T["ADV"][i]
    if objections >= 2:
        advice += " " + ADV2[lang]; warnings.append("repeat_objection")
    if a["intent"] == "objection" and was_buying:
        advice += " " + ADV3[lang]
    if miss:
        warnings.append("missing:" + ",".join(sorted(miss)))
    if channel == "whatsapp" and max(map(len, opts)) > 700:
        warnings.append("long")
    return {
        "lang": lang, "channel": channel,
        "analysis": {"intent": T["intent"][i], "heat": T["heat"][a["heat"]], "temper": T["temper"][a["temper"]], "intent_key": a["intent"], "heat_key": a["heat"]},
        "followup": T["Fc"] if a["intent"] == "complaint" else T["F"],
        "options": opts, "advice": advice, "warnings": warnings,
        "conversation": {"turns": len(hist) + 1, "trend": trend, "objections": objections, "had_complaint": had_complaint},
        "placeholders": opts and sum(o.count("⚠️") for o in opts) > 0,
        "master_prompt": master_prompt(cfg),
    }
