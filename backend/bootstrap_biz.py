"""Bouton 7 (Espace Candidat) : « Lancer mon entreprise à 0 € » — co-fondateur « lean » (BootstrapBot) par règles : gratuit, sans IA ni tiers, rien conservé.

Étape 0 : analyse du CV collé (super-pouvoirs, avantage injuste à valider, 3 idées « zéro euro » alignées sur le parcours) ; pour CHAQUE idée, 3 raisons
d'échec (avocat du diable). Une fois l'idée choisie : plan en 4 étapes (validation, proposition de valeur + Business Model Canvas, MVP gratuit en 48 h,
chiffrage minimal), chasse aux coûts cachés et boîte à outils exclusivement à plan gratuit pérenne.
Anti-hallucination : aucun chiffre de marché, de revenu ou de prix n'est inventé ; seuls les nombres saisis par l'utilisateur servent aux calculs (seuil de rentabilité)."""
from __future__ import annotations
import math
import re

LANGS = ("fr", "en", "de", "es", "it", "ar")
MAX_CV = 6000
MAX_FIELD = 300

# domaines détectés dans le CV (mots-clés toutes langues, comparés sans accents ; ≤ 5 lettres = mot entier)
DOMAINS = ("tech", "marketing", "finance", "education", "health", "creative", "sales", "ops", "hospitality", "admin")
DOM_KW = {
    "tech": "python,java,javascript,sql,react,node,developpeur,developer,informatique,software,logiciel,data,cloud,devops,reseau,network,programmation,programming,entwickler,desarrollador,sviluppatore,برمجة,مطور,معلوماتية",
    "marketing": "marketing,seo,social media,reseaux sociaux,communication,content,contenu,community,brand,publicite,advertising,werbung,publicidad,pubblicita,تسويق,اتصال",
    "finance": "comptab,accounting,finance,audit,controle de gestion,budget,fiscal,tax,buchhaltung,contabilidad,contabilita,تدقيق,محاسبة,مالية",
    "education": "enseign,formateur,formation,teacher,training,trainer,professeur,education,pedagog,lehrer,docente,insegnante,معلم,تدريس,تكوين",
    "health": "sante,health,infirmi,nurse,medecin,doctor,kine,pharma,paramedical,gesundheit,salud,salute,صحة,تمريض,طبيب",
    "creative": "design,graphi,photoshop,illustrator,figma,video,montage,photograph,creatif,creative,ui,ux,diseno,progettazione,تصميم,مصور",
    "sales": "vente,commercial,sales,business development,prospection,negociation,account manager,vertrieb,ventas,vendite,مبيعات",
    "ops": "logistique,logistics,supply,production,qualite,quality,maintenance,industrie,industry,chantier,construction,projet,project manager,gestion de projet,produktion,logistica,لوجستيك,صيانة",
    "hospitality": "restaurant,cuisine,hotel,tourisme,tourism,serveur,chef,hospitality,cafe,gastronomie,gastronomia,ristorazione,فندق,مطعم,سياحة",
    "admin": "administratif,administrative,secretar,assistant,assistante,gestion,rh,ressources humaines,recrutement,hr,recruit,juridique,legal,droit,verwaltung,administracion,amministrazione,قانون,إدارة,موارد بشرية",
}
SOFT = ("lead", "comm", "auto", "org", "crea", "ana")
SOFT_KW = {
    "lead": "manager,management,encadr,lead,diriger,direction,chef d'equipe,team lead,fuhrung,liderazgo,guida,قيادة,مدير",
    "comm": "communication,negociation,presentation,relation client,customer,client,kommunikation,comunicacion,comunicazione,تواصل",
    "auto": "autonom,independant,freelance,initiative,selbst,autonomo,مستقل",
    "org": "organis,planif,rigueur,gestion du temps,organi,planning,planung,organizacion,تنظيم,تخطيط",
    "crea": "creatif,creative,innov,idee,kreativ,creativo,إبداع,ابتكار",
    "ana": "analyse,analysis,analytique,data,statisti,resolution de probleme,problem solving,analisi,analisis,تحليل",
}
# idées : archétype → (domaines favorables), risques (3), outils
ARCH = ("consulting", "course", "nocode", "agency", "newsletter", "coaching", "templates", "directory")
ARCH_RISK = {"consulting": ("cred", "cycle", "comp"), "course": ("demand", "comp", "time"), "nocode": ("cplx", "plat", "comp"), "agency": ("comp", "time", "cycle"),
             "newsletter": ("demand", "time", "plat"), "coaching": ("cred", "cycle", "demand"), "templates": ("comp", "demand", "plat"), "directory": ("demand", "plat", "cplx")}
DOM_ARCH = {"tech": ("nocode", "agency", "consulting"), "marketing": ("agency", "newsletter", "consulting"), "finance": ("consulting", "templates", "course"),
            "education": ("course", "coaching", "templates"), "health": ("coaching", "course", "newsletter"), "creative": ("templates", "agency", "course"),
            "sales": ("agency", "consulting", "coaching"), "ops": ("consulting", "templates", "nocode"), "hospitality": ("course", "directory", "consulting"),
            "admin": ("templates", "consulting", "agency")}
DEFAULT_ARCH = ("consulting", "course", "newsletter")
ARCH_TOOLS = {"consulting": ["Notion", "Google Sheets", "Carrd", "Typeform / Google Forms"], "course": ["Canva", "Notion", "Google Forms", "CapCut"],
              "nocode": ["Notion", "Google Sheets", "Framer", "Google Forms"], "agency": ["Trello", "Canva", "Carrd", "Buffer"],
              "newsletter": ["Google Docs", "Canva", "Buffer", "Google Forms"], "coaching": ["Google Forms", "Notion", "Google Sites", "Canva"],
              "templates": ["Canva", "Notion", "Google Sheets", "Photopea"], "directory": ["Google Sheets", "Notion", "Google Sites", "Google Forms"]}
TOOLBOX = (("ideas", ["Notion (Free)", "Trello", "Google Keep"]), ("research", ["Google Trends", "Ubersuggest (Free)", "AnswerThePublic (Free)", "Similarweb (Free)"]),
           ("site", ["Carrd (Free)", "Google Sites", "Framer (free plan)", "Notion + Super / Puffify"]), ("design", ["Canva (Free)", "Photopea", "Coolors", "Remove.bg"]),
           ("finance", ["Google Sheets"]), ("acq", ["Buffer (Free)", "Meta Business Suite", "CapCut", "Typeform / Google Forms"]))

L = {}
RK = ("cred", "cycle", "comp", "demand", "time", "plat", "cplx")
BK = ("seg", "uvp", "chan", "rel", "rev", "res", "act", "par", "cost")


def _lang(dom, soft, risk, arche, cost, bmc, qs, mvp, lab):
    return dict(dom=dict(zip(DOMAINS + ("general",), dom)), soft=dict(zip(SOFT, soft)), risk=dict(zip(RK, risk)),
                arche={k: dict(name=v[0], desc=v[1], test=v[2]) for k, v in zip(ARCH, arche)}, cost=cost, bmc=dict(zip(BK, bmc)), qs=qs, mvp=mvp, lab=lab)


