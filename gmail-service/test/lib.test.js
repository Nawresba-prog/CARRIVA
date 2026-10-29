const test = require("node:test");
const assert = require("node:assert");
const { buildMime, threadHeaders, parseMessage, htmlToText } = require("../lib");

test("threading headers accept only well-formed Message-IDs (no header injection)", () => {
  const h = threadHeaders({ inReplyTo: "<a@x.test>", references: "<r1@x.test> evil\r\nBcc: x@y.z <r2@x.test>" });
  assert.deepStrictEqual(h, ["In-Reply-To: <a@x.test>", "References: <r1@x.test> <r2@x.test> <a@x.test>"]);
  assert.deepStrictEqual(threadHeaders({ inReplyTo: "<a@x.test>\r\nBcc: z@z.z" }), []);
  assert.deepStrictEqual(threadHeaders({}), []);
});

test("buildMime keeps reply headers before MIME headers and strips CR/LF from To/Subject", () => {
  const raw = buildMime({ to: "a@b.test\r\nBcc: c@d.test", subject: "Re: x\r\nBcc: e@f.test", body: "héllo", inReplyTo: "<m1@b.test>", references: "<m0@b.test>" });
  const head = raw.split("\r\n\r\n")[0];
  assert.ok(!/\r\nBcc:/i.test(head), head);
  assert.match(head, /In-Reply-To: <m1@b\.test>/); assert.match(head, /References: <m0@b\.test> <m1@b\.test>/);
  assert.ok(head.indexOf("In-Reply-To") < head.indexOf("MIME-Version"));
});

test("parseMessage reads text/plain, falls back to html, flags automated mail, ignores attachments", () => {
  const enc = (s) => Buffer.from(s).toString("base64url");
  const m = parseMessage({ id: "abc123", threadId: "t1", labelIds: ["INBOX", "UNREAD"], snippet: "s", payload: { headers: [{ name: "From", value: "A <a@x.test>" }, { name: "Subject", value: "Hi" }, { name: "List-Unsubscribe", value: "<mailto:u@x.test>" }, { name: "Message-ID", value: "<id@x.test>" }],
    mimeType: "multipart/mixed", parts: [{ mimeType: "text/html", body: { data: enc("<p>Hello&nbsp;<b>you</b></p><script>x()</script>") } }, { mimeType: "application/pdf", filename: "f.pdf", body: { data: enc("SECRET") } }] } });
  assert.strictEqual(m.body, "Hello you"); assert.strictEqual(m.auto, true); assert.strictEqual(m.unread, true); assert.ok(!JSON.stringify(m).includes("SECRET"));
  const p = parseMessage({ id: "x", payload: { headers: [], mimeType: "text/plain", body: { data: enc("plain") } } });
  assert.strictEqual(p.body, "plain"); assert.strictEqual(p.auto, false);
  assert.strictEqual(parseMessage({ id: "y", payload: { headers: [], mimeType: "text/plain", body: { data: enc("z".repeat(9000)) } } }).body.length, 6000);
});

test("htmlToText strips tags and scripts", () => assert.deepStrictEqual(htmlToText("<style>a{}</style><div>A</div><div>B &amp; C</div>").split(/\s*\n\s*/).filter(Boolean), ["A", "B & C"]));
