(function () {
"use strict";
/**
 * CARRIVA — Modèles de CV (hors Europass) pour l'agent e-mail.
 * Aucun module externe : le PDF est produit par un mini-moteur interne (polices standard Helvetica/Times),
 * le même dessin sert à l'aperçu (SVG) et au fichier final (PDF) -> ce que vous voyez est ce que vous obtenez.
 * Règles : on ne reformule pas et on n'invente rien ; seules la mise en forme, le nettoyage du texte
 * et les noms d'écoles en majuscules sont appliqués.
 */
const zlib = (typeof require === "function") ? (() => { try { return require("zlib"); } catch (e) { return null; } })() : null;   // Node : PDF compressé ; navigateur : non compressé
const enc1 = (s) => { const u = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) u[i] = s.charCodeAt(i) & 255; return u; };
const cat = (arr) => { let n = 0; arr.forEach((a) => (n += a.length)); const o = new Uint8Array(n); let k = 0; arr.forEach((a) => { o.set(a, k); k += a.length; }); return o; };

const A4 = { w: 595.28, h: 841.89 };
const WIDTHS = {"H":[278,278,355,556,556,889,667,191,333,333,389,584,278,333,278,278,556,556,556,556,556,556,556,556,556,556,278,278,584,584,584,556,1015,667,667,722,722,667,611,778,722,278,500,667,556,833,722,778,667,778,722,667,611,722,667,944,667,667,611,278,278,278,469,556,333,556,556,500,556,556,278,556,556,222,222,500,222,833,556,556,556,556,333,500,278,556,500,722,500,500,500,334,260,334,584,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,278,333,556,556,556,556,260,556,333,737,370,556,584,333,737,333,400,584,333,333,333,556,537,278,333,333,365,556,834,834,834,611,667,667,667,667,667,667,1000,722,667,667,667,667,278,278,278,278,722,722,778,778,778,778,778,584,778,722,722,722,722,667,667,611,556,556,556,556,556,556,889,500,556,556,556,556,278,278,278,278,556,556,556,556,556,556,556,584,611,556,556,556,556,500,556,500],"HB":[278,333,474,556,556,889,722,238,333,333,389,584,278,333,278,278,556,556,556,556,556,556,556,556,556,556,333,333,584,584,584,611,975,722,722,722,722,667,611,778,722,278,556,722,611,833,722,778,667,778,722,667,611,722,667,944,667,667,611,333,278,333,584,556,333,556,611,556,611,556,333,611,611,278,278,556,278,889,611,611,611,611,389,556,333,611,556,778,556,556,500,389,280,389,584,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,278,333,556,556,556,556,280,556,333,737,370,556,584,333,737,333,400,584,333,333,333,611,556,278,333,333,365,556,834,834,834,611,722,722,722,722,722,722,1000,722,667,667,667,667,278,278,278,278,722,722,778,778,778,778,778,584,778,722,722,722,722,667,667,611,556,556,556,556,556,556,889,556,556,556,556,556,278,278,278,278,611,611,611,611,611,611,611,584,611,611,611,611,611,556,611,556],"HI":[278,278,355,556,556,889,667,191,333,333,389,584,278,333,278,278,556,556,556,556,556,556,556,556,556,556,278,278,584,584,584,556,1015,667,667,722,722,667,611,778,722,278,500,667,556,833,722,778,667,778,722,667,611,722,667,944,667,667,611,278,278,278,469,556,333,556,556,500,556,556,278,556,556,222,222,500,222,833,556,556,556,556,333,500,278,556,500,722,500,500,500,334,260,334,584,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,278,333,556,556,556,556,260,556,333,737,370,556,584,333,737,333,400,584,333,333,333,556,537,278,333,333,365,556,834,834,834,611,667,667,667,667,667,667,1000,722,667,667,667,667,278,278,278,278,722,722,778,778,778,778,778,584,778,722,722,722,722,667,667,611,556,556,556,556,556,556,889,500,556,556,556,556,278,278,278,278,556,556,556,556,556,556,556,584,611,556,556,556,556,500,556,500],"T":[250,333,408,500,500,833,778,180,333,333,500,564,250,333,250,278,500,500,500,500,500,500,500,500,500,500,278,278,564,564,564,444,921,722,667,667,722,611,556,722,722,333,389,722,611,889,722,722,556,722,667,556,611,722,722,944,722,722,611,333,278,333,469,500,333,444,500,444,500,444,333,500,500,278,278,500,278,778,500,500,500,500,333,389,278,500,500,722,500,500,444,480,200,480,541,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,250,333,500,500,500,500,200,500,333,760,276,500,564,333,760,333,400,564,300,300,333,500,453,250,333,300,310,500,750,750,750,444,722,722,722,722,722,722,889,667,611,611,611,611,333,333,333,333,722,722,722,722,722,722,722,564,722,722,722,722,722,722,556,500,444,444,444,444,444,444,667,444,444,444,444,444,278,278,278,278,500,500,500,500,500,500,500,564,500,500,500,500,500,500,500,500],"TB":[250,333,555,500,500,1000,833,278,333,333,500,570,250,333,250,278,500,500,500,500,500,500,500,500,500,500,333,333,570,570,570,500,930,722,667,722,722,667,611,778,778,389,500,778,667,944,722,778,611,778,722,556,667,722,722,1000,722,722,667,333,278,333,581,500,333,500,556,444,556,444,333,500,556,278,333,556,278,833,556,500,556,556,444,389,333,556,500,722,500,500,444,394,220,394,520,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,250,333,500,500,500,500,220,500,333,747,300,500,570,333,747,333,400,570,300,300,333,556,540,250,333,300,330,500,750,750,750,500,722,722,722,722,722,722,1000,722,667,667,667,667,389,389,389,389,722,722,778,778,778,778,778,570,778,722,722,722,722,722,611,556,500,500,500,500,500,500,722,444,444,444,444,444,278,278,278,278,500,556,500,500,500,500,500,570,500,556,556,556,556,500,556,500],"TI":[250,333,420,500,500,833,778,214,333,333,500,675,250,333,250,278,500,500,500,500,500,500,500,500,500,500,333,333,675,675,675,500,920,611,611,667,722,611,611,722,722,333,444,667,556,833,667,722,611,722,611,500,556,722,611,833,611,556,556,389,278,389,422,500,333,500,500,444,500,444,278,500,500,278,278,444,278,722,500,500,500,500,389,389,278,500,444,667,444,444,389,400,275,400,541,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,250,389,500,500,500,500,275,500,333,760,276,500,675,333,760,333,400,675,300,300,333,500,523,250,333,300,310,500,750,750,750,500,611,611,611,611,611,611,889,667,611,611,611,611,333,333,333,333,722,667,722,722,722,722,722,675,722,722,722,722,722,556,611,500,500,500,500,500,500,500,667,444,444,444,444,444,278,278,278,278,500,500,500,500,500,500,500,675,500,500,500,500,500,444,500,444]};
const FONTS = {
  H:  { pdf: "Helvetica",             css: "Helvetica,Arial,sans-serif",              wt: "normal", st: "normal" },
  HB: { pdf: "Helvetica-Bold",        css: "Helvetica,Arial,sans-serif",              wt: "bold",   st: "normal" },
  HI: { pdf: "Helvetica-Oblique",     css: "Helvetica,Arial,sans-serif",              wt: "normal", st: "italic" },
  T:  { pdf: "Times-Roman",           css: "'Times New Roman',Times,serif",           wt: "normal", st: "normal" },
  TB: { pdf: "Times-Bold",            css: "'Times New Roman',Times,serif",           wt: "bold",   st: "normal" },
  TI: { pdf: "Times-Italic",          css: "'Times New Roman',Times,serif",           wt: "normal", st: "italic" },
};
const FKEYS = Object.keys(FONTS);

/* ------------------------------ Texte / encodage WinAnsi ------------------------------ */
const CP1252 = { 0x20AC: 0x80, 0x201A: 0x82, 0x0192: 0x83, 0x201E: 0x84, 0x2026: 0x85, 0x2020: 0x86, 0x2021: 0x87, 0x02C6: 0x88, 0x2030: 0x89,
  0x0160: 0x8A, 0x2039: 0x8B, 0x0152: 0x8C, 0x017D: 0x8E, 0x2018: 0x91, 0x2019: 0x92, 0x201C: 0x93, 0x201D: 0x94, 0x2022: 0x95, 0x2013: 0x96,
  0x2014: 0x97, 0x02DC: 0x98, 0x2122: 0x99, 0x0161: 0x9A, 0x203A: 0x9B, 0x0153: 0x9C, 0x017E: 0x9E, 0x0178: 0x9F };
const byteOf = (ch) => {
  const c = ch.codePointAt(0);
  if (c >= 32 && c <= 126) return c;
  if (c >= 160 && c <= 255) return c;
  return CP1252[c] || 0;
};
/* ------------------------------ Arabe : polices, formes des lettres, bidi ------------------------------ */
const AR_ANY = /[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]/;
const AR_DIAC = /[ً-ٰٟۖ-ۭ]/g;
const AR_DIGITS = { "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9", "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9" };
// lettre -> [isolée, finale, initiale, médiane] (formes de présentation Unicode) ; null = n'existe pas
const J = {}, PRES_BASE = {};
"0621:FE80,,,|0622:FE81,FE82,,|0623:FE83,FE84,,|0624:FE85,FE86,,|0625:FE87,FE88,,|0626:FE89,FE8A,FE8B,FE8C|0627:FE8D,FE8E,,|0628:FE8F,FE90,FE91,FE92|0629:FE93,FE94,,|062A:FE95,FE96,FE97,FE98|062B:FE99,FE9A,FE9B,FE9C|062C:FE9D,FE9E,FE9F,FEA0|062D:FEA1,FEA2,FEA3,FEA4|062E:FEA5,FEA6,FEA7,FEA8|062F:FEA9,FEAA,,|0630:FEAB,FEAC,,|0631:FEAD,FEAE,,|0632:FEAF,FEB0,,|0633:FEB1,FEB2,FEB3,FEB4|0634:FEB5,FEB6,FEB7,FEB8|0635:FEB9,FEBA,FEBB,FEBC|0636:FEBD,FEBE,FEBF,FEC0|0637:FEC1,FEC2,FEC3,FEC4|0638:FEC5,FEC6,FEC7,FEC8|0639:FEC9,FECA,FECB,FECC|063A:FECD,FECE,FECF,FED0|0641:FED1,FED2,FED3,FED4|0642:FED5,FED6,FED7,FED8|0643:FED9,FEDA,FEDB,FEDC|0644:FEDD,FEDE,FEDF,FEE0|0645:FEE1,FEE2,FEE3,FEE4|0646:FEE5,FEE6,FEE7,FEE8|0647:FEE9,FEEA,FEEB,FEEC|0648:FEED,FEEE,,|0649:FEEF,FEF0,,|064A:FEF1,FEF2,FEF3,FEF4|067E:FB56,FB57,FB58,FB59|0686:FB7A,FB7B,FB7C,FB7D|0698:FB8A,FB8B,,|06A9:FB8E,FB8F,FB90,FB91|06AF:FB92,FB93,FB94,FB95|06CC:FBFC,FBFD,FBFE,FBFF|0640:0640,0640,0640,0640".split("|").forEach((e) => {
  const [c, f] = e.split(":"), code = parseInt(c, 16);
  J[code] = f.split(",").map((x) => (x ? parseInt(x, 16) : null));
  J[code].forEach((x) => { if (x) PRES_BASE[x] = code; });
});
const LIG = { 0x622: [0xFEF5, 0xFEF6], 0x623: [0xFEF7, 0xFEF8], 0x625: [0xFEF9, 0xFEFA], 0x627: [0xFEFB, 0xFEFC] };
[0xFEF5, 0xFEF6, 0xFEF7, 0xFEF8, 0xFEF9, 0xFEFA, 0xFEFB, 0xFEFC].forEach((x) => { PRES_BASE[x] = 0x644; });
const AR_PUNCT = new Set([0x60C, 0x61B, 0x61F]);
const arKeep = (c) => !!J[c] || AR_PUNCT.has(c);

function shapeAr(chars) {
  const out = [], cp = (c) => c.codePointAt(0);
  for (let i = 0; i < chars.length; i++) {
    const c = cp(chars[i]), f = J[c];
    if (!f) { out.push(chars[i]); continue; }
    const pj = i > 0 && J[cp(chars[i - 1])] && J[cp(chars[i - 1])][2] != null && f[1] != null;     // le précédent se lie à celui-ci
    const nc = i + 1 < chars.length ? cp(chars[i + 1]) : 0;
    if (c === 0x644 && LIG[nc]) { out.push(String.fromCodePoint(pj ? LIG[nc][1] : LIG[nc][0])); i++; continue; }   // lam + alef
    const nj = f[2] != null && J[nc] && J[nc][1] != null;                                          // celui-ci se lie au suivant
    out.push(String.fromCodePoint(f[pj && nj ? 3 : pj ? 1 : nj ? 2 : 0] || f[0]));
  }
  return out;
}
const MIRROR = { "(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{", "<": ">", ">": "<", "«": "»", "»": "«" };
const JOINERS = /[+@._\-\/:#%&'’]/;
const classOf = (ch) => (AR_ANY.test(ch) ? "R" : /[0-9A-Za-zÀ-ɏ]/.test(ch) ? "L" : "N");
const VIS = new Map();
/** Texte logique -> morceaux dans l'ordre d'affichage (gauche -> droite) : { a: true = police arabe, s }. */
function visualParts(str) {
  if (VIS.has(str)) return VIS.get(str);
  const chars = [...str], cls = chars.map(classOf);
  for (let i = 0; i < chars.length; i++)
    if (cls[i] === "N" && JOINERS.test(chars[i]) && ((i > 0 && cls[i - 1] === "L") || (i + 1 < chars.length && cls[i + 1] === "L"))) cls[i] = "L";
  for (let i = 0; i < chars.length; i++) {
    if (cls[i] !== "N") continue;
    let p = i - 1, n = i + 1;
    while (p >= 0 && cls[p] === "N") p--;
    while (n < chars.length && cls[n] === "N") n++;
    const pc = p >= 0 ? cls[p] : null, nc = n < chars.length ? cls[n] : null;
    cls[i] = pc && pc === nc ? pc : "R";
  }
  const runs = [];
  chars.forEach((ch, i) => { const r = runs[runs.length - 1]; if (r && r.c === cls[i]) r.t.push(ch); else runs.push({ c: cls[i], t: [ch] }); });
  runs.reverse();
  const flat = [];
  for (const r of runs) {
    if (r.c === "R") shapeAr(r.t).reverse().forEach((ch) => flat.push({ ch: MIRROR[ch] || ch, a: AR_ANY.test(ch) }));
    else r.t.forEach((ch) => flat.push({ ch, a: false }));
  }
  const parts = [];
  for (const x of flat) { const l = parts[parts.length - 1]; if (l && l.a === x.a) l.s += x.ch; else parts.push({ a: x.a, s: x.ch }); }
  VIS.set(str, parts);
  return parts;
}

/* --- lecture minimale d'une police TrueType (cmap, hmtx, en-têtes) --- */
function parseTtf(u8) {
  const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength), tag = (o) => String.fromCharCode(u8[o], u8[o + 1], u8[o + 2], u8[o + 3]);
  const ver = dv.getUint32(0);
  if (ver !== 0x00010000 && tag(0) !== "true") throw Object.assign(new Error("Police arabe non prise en charge : un fichier TrueType (.ttf) est nécessaire."), { code: "ARABIC_FONT" });
  const T = {}; for (let i = 0, n = dv.getUint16(4); i < n; i++) { const o = 12 + 16 * i; T[tag(o)] = { o: dv.getUint32(o + 8), l: dv.getUint32(o + 12) }; }
  if (!T.head || !T.hhea || !T.hmtx || !T.cmap || !T.glyf) throw Object.assign(new Error("Police arabe incomplète (tables manquantes)."), { code: "ARABIC_FONT" });
  const upem = dv.getUint16(T.head.o + 18), nH = dv.getUint16(T.hhea.o + 34);
  let sub = null;
  for (let i = 0, n = dv.getUint16(T.cmap.o + 2); i < n; i++) {
    const r = T.cmap.o + 4 + 8 * i, pl = dv.getUint16(r), en = dv.getUint16(r + 2), off = T.cmap.o + dv.getUint32(r + 4), fm = dv.getUint16(off);
    if ((pl === 3 && en === 10 && fm === 12) || (!sub || sub.fm !== 12) && ((pl === 3 && en === 1 && fm === 4) || (pl === 0 && fm === 4))) sub = { off, fm };
  }
  if (!sub) throw Object.assign(new Error("Police arabe sans table de caractères Unicode."), { code: "ARABIC_FONT" });
  const cache = new Map();
  const lookup = (c) => {
    const o = sub.off;
    if (sub.fm === 12) {
      for (let i = 0, n = dv.getUint32(o + 12), b = o + 16; i < n; i++, b += 12) {
        const s0 = dv.getUint32(b), e0 = dv.getUint32(b + 4);
        if (c >= s0 && c <= e0) return dv.getUint32(b + 8) + (c - s0);
      }
      return 0;
    }
    const sc = dv.getUint16(o + 6) / 2, endO = o + 14, startO = endO + 2 * sc + 2, deltaO = startO + 2 * sc, rangeO = deltaO + 2 * sc;
    for (let i = 0; i < sc; i++) {
      if (c <= dv.getUint16(endO + 2 * i)) {
        if (c < dv.getUint16(startO + 2 * i)) return 0;
        const ro = dv.getUint16(rangeO + 2 * i), dl = dv.getInt16(deltaO + 2 * i);
        if (!ro) return (c + dl) & 0xffff;
        const g = dv.getUint16(rangeO + 2 * i + ro + 2 * (c - dv.getUint16(startO + 2 * i)));
        return g ? (g + dl) & 0xffff : 0;
      }
    }
    return 0;
  };
  const gid = (c) => { if (cache.has(c)) return cache.get(c); let g = lookup(c); if (!g && PRES_BASE[c]) g = lookup(PRES_BASE[c]); cache.set(c, g); return g; };
  const adv = (g) => dv.getUint16(T.hmtx.o + 4 * Math.min(g, nH - 1));
  return { upem, gid, adv, asc: dv.getInt16(T.hhea.o + 4), desc: dv.getInt16(T.hhea.o + 6),
    bbox: [dv.getInt16(T.head.o + 36), dv.getInt16(T.head.o + 38), dv.getInt16(T.head.o + 40), dv.getInt16(T.head.o + 42)] };
}
const ARF = { reg: null, bold: null };
const arMsg = "Police arabe absente : lancez « python backend\\fonts\\fetch_fonts.py », puis redémarrez le serveur et rechargez la page (Ctrl+F5).";
const needArabic = () => { if (!ARF.reg) throw Object.assign(new Error(arMsg), { code: "ARABIC_FONT" }); };
const mkFont = (bytes, z) => ({ bytes, z: z || null, ttf: parseTtf(bytes) });
function setArabicFonts(o) {
  ARF.reg = mkFont(o.regular, o.regularZ);
  ARF.bold = o.bold ? mkFont(o.bold, o.boldZ) : null;
  VIS.clear();
}
const arabicReady = () => !!ARF.reg;
const arFont = (f) => (/B$/.test(f) && ARF.bold ? "B" : "R");
async function loadArabic(urlReg, urlBold) {                                // navigateur
  if (ARF.reg) return true;
  const get = async (u) => { const r = await fetch(u); if (!r.ok) throw new Error("police " + r.status); return new Uint8Array(await r.arrayBuffer()); };
  const zip = async (b) => { try { if (typeof CompressionStream === "function") return new Uint8Array(await new Response(new Blob([b]).stream().pipeThrough(new CompressionStream("deflate"))).arrayBuffer()); } catch (e) { /* non compressé */ } return null; };
  let reg; try { reg = await get(urlReg); } catch (e) { throw Object.assign(new Error(arMsg), { code: "ARABIC_FONT" }); }
  let bold = null; try { bold = await get(urlBold); } catch (e) { /* facultatif */ }
  setArabicFonts({ regular: reg, regularZ: await zip(reg), bold, boldZ: bold ? await zip(bold) : null });
  return true;
}
function loadArabicFiles(regPath, boldPath) {                               // Node
  const fs = require("fs");
  const rd = (p) => new Uint8Array(fs.readFileSync(p));
  setArabicFonts({ regular: rd(regPath), bold: boldPath && fs.existsSync(boldPath) ? rd(boldPath) : null });
  return true;
}
if (typeof require === "function" && typeof process !== "undefined") {   // Node : recherche automatique de Noto Sans Arabic
  try {
    const fs = require("fs"), path = require("path"), E = process.env;
    const dirs = [E.CV_FONT_DIR, path.join(__dirname, "fonts"), path.join(__dirname, "backend", "fonts"), path.join(__dirname, "..", "backend", "fonts")].filter(Boolean);
    for (const d of dirs) {
      const r = E.ARABIC_FONT_REGULAR || path.join(d, "NotoSansArabic-Regular.ttf"), b = E.ARABIC_FONT_BOLD || path.join(d, "NotoSansArabic-Bold.ttf");
      if (fs.existsSync(r)) { loadArabicFiles(r, b); break; }
    }
  } catch (e) { /* pas de police arabe : les modèles restent disponibles hors arabe */ }
}

/** Nettoie un texte : NFC, sans caractères de contrôle, espaces compactés ; caractères non gérés -> lettre de base ou « ? ». */
function clean(s, ctx) {
  s = String(s == null ? "" : s).normalize("NFC").replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, " ").replace(/[ \t ]+/g, " ").trim();
  s = s.replace(AR_DIAC, "").replace(/[٠-٩۰-۹]/g, (d) => AR_DIGITS[d]);
  let out = "";
  for (const ch of s) {
    if (ch === "\n") { out += ch; continue; }
    if (byteOf(ch)) { out += ch; continue; }
    const c = ch.codePointAt(0);
    if (AR_ANY.test(ch) && arKeep(c)) { out += ch; if (ctx) ctx.arabic = true; continue; }
    const base = ({ "Ł": "L", "ł": "l", "Đ": "D", "đ": "d", "ı": "i", "Ħ": "H", "ħ": "h" })[ch] || ch.normalize("NFD").replace(/[̀-ͯ]/g, "");
    if (base && base !== ch && [...base].every((b) => byteOf(b))) { out += base; continue; }
    out += "?"; if (ctx) ctx.unsupported.add(ch);
  }
  return out;
}
const latinW = (s, f, size) => { let w = 0; const t = WIDTHS[f]; for (const ch of String(s)) { const b = byteOf(ch); w += b ? t[b - 32] : 0; } return (w * size) / 1000; };
const arW = (s, f, size) => {
  needArabic(); const F = arFont(f) === "B" ? ARF.bold : ARF.reg; let w = 0;
  for (const ch of s) w += F.ttf.adv(F.ttf.gid(ch.codePointAt(0)));
  return (w * size) / F.ttf.upem;
};
const tw = (s, f, size, sp = 0) => {
  s = String(s);
  if (AR_ANY.test(s)) return visualParts(s).reduce((w, p) => w + (p.a ? arW(p.s, f, size) : latinW(p.s, f, size)), 0);
  return latinW(s, f, size) + sp * [...s].length;
};
function wrap(s, f, size, maxW, sp = 0) {
  const out = [];
  for (const para of String(s).split("\n")) {
    let line = "";
    for (let word of para.split(" ")) {
      if (!word) continue;
      while (tw(word, f, size, sp) > maxW) {                     // mot trop long : coupe
        let k = 1; while (k < word.length && tw(word.slice(0, k + 1), f, size, sp) <= maxW) k++;
        if (line) { out.push(line); line = ""; }
        out.push(word.slice(0, k)); word = word.slice(k);
      }
      const t = line ? line + " " + word : word;
      if (tw(t, f, size, sp) <= maxW) line = t; else { out.push(line); line = word; }
    }
    out.push(line);
  }
  return out.length ? out : [""];
}