L["fr"] = _lang(
    ["Technologie / informatique", "Marketing / communication", "Finance / comptabilité", "Enseignement / formation", "Santé / bien-être", "Création / design / image", "Vente / développement commercial", "Opérations / logistique / projets", "Restauration / hôtellerie / tourisme", "Administration / RH / juridique", "Polyvalent"],
    ["Leadership / encadrement", "Communication / relationnel", "Autonomie", "Organisation / rigueur", "Créativité", "Analyse / résolution de problèmes"],
    ["Crédibilité : sans références publiques, les clients hésitent à payer en premier.", "Cycle de vente long : les décisions d'achat peuvent prendre des semaines.", "Concurrence cachée : des freelances et agences font déjà la même chose, souvent moins cher.", "Demande non prouvée : personne n'a encore payé pour cela.", "Temps : vous vendez votre temps, votre revenu plafonne si vous n'automatisez pas.", "Dépendance à une plateforme : un changement de règles ou d'algorithme peut détruire votre audience.", "Complexité : maintenir un outil ou un service demande plus de travail que prévu."],
    [("Conseil / prestation haut de gamme", "Vendre votre expertise {domain} en missions courtes et chiffrées à de petites entreprises, sans stock ni outil payant.", "Proposez un diagnostic gratuit de 30 minutes à 5 entreprises ciblées et notez combien demandent une mission payante."),
     ("Infoproduit / mini-formation", "Transformer votre savoir-faire {domain} en guide ou mini-cours pour débutants, vendu après une préinscription.", "Publiez le plan du cours et collectez des préinscriptions par formulaire gratuit : visez des engagements réels avant de produire."),
     ("Outil no-code / automatisation", "Construire pour des professionnels du domaine {domain} un petit outil ou une automatisation sur tableur et formulaires gratuits.", "Montrez une maquette à 5 utilisateurs et demandez : combien paieriez-vous pour l'avoir demain ?"),
     ("Agence spécialisée / service packagé", "Proposer un service {domain} à périmètre fixe (une offre, un livrable, un délai) pour une niche précise.", "Contactez 20 entreprises de votre niche avec une offre en une phrase et mesurez le taux de réponse."),
     ("Newsletter / contenu de niche", "Publier chaque semaine une veille {domain} utile pour bâtir une audience, puis monétiser par prestations ou partenariats.", "Lancez le numéro 1 gratuitement et mesurez abonnés, ouvertures et réponses en 14 jours."),
     ("Coaching / mentorat", "Accompagner des personnes qui veulent progresser en {domain}, en séances à la carte.", "Offrez 3 séances d'essai contre un témoignage honnête et un avis sur le prix qu'ils paieraient."),
     ("Modèles et outils prêts à l'emploi", "Créer des modèles {domain} (tableurs, documents, visuels) vendus en téléchargement.", "Offrez un modèle gratuit contre un e-mail, puis proposez la version complète à ceux qui l'utilisent."),
     ("Annuaire / sélection curatée", "Rassembler et trier des ressources utiles du domaine {domain} dans un répertoire gratuit, monétisé ensuite par mise en avant.", "Publiez 20 entrées dans un tableur partagé et mesurez visites et demandes d'ajout.")],
    [("Nom de domaine personnalisé", "Utilisez le sous-domaine gratuit de votre outil (Carrd, Google Sites…) pendant le test."), ("Hébergement ou abonnement du site", "Restez sur le plan gratuit ; ne passez au payant qu'après une première vente."),
     ("Frais de paiement en ligne", "Encaissez d'abord par virement ou lien de paiement dont les frais ne sont dus qu'à la vente."), ("Statut juridique, assurance, comptabilité", "Vérifiez le régime le plus léger de votre pays et les aides à la création avant de formaliser."),
     ("Options payantes cachées des outils gratuits", "Lisez les limites du plan gratuit (marque, export, nombre de pages) avant de construire."), ("Votre temps", "Fixez un budget d'heures par semaine et arrêtez si aucun signal d'achat après 4 semaines.")],
    ["Segments de clientèle", "Proposition de valeur", "Canaux", "Relation client", "Sources de revenus", "Ressources clés", "Activités clés", "Partenaires clés", "Structure de coûts"],
    ["Racontez-moi la dernière fois que vous avez rencontré ce problème : que s'est-il passé ?", "Comment le résolvez-vous aujourd'hui, avec quels outils ou quelles personnes ?", "Qu'est-ce qui est le plus pénible ou coûteux dans cette solution ?", "Avez-vous déjà payé pour le résoudre ? Combien de temps ou d'argent y consacrez-vous ?", "Qu'est-ce qui vous ferait changer de solution ?", "Connaissez-vous quelqu'un d'autre qui a ce problème et accepterait d'en parler ?"],
    ["H0-H4 : une page d'une phrase de promesse et un bouton d'action (Carrd ou Google Sites).", "H4-H8 : un formulaire gratuit (Google Forms / Typeform) pour recueillir e-mail et besoin.", "H8-H16 : 3 visuels simples (Canva) et un court message d'accroche.", "H16-H32 : contactez 20 personnes de votre cible par message direct, proposez 15 minutes d'échange.", "H32-H44 : menez 5 échanges, notez les phrases exactes et les objections.", "H44-H48 : comptez les engagements concrets (préinscriptions, rendez-vous, précommandes) et décidez : continuer, ajuster ou abandonner."],
    dict(unfair_two="Hypothèse d'avantage injuste (à valider auprès de clients) : la combinaison rare « {d1} + {d2} »{years} vous permet de parler aux deux mondes ; vendez-la à une niche précise plutôt qu'en offre généraliste.",
         unfair_one="Hypothèse d'avantage injuste (à valider auprès de clients) : votre profondeur en « {d1} »{years}, appliquée à un problème précis d'une niche.",
         years=" ({n} ans d'expérience indiqués dans votre CV)", uvp="Nous aidons {seg} à {result} grâce à {solution}, sans {pain}.", ph="[⚠️ À COMPLÉTER : {x}]",
         phx=dict(seg="clients cibles", result="résultat visé", solution="votre solution", pain="la frustration actuelle", price="prix", var="coût variable", fixed="coûts fixes mensuels", domain="votre domaine"),
         be_zero="Sans coûts fixes, chaque vente est déjà au-dessus du seuil de rentabilité.", be_line="Seuil de rentabilité : {n} vente(s) par mois pour couvrir {fixed} de coûts fixes (marge unitaire {m}).",
         goal_line="Pour dégager en plus {goal} par mois : {n} vente(s) par mois.", be_bad="Le prix doit être supérieur au coût variable pour dégager une marge.",
         be_ph="Renseignez prix, coût variable et coûts fixes pour calculer votre seuil de rentabilité.", hours_line="Avec {h} h par semaine : environ {u} vente(s) à conclure par semaine."))
