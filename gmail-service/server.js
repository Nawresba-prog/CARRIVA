// Service Gmail (Node.js) — isolé, secret inter-service.
//  - Envoi (scope gmail.send) ; DRY_RUN=true (défaut) : aucun mail réel n'est envoyé.
//  - Lecture SEULE de la boîte de réception (scope gmail.readonly), désactivée par défaut : GMAIL_READ=true pour l'activer.
//    Jamais de suppression, d'archivage ni de marquage « lu » ; aucune pièce jointe n'est lue. Sans jeton Gmail : boîte de démonstration.
const express = require("express");
const { google } = require("googleapis");
const { buildMime, b64url, parseMessage } = require("./lib");

const app = express();
app.use(express.json({ limit: "6mb" }));

const DRY_RUN = (process.env.DRY_RUN || "true") !== "false";
const GMAIL_READ = (process.env.GMAIL_READ || "false") === "true";
const INTERNAL_SECRET = process.env.INTERNAL_SECRET || "dev-internal-secret";
const HAS_TOKEN = () => !!process.env.GOOGLE_REFRESH_TOKEN;

function gmailClient() {
  const oauth2 = new google.auth.OAuth2(process.env.GOOGLE_CLIENT_ID, process.env.GOOGLE_CLIENT_SECRET, process.env.GOOGLE_REDIRECT_URI);
  oauth2.setCredentials({ refresh_token: process.env.GOOGLE_REFRESH_TOKEN });
  return google.gmail({ version: "v1", auth: oauth2 });
}
const guard = (req, res) => { if (req.get("x-internal-secret") !== INTERNAL_SECRET) { res.status(403).json({ error: "forbidden" }); return false; } return true; };

const DEMO = [
  { id: "demo1", thread_id: "demo1", from: "Claire Martin <claire.martin@client-exemple.test>", reply_to: "", to: "contact@votre-entreprise.test", subject: "Demande de devis - 20 postes de travail", date: "Mon, 20 Oct 2026 09:12:00 +0200", message_id: "<demo1@client-exemple.test>", references: "", auto: false, unread: true, snippet: "", body: "Bonjour,\n\nNous équipons de nouveaux bureaux et souhaiterions recevoir un devis pour 20 postes de travail, livraison avant la fin du mois. Pouvez-vous nous indiquer vos délais et conditions de paiement ?\n\nCordialement,\nClaire Martin" },
  { id: "demo2", thread_id: "demo2", from: "Karim B. <karim@fournisseur-exemple.test>", reply_to: "", to: "contact@votre-entreprise.test", subject: "URGENT : facture 2026-118 impayée", date: "Tue, 21 Oct 2026 08:40:00 +0200", message_id: "<demo2@fournisseur-exemple.test>", references: "", auto: false, unread: true, snippet: "", body: "Bonjour,\n\nSauf erreur de notre part, la facture 2026-118 reste impayée. Merci de procéder au règlement sous 8 jours.\n\nKarim" },
  { id: "demo3", thread_id: "demo3", from: "Sophie L. <sophie@exemple-client.test>", reply_to: "", to: "contact@votre-entreprise.test", subject: "Réclamation : commande jamais reçue", date: "Tue, 21 Oct 2026 14:05:00 +0200", message_id: "<demo3@exemple-client.test>", references: "", auto: false, unread: true, snippet: "", body: "Bonjour,\n\nJ'ai passé commande il y a trois semaines et je n'ai toujours rien reçu. Je suis très déçue, merci de me rembourser ou de m'envoyer le colis rapidement." },
  { id: "demo4", thread_id: "demo4", from: "Newsletter <newsletter@promo-exemple.test>", reply_to: "", to: "contact@votre-entreprise.test", subject: "Nos offres de la semaine", date: "Wed, 22 Oct 2026 07:00:00 +0200", message_id: "<demo4@promo-exemple.test>", references: "", auto: true, unread: true, snippet: "", body: "Découvrez nos offres. Se désabonner." },
  { id: "demo5", thread_id: "demo5", from: "Support <alerte@verif-compte-exemple.test>", reply_to: "", to: "contact@votre-entreprise.test", subject: "Vérifiez votre mot de passe immédiatement", date: "Wed, 22 Oct 2026 10:30:00 +0200", message_id: "<demo5@verif-compte-exemple.test>", references: "", auto: false, unread: true, snippet: "", body: "Votre compte sera suspendu. Cliquez ici et confirmez votre mot de passe dans les 24 h." },
];