/* ------------------------------------- Dessin ------------------------------------- */
class Doc {
  constructor() { this.pages = []; this.newPage(); }
  newPage() { this.ops = []; this.pages.push(this.ops); }
  rect(x, y, w, h, fill, o = {}) { this.ops.push({ t: "r", x, y, w, h, fill, r: o.r || 0, stroke: o.stroke, sw: o.sw || 0.8 }); }
  circle(cx, cy, r, fill) { this.ops.push({ t: "r", x: cx - r, y: cy - r, w: 2 * r, h: 2 * r, fill, r }); }
  image(x, y, w, h, o = {}) { this.ops.push({ t: "i", x, y, w, h, shape: o.shape || "rect", r: o.r || 0, ring: o.ring || null, rw: o.rw || 2 }); }
  line(x1, y1, x2, y2, color, sw = 0.8) { this.ops.push({ t: "l", x1, y1, x2, y2, color, sw }); }
  /** (x, y) = point de départ et ligne de base ; align center/right : x = centre / bord droit. */
  text(s, x, y, o = {}) {
    const font = o.font || "H", size = o.size || 10, ar = AR_ANY.test(s), sp = ar ? 0 : (o.spacing || 0);   // pas d'espacement entre lettres arabes (elles se lient)
    const w = tw(s, font, size, sp);
    if (o.align === "center") x -= w / 2; else if (o.align === "right") x -= w;
    this.ops.push({ t: "t", s: String(s), x, y, font, size, color: o.color || "#222222", sp, w, al: o.align || "left", ar, parts: ar ? visualParts(String(s)) : null });
    return w;
  }
}