L["en"] = _lang(
    ["Technology / IT", "Marketing / communication", "Finance / accounting", "Teaching / training", "Health / wellbeing", "Creative / design / imagery", "Sales / business development", "Operations / logistics / projects", "Food / hospitality / tourism", "Administration / HR / legal", "Generalist"],
    ["Leadership / management", "Communication / people skills", "Autonomy", "Organisation / rigour", "Creativity", "Analysis / problem solving"],
    ["Credibility: without public references, clients hesitate to pay first.", "Long sales cycle: purchase decisions can take weeks.", "Hidden competition: freelancers and agencies already do the same, often cheaper.", "Unproven demand: nobody has paid for this yet.", "Time: you sell your time, so income caps out unless you automate.", "Platform dependence: a rule or algorithm change can wipe out your audience.", "Complexity: maintaining a tool or service takes more work than planned."],
    [("Consulting / high-end service", "Sell your {domain} expertise as short, priced engagements to small businesses, with no stock or paid tools.", "Offer a free 30-minute diagnosis to 5 targeted companies and note how many ask for a paid engagement."),
     ("Info product / mini-course", "Turn your {domain} know-how into a guide or mini-course for beginners, sold after a pre-registration.", "Publish the course outline and collect pre-registrations with a free form: aim for real commitments before producing."),
     ("No-code tool / automation", "Build a small tool or automation for {domain} professionals using free spreadsheets and forms.", "Show a mock-up to 5 users and ask: how much would you pay to have it tomorrow?"),
     ("Specialised agency / productised service", "Offer a fixed-scope {domain} service (one offer, one deliverable, one deadline) for a precise niche.", "Contact 20 companies in your niche with a one-sentence offer and measure the reply rate."),
     ("Niche newsletter / content", "Publish a useful weekly {domain} digest to build an audience, then monetise through services or partnerships.", "Launch issue 1 for free and measure subscribers, opens and replies over 14 days."),
     ("Coaching / mentoring", "Help people who want to improve in {domain}, in pay-as-you-go sessions.", "Offer 3 trial sessions in exchange for an honest testimonial and feedback on what they would pay."),
     ("Ready-to-use templates and tools", "Create {domain} templates (spreadsheets, documents, visuals) sold as downloads.", "Give one template for free in exchange for an email, then offer the full pack to those who use it."),
     ("Directory / curated selection", "Gather and sort useful {domain} resources in a free directory, monetised later through featured listings.", "Publish 20 entries in a shared spreadsheet and measure visits and submission requests.")],
    [("Custom domain name", "Use the free subdomain of your tool (Carrd, Google Sites…) during the test."), ("Website hosting or subscription", "Stay on the free plan; upgrade only after a first sale."),
     ("Online payment fees", "Collect first by bank transfer or a payment link whose fees only apply on a sale."), ("Legal status, insurance, accounting", "Check the lightest regime in your country and start-up support before formalising."),
     ("Hidden paid options in free tools", "Read the free plan limits (branding, export, page count) before building."), ("Your time", "Set a weekly hours budget and stop if there is no buying signal after 4 weeks.")],
    ["Customer segments", "Value proposition", "Channels", "Customer relationships", "Revenue streams", "Key resources", "Key activities", "Key partners", "Cost structure"],
    ["Tell me about the last time you ran into this problem: what happened?", "How do you solve it today, with which tools or people?", "What is the most painful or costly part of that solution?", "Have you ever paid to solve it? How much time or money do you spend?", "What would make you switch solutions?", "Do you know anyone else with this problem who would talk about it?"],
    ["H0-H4: one page with a one-sentence promise and an action button (Carrd or Google Sites).", "H4-H8: a free form (Google Forms / Typeform) to collect email and need.", "H8-H16: 3 simple visuals (Canva) and a short hook message.", "H16-H32: message 20 people in your target and offer a 15-minute chat.", "H32-H44: hold 5 conversations, note exact phrases and objections.", "H44-H48: count concrete commitments (pre-registrations, meetings, pre-orders) and decide: continue, adjust or drop."],
    dict(unfair_two="Unfair-advantage hypothesis (to validate with customers): the rare combination “{d1} + {d2}”{years} lets you speak to both worlds; sell it to a precise niche rather than as a generalist offer.",
         unfair_one="Unfair-advantage hypothesis (to validate with customers): your depth in “{d1}”{years}, applied to one precise problem in a niche.",
         years=" ({n} years of experience stated in your CV)", uvp="We help {seg} to {result} with {solution}, without {pain}.", ph="[⚠️ TO COMPLETE: {x}]",
         phx=dict(seg="target customers", result="desired outcome", solution="your solution", pain="today's frustration", price="price", var="variable cost", fixed="monthly fixed costs", domain="your field"),
         be_zero="With no fixed costs, every sale is already above break-even.", be_line="Break-even: {n} sale(s) per month to cover {fixed} of fixed costs (unit margin {m}).",
         goal_line="To earn an extra {goal} per month: {n} sale(s) per month.", be_bad="The price must be higher than the variable cost to make a margin.",
         be_ph="Enter price, variable cost and fixed costs to compute your break-even.", hours_line="With {h} h per week: about {u} sale(s) to close per week."))


