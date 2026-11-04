/* Générateur de code QR (norme ISO/IEC 18004), autonome : aucun service tiers, tout est calculé dans le navigateur.
   Mode octets (UTF-8), correction d'erreurs M, versions 1 à 20 (jusqu'à ~ 600 octets).  Usage : CARRIVA_QR.matrix("https://…") -> tableau de lignes de booléens. */
(function(){
  "use strict";
  var RS = [[1, 26, 16], [1, 44, 28], [1, 70, 44], [2, 50, 32], [2, 67, 43], [4, 43, 27], [4, 49, 31], [2, 60, 38, 2, 61, 39], [3, 58, 36, 2, 59, 37], [4, 69, 43, 1, 70, 44], [1, 80, 50, 4, 81, 51], [6, 58, 36, 2, 59, 37], [8, 59, 37, 1, 60, 38], [4, 64, 40, 5, 65, 41], [5, 65, 41, 5, 66, 42], [7, 73, 45, 3, 74, 46], [10, 74, 46, 1, 75, 47], [9, 69, 43, 4, 70, 44], [3, 70, 44, 11, 71, 45], [3, 67, 41, 13, 68, 42]];  // par version (1..20) : suites [nombre de blocs, mots de code totaux, mots de données] pour le niveau M
  var EXP = new Array(512), LOG = new Array(256), x = 1, i;
  for(i = 0; i < 255; i++){ EXP[i] = x; LOG[x] = i; x <<= 1; if(x & 256) x ^= 0x11d; }
  for(i = 255; i < 512; i++) EXP[i] = EXP[i - 255];
  function mul(a, b){ return a && b ? EXP[LOG[a] + LOG[b]] : 0; }
  function genPoly(n){ var p = [1]; for(var k = 0; k < n; k++){ var q = new Array(p.length + 1).fill(0); for(var j = 0; j < p.length; j++){ q[j] ^= p[j]; q[j + 1] ^= mul(p[j], EXP[k]); } p = q; } return p; }
  function rsEcc(data, n){ var g = genPoly(n), r = new Array(n).fill(0); data.forEach(function(d){ var f = d ^ r.shift(); r.push(0); for(var j = 0; j < n; j++) r[j] ^= mul(g[j + 1], f); }); return r; }
  function utf8(s){ return Array.prototype.slice.call(new TextEncoder().encode(s)); }
  function dataCap(v){ var t = RS[v - 1], n = 0; for(var j = 0; j < t.length; j += 3) n += t[j] * t[j + 2]; return n; }
  function pickVersion(len){ for(var v = 1; v <= 20; v++){ var cc = v < 10 ? 8 : 16; if(Math.ceil((4 + cc + len * 8) / 8) <= dataCap(v)) return v; } throw new Error("Texte trop long pour le code QR"); }
  function codewords(bytes, v){
    var cc = v < 10 ? 8 : 16, bits = [];
    function put(val, n){ for(var b = n - 1; b >= 0; b--) bits.push((val >>> b) & 1); }
    put(4, 4); put(bytes.length, cc); bytes.forEach(function(b){ put(b, 8); });
    var cap = dataCap(v) * 8; put(0, Math.min(4, cap - bits.length)); while(bits.length % 8) bits.push(0);
    var out = []; for(var j = 0; j < bits.length; j += 8){ var b = 0; for(var k = 0; k < 8; k++) b = (b << 1) | bits[j + k]; out.push(b); }
    for(var pad = 0xEC; out.length < dataCap(v); pad ^= 0xEC ^ 0x11) out.push(pad);
    var t = RS[v - 1], blocks = [], pos = 0;
    for(var q = 0; q < t.length; q += 3) for(var c = 0; c < t[q]; c++){ var d = out.slice(pos, pos + t[q + 2]); pos += t[q + 2]; blocks.push({d: d, e: rsEcc(d, t[q + 1] - t[q + 2])}); }
    var res = [], maxD = Math.max.apply(null, blocks.map(function(b){ return b.d.length; })), maxE = blocks[0].e.length;
    for(var a = 0; a < maxD; a++) blocks.forEach(function(b){ if(a < b.d.length) res.push(b.d[a]); });
    for(var e = 0; e < maxE; e++) blocks.forEach(function(b){ res.push(b.e[e]); });
    return res;
  }
  function alignPos(v){ if(v === 1) return []; var n = Math.floor(v / 7) + 2, size = v * 4 + 17, step = v === 32 ? 26 : Math.ceil((size - 13) / (n * 2 - 2)) * 2, r = [6];
    for(var p = size - 7; r.length < n; p -= step) r.splice(1, 0, p); return r; }
  function bch(val, poly, bitsLen){ var r = val << bitsLen, top = 31 - Math.clz32(poly); for(var k = 31 - Math.clz32(r); k >= top; k--) if((r >>> k) & 1) r ^= poly << (k - top); return r; }
  function build(v, cw, mask){
    var n = v * 4 + 17, m = [], fn = [], r, c;
    for(r = 0; r < n; r++){ m.push(new Array(n).fill(false)); fn.push(new Array(n).fill(false)); }
    function set(r, c, val){ m[r][c] = !!val; fn[r][c] = true; }
    function finder(r0, c0){ for(var dr = -1; dr <= 7; dr++) for(var dc = -1; dc <= 7; dc++){ var rr = r0 + dr, cc = c0 + dc; if(rr < 0 || cc < 0 || rr >= n || cc >= n) continue;
      var d = dr < 0 || dr > 6 || dc < 0 || dc > 6 ? false : (dr === 0 || dr === 6 || dc === 0 || dc === 6 || (dr >= 2 && dr <= 4 && dc >= 2 && dc <= 4)); set(rr, cc, d); } }
    finder(0, 0); finder(0, n - 7); finder(n - 7, 0);
    for(c = 8; c < n - 8; c++){ set(6, c, c % 2 === 0); set(c, 6, c % 2 === 0); }
    var ap = alignPos(v);
    ap.forEach(function(ar, ai){ ap.forEach(function(ac, aj){ if((ai === 0 && aj === 0) || (ai === 0 && aj === ap.length - 1) || (ai === ap.length - 1 && aj === 0)) return;
      for(var dr = -2; dr <= 2; dr++) for(var dc = -2; dc <= 2; dc++) set(ar + dr, ac + dc, Math.max(Math.abs(dr), Math.abs(dc)) !== 1); }); });
    // formats (niveau M = 00) et version
    var fmt = ((0 << 3) | mask), fbits = ((fmt << 10) | bch(fmt, 0x537, 10)) ^ 0x5412;
    function fb(k){ return (fbits >>> k) & 1; }
    for(var k = 0; k <= 5; k++) set(k, 8, fb(k)); set(7, 8, fb(6)); set(8, 8, fb(7)); set(8, 7, fb(8)); for(k = 9; k < 15; k++) set(8, 14 - k, fb(k));
    for(k = 0; k < 8; k++) set(8, n - 1 - k, fb(k)); for(k = 8; k < 15; k++) set(n - 15 + k, 8, fb(k)); set(n - 8, 8, true);
    if(v >= 7){ var vb = (v << 12) | bch(v, 0x1f25, 12); for(k = 0; k < 18; k++){ var bit = (vb >>> k) & 1, a = n - 11 + (k % 3), b = Math.floor(k / 3); set(a, b, bit); set(b, a, bit); } }
    // données en zigzag
    var bi = 0, total = cw.length * 8;
    for(var right = n - 1; right >= 1; right -= 2){ if(right === 6) right = 5;
      for(var vert = 0; vert < n; vert++) for(var j = 0; j < 2; j++){ var cc = right - j, up = ((right + 1) & 2) === 0, rr = up ? n - 1 - vert : vert;
        if(!fn[rr][cc] && bi < total){ m[rr][cc] = ((cw[bi >> 3] >>> (7 - (bi & 7))) & 1) === 1; bi++; } } }
    var inv = [function(r, c){ return (r + c) % 2 === 0; }, function(r){ return r % 2 === 0; }, function(r, c){ return c % 3 === 0; }, function(r, c){ return (r + c) % 3 === 0; },
      function(r, c){ return (Math.floor(r / 2) + Math.floor(c / 3)) % 2 === 0; }, function(r, c){ return (r * c) % 2 + (r * c) % 3 === 0; },
      function(r, c){ return ((r * c) % 2 + (r * c) % 3) % 2 === 0; }, function(r, c){ return ((r + c) % 2 + (r * c) % 3) % 2 === 0; }][mask];
    for(r = 0; r < n; r++) for(c = 0; c < n; c++) if(!fn[r][c] && inv(r, c)) m[r][c] = !m[r][c];
    return m;
  }
  function penalty(m){
    var n = m.length, p = 0, r, c, k;
    function runs(get){ for(var a = 0; a < n; a++){ var run = 1; for(var b = 1; b < n; b++){ if(get(a, b) === get(a, b - 1)) run++; else { if(run >= 5) p += run - 2; run = 1; } } if(run >= 5) p += run - 2;
      var s = ""; for(b = 0; b < n; b++) s += get(a, b) ? "1" : "0"; var re = /10111010000|00001011101/g; while(re.exec(s)){ p += 40; re.lastIndex -= 10; } } }
    runs(function(a, b){ return m[a][b]; }); runs(function(a, b){ return m[b][a]; });
    for(r = 0; r < n - 1; r++) for(c = 0; c < n - 1; c++) if(m[r][c] === m[r][c + 1] && m[r][c] === m[r + 1][c] && m[r][c] === m[r + 1][c + 1]) p += 3;
    var dark = 0; for(r = 0; r < n; r++) for(c = 0; c < n; c++) if(m[r][c]) dark++;
    k = Math.ceil(Math.abs(dark * 20 - n * n * 10) / (n * n)) - 1; return p + k * 10;
  }
  function matrix(text){
    var bytes = utf8(String(text)), v = pickVersion(bytes.length), cw = codewords(bytes, v), best = null, bp = 1e9;
    for(var mk = 0; mk < 8; mk++){ var m = build(v, cw, mk), s = penalty(m); if(s < bp){ bp = s; best = m; } }
    return best;
  }
  function svg(text, opts){
    opts = opts || {}; var m = matrix(text), n = m.length, q = opts.quiet == null ? 4 : opts.quiet, px = opts.size || 256, d = "";
    for(var r = 0; r < n; r++) for(var c = 0; c < n; c++) if(m[r][c]) d += "M" + (c + q) + " " + (r + q) + "h1v1h-1z";
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + (n + 2 * q) + ' ' + (n + 2 * q) + '" width="' + px + '" height="' + px + '" shape-rendering="crispEdges" role="img" aria-label="QR code"><rect width="100%" height="100%" fill="' + (opts.bg || "#fff") + '"/><path d="' + d + '" fill="' + (opts.fg || "#000") + '"/></svg>';
  }
  function png(text, size, cb){ var img = new Image(); img.onload = function(){ var cv = document.createElement("canvas"); cv.width = cv.height = size || 512; var cx = cv.getContext("2d"); cx.imageSmoothingEnabled = false; cx.drawImage(img, 0, 0, cv.width, cv.height); cv.toBlob(cb, "image/png"); };
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg(text, {size: size || 512})); }
  window.CARRIVA_QR = {matrix: matrix, svg: svg, png: png};
})();
