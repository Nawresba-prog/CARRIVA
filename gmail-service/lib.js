// Fonctions pures du service Gmail (testables sans googleapis ni réseau).
const clean = (s) => String(s ?? "").replace(/[\r\n]+/g, " "); // anti header-injection
const b64 = (s) => Buffer.from(s).toString("base64");
const b64url = (s) => b64(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const wrap = (b64s) => b64s.replace(/(.{76})/g, "$1\r\n");
const MSGID = /^<[^<>\s@]+@[^<>\s@]+>$/;

// Réponse dans un fil : seuls des Message-ID bien formés sont acceptés (jamais de texte libre dans les en-têtes).
function threadHeaders({ inReplyTo, references }) {
  const out = [];
  if (inReplyTo && MSGID.test(inReplyTo.trim())) out.push(`In-Reply-To: ${inReplyTo.trim()}`);
  const refs = String(references || "").split(/\s+/).filter((r) => MSGID.test(r)).slice(-10);
  if (inReplyTo && MSGID.test(inReplyTo.trim()) && !refs.includes(inReplyTo.trim())) refs.push(inReplyTo.trim());
  if (refs.length) out.push(`References: ${refs.join(" ")}`);
  return out;
}

function buildMime({ to, subject, body, attachment, inReplyTo, references }) {
  const boundary = "career_" + Date.now();
  const parts = [
    `To: ${clean(to)}`,
    `Subject: =?UTF-8?B?${b64(clean(subject))}?=`,
    ...threadHeaders({ inReplyTo, references }),
    "MIME-Version: 1.0",
    `Content-Type: multipart/mixed; boundary="${boundary}"`,
    "",
    `--${boundary}`,
    'Content-Type: text/plain; charset="UTF-8"',
    "Content-Transfer-Encoding: base64",
    "",
    wrap(b64(body)),
  ];
  if (attachment && attachment.data_b64) {
    const fname = clean(attachment.filename || "CV.pdf").replace(/"/g, "");
    parts.push(
      `--${boundary}`,
      `Content-Type: ${clean(attachment.mime || "application/pdf")}; name="${fname}"`,
      `Content-Disposition: attachment; filename="${fname}"`,
      "Content-Transfer-Encoding: base64",
      "",
      wrap(attachment.data_b64)
    );
  }
  parts.push(`--${boundary}--`);
  return parts.join("\r\n");
}

// --- lecture : extraction du texte d'un message Gmail (format "full"), sans pièces jointes
const decode = (data) => Buffer.from(String(data || "").replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("utf8");
function htmlToText(h) {
  return String(h)
    .replace(/<(script|style)[\s\S]*?<\/\1>/gi, " ")
    .replace(/<br\s*\/?>|<\/(p|div|tr|li|h\d)>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/[ \t]+/g, " ").replace(/\n\s*\n+/g, "\n\n").trim();
}
function bodyOf(payload) {
  let plain = "", html = "";
  (function walk(p) {
    if (!p) return;
    const mt = (p.mimeType || "").toLowerCase();
    if (p.body && p.body.data && !p.filename) {
      if (mt === "text/plain" && !plain) plain = decode(p.body.data);
      else if (mt === "text/html" && !html) html = decode(p.body.data);
    }
    (p.parts || []).forEach(walk);
  })(payload);
  return plain.trim() || htmlToText(html);
}
const MAX_BODY = 6000;
function parseMessage(m) {
  const h = {};
  for (const x of (m.payload && m.payload.headers) || []) h[String(x.name).toLowerCase()] = x.value;
  const auto = !!(h["list-unsubscribe"] || /^(bulk|list|junk)$/i.test(h["precedence"] || "") || (h["auto-submitted"] && h["auto-submitted"] !== "no"));
  return {
    id: m.id, thread_id: m.threadId, from: h["from"] || "", reply_to: h["reply-to"] || "", to: h["to"] || "", subject: h["subject"] || "",
    date: h["date"] || "", message_id: h["message-id"] || "", references: h["references"] || "", auto,
    unread: (m.labelIds || []).includes("UNREAD"), snippet: m.snippet || "", body: bodyOf(m.payload).slice(0, MAX_BODY),
  };
}

module.exports = { clean, b64, b64url, buildMime, threadHeaders, parseMessage, htmlToText, bodyOf, MSGID };