L["de"] = _lang(
    ["Technologie / IT", "Marketing / Kommunikation", "Finanzen / Buchhaltung", "Lehre / Weiterbildung", "Gesundheit / Wohlbefinden", "Kreativ / Design / Bild", "Vertrieb / Geschäftsentwicklung", "Betrieb / Logistik / Projekte", "Gastronomie / Hotellerie / Tourismus", "Verwaltung / Personal / Recht", "Vielseitig"],
    ["Führung / Teamleitung", "Kommunikation / Beziehungen", "Selbstständigkeit", "Organisation / Sorgfalt", "Kreativität", "Analyse / Problemlösung"],
    ["Glaubwürdigkeit: ohne öffentliche Referenzen zögern Kunden, als Erste zu zahlen.", "Langer Verkaufszyklus: Kaufentscheidungen können Wochen dauern.", "Versteckte Konkurrenz: Freelancer und Agenturen bieten dasselbe oft schon günstiger an.", "Unbewiesene Nachfrage: noch niemand hat dafür bezahlt.", "Zeit: Sie verkaufen Ihre Zeit; ohne Automatisierung ist Ihr Einkommen gedeckelt.", "Plattformabhängigkeit: eine Regel- oder Algorithmusänderung kann Ihre Reichweite zerstören.", "Komplexität: Ein Tool oder Service zu pflegen kostet mehr Arbeit als geplant."],
    [("Beratung / Premium-Dienstleistung", "Verkaufen Sie Ihre Expertise in {domain} in kurzen, kalkulierten Einsätzen an kleine Unternehmen, ohne Lager und ohne kostenpflichtige Tools.", "Bieten Sie 5 gezielten Unternehmen eine kostenlose 30-Minuten-Analyse an und notieren Sie, wie viele einen bezahlten Auftrag wünschen."),
     ("Infoprodukt / Mini-Kurs", "Machen Sie Ihr Know-how in {domain} zu einem Leitfaden oder Mini-Kurs für Einsteiger, verkauft nach Vorabanmeldung.", "Veröffentlichen Sie den Kursplan und sammeln Sie Vorabanmeldungen per kostenlosem Formular: Ziel sind echte Zusagen vor der Produktion."),
     ("No-Code-Tool / Automatisierung", "Bauen Sie für Fachleute aus {domain} ein kleines Tool oder eine Automatisierung mit kostenloser Tabelle und Formularen.", "Zeigen Sie 5 Nutzern einen Entwurf und fragen Sie: Wie viel würden Sie zahlen, um es morgen zu haben?"),
     ("Spezialagentur / Service-Paket", "Bieten Sie einen Service in {domain} mit festem Umfang (ein Angebot, ein Ergebnis, eine Frist) für eine klare Nische an.", "Kontaktieren Sie 20 Unternehmen Ihrer Nische mit einem Ein-Satz-Angebot und messen Sie die Antwortquote."),
     ("Nischen-Newsletter / Content", "Veröffentlichen Sie wöchentlich nützliche Updates zu {domain}, bauen Sie eine Zielgruppe auf und monetarisieren Sie über Leistungen oder Partnerschaften.", "Starten Sie Ausgabe 1 kostenlos und messen Sie Abonnenten, Öffnungen und Antworten über 14 Tage."),
     ("Coaching / Mentoring", "Begleiten Sie Menschen, die sich in {domain} verbessern wollen, in einzelnen Sitzungen.", "Bieten Sie 3 Probesitzungen gegen ein ehrliches Feedback und eine Einschätzung zum Preis an."),
     ("Fertige Vorlagen und Tools", "Erstellen Sie Vorlagen für {domain} (Tabellen, Dokumente, Grafiken) zum Download.", "Verschenken Sie eine Vorlage gegen eine E-Mail und bieten Sie die Vollversion denen an, die sie nutzen."),
     ("Verzeichnis / kuratierte Auswahl", "Sammeln und sortieren Sie nützliche Ressourcen aus {domain} in einem kostenlosen Verzeichnis, später über Hervorhebungen monetarisiert.", "Veröffentlichen Sie 20 Einträge in einer geteilten Tabelle und messen Sie Besuche und Aufnahmeanfragen.")],
    [("Eigene Domain", "Nutzen Sie während des Tests die kostenlose Subdomain Ihres Tools (Carrd, Google Sites …)."), ("Hosting oder Website-Abo", "Bleiben Sie im kostenlosen Tarif; wechseln Sie erst nach dem ersten Verkauf zu einem bezahlten."),
     ("Gebühren für Online-Zahlung", "Kassieren Sie zuerst per Überweisung oder Zahlungslink, dessen Gebühren erst beim Verkauf anfallen."), ("Rechtsform, Versicherung, Buchhaltung", "Prüfen Sie die leichteste Form in Ihrem Land und Gründungsförderung, bevor Sie formalisieren."),
     ("Versteckte Bezahloptionen kostenloser Tools", "Lesen Sie die Grenzen des kostenlosen Tarifs (Logo, Export, Seitenzahl), bevor Sie darauf aufbauen."), ("Ihre Zeit", "Legen Sie ein Stundenbudget pro Woche fest und stoppen Sie, wenn nach 4 Wochen kein Kaufsignal kommt.")],
    ["Kundensegmente", "Nutzenversprechen", "Kanäle", "Kundenbeziehungen", "Einnahmequellen", "Schlüsselressourcen", "Schlüsselaktivitäten", "Schlüsselpartner", "Kostenstruktur"],
    ["Erzählen Sie mir vom letzten Mal, als Sie dieses Problem hatten: Was ist passiert?", "Wie lösen Sie es heute, mit welchen Tools oder Personen?", "Was ist an dieser Lösung am mühsamsten oder teuersten?", "Haben Sie schon dafür bezahlt? Wie viel Zeit oder Geld investieren Sie?", "Was würde Sie zum Wechsel bewegen?", "Kennen Sie jemanden mit demselben Problem, der darüber sprechen würde?"],
    ["H0-H4: eine Seite mit einem Versprechen in einem Satz und einem Aktionsbutton (Carrd oder Google Sites).", "H4-H8: ein kostenloses Formular (Google Forms / Typeform) für E-Mail und Bedarf.", "H8-H16: 3 einfache Grafiken (Canva) und eine kurze Ansprache.", "H16-H32: Sprechen Sie 20 Personen Ihrer Zielgruppe per Direktnachricht an und bieten Sie 15 Minuten Austausch an.", "H32-H44: Führen Sie 5 Gespräche, notieren Sie genaue Sätze und Einwände.", "H44-H48: Zählen Sie konkrete Zusagen (Voranmeldungen, Termine, Vorbestellungen) und entscheiden Sie: weiter, anpassen oder aufgeben."],
    dict(unfair_two="Hypothese eines unfairen Vorteils (bei Kunden zu prüfen): die seltene Kombination „{d1} + {d2}“{years} lässt Sie mit beiden Welten sprechen; verkaufen Sie sie an eine klare Nische statt als Allround-Angebot.",
         unfair_one="Hypothese eines unfairen Vorteils (bei Kunden zu prüfen): Ihre Tiefe in „{d1}“{years}, angewendet auf ein präzises Problem einer Nische.",
         years=" ({n} Jahre Erfahrung laut Ihrem Lebenslauf)", uvp="Wir helfen {seg}, {result} zu erreichen, mit {solution}, ohne {pain}.", ph="[⚠️ ZU ERGÄNZEN: {x}]",
         phx=dict(seg="Zielkunden", result="gewünschtes Ergebnis", solution="Ihre Lösung", pain="die heutige Frustration", price="Preis", var="variable Kosten", fixed="monatliche Fixkosten", domain="Ihr Fachgebiet"),
         be_zero="Ohne Fixkosten liegt jeder Verkauf bereits über der Gewinnschwelle.", be_line="Gewinnschwelle: {n} Verkauf/Verkäufe pro Monat, um {fixed} Fixkosten zu decken (Stückmarge {m}).",
         goal_line="Um zusätzlich {goal} pro Monat zu verdienen: {n} Verkauf/Verkäufe pro Monat.", be_bad="Der Preis muss über den variablen Kosten liegen, damit eine Marge entsteht.",
         be_ph="Tragen Sie Preis, variable Kosten und Fixkosten ein, um Ihre Gewinnschwelle zu berechnen.", hours_line="Mit {h} Std. pro Woche: etwa {u} Verkauf/Verkäufe pro Woche."))