/** Flux de texte dans une colonne, avec saut de page automatique (ou coupe silencieuse si clip). */
class Flow {
  constructor(doc, o) { Object.assign(this, { doc, x: o.x, w: o.w, top: o.top, bottom: o.bottom, deco: o.deco || null, clip: !!o.clip, y: o.top }); }
  brk(h) {
    if (this.y + h <= this.bottom) return true;
    if (this.clip) return false;
    this.doc.newPage(); if (this.deco) this.deco(this.doc); this.y = this.top; return true;
  }
  gap(h) { this.y += h; }
  rule(color, sw = 0.7, w = this.w, x = this.x) { if (this.brk(sw + 1)) this.doc.line(x, this.y, x + w, this.y, color, sw); }
  para(s, o = {}) {
    const font = o.font || "H", size = o.size || 10, lh = o.lh || 1.38, sp = o.spacing || 0, ind = o.indent || 0;
    const lines = wrap(s, font, size, this.w - ind, sp);
    for (let i = 0; i < lines.length; i++) {
      if (!this.brk(size * lh)) return false;
      const by = this.y + size * 1.0;
      if (i === 0 && o.bullet) this.doc.text(o.bullet, this.x + (o.bx || 0), by, { font, size, color: o.bcolor || o.color });
      const ax = o.align === "center" ? this.x + this.w / 2 : o.align === "right" ? this.x + this.w : this.x + ind;
      this.doc.text(lines[i], ax, by, { font, size, color: o.color, spacing: sp, align: o.align });
      this.y += size * lh;
    }
    if (o.after) this.y += o.after;
    return true;
  }
  chips(items, o = {}) {
    const size = o.size || 8.5, ph = o.ph || 6, h = o.h || size + 8, gx = o.gx || 5, gy = o.gy || 5;
    let x = this.x;
    for (const it of items) {
      const w = tw(it, o.font || "H", size) + 2 * ph;
      if (x + w > this.x + this.w && x > this.x) { x = this.x; this.y += h + gy; }
      if (!this.brk(h)) return;
      this.doc.rect(x, this.y, w, h, o.fill || "#E3EDFC", { r: h / 2, stroke: o.stroke });
      this.doc.text(it, x + ph, this.y + h / 2 + size * 0.35, { font: o.font || "H", size, color: o.color || "#1747A3" });
      x += w + gx;
    }
    this.y += h + (o.after || 0);
  }
  grid(items, cols, o = {}) {
    const cw = this.w / cols, size = o.size || 9.5, lh = o.lh || 1.5;
    for (let i = 0; i < items.length; i += cols) {
      if (!this.brk(size * lh)) return;
      for (let c = 0; c < cols && i + c < items.length; c++) {
        const x = this.x + c * cw, by = this.y + size;
        if (o.bullet) this.doc.text(o.bullet, x, by, { font: o.font || "H", size, color: o.bcolor || o.color });
        const line = wrap(items[i + c], o.font || "H", size, cw - (o.bullet ? 12 : 4))[0];
        this.doc.text(line, x + (o.bullet ? 10 : 0), by, { font: o.font || "H", size, color: o.color });
      }
      this.y += size * lh;
    }
  }
}