app.get("/health", (_req, res) => res.json({ ok: true, dryRun: DRY_RUN }));

app.get("/status", (req, res) => {
  if (!guard(req, res)) return;
  res.json({ ok: true, dryRun: DRY_RUN, readEnabled: GMAIL_READ, connected: HAS_TOKEN(), demo: !HAS_TOKEN() });
});

// Lecture seule : derniers messages de la boîte de réception
app.get("/inbox", async (req, res) => {
  if (!guard(req, res)) return;
  const max = Math.min(Math.max(parseInt(req.query.max, 10) || 15, 1), 30);
  if (!HAS_TOKEN()) return res.json({ demo: true, messages: DEMO.slice(0, max) });
  if (!GMAIL_READ) return res.status(501).json({ error: "read_disabled" });
  const q = ["in:inbox", String(req.query.q || "").replace(/[^\w@.\-: ]/g, "").slice(0, 100)].filter(Boolean).join(" ");
  try {
    const gm = gmailClient();
    const list = await gm.users.messages.list({ userId: "me", q, maxResults: max });
    const ids = (list.data.messages || []).map((m) => m.id);
    const messages = [];
    for (const id of ids) {
      const m = await gm.users.messages.get({ userId: "me", id, format: "full" });
      messages.push(parseMessage(m.data));
    }
    res.json({ demo: false, messages });
  } catch (e) {
    console.error("gmail read error", e.message);
    res.status(502).json({ error: "gmail_failed" });
  }
});

// Un message (pour retrouver l'expéditeur côté serveur avant une réponse)
app.get("/message/:id", async (req, res) => {
  if (!guard(req, res)) return;
  const id = String(req.params.id || "");
  if (!HAS_TOKEN()) { const m = DEMO.find((x) => x.id === id); return m ? res.json(m) : res.status(404).json({ error: "not_found" }); }
  if (!GMAIL_READ) return res.status(501).json({ error: "read_disabled" });
  if (!/^[A-Za-z0-9_-]{6,64}$/.test(id)) return res.status(400).json({ error: "bad_id" });
  try {
    const m = await gmailClient().users.messages.get({ userId: "me", id, format: "full" });
    res.json(parseMessage(m.data));
  } catch (e) {
    console.error("gmail get error", e.message);
    res.status(502).json({ error: "gmail_failed" });
  }
});

app.post("/send", async (req, res) => {
  if (!guard(req, res)) return;
  const { to, subject, body, attachment, inReplyTo, references, threadId } = req.body || {};
  if (!to || !subject || !body || !/^[^@\s]+@[^@\s]+$/.test(to)) return res.status(400).json({ error: "invalid payload" });

  const raw = buildMime({ to, subject, body, attachment, inReplyTo, references });
  if (DRY_RUN) {
    console.log(`[DRY_RUN] mail to=${to} subject=${subject} bytes=${raw.length}`);
    return res.json({ dryRun: true, to });
  }
  try {
    const requestBody = { raw: b64url(raw) };
    if (threadId && /^[A-Za-z0-9_-]{6,64}$/.test(threadId)) requestBody.threadId = threadId;
    const r = await gmailClient().users.messages.send({ userId: "me", requestBody });
    res.json({ id: r.data.id, to });
  } catch (e) {
    console.error("gmail error", e.message);
    res.status(502).json({ error: "gmail_failed" });
  }
});

const port = process.env.PORT || 3001;
if (require.main === module) app.listen(port, () => console.log(`gmail-service on :${port} (dryRun=${DRY_RUN}, read=${GMAIL_READ})`));
module.exports = app;