L["es"] = _lang(
    ["Tecnología / informática", "Marketing / comunicación", "Finanzas / contabilidad", "Enseñanza / formación", "Salud / bienestar", "Creación / diseño / imagen", "Ventas / desarrollo comercial", "Operaciones / logística / proyectos", "Restauración / hostelería / turismo", "Administración / RR. HH. / jurídico", "Polivalente"],
    ["Liderazgo / gestión de equipos", "Comunicación / trato personal", "Autonomía", "Organización / rigor", "Creatividad", "Análisis / resolución de problemas"],
    ["Credibilidad: sin referencias públicas, los clientes dudan en ser los primeros en pagar.", "Ciclo de venta largo: las decisiones de compra pueden tardar semanas.", "Competencia oculta: freelances y agencias ya hacen lo mismo, a menudo más barato.", "Demanda no probada: nadie ha pagado todavía por esto.", "Tiempo: vende su tiempo; sin automatizar, sus ingresos tienen un techo.", "Dependencia de una plataforma: un cambio de reglas o de algoritmo puede destruir su audiencia.", "Complejidad: mantener una herramienta o un servicio exige más trabajo del previsto."],
    [("Consultoría / servicio premium", "Venda su experiencia en {domain} en misiones cortas y presupuestadas a pequeñas empresas, sin stock ni herramientas de pago.", "Ofrezca un diagnóstico gratuito de 30 minutos a 5 empresas elegidas y anote cuántas piden una misión de pago."),
     ("Infoproducto / minicurso", "Convierta su saber hacer en {domain} en una guía o minicurso para principiantes, vendido tras una preinscripción.", "Publique el temario y recoja preinscripciones con un formulario gratuito: busque compromisos reales antes de producir."),
     ("Herramienta no-code / automatización", "Construya para profesionales de {domain} una pequeña herramienta o automatización con hojas de cálculo y formularios gratuitos.", "Muestre una maqueta a 5 usuarios y pregunte: ¿cuánto pagaría por tenerlo mañana?"),
     ("Agencia especializada / servicio empaquetado", "Ofrezca un servicio de {domain} de alcance fijo (una oferta, un entregable, un plazo) para un nicho preciso.", "Contacte con 20 empresas de su nicho con una oferta de una frase y mida la tasa de respuesta."),
     ("Newsletter / contenido de nicho", "Publique cada semana una vigilancia útil de {domain} para crear audiencia y luego monetice con servicios o alianzas.", "Lance el número 1 gratis y mida suscriptores, aperturas y respuestas en 14 días."),
     ("Coaching / mentoría", "Acompañe a personas que quieren progresar en {domain}, en sesiones a la carta.", "Ofrezca 3 sesiones de prueba a cambio de un testimonio honesto y una opinión sobre el precio."),
     ("Plantillas y herramientas listas para usar", "Cree plantillas de {domain} (hojas de cálculo, documentos, visuales) para vender en descarga.", "Regale una plantilla a cambio de un correo y ofrezca la versión completa a quienes la usen."),
     ("Directorio / selección curada", "Reúna y ordene recursos útiles de {domain} en un directorio gratuito, monetizado después con destacados.", "Publique 20 entradas en una hoja compartida y mida visitas y solicitudes de inclusión.")],
    [("Nombre de dominio propio", "Use el subdominio gratuito de su herramienta (Carrd, Google Sites…) durante la prueba."), ("Alojamiento o suscripción del sitio", "Quédese en el plan gratuito; pase a uno de pago solo tras la primera venta."),
     ("Comisiones de pago en línea", "Cobre primero por transferencia o enlace de pago cuyas comisiones solo se deben al vender."), ("Forma jurídica, seguro, contabilidad", "Compruebe el régimen más ligero de su país y las ayudas a la creación antes de formalizar."),
     ("Opciones de pago ocultas de herramientas gratuitas", "Lea los límites del plan gratuito (marca, exportación, número de páginas) antes de construir."), ("Su tiempo", "Fije un presupuesto de horas por semana y pare si no hay señal de compra tras 4 semanas.")],
    ["Segmentos de clientes", "Propuesta de valor", "Canales", "Relación con clientes", "Fuentes de ingresos", "Recursos clave", "Actividades clave", "Socios clave", "Estructura de costes"],
    ["Cuénteme la última vez que tuvo este problema: ¿qué pasó?", "¿Cómo lo resuelve hoy, con qué herramientas o personas?", "¿Qué es lo más molesto o caro de esa solución?", "¿Ha pagado alguna vez por resolverlo? ¿Cuánto tiempo o dinero le dedica?", "¿Qué le haría cambiar de solución?", "¿Conoce a alguien más con este problema que aceptaría hablar de ello?"],
    ["H0-H4: una página con una frase de promesa y un botón de acción (Carrd o Google Sites).", "H4-H8: un formulario gratuito (Google Forms / Typeform) para recoger correo y necesidad.", "H8-H16: 3 visuales sencillos (Canva) y un mensaje corto de enganche.", "H16-H32: contacte a 20 personas de su público por mensaje directo y proponga 15 minutos de charla.", "H32-H44: haga 5 conversaciones y anote frases exactas y objeciones.", "H44-H48: cuente los compromisos concretos (preinscripciones, citas, preventas) y decida: continuar, ajustar o abandonar."],
    dict(unfair_two="Hipótesis de ventaja injusta (por validar con clientes): la combinación poco común «{d1} + {d2}»{years} le permite hablar con ambos mundos; véndala a un nicho preciso y no como oferta generalista.",
         unfair_one="Hipótesis de ventaja injusta (por validar con clientes): su profundidad en «{d1}»{years}, aplicada a un problema preciso de un nicho.",
         years=" ({n} años de experiencia indicados en su CV)", uvp="Ayudamos a {seg} a {result} gracias a {solution}, sin {pain}.", ph="[⚠️ POR COMPLETAR: {x}]",
         phx=dict(seg="clientes objetivo", result="resultado buscado", solution="su solución", pain="la frustración actual", price="precio", var="coste variable", fixed="costes fijos mensuales", domain="su ámbito"),
         be_zero="Sin costes fijos, cada venta ya supera el punto de equilibrio.", be_line="Punto de equilibrio: {n} venta(s) al mes para cubrir {fixed} de costes fijos (margen unitario {m}).",
         goal_line="Para ganar además {goal} al mes: {n} venta(s) al mes.", be_bad="El precio debe ser superior al coste variable para obtener margen.",
         be_ph="Indique precio, coste variable y costes fijos para calcular su punto de equilibrio.", hours_line="Con {h} h por semana: unas {u} venta(s) por cerrar cada semana."))