/* ---------------------------- Mise en forme d'une expérience ---------------------------- */
const splitDetail = (d) => String(d || "").split(/\s*(?:;|\n|•)\s*/).map((x) => x.trim()).filter(Boolean);
function entry(f, e, st) {
  const per = e.period || "";
  let x0 = f.x, w0 = f.w;
  const colW = st.period === "col" ? st.pcw : 0;
  if (colW) { f.x += colW; f.w -= colW; }
  const pw = st.period === "right" && per ? tw(per, st.pf || "HI", st.os) + 10 : 0;
  const tl = wrap(e.title, st.tf, st.ts, f.w - pw);
  const sub = [e.org, st.period === "below" ? per : ""].filter(Boolean).join("  ·  ");
  f.brk(tl.length * st.ts * 1.32 + (sub ? st.os * 1.4 : 0) + st.ds * 1.4);
  if (colW && per) f.doc.text(per, x0, f.y + st.ts, { font: st.pf || "H", size: st.os, color: st.pc || "#667085" });
  tl.forEach((ln, i) => {
    f.doc.text(ln, f.x, f.y + st.ts, { font: st.tf, size: st.ts, color: st.tc });
    if (i === 0 && pw) f.doc.text(per, f.x + f.w, f.y + st.ts, { font: st.pf || "HI", size: st.os, color: st.pc || "#667085", align: "right" });
    f.y += st.ts * 1.32;
  });
  if (sub) f.para(sub, { font: st.of, size: st.os, color: st.oc, lh: 1.4 });
  const items = splitDetail(e.detail);
  if (items.length > 1) items.forEach((it) => f.para(it, { font: st.df, size: st.ds, color: st.dc, bullet: "•", bcolor: st.bc || st.tc, indent: 10, lh: 1.36 }));
  else if (items.length) f.para(items[0], { font: st.df, size: st.ds, color: st.dc, lh: 1.4 });
  f.gap(st.after == null ? 8 : st.after);
  f.x = x0; f.w = w0;
}

/* ------------------------------------- Données ------------------------------------- */
const LABELS = {
  fr: { contact: "Contact", profile: "Profil", exp: "Expérience professionnelle", edu: "Formation", skills: "Compétences", lang: "Langues", links: "Liens" },
  en: { contact: "Contact", profile: "Profile", exp: "Work experience", edu: "Education", skills: "Skills", lang: "Languages", links: "Links" },
  de: { contact: "Kontakt", profile: "Profil", exp: "Berufserfahrung", edu: "Ausbildung", skills: "Kenntnisse", lang: "Sprachen", links: "Links" },
  es: { contact: "Contacto", profile: "Perfil", exp: "Experiencia profesional", edu: "Formación", skills: "Competencias", lang: "Idiomas", links: "Enlaces" },
  it: { contact: "Contatti", profile: "Profilo", exp: "Esperienza professionale", edu: "Formazione", skills: "Competenze", lang: "Lingue", links: "Link" },
  ar: { contact: "الاتصال", profile: "الملف الشخصي", exp: "الخبرة المهنية", edu: "التعليم والتكوين", skills: "المهارات", lang: "اللغات", links: "روابط" },
};
const CV_LANGS = Object.keys(LABELS);
const PERIOD_START = /^((?:\d{1,2}[\/.]\d{4}|\d{4})\s*[-–—]\s*(?:\d{1,2}[\/.]\d{4}|\d{4}|[\p{L}.]+)|\d{1,2}[\/.]\d{4}|\d{4})\s*[:\-–—]?\s+(.*)$/u;
const PERIOD_LIKE = /\d{4}|pr[ée]sent|actuel|current|today|heute|oggi|hoy|ahora|aujourd|الآن|حاليا/i;

function parseEntries(text, ctx, isEdu) {
  const out = [];
  for (const raw of String(text || "").split(/\r?\n/).slice(0, 12)) {
    const line = clean(raw, ctx); if (!line) continue;
    let parts = line.split("|").map((x) => x.trim());
    let period = "";
    if (parts.length > 1 && parts[0].length <= 28 && !/:\s/.test(parts[0]) && parts[0].split(/\s+/).length <= 5 && PERIOD_LIKE.test(parts[0])) period = parts.shift();
    else { const m = parts[0].match(PERIOD_START); if (m) { period = m[1]; parts[0] = m[2]; } }
    let [title = "", org = "", ...rest] = parts;
    if (!title) { title = org; org = ""; }
    if (!title) continue;
    if (isEdu && org) org = org.toLocaleUpperCase("fr");           // noms d'écoles en majuscules (comme dans le CV Europass)
    out.push({ period: period.slice(0, 40), title: title.slice(0, 160), org: org.slice(0, 160), detail: rest.join("; ").slice(0, 700) });
  }
  return out;
}
const splitList = (s, ctx, max) => [...new Set(String(s || "").split(/[,;\n•·]+/).map((x) => clean(x, ctx)).filter(Boolean))].map((x) => x.slice(0, 60)).slice(0, max);

/** Profil du formulaire -> structure de CV (texte nettoyé, rien d'ajouté). */
/** Photo facultative : JPEG en data-URI (le navigateur la convertit et la recadre avant). Renvoie null si absente ou invalide. */
function parsePhoto(src, ctx) {
  if (!src) return null;
  try {
    const m = /^data:image\/jpe?g;base64,([A-Za-z0-9+\/=\s]+)$/.exec(String(src));
    if (!m) throw 0;
    const b64 = m[1].replace(/\s/g, ""), bin = typeof atob === "function" ? atob(b64) : Buffer.from(b64, "base64").toString("latin1");
    if (bin.length < 200 || bin.length > 900000) throw 0;
    const u = enc1(bin);
    if (u[0] !== 0xFF || u[1] !== 0xD8) throw 0;
    let i = 2, w = 0, h = 0, nc = 0;
    while (i + 9 < u.length) {
      if (u[i] !== 0xFF) { i++; continue; }
      const mk = u[i + 1];
      if (mk === 0xFF) { i++; continue; }
      if (mk === 0xD8 || mk === 0x01 || (mk >= 0xD0 && mk <= 0xD7)) { i += 2; continue; }
      const len = (u[i + 2] << 8) | u[i + 3];
      if (mk >= 0xC0 && mk <= 0xCF && mk !== 0xC4 && mk !== 0xC8 && mk !== 0xCC) { h = (u[i + 5] << 8) | u[i + 6]; w = (u[i + 7] << 8) | u[i + 8]; nc = u[i + 9]; break; }
      i += 2 + len;
    }
    if (!w || !h || (nc !== 1 && nc !== 3)) throw 0;
    return { bytes: u, w, h, nc, uri: "data:image/jpeg;base64," + b64 };
  } catch (e) { if (ctx) ctx.photoBad = true; return null; }
}

function buildCv(p = {}, ctx = { unsupported: new Set() }) {
  const links = String(p.links || "").split(/[\s,;]+/).map((x) => clean(x, ctx).replace(/^https?:\/\/(www\.)?/i, "").replace(/\/$/, "")).filter(Boolean).slice(0, 4);
  return {
    name: clean(p.name, ctx).slice(0, 80), job: clean(p.job, ctx).slice(0, 100), email: clean(p.email, ctx).slice(0, 100), phone: clean(p.phone, ctx).slice(0, 40),
    place: [clean(p.city, ctx), clean(p.country, ctx)].filter(Boolean).join(", ").slice(0, 80), links,
    summary: clean(p.summary, ctx).replace(/\n+/g, " ").slice(0, 900),
    skills: splitList(p.skills, ctx, 24), languages: splitList(p.languages, ctx, 8),
    experience: parseEntries(p.experience, ctx, false), education: parseEntries(p.education, ctx, true),
    photo: parsePhoto(p.photo, ctx),
  };
}

