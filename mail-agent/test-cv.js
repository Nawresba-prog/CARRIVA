// Tests des modèles de CV : node test-cv.js (aucune dépendance)
const assert = require("assert"); const T = require("./cv-templates");
const p = { name: "Zoé Müller", job: "Comptable", skills: "Excel, Excel, SAP", education: "2015 | Master | école de commerce", experience: "2019 - 2022: Comptable | ACME" };
assert.strictEqual(T.TEMPLATES.length, 6); assert(!T.TEMPLATES.some((t) => /europass/i.test(t.id)));
for (const t of T.TEMPLATES) { const r = T.createPdf(t.id, p, "fr"); assert(r.pdf.slice(0, 5).toString() === "%PDF-" && r.pdf.slice(-6).toString().includes("%%EOF")); assert(r.pages >= 1); }
const cv = T.buildCv(p); assert.deepStrictEqual(cv.skills, ["Excel", "SAP"]); assert.strictEqual(cv.education[0].org, "ÉCOLE DE COMMERCE");
assert.strictEqual(cv.experience[0].period, "2019 - 2022"); assert.strictEqual(cv.experience[0].title, "Comptable");
// Arabe : sans police -> erreur explicite ; avec une police TrueType -> PDF valide
if (!T.arabicReady()) assert.throws(() => T.createPdf("modern", { name: "مرحبا" }), (e) => e.code === "ARABIC_FONT" || e.code === "ARABIC");
const dj = process.env.TEST_ARABIC_FONT || "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf";
if (T.arabicReady() || require("fs").existsSync(dj)) {
  if (!T.arabicReady()) T.loadArabicFiles(dj, null);
  for (const t of T.TEMPLATES) { const r = T.createPdf(t.id, { name: "سارة حداد", job: "محاسبة", skills: "إكسل, SAP" }, "ar"); assert(r.pdf.slice(0, 5).toString() === "%PDF-"); }
}
// Photo facultative : JPEG intégré (un faux JPEG est ignoré sans casser le PDF)
const jpg = "/tmp/cvt/face.jpg";
if (require("fs").existsSync(jpg)) {
  const uri = "data:image/jpeg;base64," + require("fs").readFileSync(jpg).toString("base64");
  for (const t of T.TEMPLATES) { const r = T.createPdf(t.id, { ...p, photo: uri }, "fr"); assert(r.pdf.includes(Buffer.from("/DCTDecode"))); }
}
assert.doesNotThrow(() => T.createPdf("modern", { ...p, photo: "data:image/jpeg;base64,AAAA" }, "fr"));
assert.throws(() => T.createPdf("modern", {}), (e) => e.code === "NAME");
assert.throws(() => T.createPdf("nope", p), (e) => e.code === "TEMPLATE");
assert(T.previews({}, "en").sample === true);
assert(!T.previews({ name: "<script>x</script>" }, "fr").previews.modern.svg.includes("<script>"));
console.log("OK : tests modèles de CV");