L["it"] = _lang(
    ["Tecnologia / informatica", "Marketing / comunicazione", "Finanza / contabilità", "Insegnamento / formazione", "Salute / benessere", "Creatività / design / immagine", "Vendite / sviluppo commerciale", "Operazioni / logistica / progetti", "Ristorazione / ospitalità / turismo", "Amministrazione / risorse umane / legale", "Polivalente"],
    ["Leadership / gestione di team", "Comunicazione / relazioni", "Autonomia", "Organizzazione / rigore", "Creatività", "Analisi / risoluzione di problemi"],
    ["Credibilità: senza referenze pubbliche, i clienti esitano a pagare per primi.", "Ciclo di vendita lungo: le decisioni d'acquisto possono richiedere settimane.", "Concorrenza nascosta: freelance e agenzie fanno già la stessa cosa, spesso a meno.", "Domanda non provata: nessuno ha ancora pagato per questo.", "Tempo: vende il suo tempo; senza automazione il reddito ha un tetto.", "Dipendenza da una piattaforma: un cambio di regole o di algoritmo può distruggere il suo pubblico.", "Complessità: mantenere uno strumento o un servizio richiede più lavoro del previsto."],
    [("Consulenza / servizio premium", "Venda la sua competenza in {domain} in incarichi brevi e preventivati a piccole imprese, senza scorte né strumenti a pagamento.", "Proponga una diagnosi gratuita di 30 minuti a 5 aziende mirate e annoti quante chiedono un incarico a pagamento."),
     ("Infoprodotto / mini-corso", "Trasformi il suo know-how in {domain} in una guida o un mini-corso per principianti, venduto dopo una preiscrizione.", "Pubblichi il programma e raccolga preiscrizioni con un modulo gratuito: miri a impegni reali prima di produrre."),
     ("Strumento no-code / automazione", "Costruisca per i professionisti di {domain} un piccolo strumento o un'automazione con fogli di calcolo e moduli gratuiti.", "Mostri una bozza a 5 utenti e chieda: quanto pagherebbe per averlo domani?"),
     ("Agenzia specializzata / servizio in pacchetto", "Proponga un servizio di {domain} a perimetro fisso (un'offerta, un risultato, una scadenza) per una nicchia precisa.", "Contatti 20 aziende della sua nicchia con un'offerta in una frase e misuri il tasso di risposta."),
     ("Newsletter / contenuti di nicchia", "Pubblichi ogni settimana un aggiornamento utile su {domain} per costruire un pubblico, poi monetizzi con servizi o partnership.", "Lanci il numero 1 gratis e misuri iscritti, aperture e risposte in 14 giorni."),
     ("Coaching / mentoring", "Accompagni chi vuole migliorare in {domain}, con sessioni a richiesta.", "Offra 3 sessioni di prova in cambio di una testimonianza onesta e di un parere sul prezzo."),
     ("Modelli e strumenti pronti all'uso", "Crei modelli di {domain} (fogli di calcolo, documenti, grafiche) da vendere in download.", "Regali un modello in cambio di un'e-mail e proponga la versione completa a chi lo usa."),
     ("Directory / selezione curata", "Raccolga e ordini risorse utili di {domain} in una directory gratuita, monetizzata poi con inserzioni in evidenza.", "Pubblichi 20 voci in un foglio condiviso e misuri visite e richieste di inserimento.")],
    [("Dominio personalizzato", "Usi il sottodominio gratuito del suo strumento (Carrd, Google Sites…) durante il test."), ("Hosting o abbonamento del sito", "Resti sul piano gratuito; passi a quello a pagamento solo dopo la prima vendita."),
     ("Commissioni sui pagamenti online", "Incassi prima con bonifico o link di pagamento le cui commissioni sono dovute solo alla vendita."), ("Forma giuridica, assicurazione, contabilità", "Verifichi il regime più leggero del suo Paese e gli aiuti alla creazione prima di formalizzare."),
     ("Opzioni a pagamento nascoste degli strumenti gratuiti", "Legga i limiti del piano gratuito (marchio, esportazione, numero di pagine) prima di costruire."), ("Il suo tempo", "Fissi un budget di ore settimanali e si fermi se dopo 4 settimane non c'è alcun segnale d'acquisto.")],
    ["Segmenti di clientela", "Proposta di valore", "Canali", "Relazioni con i clienti", "Fonti di ricavo", "Risorse chiave", "Attività chiave", "Partner chiave", "Struttura dei costi"],
    ["Mi racconti l'ultima volta che ha avuto questo problema: cos'è successo?", "Come lo risolve oggi, con quali strumenti o persone?", "Qual è la parte più fastidiosa o costosa di questa soluzione?", "Ha già pagato per risolverlo? Quanto tempo o denaro ci dedica?", "Cosa la farebbe cambiare soluzione?", "Conosce qualcun altro con questo problema che accetterebbe di parlarne?"],
    ["H0-H4: una pagina con una frase di promessa e un pulsante d'azione (Carrd o Google Sites).", "H4-H8: un modulo gratuito (Google Forms / Typeform) per raccogliere e-mail e bisogno.", "H8-H16: 3 grafiche semplici (Canva) e un breve messaggio di aggancio.", "H16-H32: contatti 20 persone del suo target con un messaggio diretto e proponga 15 minuti di confronto.", "H32-H44: faccia 5 colloqui e annoti frasi esatte e obiezioni.", "H44-H48: conti gli impegni concreti (preiscrizioni, appuntamenti, prevendite) e decida: continuare, correggere o abbandonare."],
    dict(unfair_two="Ipotesi di vantaggio ingiusto (da validare con i clienti): la rara combinazione «{d1} + {d2}»{years} le permette di parlare a due mondi; la venda a una nicchia precisa e non come offerta generalista.",
         unfair_one="Ipotesi di vantaggio ingiusto (da validare con i clienti): la sua profondità in «{d1}»{years}, applicata a un problema preciso di una nicchia.",
         years=" ({n} anni di esperienza indicati nel suo CV)", uvp="Aiutiamo {seg} a {result} grazie a {solution}, senza {pain}.", ph="[⚠️ DA COMPLETARE: {x}]",
         phx=dict(seg="clienti target", result="risultato desiderato", solution="la sua soluzione", pain="la frustrazione attuale", price="prezzo", var="costo variabile", fixed="costi fissi mensili", domain="il suo ambito"),
         be_zero="Senza costi fissi, ogni vendita è già sopra il punto di pareggio.", be_line="Punto di pareggio: {n} vendita/e al mese per coprire {fixed} di costi fissi (margine unitario {m}).",
         goal_line="Per guadagnare in più {goal} al mese: {n} vendita/e al mese.", be_bad="Il prezzo deve superare il costo variabile per ottenere un margine.",
         be_ph="Inserisca prezzo, costo variabile e costi fissi per calcolare il suo punto di pareggio.", hours_line="Con {h} ore a settimana: circa {u} vendita/e da chiudere ogni settimana."))