const SAMPLE = {
  ar: { name: "الاسم الكامل", job: "المسمى الوظيفي المطلوب", email: "name@example.com", phone: "+00 0 00 00 00 00", city: "المدينة", country: "البلد", links: "linkedin.com/in/your-profile",
    summary: "هنا يظهر ملخصك المهني: جملتان أو ثلاث عن مسارك ونقاط قوتك والوظيفة التي تبحث عنها.",
    skills: "مهارة 1, مهارة 2, مهارة 3, مهارة 4, مهارة 5, مهارة 6", languages: "العربية (اللغة الأم), الفرنسية (B2)",
    experience: "2022 – 2025 | المسمى الوظيفي | الشركة، المدينة | المهمة الرئيسية ; النتيجة المحققة ; الأداة المستخدمة\n2019 – 2022 | المسمى الوظيفي السابق | شركة أخرى، المدينة | المهمة الرئيسية ; النتيجة المحققة",
    education: "2016 – 2019 | الشهادة المحصلة | اسم المؤسسة، المدينة" },
  fr: { name: "Prénom Nom", job: "Intitulé du poste visé", email: "prenom.nom@exemple.com", phone: "+00 0 00 00 00 00", city: "Ville", country: "Pays", links: "linkedin.com/in/votre-profil",
    summary: "Ici apparaîtra votre résumé : deux ou trois phrases sur votre parcours, vos points forts et le poste que vous recherchez.",
    skills: "Compétence 1, Compétence 2, Compétence 3, Compétence 4, Compétence 5, Compétence 6", languages: "Français (langue maternelle), Anglais (B2)",
    experience: "2022 – 2025 | Intitulé du poste | Entreprise, Ville | Mission principale ; résultat obtenu ; outil utilisé\n2019 – 2022 | Intitulé du poste précédent | Autre entreprise, Ville | Mission principale ; résultat obtenu",
    education: "2016 – 2019 | Diplôme obtenu | Nom de l'école, Ville" },
  en: { name: "First Last", job: "Target job title", email: "first.last@example.com", phone: "+00 0 00 00 00 00", city: "City", country: "Country", links: "linkedin.com/in/your-profile",
    summary: "Your summary will appear here: two or three sentences about your background, your strengths and the role you are looking for.",
    skills: "Skill 1, Skill 2, Skill 3, Skill 4, Skill 5, Skill 6", languages: "English (native), French (B2)",
    experience: "2022 – 2025 | Job title | Company, City | Main task ; result achieved ; tool used\n2019 – 2022 | Previous job title | Other company, City | Main task ; result achieved",
    education: "2016 – 2019 | Degree obtained | School name, City" },
};

/* ------------------------------------- Modèles ------------------------------------- */
const contactList = (cv) => [cv.email, cv.phone, cv.place, ...cv.links].filter(Boolean);

function tModern(doc, cv, L) {
  const ACC = "#1F5FD6", DK = "#0F2A4F", SW = 188;
  const deco = (d) => d.rect(0, 0, SW, A4.h, DK);
  deco(doc);
  if (cv.photo) doc.image(SW / 2 - 50, 40, 100, 100, { shape: "circle", ring: "#5CB4FF", rw: 3 });
  const sb = new Flow(doc, { x: 22, w: SW - 42, top: cv.photo ? 148 : 46, bottom: A4.h - 30, clip: true });
  const sh = (t) => { sb.gap(10); sb.para(t.toUpperCase(), { font: "HB", size: 9.5, color: "#8FC2FF", spacing: 1.2, after: 2 }); sb.rule("#35527F", 0.6); sb.gap(6); };
  if (contactList(cv).length) { sh(L.contact); contactList(cv).forEach((c) => sb.para(c, { size: 8.8, color: "#E6EEFA", lh: 1.35, after: 4 })); }
  if (cv.skills.length) { sh(L.skills); cv.skills.forEach((s) => sb.para(s, { size: 9, color: "#FFFFFF", bullet: "•", bcolor: "#5CB4FF", indent: 10, lh: 1.35, after: 2 })); }
  if (cv.languages.length) { sh(L.lang); cv.languages.forEach((s) => sb.para(s, { size: 9, color: "#FFFFFF", lh: 1.35, after: 3 })); }
  const m = new Flow(doc, { x: SW + 30, w: A4.w - SW - 62, top: 48, bottom: A4.h - 40, deco });
  m.para(cv.name, { font: "HB", size: 27, color: DK, lh: 1.1 });
  if (cv.job) m.para(cv.job, { font: "H", size: 13, color: ACC, lh: 1.3, after: 4 });
  m.gap(2); m.rule(ACC, 2.2, 44); m.gap(14);
  const head = (t) => { m.brk(46); m.para(t.toUpperCase(), { font: "HB", size: 10.5, color: ACC, spacing: 1.3, after: 2 }); m.rule("#D5DBE4", 0.7); m.gap(7); };
  if (cv.summary) { head(L.profile); m.para(cv.summary, { size: 9.8, color: "#2B3545", lh: 1.45, after: 12 }); }
  const st = { period: "right", tf: "HB", ts: 10.8, tc: DK, of: "H", os: 9.3, oc: "#5B6775", df: "H", ds: 9.4, dc: "#2B3545", pf: "HI", pc: "#5B6775", bc: ACC };
  if (cv.experience.length) { head(L.exp); cv.experience.forEach((e) => entry(m, e, st)); m.gap(4); }
  if (cv.education.length) { head(L.edu); cv.education.forEach((e) => entry(m, e, st)); }
}

function tClassic(doc, cv, L) {
  const INK = "#1B1B1B", GR = "#555555", AC = "#7A1F2B";
  const f = new Flow(doc, { x: 58, w: A4.w - 116, top: 52, bottom: A4.h - 50 });
  const FX = f.x, FW = f.w;
  if (cv.photo) { doc.image(A4.w - 58 - 78, 46, 78, 96, { shape: "rect", ring: AC, rw: 1.2 }); f.x = FX + 90; f.w = FW - 180; }   // en-tête resserré, centré autour de la page
  f.para(cv.name, { font: "TB", size: 26, color: INK, align: "center", lh: 1.15 });
  if (cv.job) f.para(cv.job, { font: "TI", size: 13, color: AC, align: "center", lh: 1.4, after: 2 });
  const c = contactList(cv); if (c.length) f.para(c.join("   ·   "), { font: "T", size: 9.5, color: GR, align: "center", lh: 1.4 });
  f.x = FX; f.w = FW; if (cv.photo) f.y = Math.max(f.y, 150);
  f.gap(6); f.rule(INK, 1.4); f.gap(2); f.rule(INK, 0.4); f.gap(12);
  const head = (t) => { f.brk(44); f.para(t.toUpperCase(), { font: "TB", size: 11.5, color: INK, spacing: 1.4, after: 1 }); f.rule(GR, 0.5); f.gap(7); };
  if (cv.summary) { head(L.profile); f.para(cv.summary, { font: "T", size: 10.5, color: "#262626", lh: 1.45, after: 10 }); }
  const st = { period: "right", tf: "TB", ts: 11.2, tc: INK, of: "TI", os: 10, oc: GR, df: "T", ds: 10.2, dc: "#262626", pf: "TI", pc: GR, bc: AC };
  if (cv.experience.length) { head(L.exp); cv.experience.forEach((e) => entry(f, e, st)); f.gap(3); }
  if (cv.education.length) { head(L.edu); cv.education.forEach((e) => entry(f, e, st)); f.gap(3); }
  if (cv.skills.length) { head(L.skills); f.para(cv.skills.join("  ·  "), { font: "T", size: 10.3, color: "#262626", lh: 1.5, after: 8 }); }
  if (cv.languages.length) { head(L.lang); f.para(cv.languages.join("  ·  "), { font: "T", size: 10.3, color: "#262626", lh: 1.5 }); }
}

function tMinimal(doc, cv, L) {
  const INK = "#111111", GR = "#8A8F98", LX = 58, CX = 176;
  const f = new Flow(doc, { x: CX, w: A4.w - CX - 58, top: 64, bottom: A4.h - 56 });
  const HW = cv.photo ? A4.w - 2 * LX - 92 : A4.w - 2 * LX;
  if (cv.photo) doc.image(A4.w - 58 - 72, 60, 72, 72, { shape: "circle" });
  const nameLines = wrap(cv.name, "H", 31, HW);
  nameLines.forEach((ln) => { doc.text(ln, LX, f.y + 31, { font: "H", size: 31, color: INK }); f.y += 36; });
  if (cv.job) { doc.text(cv.job, LX, f.y + 12, { font: "H", size: 12.5, color: GR }); f.y += 20; }
  const c = contactList(cv); if (c.length) wrap(c.join("   /   "), "H", 8.8, HW).forEach((ln) => { doc.text(ln, LX, f.y + 10, { font: "H", size: 8.8, color: GR }); f.y += 13; });
  f.y += 22; if (cv.photo) f.y = Math.max(f.y, 150);
  const sec = (t, draw) => {
    f.brk(60);
    wrap(t.toUpperCase(), "HB", 7.8, CX - LX - 14, 1.4).forEach((ln, i) => doc.text(ln, LX, f.y + 9 + i * 11, { font: "HB", size: 7.8, color: GR, spacing: 1.4 }));
    draw(); f.gap(14);
  };
  if (cv.summary) sec(L.profile, () => f.para(cv.summary, { size: 9.8, color: "#2A2A2A", lh: 1.55 }));
  const st = { period: "below", tf: "HB", ts: 10.3, tc: INK, of: "H", os: 9, oc: GR, df: "H", ds: 9.3, dc: "#2A2A2A", pc: GR, bc: GR, after: 9 };
  if (cv.experience.length) sec(L.exp, () => cv.experience.forEach((e) => entry(f, e, st)));
  if (cv.education.length) sec(L.edu, () => cv.education.forEach((e) => entry(f, e, st)));
  if (cv.skills.length) sec(L.skills, () => f.para(cv.skills.join("   /   "), { size: 9.6, color: "#2A2A2A", lh: 1.7 }));
  if (cv.languages.length) sec(L.lang, () => f.para(cv.languages.join("   /   "), { size: 9.6, color: "#2A2A2A", lh: 1.7 }));
}

function tCreative(doc, cv, L) {
  const ACC = "#E4572E", NAVY = "#14213D", PANEL = "#F3F4F8", PX = 392;
  const deco = (d) => d.rect(PX - 14, 150, A4.w - PX + 14, A4.h - 150, PANEL);
  doc.rect(0, 0, A4.w, 150, ACC);
  doc.circle(520, 28, 92, "#EE7A58"); doc.circle(560, 120, 54, "#F29A7F");
  const nl = wrap(cv.name, "HB", 30, 380); let y = 62;
  nl.slice(0, 2).forEach((ln) => { doc.text(ln, 40, y, { font: "HB", size: 30, color: "#FFFFFF" }); y += 34; });
  if (cv.job) doc.text(wrap(cv.job, "H", 13.5, 400)[0], 40, y + 4, { font: "H", size: 13.5, color: "#FFE9E1", spacing: 0.6 });
  if (cv.photo) doc.image(A4.w - 40 - 104, 23, 104, 104, { shape: "circle", ring: "#FFFFFF", rw: 4 });
  deco(doc);
  const side = new Flow(doc, { x: PX, w: A4.w - PX - 26, top: 172, bottom: A4.h - 30, clip: true });
  const sh = (t) => { side.gap(6); side.para(t.toUpperCase(), { font: "HB", size: 9.5, color: ACC, spacing: 1.2, after: 5 }); };
  if (contactList(cv).length) { sh(L.contact); contactList(cv).forEach((c) => side.para(c, { size: 8.7, color: "#2B3345", lh: 1.35, after: 4 })); side.gap(6); }
  if (cv.skills.length) { sh(L.skills); side.chips(cv.skills, { size: 8.2, ph: 6, h: 16, fill: "#FFFFFF", stroke: "#DADDE8", color: NAVY, after: 8 }); }
  if (cv.languages.length) { sh(L.lang); cv.languages.forEach((l) => side.para(l, { size: 9, color: "#2B3345", lh: 1.35, after: 3 })); }
  const m = new Flow(doc, { x: 40, w: PX - 40 - 26, top: 176, bottom: A4.h - 44, deco });
  const head = (t) => { m.brk(44); doc.rect(m.x, m.y + 2, 9, 9, ACC, { r: 2 }); doc.text(t.toUpperCase(), m.x + 16, m.y + 10.5, { font: "HB", size: 11, color: NAVY, spacing: 1.1 }); m.y += 24; };
  if (cv.summary) { head(L.profile); m.para(cv.summary, { size: 9.6, color: "#2B3345", lh: 1.5, after: 14 }); }
  const st = { period: "below", tf: "HB", ts: 10.8, tc: NAVY, of: "HB", os: 8.8, oc: ACC, df: "H", ds: 9.2, dc: "#2B3345", pc: ACC, bc: ACC, after: 10 };
  if (cv.experience.length) { head(L.exp); cv.experience.forEach((e) => entry(m, e, st)); m.gap(4); }
  if (cv.education.length) { head(L.edu); cv.education.forEach((e) => entry(m, e, st)); }
}

function tExecutive(doc, cv, L) {
  const NAVY = "#0B1F3A", GOLD = "#B8903A", INK = "#1F2937", GR = "#6B7280";
  doc.rect(0, 0, A4.w, 108, NAVY);
  const nl = wrap(cv.name, "TB", 27, cv.photo ? 390 : A4.w - 100); let y = 52;
  if (cv.photo) doc.image(A4.w - 50 - 72, 11, 72, 86, { shape: "rect", ring: GOLD, rw: 2 });
  nl.slice(0, 2).forEach((ln) => { doc.text(ln, 50, y, { font: "TB", size: 27, color: "#FFFFFF" }); y += 30; });
  if (cv.job) doc.text(cv.job.toUpperCase(), 50, y + 2, { font: "HB", size: 9.5, color: "#E2C275", spacing: 2 });
  doc.rect(0, 108, A4.w, 3, GOLD);
  const c = contactList(cv);
  doc.rect(0, 111, A4.w, 26, "#F4F1E8");
  if (c.length) doc.text(c.join("     |     "), A4.w / 2, 128, { font: "H", size: 8.8, color: INK, align: "center" });
  const f = new Flow(doc, { x: 50, w: A4.w - 100, top: 160, bottom: A4.h - 46 });
  const head = (t) => { f.brk(50); f.para(t.toUpperCase(), { font: "TB", size: 12.5, color: NAVY, spacing: 1.4, after: 2 }); f.rule(GOLD, 1.8, 38); f.gap(9); };
  if (cv.summary) { head(L.profile); f.para(cv.summary, { font: "TI", size: 10.6, color: INK, lh: 1.5, after: 14 }); }
  const st = { period: "col", pcw: 98, pf: "HB", tf: "HB", ts: 10.6, tc: NAVY, of: "TI", os: 9.6, oc: GR, df: "H", ds: 9.3, dc: INK, pc: GOLD, bc: GOLD, after: 10 };
  if (cv.experience.length) { head(L.exp); cv.experience.forEach((e) => entry(f, e, st)); f.gap(4); }
  if (cv.education.length) { head(L.edu); cv.education.forEach((e) => entry(f, e, st)); f.gap(4); }
  if (cv.skills.length) { head(L.skills); f.grid(cv.skills, 3, { size: 9.5, color: INK, bullet: "•", bcolor: GOLD, lh: 1.6 }); f.gap(10); }
  if (cv.languages.length) { head(L.lang); f.para(cv.languages.join("     •     "), { size: 9.5, color: INK, lh: 1.5 }); }
}

function tCompact(doc, cv, L) {
  const ACC = "#0B7285", INK = "#1A202C", GR = "#5B6575", BG = "#EAF2F5", M = 34;
  const W = A4.w - 2 * M;
  const NX = cv.photo ? M + 76 : M, NW = W * 0.58 - (cv.photo ? 76 : 0);
  if (cv.photo) doc.image(M, M, 64, 64, { shape: "round", r: 12, ring: ACC, rw: 1.5 });
  const nl = wrap(cv.name, "HB", 22, NW)[0];
  doc.text(nl, NX, M + 20, { font: "HB", size: 22, color: INK });
  if (cv.job) doc.text(wrap(cv.job, "H", 11.5, NW)[0], NX, M + 38, { font: "H", size: 11.5, color: ACC });
  let cy = M + 12; contactList(cv).slice(0, 5).forEach((c) => { doc.text(wrap(c, "H", 8.6, W * 0.4)[0], A4.w - M, cy, { font: "H", size: 8.6, color: GR, align: "right" }); cy += 11.5; });
  const f0 = new Flow(doc, { x: M, w: W, top: Math.max(M + 52, cy + 4, cv.photo ? M + 74 : 0), bottom: A4.h - 30 });
  f0.rule(INK, 1.6); f0.gap(9);
  if (cv.skills.length) { f0.chips(cv.skills, { size: 8, ph: 6, h: 15, fill: BG, color: "#0A4F5C", gx: 4, gy: 4, after: 10 }); }
  const LW = W * 0.63, RX = M + LW + 20, RW = W - LW - 20, top = f0.y;
  const deco = () => {};
  const left = new Flow(doc, { x: M, w: LW, top, bottom: A4.h - 34, deco });
  const right = new Flow(doc, { x: RX, w: RW, top, bottom: A4.h - 34, clip: true });
  const head = (fl, t) => { fl.brk(36); doc.rect(fl.x, fl.y + 1, 3.5, 11, ACC); doc.text(t.toUpperCase(), fl.x + 10, fl.y + 10, { font: "HB", size: 9.6, color: INK, spacing: 1 }); fl.y += 20; };
  if (cv.summary) { head(left, L.profile); left.para(cv.summary, { size: 9.2, color: "#2D3748", lh: 1.45, after: 10 }); }
  const st = { period: "below", tf: "HB", ts: 10, tc: INK, of: "H", os: 8.6, oc: ACC, df: "H", ds: 8.9, dc: "#2D3748", pc: ACC, bc: ACC, after: 7 };
  if (cv.experience.length) { head(left, L.exp); cv.experience.forEach((e) => entry(left, e, st)); }
  if (cv.education.length) { head(right, L.edu); cv.education.forEach((e) => entry(right, e, { ...st, ts: 9.6, after: 6 })); right.gap(4); }
  if (cv.languages.length) { head(right, L.lang); cv.languages.forEach((l) => right.para(l, { size: 9, color: "#2D3748", lh: 1.4, after: 2 })); right.gap(6); }
  if (cv.links.length) { head(right, L.links); cv.links.forEach((l) => right.para(l, { size: 8.4, color: ACC, lh: 1.35, after: 2 })); }
}