L["ar"] = _lang(
    ["التقنية / المعلوماتية", "التسويق / الاتصال", "المالية / المحاسبة", "التعليم / التكوين", "الصحة / العافية", "الإبداع / التصميم / الصورة", "المبيعات / التطوير التجاري", "العمليات / اللوجستيك / المشاريع", "المطاعم / الفندقة / السياحة", "الإدارة / الموارد البشرية / القانون", "متعدد المهارات"],
    ["القيادة / إدارة الفرق", "التواصل / العلاقات", "الاستقلالية", "التنظيم / الدقة", "الإبداع", "التحليل / حل المشكلات"],
    ["المصداقية: دون مراجع علنية يتردد العملاء في أن يكونوا أول من يدفع.", "دورة بيع طويلة: قد تستغرق قرارات الشراء أسابيع.", "منافسة خفية: مستقلون ووكالات يقدّمون الشيء نفسه غالباً بسعر أقل.", "طلب غير مثبت: لم يدفع أحد بعد مقابل هذا.", "الوقت: أنت تبيع وقتك، ودخلك محدود إن لم تؤتمت العمل.", "الاعتماد على منصة: تغيير في القواعد أو الخوارزمية قد يدمّر جمهورك.", "التعقيد: صيانة أداة أو خدمة تتطلب جهداً أكبر مما خُطِّط."],
    [("استشارات / خدمة مميّزة", "بع خبرتك في {domain} في مهام قصيرة ومسعّرة للشركات الصغيرة، دون مخزون ودون أدوات مدفوعة.", "اعرض تشخيصاً مجانياً من 30 دقيقة على 5 شركات مستهدفة وسجّل كم منها يطلب مهمة مدفوعة."),
     ("منتج معرفي / دورة مصغّرة", "حوّل خبرتك في {domain} إلى دليل أو دورة مصغّرة للمبتدئين تُباع بعد تسجيل مسبق.", "انشر مخطط الدورة واجمع التسجيلات المسبقة بنموذج مجاني: ابحث عن التزامات حقيقية قبل الإنتاج."),
     ("أداة بلا برمجة / أتمتة", "ابنِ لمحترفي {domain} أداة صغيرة أو أتمتة بجداول ونماذج مجانية.", "اعرض نموذجاً أولياً على 5 مستخدمين واسأل: كم ستدفع لتحصل عليه غداً؟"),
     ("وكالة متخصصة / خدمة مُعبّأة", "قدّم خدمة في {domain} بنطاق ثابت (عرض واحد ومُخرَج واحد وأجل واحد) لشريحة متخصصة.", "تواصل مع 20 شركة من شريحتك بعرض في جملة واحدة وقِس نسبة الردود."),
     ("نشرة متخصصة / محتوى", "انشر كل أسبوع متابعة مفيدة في {domain} لبناء جمهور ثم حقّق الدخل عبر الخدمات أو الشراكات.", "أطلق العدد الأول مجاناً وقِس المشتركين وفتح الرسائل والردود خلال 14 يوماً."),
     ("تدريب فردي / إرشاد", "رافق من يريدون التقدم في {domain} عبر جلسات حسب الطلب.", "اعرض 3 جلسات تجريبية مقابل شهادة صادقة ورأي في السعر."),
     ("قوالب وأدوات جاهزة", "أنشئ قوالب في {domain} (جداول، مستندات، تصاميم) للبيع كتنزيل.", "امنح قالباً مجاناً مقابل بريد إلكتروني ثم اعرض النسخة الكاملة على من يستخدمه."),
     ("دليل / مجموعة منتقاة", "اجمع ورتّب موارد مفيدة في {domain} في دليل مجاني يُربح لاحقاً عبر الإبراز.", "انشر 20 مدخلاً في جدول مشترك وقِس الزيارات وطلبات الإضافة.")],
    [("اسم نطاق خاص", "استخدم النطاق الفرعي المجاني لأداتك (Carrd أو Google Sites…) أثناء الاختبار."), ("استضافة الموقع أو اشتراكه", "ابقَ على الخطة المجانية ولا تنتقل إلى المدفوعة إلا بعد أول عملية بيع."),
     ("رسوم الدفع عبر الإنترنت", "اقبض أولاً بتحويل بنكي أو رابط دفع لا تُستحق رسومه إلا عند البيع."), ("الشكل القانوني والتأمين والمحاسبة", "تحقق من أخف نظام في بلدك ومن مساعدات الإنشاء قبل التسجيل."),
     ("خيارات مدفوعة خفية في الأدوات المجانية", "اقرأ حدود الخطة المجانية (العلامة، التصدير، عدد الصفحات) قبل البناء."), ("وقتك", "حدّد ميزانية ساعات أسبوعية وتوقف إن لم تظهر إشارة شراء بعد 4 أسابيع.")],
    ["شرائح العملاء", "القيمة المقدَّمة", "القنوات", "علاقات العملاء", "مصادر الدخل", "الموارد الرئيسية", "الأنشطة الرئيسية", "الشركاء الرئيسيون", "هيكل التكاليف"],
    ["احكِ لي عن آخر مرة واجهت فيها هذه المشكلة: ماذا حدث؟", "كيف تحلها اليوم وبأي أدوات أو أشخاص؟", "ما أكثر ما يزعج أو يكلّف في هذا الحل؟", "هل دفعت يوماً لحلها؟ كم من الوقت أو المال تخصص لها؟", "ما الذي سيجعلك تغيّر الحل؟", "هل تعرف شخصاً آخر لديه المشكلة نفسها ويقبل الحديث عنها؟"],
    ["الساعة 0-4: صفحة بجملة وعد وزر إجراء (Carrd أو Google Sites).", "الساعة 4-8: نموذج مجاني (Google Forms / Typeform) لجمع البريد والحاجة.", "الساعة 8-16: 3 تصاميم بسيطة (Canva) ورسالة قصيرة جاذبة.", "الساعة 16-32: تواصل مع 20 شخصاً من فئتك برسالة مباشرة واقترح 15 دقيقة للحديث.", "الساعة 32-44: أجرِ 5 محادثات وسجّل الجمل الدقيقة والاعتراضات.", "الساعة 44-48: احسب الالتزامات الملموسة (تسجيلات مسبقة، مواعيد، طلبات مسبقة) وقرّر: المتابعة أو التعديل أو التوقف."],
    dict(unfair_two="فرضية ميزة غير عادلة (تحتاج إلى تحقق مع العملاء): التركيبة النادرة «{d1} + {d2}»{years} تتيح لك مخاطبة عالمين؛ بِعها لشريحة محددة لا كعرض عام.",
         unfair_one="فرضية ميزة غير عادلة (تحتاج إلى تحقق مع العملاء): عمقك في «{d1}»{years} مطبَّقاً على مشكلة دقيقة في شريحة محددة.",
         years=" ({n} سنوات خبرة مذكورة في سيرتك الذاتية)", uvp="نساعد {seg} على {result} بفضل {solution}، دون {pain}.", ph="[⚠️ يُستكمل: {x}]",
         phx=dict(seg="العملاء المستهدفين", result="النتيجة المرجوّة", solution="حلّك", pain="الإحباط الحالي", price="السعر", var="التكلفة المتغيرة", fixed="التكاليف الثابتة الشهرية", domain="مجالك"),
         be_zero="دون تكاليف ثابتة، كل عملية بيع تتجاوز نقطة التعادل أصلاً.", be_line="نقطة التعادل: {n} عملية بيع شهرياً لتغطية {fixed} من التكاليف الثابتة (هامش الوحدة {m}).",
         goal_line="لكسب {goal} إضافية شهرياً: {n} عملية بيع شهرياً.", be_bad="يجب أن يكون السعر أعلى من التكلفة المتغيرة لتحقيق هامش.",
         be_ph="أدخل السعر والتكلفة المتغيرة والتكاليف الثابتة لحساب نقطة التعادل.", hours_line="بمعدل {h} ساعة أسبوعياً: نحو {u} عملية بيع في الأسبوع."))


# ---------------------------------------------------------------------------------------------------------------------------------------
# logique
# ---------------------------------------------------------------------------------------------------------------------------------------
import os
import unicodedata