const TEMPLATES = [
  { id: "modern",    name: "Moderne",     desc: "Bandeau latéral bleu nuit, lecture rapide.",       accent: "#1F5FD6", draw: tModern },
  { id: "classic",   name: "Classique",   desc: "Sobre, police à empattements, très formel.",       accent: "#7A1F2B", draw: tClassic },
  { id: "minimal",   name: "Minimaliste", desc: "Beaucoup d'espace, noir et gris, ultra lisible.",  accent: "#111111", draw: tMinimal },
  { id: "creative",  name: "Créatif",     desc: "En-tête coloré et pastilles de compétences.",      accent: "#E4572E", draw: tCreative },
  { id: "executive", name: "Exécutif",    desc: "Bandeau marine et filets dorés, profil senior.",   accent: "#B8903A", draw: tExecutive },
  { id: "compact",   name: "Compact",     desc: "Dense, tient sur une page, idéal métiers tech.",   accent: "#0B7285", draw: tCompact },
];
const publicTemplates = () => TEMPLATES.map(({ id, name, desc, accent }) => ({ id, name, desc, accent }));

/** Arabe : le même dessin est retourné de gauche à droite (colonne latérale à droite, texte aligné à droite). */
function mirror(doc) {
  const W = A4.w;
  for (const ops of doc.pages) for (const p of ops) {
    if (p.t === "r") p.x = W - p.x - p.w;
    else if (p.t === "l") { p.x1 = W - p.x1; p.x2 = W - p.x2; }
    else p.x = W - p.x - p.w;
  }
  doc.mirrored = true;
}

/** Dessine le CV : renvoie { doc, cv, pages, warnings, sample }. Un profil vide -> exemple (aperçu seulement). */
function layout(templateId, profile, lang = "fr", { allowSample = false } = {}) {
  const t = TEMPLATES.find((x) => x.id === templateId);
  if (!t) { const e = new Error("Modèle inconnu"); e.code = "TEMPLATE"; throw e; }
  const lg = CV_LANGS.includes(lang) ? lang : "fr";
  const ctx = { unsupported: new Set() };
  let sample = false, p = profile || {};
  if (!String(p.name || "").trim()) {
    if (!allowSample) { const e = new Error("Renseignez au moins votre nom (et le poste visé) dans le profil avant de créer le CV."); e.code = "NAME"; throw e; }
    p = lg === "fr" ? SAMPLE.fr : lg === "ar" ? SAMPLE.ar : SAMPLE.en; sample = true;
  }
  const cv = buildCv(p, ctx);
  if (lg === "ar" || ctx.arabic) needArabic();
  const doc = new Doc(); doc.photo = cv.photo;
  t.draw(doc, cv, LABELS[lg]);
  if (lg === "ar") mirror(doc);
  return { doc, cv, pages: doc.pages.length, sample, warnings: [...(ctx.unsupported.size ? ["Caractères non gérés remplacés par « ? » : " + [...ctx.unsupported].slice(0, 8).join(" ")] : []), ...(ctx.photoBad ? ["Photo ignorée (JPEG invalide ou trop lourd)."] : [])] };
}

/* --------------------------------- Rendu SVG (aperçu) --------------------------------- */
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const n2 = (v) => (Math.round(v * 100) / 100).toString();
function toSvg(doc, pageIndex = 0) {
  let n = 0;
  const o = [`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${A4.w} ${A4.h}" width="${A4.w}" height="${A4.h}"><rect width="100%" height="100%" fill="#fff"/>`];
  for (const p of doc.pages[pageIndex] || []) {
    if (p.t === "r") o.push(`<rect x="${n2(p.x)}" y="${n2(p.y)}" width="${n2(p.w)}" height="${n2(p.h)}"${p.r ? ` rx="${n2(p.r)}"` : ""} fill="${p.fill || "none"}"${p.stroke ? ` stroke="${p.stroke}" stroke-width="${p.sw}"` : ""}/>`);
    else if (p.t === "i" && doc.photo) {
      const id = "cp" + (n++), sh = p.shape === "circle" ? `<circle cx="${n2(p.x + p.w / 2)}" cy="${n2(p.y + p.h / 2)}" r="${n2(Math.min(p.w, p.h) / 2)}"` : `<rect x="${n2(p.x)}" y="${n2(p.y)}" width="${n2(p.w)}" height="${n2(p.h)}" rx="${n2(p.shape === "round" ? p.r : 0)}"`;
      o.push(`<clipPath id="${id}">${sh}/></clipPath><image href="${doc.photo.uri}" x="${n2(p.x)}" y="${n2(p.y)}" width="${n2(p.w)}" height="${n2(p.h)}" preserveAspectRatio="xMidYMin slice" clip-path="url(#${id})"/>`);
      if (p.ring) o.push(`${sh} fill="none" stroke="${p.ring}" stroke-width="${p.rw}"/>`);
    }
    else if (p.t === "l") o.push(`<line x1="${n2(p.x1)}" y1="${n2(p.y1)}" x2="${n2(p.x2)}" y2="${n2(p.y2)}" stroke="${p.color}" stroke-width="${p.sw}"/>`);
    else {
      const F = FONTS[p.font], ax = doc.mirrored ? (p.al === "left" ? p.x + p.w : p.al === "center" ? p.x + p.w / 2 : p.x) : p.x;
      const anc = doc.mirrored ? (p.al === "left" ? "end" : p.al === "center" ? "middle" : "start") : "start";
      const fam = p.ar ? "'Noto Sans Arabic',Tahoma,'Segoe UI',Arial,sans-serif" : F.css;
      o.push(`<text x="${n2(ax)}" y="${n2(p.y)}" text-anchor="${anc}" font-family="${fam.replace(/'/g, "&apos;")}" font-size="${p.size}" font-weight="${F.wt}" font-style="${F.st}" fill="${p.color}"${p.sp ? ` letter-spacing="${p.sp}"` : ""}${p.ar ? ' direction="rtl" unicode-bidi="plaintext"' : ""} xml:space="preserve">${esc(p.s)}</text>`);
    }
  }
  o.push("</svg>");
  return o.join("");
}

/* ------------------------------------ Rendu PDF ------------------------------------ */
const rgb = (hex) => { const h = hex.replace("#", ""); return [0, 2, 4].map((i) => (parseInt(h.slice(i, i + 2), 16) / 255).toFixed(3)).join(" "); };
const hexStr = (s) => "<" + [...String(s)].map((ch) => (byteOf(ch) || 63).toString(16).padStart(2, "0")).join("") + ">";
function rrPath(x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2); const k = 0.5523 * r, f = n2;
  return `${f(x + r)} ${f(y)} m ${f(x + w - r)} ${f(y)} l ${f(x + w - r + k)} ${f(y)} ${f(x + w)} ${f(y + r - k)} ${f(x + w)} ${f(y + r)} c ${f(x + w)} ${f(y + h - r)} l ` +
    `${f(x + w)} ${f(y + h - r + k)} ${f(x + w - r + k)} ${f(y + h)} ${f(x + w - r)} ${f(y + h)} c ${f(x + r)} ${f(y + h)} l ${f(x + r - k)} ${f(y + h)} ${f(x)} ${f(y + h - r + k)} ${f(x)} ${f(y + h - r)} c ` +
    `${f(x)} ${f(y + r)} l ${f(x)} ${f(y + r - k)} ${f(x + r - k)} ${f(y)} ${f(x + r)} ${f(y)} c h`;
}
function arHex(F, k, str, usage) {                      // chaîne -> identifiants de glyphes (Identity-H), et mémorisation des glyphes utilisés
  let h = "";
  for (const ch of str) { const c = ch.codePointAt(0), g = F.ttf.gid(c); h += g.toString(16).padStart(4, "0"); if (g) usage[k].set(g, c); }
  return "<" + h + ">";
}
function pageStream(ops, usage) {
  const H = A4.h, out = [];
  for (const p of ops) {
    if (p.t === "r") {
      const y = H - p.y - p.h, op = p.fill && p.stroke ? "B" : p.fill ? "f" : "S";
      out.push((p.fill ? `${rgb(p.fill)} rg ` : "") + (p.stroke ? `${rgb(p.stroke)} RG ${p.sw} w ` : "") + (p.r ? rrPath(p.x, y, p.w, p.h, p.r) + " " : `${n2(p.x)} ${n2(y)} ${n2(p.w)} ${n2(p.h)} re `) + op);
    } else if (p.t === "i") {
      const ph = usage.photo; if (!ph) continue;
      const sc = Math.max(p.w / ph.w, p.h / ph.h), dw = ph.w * sc, dh = ph.h * sc, x0 = p.x - (dw - p.w) / 2, top = p.y - (dh - p.h) * 0.15, y0 = H - p.y - p.h;
      const path = p.shape === "rect" ? `${n2(p.x)} ${n2(y0)} ${n2(p.w)} ${n2(p.h)} re` : rrPath(p.x, y0, p.w, p.h, p.shape === "circle" ? Math.min(p.w, p.h) / 2 : p.r);
      out.push(`q ${path} W n ${n2(dw)} 0 0 ${n2(dh)} ${n2(x0)} ${n2(H - top - dh)} cm /Im0 Do Q`);
      if (p.ring) out.push(`${rgb(p.ring)} RG ${p.rw} w ${path} S`);
    } else if (p.t === "l") out.push(`${rgb(p.color)} RG ${p.sw} w ${n2(p.x1)} ${n2(H - p.y1)} m ${n2(p.x2)} ${n2(H - p.y2)} l S`);
    else if (p.ar) {                                    // texte arabe : morceaux déjà dans l'ordre visuel, police arabe ou latine selon le morceau
      let x = p.x; const k = arFont(p.font), F = k === "B" ? ARF.bold : ARF.reg;
      for (const part of p.parts) {
        if (part.a) { out.push(`BT /FA${k === "B" ? 1 : 0} ${p.size} Tf ${rgb(p.color)} rg 0 Tc ${n2(x)} ${n2(H - p.y)} Td ${arHex(F, k, part.s, usage)} Tj ET`); x += arW(part.s, p.font, p.size); }
        else { out.push(`BT /F${FKEYS.indexOf(p.font)} ${p.size} Tf ${rgb(p.color)} rg 0 Tc ${n2(x)} ${n2(H - p.y)} Td ${hexStr(part.s)} Tj ET`); x += latinW(part.s, p.font, p.size); }
      }
    }
    else out.push(`BT /F${FKEYS.indexOf(p.font)} ${p.size} Tf ${rgb(p.color)} rg ${p.sp || 0} Tc ${n2(p.x)} ${n2(H - p.y)} Td ${hexStr(p.s)} Tj ET`);
  }
  return enc1(out.join("\n"));
}
function toPdf(doc, title = "CV") {
  const chunks = [], offs = [];
  let len = 0;
  const push = (b) => { b = typeof b === "string" ? enc1(b) : b; chunks.push(b); len += b.length; };
  const obj = (id, body) => { offs[id] = len; push(`${id} 0 obj\n`); push(body); push("\nendobj\n"); };
  const stream = (id, dict, raw, z) => {                      // flux compressé si possible (Node, ou octets déjà compressés par le navigateur)
    const data = z || (zlib ? zlib.deflateSync(raw) : raw), comp = !!(z || zlib);
    obj(id, cat([enc1(`<< ${dict} /Length ${data.length}${comp ? " /Filter /FlateDecode" : ""} >>\nstream\n`), data, enc1("\nendstream")]));
  };
  const nP = doc.pages.length, firstPage = 10;
  const usage = { R: new Map(), B: new Map(), photo: doc.photo || null };
  const hasImg = !!(usage.photo && doc.pages.some((ops) => ops.some((p) => p.t === "i")));
  const streams = doc.pages.map((ops) => pageStream(ops, usage));
  const arKeys = ["R", "B"].filter((k) => usage[k].size);
  let nid = firstPage + 2 * nP; const arIds = {}; const imgId = hasImg ? nid++ : 0;
  arKeys.forEach((k) => { arIds[k] = { type0: nid, cid: nid + 1, desc: nid + 2, file: nid + 3, uni: nid + 4 }; nid += 5; });
  push("%PDF-1.4\n%\xE2\xE3\xCF\xD3\n");
  obj(1, "<< /Type /Catalog /Pages 2 0 R >>");
  obj(2, `<< /Type /Pages /Count ${nP} /Kids [${doc.pages.map((_, i) => `${firstPage + 2 * i + 1} 0 R`).join(" ")}] >>`);
  FKEYS.forEach((k, i) => obj(3 + i, `<< /Type /Font /Subtype /Type1 /BaseFont /${FONTS[k].pdf} /Encoding /WinAnsiEncoding >>`));
  const t16 = "<FEFF" + [...String(title)].map((ch) => ch.codePointAt(0) > 0xffff ? "003F" : ch.charCodeAt(0).toString(16).padStart(4, "0")).join("") + ">";
  obj(9, `<< /Title ${t16} /Producer (CARRIVA) >>`);
  const res = `/Font << ${FKEYS.map((_, j) => `/F${j} ${3 + j} 0 R`).join(" ")}${arKeys.map((k) => ` /FA${k === "B" ? 1 : 0} ${arIds[k].type0} 0 R`).join("")} >>${hasImg ? ` /XObject << /Im0 ${imgId} 0 R >>` : ""}`;
  doc.pages.forEach((ops, i) => {
    stream(firstPage + 2 * i, "", streams[i]);
    obj(firstPage + 2 * i + 1, `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${A4.w} ${A4.h}] /Resources << ${res} >> /Contents ${firstPage + 2 * i} 0 R >>`);
  });
  if (hasImg) {
    const ph = usage.photo;
    obj(imgId, cat([enc1(`<< /Type /XObject /Subtype /Image /Width ${ph.w} /Height ${ph.h} /ColorSpace /${ph.nc === 1 ? "DeviceGray" : "DeviceRGB"} /BitsPerComponent 8 /Filter /DCTDecode /Length ${ph.bytes.length} >>\nstream\n`), ph.bytes, enc1("\nendstream")]));
  }
  arKeys.forEach((k) => {
    const F = k === "B" ? ARF.bold : ARF.reg, I = arIds[k], u = F.ttf.upem, k1000 = (v) => Math.round((v * 1000) / u), name = "CareerAr" + k;
    const gids = [...usage[k].keys()].sort((x, y) => x - y);
    obj(I.type0, `<< /Type /Font /Subtype /Type0 /BaseFont /${name} /Encoding /Identity-H /DescendantFonts [${I.cid} 0 R] /ToUnicode ${I.uni} 0 R >>`);
    obj(I.cid, `<< /Type /Font /Subtype /CIDFontType2 /BaseFont /${name} /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /FontDescriptor ${I.desc} 0 R /CIDToGIDMap /Identity /DW 600 /W [${gids.map((g) => `${g} [${k1000(F.ttf.adv(g))}]`).join(" ")}] >>`);
    obj(I.desc, `<< /Type /FontDescriptor /FontName /${name} /Flags 4 /FontBBox [${F.ttf.bbox.map(k1000).join(" ")}] /ItalicAngle 0 /Ascent ${k1000(F.ttf.asc)} /Descent ${k1000(F.ttf.desc)} /CapHeight ${k1000(F.ttf.asc)} /StemV 80 /FontFile2 ${I.file} 0 R >>`);
    stream(I.file, `/Length1 ${F.bytes.length}`, F.bytes, F.z);
    const hex4 = (c) => (c > 0xffff ? "003F" : c.toString(16).padStart(4, "0"));
    const map = gids.map((g) => `<${g.toString(16).padStart(4, "0")}> <${hex4(PRES_BASE[usage[k].get(g)] || usage[k].get(g))}>`);
    const cmap = "/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /Adobe-Identity-UCS def /CMapType 2 def 1 begincodespacerange <0000> <FFFF> endcodespacerange " +
      map.reduce((acc, m, i) => acc + (i % 100 === 0 ? `${Math.min(100, map.length - i)} beginbfchar\n` : "") + m + "\n" + (i % 100 === 99 || i === map.length - 1 ? "endbfchar\n" : ""), "") + "endcmap CMapName currentdict /CMap defineresource pop end end";
    stream(I.uni, "", enc1(cmap));
  });
  const total = nid, xref = len;
  push(`xref\n0 ${total}\n0000000000 65535 f \n`);
  for (let i = 1; i < total; i++) push(String(offs[i]).padStart(10, "0") + " 00000 n \n");
  push(`trailer\n<< /Size ${total} /Root 1 0 R /Info 9 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
  return cat(chunks);
}

/* ------------------------------------ API publique ------------------------------------ */
/** Aperçus (SVG page 1) de tous les modèles avec les données de l'utilisateur (ou l'exemple si le profil est vide). */
function previews(profile, lang) {
  const out = {}; let sample = false, warnings = [];
  for (const t of TEMPLATES) {
    const r = layout(t.id, profile, lang, { allowSample: true });
    out[t.id] = { svg: toSvg(r.doc, 0), pages: r.pages };
    sample = r.sample; if (r.warnings.length) warnings = r.warnings;
  }
  return { previews: out, sample, warnings };
}
function createPdf(templateId, profile, lang) {
  const r = layout(templateId, profile, lang);
  const u8 = toPdf(r.doc, (r.cv.name + " - CV").slice(0, 100));
  return { pdf: typeof Buffer !== "undefined" ? Buffer.from(u8.buffer, u8.byteOffset, u8.length) : u8, pages: r.pages, warnings: r.warnings };
}

const API = { TEMPLATES, publicTemplates, previews, createPdf, layout, toSvg, toPdf, buildCv, clean, wrap, tw, CV_LANGS, LABELS, parseEntries, loadArabic, loadArabicFiles, setArabicFonts, arabicReady, parsePhoto };
if (typeof module !== "undefined" && module.exports) module.exports = API; else (typeof window !== "undefined" ? window : globalThis).CVT = API;

})();