_PROMPT_FILE = os.path.join(os.path.dirname(__file__), "bootstrap_prompt.txt")
LANG_NAME = {"fr": "français", "en": "English", "de": "Deutsch", "es": "español", "it": "italiano", "ar": "العربية"}
_YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:ans|an|years|year|yrs|jahre|jahren|a[nñ]os|anni|سنة|سنوات|عاما|أعوام)\b", re.I)


def _fold(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c)).replace("ـ", "")


def _hit(text, kw):
    kw = _fold(kw).strip()
    if not kw:
        return False
    if len(kw) <= 5 and " " not in kw:
        return re.search(r"(?<!\w)" + re.escape(kw) + r"(?!\w)", text) is not None
    return kw in text


def _matches(text, table):
    out = {}
    for key, kws in table.items():
        found = [k for k in kws.split(",") if _hit(text, k)]
        if found:
            out[key] = found
    return out


def _num(v, name, hi=1e9):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        x = float(str(v).strip().replace(",", ".").replace(" ", ""))
    except ValueError:
        raise ValueError(f"{name}: nombre invalide")
    if not math.isfinite(x) or x < 0 or x > hi:
        raise ValueError(f"{name}: valeur hors limites")
    return x


def _f(x):
    return str(int(x)) if x == int(x) else f"{x:.2f}".rstrip("0").rstrip(".")


def _clip(s, n=MAX_FIELD):
    return re.sub(r"\s+", " ", str(s or "")).strip()[:n]


def _master(cv, passions, hours, lang, idea_name):
    try:
        with open(_PROMPT_FILE, encoding="utf-8") as fh:
            base = fh.read().strip()
    except OSError:
        base = ""
    parts = [base, "---", f"# Langue de réponse / Answer language : {LANG_NAME[lang]}", "# CV / parcours de l'utilisateur\n" + cv]
    if passions:
        parts.append("# Passions\n" + passions)
    if hours:
        parts.append(f"# Disponibilité\n{_f(hours)} h / semaine")
    if idea_name:
        parts.append("# Idée choisie\n" + idea_name + "\nAvance maintenant étape par étape (Étapes 1 à 4).")
    else:
        parts.append("Commence par l'Étape 0 : analyse mon CV et propose-moi 3 idées sur-mesure, chacune avec ses 3 raisons d'échec.")
    return "\n\n".join(p for p in parts if p)


def reply(p):
    lang = p.get("lang") or "fr"
    if lang not in LANGS:
        raise ValueError("lang invalide")
    cv = str(p.get("cv_text") or "").replace("\x00", "").strip()
    if len(cv) < 30:
        raise ValueError("cv_text trop court (30 caractères minimum)")
    cv = cv[:MAX_CV]
    passions, hours = _clip(p.get("passions")), _num(p.get("hours"), "hours", 168)
    price, var, fixed, goal = (_num(p.get(k), k) for k in ("price", "var_cost", "fixed", "goal"))
    idea = p.get("idea")
    if idea is not None and (isinstance(idea, bool) or idea not in (0, 1, 2)):
        raise ValueError("idea invalide")
    T = L[lang]
    lab = T["lab"]
    ph = lambda x: lab["ph"].format(x=x)

    text = _fold(cv + " " + passions)
    dom_hits = _matches(text, DOM_KW)
    ranked = sorted(dom_hits, key=lambda k: (-len(dom_hits[k]), DOMAINS.index(k)))[:3]
    soft_hits = _matches(text, SOFT_KW)
    ym = [int(m.group(1)) for m in _YEARS.finditer(cv)]
    years = max(ym) if ym and max(ym) <= 50 else None
    ysuf = lab["years"].format(n=years) if years else ""
    hard = []
    for k in ranked:
        for w in dom_hits[k]:
            if w not in hard:
                hard.append(w)
    if len(ranked) >= 2:
        unfair = lab["unfair_two"].format(d1=T["dom"][ranked[0]], d2=T["dom"][ranked[1]], years=ysuf)
    elif ranked:
        unfair = lab["unfair_one"].format(d1=T["dom"][ranked[0]], years=ysuf)
    else:
        unfair = lab["unfair_one"].format(d1=ph(lab["phx"]["domain"]), years=ysuf)
    skills = dict(domains=[dict(key=k, label=T["dom"][k], hits=len(dom_hits[k])) for k in ranked] or [dict(key="general", label=T["dom"]["general"], hits=0)],
                  hard=hard[:12], soft=[dict(key=k, label=T["soft"][k]) for k in SOFT if k in soft_hits], years=years)

    keys = []
    for d in ranked:
        keys += list(DOM_ARCH[d])
    for k in DEFAULT_ARCH + ARCH:
        keys.append(k)
    sel = []
    for k in keys:
        if k not in sel:
            sel.append(k)
        if len(sel) == 3:
            break
    dname = T["dom"][ranked[0]] if ranked else ph(lab["phx"]["domain"])
    ideas = []
    for i, k in enumerate(sel):
        a = T["arche"][k]
        ideas.append(dict(i=i, key=k, name=a["name"], desc=a["desc"].format(domain=dname), test=a["test"],
                          risks=[T["risk"][r] for r in ARCH_RISK[k]], tools=ARCH_TOOLS[k]))
    out = dict(lang=lang, skills=skills, unfair=unfair, ideas=ideas, chosen=idea, plan=None,
               hidden_costs=[dict(cost=c, alt=a) for c, a in T["cost"]],
               toolbox=[dict(cat=c, tools=t) for c, t in TOOLBOX])
    if idea is not None:
        ch = ideas[idea]
        px = lab["phx"]
        uvp = lab["uvp"].format(seg=ph(px["seg"]), result=ph(px["result"]), solution=ph(px["solution"]), pain=ph(px["pain"]))
        acq = ", ".join(ch["tools"])
        bmc = {"seg": ph(px["seg"]), "uvp": uvp, "chan": acq, "rev": (_f(price) if price is not None else ph(px["price"])),
               "cost": (f"{_f(fixed)} + {_f(var)}/u" if fixed is not None and var is not None else ph(px["fixed"]))}
        bmc = [dict(key=k, label=T["bmc"][k], value=bmc.get(k) or ph(T["bmc"][k])) for k in BK]
        fin = []
        if price is None or var is None or fixed is None:
            fin.append(lab["be_ph"])
        elif price - var <= 0:
            fin.append(lab["be_bad"])
        else:
            m = price - var
            n = max(1, math.ceil(fixed / m)) if fixed > 0 else 1
            fin.append(lab["be_zero"] if fixed == 0 else lab["be_line"].format(n=n, fixed=_f(fixed), m=_f(m)))
            tgt = n
            if goal:
                tgt = max(1, math.ceil((fixed + goal) / m))
                fin.append(lab["goal_line"].format(goal=_f(goal), n=tgt))
            if hours:
                fin.append(lab["hours_line"].format(h=_f(hours), u=max(1, math.ceil(tgt / 4.33))))
        out["plan"] = dict(idea=ch["name"], questions=T["qs"], uvp=uvp, bmc=bmc, mvp=T["mvp"], finance=fin, test=ch["test"])
    out["master_prompt"] = _master(cv, passions, hours, lang, out["plan"]["idea"] if out["plan"] else None)
    return out
